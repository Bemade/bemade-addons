"""Tests for the producer auto-tag script (bemade-addons)."""
import subprocess
from pathlib import Path

import pytest
import vendor_autotag as vt


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path):
    repo = tmp_path / "addons"
    (repo / "my_addon").mkdir(parents=True)
    (repo / "my_addon" / "__manifest__.py").write_text(
        "{'name': 'My', 'version': '19.0.1.0.0'}\n"
    )
    (repo / "my_addon" / "m.py").write_text("v = 1\n")
    (repo / "other").mkdir()
    (repo / "other" / "__manifest__.py").write_text(
        "{'name': 'Other', 'version': '19.0.2.0.0'}\n"
    )
    (repo / "notanaddon").mkdir()
    (repo / "notanaddon" / "readme.txt").write_text("hi\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v1")
    return repo


def _commit_change(repo, addon, version):
    (repo / addon / "m.py").write_text("v = 2\n")
    (repo / addon / "__manifest__.py").write_text(
        f"{{'name': '{addon}', 'version': '{version}'}}\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"bump {addon} {version}")
    return _git(repo, "rev-parse", "HEAD")


def test_plan_tags_only_changed_bumped_addon(tmp_path):
    repo = _repo(tmp_path)
    before = _git(repo, "rev-parse", "HEAD")
    after = _commit_change(repo, "my_addon", "19.0.1.1.0")

    tags = vt.plan_tags(str(repo), before, after)
    assert tags == [("my_addon/19.0.1.1.0", after)]


def test_plan_tags_skips_existing_tag(tmp_path):
    repo = _repo(tmp_path)
    before = _git(repo, "rev-parse", "HEAD")
    after = _commit_change(repo, "my_addon", "19.0.1.1.0")
    _git(repo, "tag", "my_addon/19.0.1.1.0")  # already tagged -> immutable

    assert vt.plan_tags(str(repo), before, after) == []


def test_plan_tags_ignores_non_addon_dirs(tmp_path):
    repo = _repo(tmp_path)
    before = _git(repo, "rev-parse", "HEAD")
    (repo / "notanaddon" / "readme.txt").write_text("changed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "touch non-addon")
    after = _git(repo, "rev-parse", "HEAD")

    assert vt.plan_tags(str(repo), before, after) == []


def test_apply_tags_creates_local_tags(tmp_path):
    repo = _repo(tmp_path)
    before = _git(repo, "rev-parse", "HEAD")
    after = _commit_change(repo, "other", "19.0.2.1.0")

    created = vt.apply_tags(
        str(repo), vt.plan_tags(str(repo), before, after), push=False
    )
    assert created == ["other/19.0.2.1.0"]
    assert "other/19.0.2.1.0" in vt.existing_tags(str(repo))


def test_manifest_version_reads_version(tmp_path):
    repo = _repo(tmp_path)
    assert vt.manifest_version(str(repo), "my_addon") == "19.0.1.0.0"
    assert vt.manifest_version(str(repo), "notanaddon") is None


def test_two_addons_changed_both_tagged(tmp_path):
    repo = _repo(tmp_path)
    before = _git(repo, "rev-parse", "HEAD")
    (repo / "my_addon" / "__manifest__.py").write_text(
        "{'name': 'My', 'version': '19.0.1.2.0'}\n"
    )
    (repo / "other" / "__manifest__.py").write_text(
        "{'name': 'Other', 'version': '19.0.2.2.0'}\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "bump both")
    after = _git(repo, "rev-parse", "HEAD")

    tags = dict(vt.plan_tags(str(repo), before, after))
    assert set(tags) == {"my_addon/19.0.1.2.0", "other/19.0.2.2.0"}
