from datetime import datetime
from zoneinfo import ZoneInfo

from meditationapp.models import CandidateStatus, FailureReason, FailureStage, RecurrenceType
from meditationapp.pipeline.quality import normalize_text


RECURRING_THRESHOLD = 3


def collapse_recurring_candidates(candidates):
    grouped_candidates = group_candidates_by_event_signature(candidates)
    collapsed_candidate_ids = set()
    for group in grouped_candidates.values():
        if len(group) >= RECURRING_THRESHOLD:
            keeper = keep_recurring_candidate(group)
            collapsed_candidate_ids.update(candidate.id for candidate in group if candidate.id != keeper.id)
        elif len(group) == 2:
            flag_ambiguous_candidates(group)
            collapsed_candidate_ids.update(candidate.id for candidate in group)
    return [candidate for candidate in candidates if candidate.id not in collapsed_candidate_ids]


def group_candidates_by_event_signature(candidates):
    groups = {}
    for candidate in candidates:
        signature = event_signature(candidate)
        if signature:
            groups.setdefault(signature, []).append(candidate)
    return groups


def event_signature(candidate):
    event_time = event_start_datetime(candidate.raw_payload)
    if not event_time:
        return None
    return (
        normalize_text(candidate.raw_name),
        event_time.strftime("%A").lower(),
        event_time.strftime("%H:%M"),
        normalize_text(candidate.raw_address),
        normalize_text(event_title(candidate.raw_payload)),
    )


def keep_recurring_candidate(group):
    keeper = sorted(group, key=lambda candidate: event_start_datetime(candidate.raw_payload))[0]
    occurrence_dates = occurrence_date_values(group)
    payload = dict(keeper.raw_payload or {})
    payload["recurrence"] = RecurrenceType.WEEKLY.value
    payload["recurrence_note"] = f"Every {event_start_datetime(keeper.raw_payload).strftime('%A')}"
    payload["recurrence_end_date"] = occurrence_dates[-1] if occurrence_dates else ""
    payload["collapsed_occurrence_count"] = len(group)
    payload["collapsed_occurrence_source_ids"] = [candidate.source_id for candidate in group]
    keeper.raw_payload = payload
    keeper.notes = f"Collapsed {len(group)} matching event occurrences into one weekly recurring candidate."
    keeper.status = CandidateStatus.NEW
    keeper.failed_stage = ""
    keeper.reason_code = ""
    keeper.save(update_fields=["raw_payload", "status", "failed_stage", "reason_code", "notes", "updated_at"])
    delete_duplicate_occurrences(group, keeper)
    return keeper


def delete_duplicate_occurrences(group, keeper):
    for candidate in group:
        if candidate.id != keeper.id:
            candidate.delete()


def flag_ambiguous_candidates(group):
    for candidate in group:
        candidate.status = CandidateStatus.NEEDS_REVIEW
        candidate.failed_stage = FailureStage.INGESTION
        candidate.reason_code = FailureReason.AMBIGUOUS_CONTENT
        candidate.notes = "Only two matching event occurrences found; review before treating as recurring."
        candidate.save(update_fields=["status", "failed_stage", "reason_code", "notes", "updated_at"])


def occurrence_date_values(group):
    datetimes = sorted(event_start_datetime(candidate.raw_payload) for candidate in group)
    return [value.date().isoformat() for value in datetimes if value]


def event_start_datetime(payload):
    value = first_present_nested(
        payload or {},
        [
            ["start", "local"],
            ["start", "utc"],
            ["start_datetime"],
            ["date"],
            ["datetime"],
            ["start_date"],
            ["event_date"],
            ["fields", "start"],
            ["fields", "start_datetime"],
            ["fields", "date"],
            ["fields", "datetime"],
            ["fields", "start_date"],
        ],
    )
    return parse_datetime(value)


def event_end_datetime(payload):
    value = first_present_nested(
        payload or {},
        [
            ["end", "local"],
            ["end", "utc"],
            ["end_datetime"],
            ["end_date"],
            ["fields", "end"],
            ["fields", "end_datetime"],
            ["fields", "end_date"],
        ],
    )
    return parse_datetime(value)


def event_title(payload):
    return first_present_nested(
        payload or {},
        [
            ["name", "text"],
            ["title"],
            ["event_name"],
            ["subject"],
            ["activity"],
            ["fields", "name"],
            ["fields", "title"],
            ["fields", "event_name"],
            ["fields", "activity"],
        ],
    )


def first_present_nested(payload, paths):
    for path in paths:
        value = nested_value(payload, path)
        if value:
            return str(value)
    return ""


def nested_value(payload, path):
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return value or ""


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for format_string in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
        try:
            return as_brisbane_time(datetime.strptime(text, format_string))
        except ValueError:
            continue
    try:
        return as_brisbane_time(datetime.fromisoformat(text))
    except ValueError:
        return None


def as_brisbane_time(value):
    if value.tzinfo:
        return value.astimezone(ZoneInfo("Australia/Brisbane"))
    return value
