import logging
import re
import uuid

import pytz
from dateutil import rrule

from odoo import api, fields, models

# Import helper functions and constants from parent module
from odoo.addons.calendar.models.calendar_recurrence import (
    RRULE_FREQ_TO_SELECT,
    RRULE_WEEKDAY_TO_FIELD,
)

_logger = logging.getLogger(__name__)


def freq_to_select(rrule_freq):
    """Convert rrule frequency constant to Odoo select field value."""
    return RRULE_FREQ_TO_SELECT[rrule_freq]


def weekday_to_field(weekday_index):
    """Convert weekday index to Odoo field name."""
    return RRULE_WEEKDAY_TO_FIELD.get(weekday_index)


class RecurrenceRule(models.Model):
    _inherit = "calendar.recurrence"

    caldav_uid = fields.Char(
        readonly=True,
        copy=False,
    )
    _sql_constraints = [
        ("caldav_uid_unique", "UNIQUE (caldav_uid)", "caldav_uid must be unique")
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self._context.get("caldav_keep_ids"):
            for vals in vals_list:
                vals["caldav_uid"] = str(uuid.uuid4())
        else:
            for vals in vals_list:
                base_event = self.env["calendar.event"].browse(vals["base_event_id"])
                vals.update(caldav_uid=base_event.caldav_uid)
        return super().create(vals_list)

    @api.model
    def _detach_events(self, events):
        """When events are detached from a recurrence, their CalDAV UID and
        recurrence-id are no longer going to be valid, so we remove them from
        the server. They may then be re-written to the server with their new
        IDs later, but we don't care about that here.
        """
        detached_events = super()._detach_events(events)
        for event in detached_events:
            event._sync_unlink_to_caldav()
        return detached_events

    @api.model
    def _rrule_parse(self, rule_str, date_start):
        """Override to fix compatibility with python-dateutil 2.9.x+

        In python-dateutil 2.9.x+, monthly recurrence with BYSETPOS (e.g., "2nd Sunday")
        is no longer stored in _bynweekday. Instead:
        - _byweekday contains the weekday (e.g., (6,) for Sunday)
        - _bysetpos contains the position (e.g., (2,) for 2nd)

        This patch maintains compatibility with both old and new python-dateutil versions.
        """
        data = {}
        day_list = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

        # Remove X- properties that rrulestr cannot parse
        rule_str = re.sub(r';?X-[-\w]+=[^;:]*', '', rule_str).replace(":;", ":").lstrip(":;")

        if 'Z' in rule_str and date_start and not date_start.tzinfo:
            date_start = pytz.utc.localize(date_start)
        rule = rrule.rrulestr(rule_str, dtstart=date_start)

        data['rrule_type'] = freq_to_select(rule._freq)
        data['count'] = rule._count
        data['interval'] = rule._interval
        data['until'] = rule._until

        # Repeat monthly by nweekday ((weekday, weeknumber), )
        # Support both old python-dateutil (using _bynweekday) and new versions 2.9.x+ (using _byweekday + _bysetpos)
        if rule._bynweekday:
            # Old python-dateutil versions: _bynweekday contains ((weekday, position), )
            data['weekday'] = day_list[list(rule._bynweekday)[0][0]].upper()
            data['byday'] = str(list(rule._bynweekday)[0][1])
            data['month_by'] = 'day'
            data['rrule_type'] = 'monthly'
        elif rule._bysetpos and rule._byweekday and rule._freq == 1:  # MONTHLY = 1
            # New python-dateutil 2.9.x+: _byweekday + _bysetpos for monthly recurring by day
            # Example: FREQ=MONTHLY;BYDAY=SU;BYSETPOS=2 (2nd Sunday of each month)
            data['weekday'] = day_list[list(rule._byweekday)[0]].upper()
            data['byday'] = str(list(rule._bysetpos)[0])
            data['month_by'] = 'day'
            data['rrule_type'] = 'monthly'

        # Repeat weekly
        # Only set weekly if not already identified as monthly
        if rule._byweekday and data.get('rrule_type') != 'monthly':
            for weekday in day_list:
                data[weekday] = False  # reset
            for weekday_index in rule._byweekday:
                weekday = rrule.weekday(weekday_index)
                data[weekday_to_field(weekday.weekday)] = True
                data['rrule_type'] = 'weekly'

        if rule._bymonthday and data['rrule_type'] == 'monthly':
            data['day'] = list(rule._bymonthday)[0]
            data['month_by'] = 'date'

        if data.get('until'):
            data['end_type'] = 'end_date'
        elif data.get('count'):
            data['end_type'] = 'count'
        else:
            data['end_type'] = 'forever'
        return data
