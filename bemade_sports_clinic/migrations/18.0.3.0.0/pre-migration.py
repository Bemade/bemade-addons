"""Drop event<->task linkage and clean up auto-spawned project tasks.

Background
----------
sports.event used to auto-create a project.task ("management task") on
creation, both internally via the model's create() override and from the
portal create endpoint. The intent was billing — but the timesheeting
workflow now runs directly off sports.event.timesheet records, so the
linked tasks no longer serve any purpose. They accumulate (one per event,
~700 in production) and clutter the project module for portal users.

This pre-migration runs *before* the 18.0.3.0.0 schema/data load. It:

1. Snapshots the project.task ids targeted by sports_event.task_id and
   the auto-spawned tasks living in the affected projects (matched by
   the canonical "Event:" and "(Event ID: N)" name patterns) so we can
   delete them in one shot.
2. unlinks() those tasks via the ORM so cascades, mail.followers,
   mail.messages, mail.activities and ir.model.data rows are cleaned
   properly.
3. NULLs sports_event.task_id and sports_event.project_id so the
   subsequent column drops (handled by Odoo when the fields disappear
   from the model) leave behind no stale references.
4. unlinks() the (now-empty) auto-spawned project.project records that
   were created by the old _get_or_create_team_project flow — they
   served no purpose beyond hosting the management tasks.

Why ORM unlink instead of DELETE? The targeted records have mail
followers, messages, activities, ir.model.data references and (for
projects) analytic accounts that need the standard cleanup hooks fired.
Total volume (~800 tasks + 13 projects) is fine for unlink in a single
transaction.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Tasks currently linked from a sports.event (skip rows where the
    #    column was already dropped — defensive against re-runs).
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'sports_event' AND column_name = 'task_id'
        """
    )
    if not cr.fetchone():
        _logger.info("sports_event.task_id column already absent; skipping cleanup.")
        return

    cr.execute(
        "SELECT DISTINCT task_id FROM sports_event WHERE task_id IS NOT NULL"
    )
    linked_task_ids = {row[0] for row in cr.fetchall()}

    # 2. Auto-spawned tasks living in the affected projects whose name
    #    matches the canonical patterns. Catches tasks whose source
    #    sports.event was deleted (ondelete='set null' would have
    #    detached them).
    cr.execute(
        "SELECT DISTINCT project_id FROM sports_event WHERE project_id IS NOT NULL"
    )
    project_ids = [row[0] for row in cr.fetchall()]

    auto_task_ids = set()
    if project_ids:
        cr.execute(
            """
            SELECT id FROM project_task
            WHERE project_id = ANY(%s)
              AND (name LIKE 'Event:%%' OR name LIKE '%%(Event ID: %%')
            """,
            (project_ids,),
        )
        auto_task_ids = {row[0] for row in cr.fetchall()}

    task_ids_to_delete = sorted(linked_task_ids | auto_task_ids)

    if not task_ids_to_delete:
        _logger.info("No event-linked or auto-spawned project tasks to remove.")
    else:
        _logger.info(
            "Removing %d event-linked / auto-spawned project tasks "
            "(linked=%d, auto-by-name=%d).",
            len(task_ids_to_delete),
            len(linked_task_ids),
            len(auto_task_ids),
        )
        # Null out the sports_event back-references first so unlink does
        # not trigger any sync-to-task logic that may still be loaded
        # from the previous module version's compiled python.
        cr.execute(
            "UPDATE sports_event SET task_id = NULL WHERE task_id IS NOT NULL"
        )
        env['project.task'].browse(task_ids_to_delete).unlink()

    # 3. Clear the project_id back-reference too — column will be removed
    #    by the schema sync when the field disappears from the model,
    #    but nulling here is cheap and avoids leaving FKs in an awkward
    #    intermediate state if the model load fails.
    cr.execute(
        "UPDATE sports_event SET project_id = NULL WHERE project_id IS NOT NULL"
    )

    # 4. Delete the (now-empty) auto-spawned projects. We only unlink
    #    projects that have zero remaining tasks — defensive against any
    #    project a user has since adopted for unrelated work.
    if project_ids:
        projects = env['project.project'].browse(project_ids).exists()
        empty_projects = projects.filtered(lambda p: not p.task_ids)
        non_empty_count = len(projects) - len(empty_projects)
        if non_empty_count:
            _logger.info(
                "Skipping %d project(s) that still have non-event tasks; "
                "they will need manual cleanup if no longer wanted.",
                non_empty_count,
            )
        if empty_projects:
            _logger.info(
                "Removing %d empty auto-spawned projects: %s",
                len(empty_projects),
                empty_projects.mapped('name'),
            )
            empty_projects.unlink()

    env.cr.commit()
