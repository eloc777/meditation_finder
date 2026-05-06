from difflib import SequenceMatcher
from urllib.parse import urlparse

from meditationapp.models import CandidateRecord, CandidateStatus, FailureReason, FailureStage


INCLUDE_KEYWORDS = [
    "meditation",
    "mindfulness",
    "zen",
    "vipassana",
    "zazen",
    "dharma",
    "metta",
    "loving-kindness",
    "mantra",
    "contemplative",
    "buddhist",
    "kadampa",
    "theravada",
    "transcendental",
    "sangha",
    "yoga",
    "breathwork",
    "tai chi",
    "monastery",
    "temple",
    "ashram",
    "retreat",
    "spiritual",
    "insight",
    "dhamma",
    "dharma",
    "chan",
    "bodhi",
    "brahma",
]

EXCLUDE_KEYWORDS = [
    "gym",
    "fitness bootcamp",
    "personal training",
    "massage only",
    "day spa",
    "beauty salon",
]


def normalize_text(value):
    return " ".join((value or "").strip().lower().split())


def normalize_url(value):
    if not value:
        return ""
    parsed = urlparse(value.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{value.strip()}")
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{host}{path}"


def candidate_search_text(candidate):
    return normalize_text(
        " ".join(
            [
                candidate.raw_name,
                candidate.raw_description,
                candidate.raw_address,
                candidate.normalized_name,
                candidate.normalized_address,
            ]
        )
    )


def has_include_keyword(text):
    return any(keyword in text for keyword in INCLUDE_KEYWORDS)


def has_exclude_keyword(text):
    return any(keyword in text for keyword in EXCLUDE_KEYWORDS)


def name_similarity(first, second):
    return SequenceMatcher(None, normalize_text(first), normalize_text(second)).ratio()


def duplicate_exists(candidate):
    address = candidate.normalized_address or normalize_text(candidate.raw_address)
    if not address:
        return False
    existing_candidates = CandidateRecord.objects.exclude(id=candidate.id).filter(
        normalized_address=address,
        status__in=[
            CandidateStatus.KEYWORD_PASSED,
            CandidateStatus.STRUCTURED_READY,
            CandidateStatus.EXTRACTION_READY,
            CandidateStatus.EXTRACTION_PASSED,
            CandidateStatus.PROMOTED,
        ],
    )
    return any(name_similarity(candidate.normalized_name, item.normalized_name) >= 0.86 for item in existing_candidates)


def fail_candidate(candidate, stage, reason, notes=""):
    candidate.status = CandidateStatus.FAILED
    candidate.failed_stage = stage
    candidate.reason_code = reason
    candidate.notes = notes
    candidate.save(update_fields=["status", "failed_stage", "reason_code", "notes", "updated_at"])


def delete_duplicate_candidate(candidate):
    candidate.delete()


def pass_keyword_check(candidate):
    candidate.normalized_name = normalize_text(candidate.raw_name)
    candidate.normalized_address = normalize_text(candidate.raw_address)
    candidate.normalized_website = normalize_url(candidate.raw_website)
    text = candidate_search_text(candidate)
    if not keyword_check_is_generous_pass(candidate, text):
        fail_candidate(candidate, FailureStage.KEYWORD_CHECK, FailureReason.NOT_MEDITATION_RELATED)
        return False
    if has_exclude_keyword(text):
        fail_candidate(candidate, FailureStage.KEYWORD_CHECK, FailureReason.NOT_MEDITATION_RELATED)
        return False
    if duplicate_exists(candidate):
        delete_duplicate_candidate(candidate)
        return False
    candidate.status = CandidateStatus.KEYWORD_PASSED
    candidate.save(update_fields=["normalized_name", "normalized_address", "normalized_website", "status", "updated_at"])
    return True


def keyword_check_is_generous_pass(candidate, text):
    if candidate.source == "google_places":
        return True
    if has_include_keyword(text):
        return True
    return False


def pass_structured_quality_check(candidate, target_location):
    payload = candidate.raw_payload or {}
    address_text = normalize_text(candidate.raw_address)
    target_text = normalize_text(target_location)
    if not candidate_in_target_location(candidate, address_text, target_text):
        fail_candidate(candidate, FailureStage.QUALITY_CHECK, FailureReason.INVALID_GEOGRAPHY)
        return False
    if not candidate.raw_website and not payload.get("web_link"):
        fail_candidate(candidate, FailureStage.QUALITY_CHECK, FailureReason.NO_WEBSITE)
        return False
    if candidate_has_structured_session(candidate):
        candidate.status = CandidateStatus.STRUCTURED_READY
    else:
        candidate.status = CandidateStatus.EXTRACTION_READY
    candidate.failed_stage = ""
    candidate.reason_code = ""
    candidate.save(update_fields=["status", "failed_stage", "reason_code", "updated_at"])
    return True


def candidate_has_structured_session(candidate):
    payload = candidate.raw_payload or {}
    has_start = bool(payload.get("start_datetime") or payload.get("start") or payload.get("date"))
    has_end = bool(payload.get("end_datetime") or payload.get("end"))
    has_location = bool(candidate.raw_address or payload.get("venueaddress") or payload.get("location"))
    has_title = bool(candidate.raw_name or payload.get("subject") or payload.get("title"))
    return has_start and has_end and has_location and has_title


def candidate_in_target_location(candidate, address_text, target_text):
    if not target_text:
        return True
    if candidate.source == "brisbane_council" and target_text == "brisbane":
        return True
    if candidate.source == "google_places" and target_text in ["brisbane", ""]:
        return "qld" in address_text or "queensland" in address_text or "brisbane" in address_text
    return target_text in address_text


def session_passes_quality(session_data, threshold):
    confidence = float(session_data.get("confidence_score") or 0)
    sessions = session_data.get("sessions") or []
    if confidence < threshold:
        return False
    return any((session.get("day") and session.get("start_time")) for session in sessions)
