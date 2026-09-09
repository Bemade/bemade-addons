#!/usr/bin/env python3
# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Auto-tag changed addons as ``<addon>/<version>`` on a push to a mainline branch.

Runs in bemade-addons GitHub Actions after a merge. For each top-level addon dir
that changed in the pushed range, it reads the manifest version and creates a tag
``<addon>/<version>`` at the merge commit — the pin the per-addon vendoring
lockfile references. Tags are **immutable**: a version is tagged once and never
moved (matches the lockfile's tag-immutability assumption), so re-runs and
version-unchanged pushes are no-ops.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

_MANIFESTS = ("__manifest__.py", "__openerp__.py")


def _run(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return _run("git", "-C", str(repo), *args)


def changed_top_dirs(repo: str, before: str, after: str) -> set[str]:
    """Top-level directory names touched between two commits."""
    out = _git(repo, "diff", "--name-only", before, after).stdout
    dirs = set()
    for line in out.splitlines():
        head, _, tail = line.partition("/")
        if tail:  # a file inside a top-level dir
            dirs.add(head)
    return dirs


def is_addon(repo: str, name: str) -> bool:
    return any((Path(repo) / name / mf).is_file() for mf in _MANIFESTS)


def manifest_version(repo: str, addon: str) -> str | None:
    for mf in _MANIFESTS:
        p = Path(repo) / addon / mf
        if p.is_file():
            try:
                data = ast.literal_eval(p.read_text().strip())
            except (ValueError, SyntaxError):
                return None
            if isinstance(data, dict) and data.get("version"):
                return str(data["version"])
            return None
    return None


def existing_tags(repo: str) -> set[str]:
    return set(_git(repo, "tag", "-l").stdout.split())


def plan_tags(repo: str, before: str, after: str) -> list[tuple[str, str]]:
    """Return ``[(tag, commit)]`` to create — only new (addon, version) pairs."""
    existing = existing_tags(repo)
    tags: list[tuple[str, str]] = []
    for d in sorted(changed_top_dirs(repo, before, after)):
        if not is_addon(repo, d):
            continue
        version = manifest_version(repo, d)
        if not version:
            continue
        tag = f"{d}/{version}"
        if tag in existing:  # immutable — a version is tagged once
            continue
        tags.append((tag, after))
    return tags


def apply_tags(repo: str, tags: list[tuple[str, str]], push: bool = True) -> list[str]:
    created = []
    for tag, sha in tags:
        r = _git(repo, "tag", tag, sha)
        if r.returncode != 0:
            print(f"tag {tag}: FAILED: {r.stderr.strip()}", file=sys.stderr)
            continue
        created.append(tag)
        print(f"created tag {tag} -> {sha[:12]}")
    if push and created:
        refs = [f"refs/tags/{t}" for t in created]
        r = _git(repo, "push", "origin", *refs)
        if r.returncode != 0:
            print(f"push tags FAILED: {r.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    return created


def main() -> None:
    repo = os.environ.get("GITHUB_WORKSPACE", ".")
    before = os.environ.get("BEFORE_SHA", "")
    after = os.environ.get("AFTER_SHA", "HEAD")
    # First push of a new branch: before is all-zeros — nothing to diff, and we do
    # NOT mass-tag every addon. Skip.
    if not before or set(before) == {"0"}:
        print("new-branch or empty before-sha; skipping auto-tag")
        return
    tags = plan_tags(repo, before, after)
    if not tags:
        print("no new addon version tags to create")
        return
    apply_tags(repo, tags, push=os.environ.get("AUTOTAG_PUSH", "1") != "0")


if __name__ == "__main__":
    main()
