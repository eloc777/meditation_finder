from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from meditationapp.models import CandidateStatus, CostType, MeditationGroup, RecurrenceType, Session, Source, Style
from meditationapp.pipeline.recurrence import event_end_datetime, event_start_datetime


DAY_INDEX = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


def promote_candidate(candidate, extraction):
    parsed = extraction.parsed_response
    with transaction.atomic():
        group = MeditationGroup.objects.create(
            name=parsed.get("group_name") or candidate.raw_name,
            description=candidate.raw_description or extraction.compact_text[:500],
            style=map_style(parsed.get("style")),
            religion="",
            suburb=extract_suburb(candidate.raw_address or parsed.get("address", "")),
            postcode=extract_postcode(candidate.raw_address or parsed.get("address", "")),
            link=parsed.get("website") or candidate.raw_website,
            cost_type=map_cost_type(parsed.get("sessions") or []),
            source=Source.SCRAPE,
        )
        sessions = create_sessions(group, candidate, parsed)
        candidate.promoted_group = group
        candidate.status = CandidateStatus.PROMOTED
        candidate.save(update_fields=["promoted_group", "status", "updated_at"])
        return group, sessions


def promote_structured_candidate(candidate):
    parsed = structured_parsed_response(candidate)
    suburb = candidate_suburb(candidate)
    with transaction.atomic():
        group = structured_group(candidate, parsed, suburb)
        sessions = create_sessions(group, candidate, parsed)
        candidate.promoted_group = group
        candidate.status = CandidateStatus.PROMOTED
        candidate.save(update_fields=["promoted_group", "status", "updated_at"])
        return group, sessions


def structured_group(candidate, parsed, suburb):
    if candidate.source == "brisbane_council":
        group, _created = MeditationGroup.objects.get_or_create(
            name="Brisbane City Council",
            source=Source.SCRAPE,
            defaults={
                "description": "Free and low-cost active and healthy activities listed by Brisbane City Council.",
                "style": map_style(parsed.get("style")),
                "religion": "",
                "suburb": "Brisbane",
                "postcode": "",
                "link": "https://www.brisbane.qld.gov.au/whats-on",
                "cost_type": map_cost_type(parsed.get("sessions") or []),
            },
        )
        return group
    return MeditationGroup.objects.create(
        name=parsed["group_name"],
        description=candidate.raw_description,
        style=map_style(parsed.get("style")),
        religion="",
        suburb=suburb,
        postcode=extract_postcode(candidate.raw_address),
        link=parsed.get("website") or candidate.raw_website,
        cost_type=map_cost_type(parsed.get("sessions") or []),
        source=Source.SCRAPE,
    )


def structured_parsed_response(candidate):
    payload = candidate.raw_payload or {}
    start = event_start_datetime(payload)
    end = event_end_datetime(payload)
    return {
        "group_name": structured_group_name(candidate),
        "style": candidate.raw_name,
        "address": candidate.raw_address,
        "contact": candidate.raw_phone or payload.get("bookings", ""),
        "website": candidate.raw_website or payload.get("web_link", ""),
        "confidence_score": 1.0,
        "sessions": [
            {
                "day": start.strftime("%A") if start else "",
                "start_time": start.strftime("%H:%M") if start else "",
                "end_time": end.strftime("%H:%M") if end else "",
                "session_type": candidate.raw_name,
                "recurrence": payload.get("recurrence", RecurrenceType.ONE_OFF),
                "recurrence_note": payload.get("recurrence_note", ""),
                "recurrence_end_date": payload.get("recurrence_end_date", ""),
                "cost": payload.get("cost", ""),
                "beginner_friendly": beginner_friendly(candidate.raw_description),
                "notes": candidate.raw_description,
            }
        ],
    }


def structured_group_name(candidate):
    if candidate.source == "brisbane_council":
        return "Brisbane City Council"
    return candidate.raw_name


def create_sessions(group, candidate, parsed):
    sessions = []
    for session_data in collapsed_session_data(candidate, parsed.get("sessions") or []):
        scheduled_from = next_datetime_for_day(session_data.get("day"), session_data.get("start_time"))
        if not scheduled_from:
            continue
        scheduled_to = next_datetime_for_day(session_data.get("day"), session_data.get("end_time")) or scheduled_from + timedelta(hours=1)
        recurrence = normalize_recurrence(session_data.get("recurrence") or candidate.raw_payload.get("recurrence"))
        is_recurring = recurrence != RecurrenceType.ONE_OFF
        session = Session.objects.create(
            group=group,
            title=session_data.get("session_type") or "Meditation session",
            style=map_style(parsed.get("style")),
            description=session_data.get("notes", ""),
            is_recurring=is_recurring,
            recurrence=recurrence,
            recurrence_pattern=recurrence_pattern(session_data, recurrence),
            recurrence_note=session_data.get("recurrence_note") or candidate.raw_payload.get("recurrence_note", ""),
            recurrence_end_date=parse_date(session_data.get("recurrence_end_date") or candidate.raw_payload.get("recurrence_end_date")),
            beginner_friendly=bool(session_data.get("beginner_friendly")),
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            suburb=candidate_suburb(candidate),
            postcode=extract_postcode(candidate.raw_address),
            meeting_link=online_meeting_link(candidate, parsed, session_data),
            cost=parse_cost(session_data.get("cost")),
        )
        sessions.append(session)
    return sessions


