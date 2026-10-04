from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def build_temporal_context() -> str:
    """Return the authoritative date reference shared by every agent invocation."""
    timezone_name = os.getenv("APP_TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata"
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Invalid APP_TIMEZONE: {timezone_name}") from exc

    now = datetime.now(timezone)
    today = now.date()
    relative_dates = {
        "today": today,
        "yesterday": today - timedelta(days=1),
        "day before yesterday": today - timedelta(days=2),
        "tomorrow": today + timedelta(days=1),
        "day after tomorrow": today + timedelta(days=2),
    }
    relative_lines = "\n".join(
        f"- {phrase}: {date.isoformat()} ({date.strftime('%A, %B')} {date.day}, {date.year})"
        for phrase, date in relative_dates.items()
    )
    formatted_now = (
        f"{now.strftime('%A, %B')} {now.day}, {now.year} at "
        f"{now.strftime('%H:%M:%S %Z')}"
    )

    return f"""Authoritative date and time for this request:
- Timezone: {timezone_name}
- Current local date and time: {formatted_now} ({now.isoformat()})
- Current date in ISO format: {today.isoformat()}
- Relative date meanings, calculated from the current local date:
{relative_lines}

Date handling rules:
- Use this reference whenever the user asks for today's date or time. Do not guess from model knowledge.
- The relative-date mappings above are examples, not a complete list. Resolve any natural-language date or time expression against the current local date and time, including arbitrary quantities of seconds, minutes, hours, days, weeks, months, or years (for example, 3 days ago, 6 weeks from now, or 2 months ago).
- Interpret phrases such as last/next week, month, or year and named weekdays using the calendar. Use Monday as the first day of the week. For a phrase with more than one reasonable interpretation, ask a concise clarification when it affects an action.
- For month/year arithmetic, keep the same day number when it exists in the target month; otherwise use that month's final day. Preserve a stated time of day and resolve it in the given timezone.
- For date ranges such as the past N days or weeks, calculate both the start and end dates from this reference; do not substitute a fixed duration for calendar months or years.
- For workflow, API, and expense date fields, send the resolved calendar date as YYYY-MM-DD.
- If the user gives a specific unambiguous date, use that date even when it is in the past or future; do not replace it with today.
- If a specific date is ambiguous (for example, 04/05/2026), ask which date they mean before taking an irreversible action."""
