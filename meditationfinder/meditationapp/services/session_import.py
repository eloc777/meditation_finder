import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from meditationapp.models import RecurrenceType
from meditationapp.services.llm import LLMExtractionError, get_llm_client
from meditationapp.services.web_fetch import compact_html, extract_internal_links, fetch_html


logger = logging.getLogger(__name__)

MAX_SUGGESTED_URLS = 3


DAY_INDEX = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


class SessionImportError(Exception):
    pass


def import_sessions_from_url(url, group_name, max_retries=2):
    """
    Fetch a URL, use the LLM to extract sessions, and retry with
    suggested internal links if nothing is found on the first page.

    Returns a list of session dicts ready for user confirmation.
    Raises SessionImportError on failure.
    """
    client = get_llm_client()

    try:
        _status, html = fetch_html(url)
    except Exception as exc:
        raise SessionImportError(f"Could not fetch {url}: {exc}") from exc

    page_text = compact_html(html)
    internal_links = extract_internal_links(url, html)

    sessions = try_extract(client, group_name, url, page_text)
    if sessions:
        return sessions

    tried_urls = {url}
    for _attempt in range(max_retries):
        suggested = client.suggest_urls(
            group_name, url, page_text, internal_links, MAX_SUGGESTED_URLS,
        )
        new_urls = [u for u in suggested if u not in tried_urls]
        if not new_urls:
            break

        for suggested_url in new_urls:
            tried_urls.add(suggested_url)
            try:
                _status, sub_html = fetch_html(suggested_url)
            except Exception:
                logger.debug("Could not fetch suggested URL %s", suggested_url)
                continue
            sub_text = compact_html(sub_html)
            sessions = try_extract(client, group_name, suggested_url, sub_text)
            if sessions:
                return sessions

            internal_links = extract_internal_links(suggested_url, sub_html)
            page_text = sub_text

    raise SessionImportError(
        "No sessions found on that website. Try a page that lists your schedule or timetable directly."
    )


def try_extract(client, group_name, url, page_text):
    """Call the LLM and return session dicts, or an empty list."""
    try:
        result = client.extract_sessions(group_name, url, page_text)
    except LLMExtractionError:
        logger.debug("LLM extraction failed for %s", url)
        return []
    raw_sessions = result.get("sessions") or []
    return [s for s in raw_sessions if s.get("day") and s.get("start_time")]


def prepare_session_for_save(session_data, group):
    """
    Map an LLM session dict to kwargs suitable for Session.objects.create().
    Returns None if the day/time can't be parsed.
    """
    scheduled_from = next_datetime_for_day(session_data.get("day"), session_data.get("start_time"))
    if not scheduled_from:
        return None

    scheduled_to = next_datetime_for_day(session_data.get("day"), session_data.get("end_time"))
    if not scheduled_to:
        duration = session_data.get("duration_minutes") or 0
        if duration > 0:
            scheduled_to = scheduled_from + timedelta(minutes=duration)
        else:
            scheduled_to = None

    recurrence = normalize_recurrence(session_data.get("recurrence"))
    is_recurring = recurrence != RecurrenceType.ONE_OFF

    return {
        "group": group,
        "title": session_data.get("session_type") or "Meditation session",
        "description": session_data.get("notes", ""),
        "is_recurring": is_recurring,
        "recurrence": recurrence,
        "recurrence_pattern": build_recurrence_pattern(session_data, recurrence),
        "recurrence_note": session_data.get("recurrence_note", ""),
        "recurrence_end_date": parse_date(session_data.get("recurrence_end_date")),
        "beginner_friendly": bool(session_data.get("beginner_friendly")),
        "scheduled_from": scheduled_from,
        "scheduled_to": scheduled_to,
        "cost": parse_cost(session_data.get("cost")),
    }


def normalize_recurrence(value):
    normalized = (value or RecurrenceType.ONE_OFF).strip().lower()
    valid_values = [choice.value for choice in RecurrenceType]
    if normalized in valid_values:
        return normalized
    return RecurrenceType.ONE_OFF


def build_recurrence_pattern(session_data, recurrence):
    day = session_data.get("day", "")
    if recurrence == RecurrenceType.WEEKLY:
        return f"Weekly on {day}"
    if recurrence == RecurrenceType.FORTNIGHTLY:
        return f"Fortnightly on {day}"
    if recurrence == RecurrenceType.MONTHLY:
        return f"Monthly on {day}"
    if recurrence == RecurrenceType.IRREGULAR:
        return "Irregular schedule"
    return ""


def next_datetime_for_day(day_name, time_value):
    day_key = (day_name or "").strip().lower()
    if day_key not in DAY_INDEX:
        return None
    parsed_time = parse_time(time_value)
    if not parsed_time:
        return None
    today = timezone.localdate()
    days_ahead = (DAY_INDEX[day_key] - today.weekday()) % 7
    target_date = today + timedelta(days=days_ahead)
    return timezone.make_aware(datetime.combine(target_date, parsed_time))


def parse_time(value):
    text = (value or "").strip().lower().replace(".", "")
    formats = ["%H:%M", "%H%M", "%I:%M%p", "%I%p", "%I:%M %p", "%I %p"]
    for format_string in formats:
        try:
            return datetime.strptime(text, format_string).time()
        except ValueError:
            continue
    return None


def compute_display_end_time(session_data):
    """
    Return a human-readable end time string for display in the review table.
    Uses end_time if available, otherwise start_time + duration_minutes.
    """
    if session_data.get("end_time"):
        return session_data["end_time"]
    start = parse_time(session_data.get("start_time"))
    duration = session_data.get("duration_minutes") or 0
    if start and duration > 0:
        end_dt = datetime.combine(datetime.today(), start) + timedelta(minutes=duration)
        return end_dt.strftime("%-I:%M %p").lower()
    return ""


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_cost(value):
    if not value:
        return None
    normalized = str(value).replace("$", "").strip()
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None