def collapsed_session_data(candidate, sessions):
    grouped_sessions = {}
    for session_data in sessions:
        key = session_signature(candidate, session_data)
        grouped_sessions.setdefault(key, []).append(session_data)
    collapsed_sessions = []
    for group in grouped_sessions.values():
        if len(group) >= 3:
            collapsed_sessions.append(recurring_session_data(group))
        elif len(group) == 1:
            collapsed_sessions.append(group[0])
        else:
            collapsed_sessions.append(ambiguous_session_data(group))
    return collapsed_sessions


def normalize_recurrence(value):
    normalized = (value or RecurrenceType.ONE_OFF).strip().lower()
    valid_values = [choice.value for choice in RecurrenceType]
    if normalized in valid_values:
        return normalized
    return RecurrenceType.ONE_OFF


def session_signature(candidate, session_data):
    return (
        (session_data.get("session_type") or "").strip().lower(),
        (session_data.get("day") or "").strip().lower(),
        (session_data.get("start_time") or "").strip().lower(),
        (candidate.raw_address or "").strip().lower(),
    )


def recurring_session_data(group):
    session_data = dict(group[0])
    session_data["recurrence"] = RecurrenceType.WEEKLY
    session_data["recurrence_note"] = f"Every {session_data.get('day')}"
    session_data["notes"] = f"{session_data.get('notes', '')} Collapsed from {len(group)} matching occurrences.".strip()
    return session_data


def ambiguous_session_data(group):
    session_data = dict(group[0])
    session_data["recurrence"] = RecurrenceType.IRREGULAR
    session_data["recurrence_note"] = f"{len(group)} similar occurrences found; staff should confirm recurrence."
    return session_data


def recurrence_pattern(session_data, recurrence):
    if recurrence == RecurrenceType.WEEKLY:
        return f"Weekly on {session_data.get('day')}"
    if recurrence == RecurrenceType.FORTNIGHTLY:
        return f"Fortnightly on {session_data.get('day')}"
    if recurrence == RecurrenceType.MONTHLY:
        return f"Monthly on {session_data.get('day')}"
    if recurrence == RecurrenceType.IRREGULAR:
        return "Irregular schedule"
    return ""


def map_style(value):
    normalized = (value or "").lower()
    if "zen" in normalized or "zazen" in normalized:
        return Style.ZEN
    if "nidra" in normalized:
        return Style.YOGA_NIDRA
    if "breath" in normalized:
        return Style.GUIDED_BREATHING
    return Style.MINDFULNESS


def map_cost_type(sessions):
    text = " ".join(str(session.get("cost", "")).lower() for session in sessions)
    if "free" in text:
        return CostType.FREE
    if "donation" in text or "dana" in text:
        return CostType.DONATION
    return CostType.PAID if text.strip() else CostType.DONATION


def beginner_friendly(description):
    text = (description or "").lower()
    return "no previous" in text or "beginner" in text or "all ages" in text


def online_meeting_link(candidate, parsed, session_data):
    if not is_online_event(candidate, session_data):
        return ""
    return parsed.get("website") or candidate.raw_website or candidate.raw_payload.get("web_link", "")


def is_online_event(candidate, session_data):
    payload = candidate.raw_payload or {}
    text = " ".join(
        str(value or "")
        for value in [
            candidate.raw_name,
            candidate.raw_description,
            candidate.raw_address,
            session_data.get("notes", ""),
            session_data.get("session_type", ""),
            payload.get("venue", ""),
            payload.get("location", ""),
            payload.get("venuetype", ""),
            payload.get("meetingpoint", ""),
        ]
    ).lower()
    online_keywords = ["virtual", "zoom", "webinar", "livestream", "live stream", "teams meeting", "google meet"]
    return any(keyword in text for keyword in online_keywords)


def parse_cost(value):
    if not value:
        return None
    normalized = str(value).replace("$", "").strip()
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


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


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def extract_postcode(address):
    parts = (address or "").split()
    for part in reversed(parts):
        if part.isdigit() and len(part) == 4:
            return part
    return ""


def extract_suburb(address):
    pieces = [piece.strip() for piece in (address or "").split(",") if piece.strip()]
    if len(pieces) >= 2:
        suburb_part = pieces[-2]
        return " ".join(word for word in suburb_part.split() if not word.isdigit())
    return ""


def candidate_suburb(candidate):
    payload = candidate.raw_payload or {}
    venue = payload.get("venue") or payload.get("location") or ""
    venue_pieces = [piece.strip() for piece in str(venue).split(",") if piece.strip()]
    if len(venue_pieces) >= 2:
        return venue_pieces[-1]
    return extract_suburb(candidate.raw_address)
