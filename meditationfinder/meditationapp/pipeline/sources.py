import json
import os
import hashlib
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen


HTTP_TIMEOUT_SECONDS = 20
DEFAULT_BRISBANE_COUNCIL_DOMAIN = "data.brisbane.qld.gov.au"
DEFAULT_BRISBANE_COUNCIL_DATASET = "active-and-healthy-events"
DEFAULT_BRISBANE_COUNCIL_WHERE_TEMPLATE = "subject LIKE '%{term}%'"
DEFAULT_BRISBANE_COUNCIL_PAGE_LIMIT = 100
DEFAULT_BRISBANE_COUNCIL_MAX_PAGES = 20
DEFAULT_BRISBANE_COUNCIL_LOOKAHEAD_DAYS = 31


class LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.link_href = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_by_name = dict(attrs)
            self.link_href = attrs_by_name.get("href", "")

    def handle_endtag(self, tag):
        if tag == "a":
            self.link_href = ""

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self.link_href.startswith("mailto:"):
            self.parts.append(self.link_href.removeprefix("mailto:").split("?")[0])
            return
        self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


def request_json(url, method="GET", headers=None, body=None):
    encoded_body = None
    if body is not None:
        encoded_body = json.dumps(body).encode("utf-8")
    request = Request(url, data=encoded_body, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {response_body}") from exc


def google_places_candidates(location, query):
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY is not set. Export it before running the Google Places seed command.")
    candidates = []
    seen_place_ids = set()
    for text_query in google_places_queries(location, query):
        for candidate in fetch_google_places_candidates(api_key, text_query):
            if candidate["source_id"] not in seen_place_ids:
                candidates.append(candidate)
                seen_place_ids.add(candidate["source_id"])
    return candidates


def google_places_queries(location, query):
    return [
        f"{query} in {location}", # TODO maybe we need to search suburbs not just brisbane
        f"meditation groups in {location}",
        f"mindfulness groups in {location}",
        f"zen meditation in {location}",
        f"vipassana meditation in {location}",
        f"buddhist meditation in {location}",
    ]


def fetch_google_places_candidates(api_key, text_query):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.editorialSummary,places.rating,places.regularOpeningHours,places.websiteUri",
    }
    body = {
        "textQuery": text_query,
        "maxResultCount": 20,
        "languageCode": "en",
    }
    payload = request_json(url, method="POST", headers=headers, body=body)
    return [map_google_place(place) for place in payload.get("places", [])]


def map_google_place(place):
    display_name = place.get("displayName") or {}
    summary = place.get("editorialSummary") or {}
    return {
        "source": "google_places",
        "source_id": place.get("id", ""),
        "raw_name": display_name.get("text", ""),
        "raw_address": place.get("formattedAddress", ""),
        "raw_website": place.get("websiteUri") or None,
        "raw_phone": "",
        "raw_description": summary.get("text", ""),
        "raw_payload": place,
    }


def eventbrite_candidates():
    token = os.getenv("EVENTBRITE_API_TOKEN", "")
    if not token:
        return []
    candidates = []
    headers = {"Authorization": f"Bearer {token}"}
    for org_id in split_env_list("EVENTBRITE_ORG_IDS"):
        url = f"https://www.eventbriteapi.com/v3/organizations/{org_id}/events/?status=live&expand=venue,organizer,ticket_classes"
        payload = request_json(url, headers=headers)
        candidates.extend(map_eventbrite_event(event) for event in payload.get("events", []))
    for venue_id in split_env_list("EVENTBRITE_VENUE_IDS"):
        url = f"https://www.eventbriteapi.com/v3/venues/{venue_id}/events/?status=live&expand=venue,organizer,ticket_classes"
        payload = request_json(url, headers=headers)
        candidates.extend(map_eventbrite_event(event) for event in payload.get("events", []))
    return candidates


def map_eventbrite_event(event):
    venue = event.get("venue") or {}
    address = venue.get("address") or {}
    organizer = event.get("organizer") or {}
    name = event.get("name") or {}
    description = event.get("description") or {}
    return {
        "source": "eventbrite",
        "source_id": event.get("id", ""),
        "raw_name": organizer.get("name") or name.get("text", ""),
        "raw_address": address.get("localized_address_display", ""),
        "raw_website": event.get("url") or None,
        "raw_phone": "",
        "raw_description": description.get("text", "") or organizer.get("description", {}).get("text", ""),
        "raw_payload": event,
    }


def brisbane_council_candidates(search_terms):
    domain = os.getenv("BRISBANE_COUNCIL_DOMAIN", DEFAULT_BRISBANE_COUNCIL_DOMAIN)
    dataset_ids = split_env_list("BRISBANE_COUNCIL_DATASET_IDS") or [DEFAULT_BRISBANE_COUNCIL_DATASET]
    where_template = os.getenv("BRISBANE_COUNCIL_WHERE_TEMPLATE", DEFAULT_BRISBANE_COUNCIL_WHERE_TEMPLATE)
    page_limit = int(os.getenv("BRISBANE_COUNCIL_PAGE_LIMIT", DEFAULT_BRISBANE_COUNCIL_PAGE_LIMIT))
    max_pages = int(os.getenv("BRISBANE_COUNCIL_MAX_PAGES", DEFAULT_BRISBANE_COUNCIL_MAX_PAGES))
    lookahead_days = int(os.getenv("BRISBANE_COUNCIL_LOOKAHEAD_DAYS", DEFAULT_BRISBANE_COUNCIL_LOOKAHEAD_DAYS))
    if not domain:
        return []
    candidates = []
    for dataset_id in dataset_ids:
        for term in search_terms:
            candidates.extend(fetch_brisbane_dataset_records(domain, dataset_id, where_template, term, page_limit, max_pages, lookahead_days))
    return candidates


def fetch_brisbane_dataset_records(domain, dataset_id, where_template, term, page_limit, max_pages, lookahead_days):
    records = []
    offset = 0
    start_at = datetime.now(timezone.utc)
    end_at = start_at + timedelta(days=lookahead_days)
    for _page in range(max_pages):
        page = fetch_brisbane_dataset_page(domain, dataset_id, where_template, term, page_limit, offset)
        if not page:
            break
        records.extend(records_in_window(page, start_at, end_at))
        if page_is_past_window(page, end_at) or len(page) < page_limit:
            break
        offset += page_limit
    return [map_brisbane_record(dataset_id, record) for record in records]


def fetch_brisbane_dataset_page(domain, dataset_id, where_template, term, page_limit, offset):
    params = urlencode(
        {
            "where": where_template.format(term=term),
            "limit": page_limit,
            "offset": offset,
            "order_by": "start_datetime",
        }
    )
    url = f"https://{domain}/api/explore/v2.1/catalog/datasets/{dataset_id}/records?{params}"
    payload = request_json(url)
    return payload.get("results") or payload.get("records") or []


def records_in_window(records, start_at, end_at):
    return [record for record in records if record_is_in_window(record, start_at, end_at)]


def record_is_in_window(record, start_at, end_at):
    starts_at = parse_api_datetime((record.get("fields") or record).get("start_datetime"))
    if not starts_at:
        return True
    return start_at <= starts_at <= end_at


def page_is_past_window(records, end_at):
    dated_records = [parse_api_datetime((record.get("fields") or record).get("start_datetime")) for record in records]
    dated_records = [value for value in dated_records if value]
    return bool(dated_records) and min(dated_records) > end_at


def map_brisbane_record(dataset_id, record):
    fields = record.get("fields") or record
    name = first_present(fields, ["subject", "name", "title", "event_name", "venue", "facility_name", "organisation"])
    address = first_present(fields, ["venueaddress", "address", "street_address", "venue_address", "location", "suburb"])
    website = brisbane_event_url(fields)
    booking_text = first_present(fields, ["bookings"])
    phone = extract_phone(first_present(fields, ["phone", "telephone", "contact_phone", "bookings"]))
    description = clean_text(
        " ".join(
            value
            for value in [
                first_present(fields, ["description", "details", "summary", "activity", "subject"]),
                booking_text,
            ]
            if value
        )
    )
    event_id = brisbane_event_id(fields)
    record_id = str(record.get("recordid") or fields.get("id") or fields.get("objectid") or event_id or stable_record_id(record))
    return {
        "source": "brisbane_council",
        "source_id": f"{dataset_id}:{record_id}",
        "raw_name": name,
        "raw_address": address,
        "raw_website": website or None,
        "raw_phone": phone,
        "raw_description": description,
        "raw_payload": record,
    }


def manual_meetup_candidates(seed_path):
    path = Path(seed_path)
    if not path.exists():
        return []
    candidates = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            candidates.append(map_manual_meetup_url(stripped, line_number))
    return candidates


def map_manual_meetup_url(url, line_number):
    return {
        "source": "manual_meetup",
        "source_id": url,
        "raw_name": f"Manual Meetup seed {line_number}",
        "raw_address": "",
        "raw_website": url,
        "raw_phone": "",
        "raw_description": "Manually supplied Meetup URL for meditation pipeline discovery.",
        "raw_payload": {"url": url, "line_number": line_number},
    }


def split_env_list(name):
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def first_present(fields, names):
    for name in names:
        value = fields.get(name)
        if value:
            return str(value)
    return ""


def stable_record_id(record):
    serialized = json.dumps(record, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def parse_api_datetime(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc)
    return parsed.replace(tzinfo=timezone.utc)


def brisbane_event_url(fields):
    subject = first_present(fields, ["subject", "name", "title", "event_name"])
    event_id = brisbane_event_id(fields)
    if subject and event_id:
        return f"https://www.brisbane.qld.gov.au/events/{slugify(subject)}/{event_id}"
    return first_present(fields, ["web_link", "website", "url", "web", "link"])


def brisbane_event_id(fields):
    event_id = first_present(fields, ["eventid", "event_id", "eventId", "id"])
    if event_id:
        return event_id
    return event_id_from_url(first_present(fields, ["web_link", "website", "url", "web", "link"]))


def event_id_from_url(value):
    if not value:
        return ""
    parsed = urlparse(value)
    params = parse_qs(parsed.query)
    for raw_value in params.get("trumbaEmbed", []):
        nested_params = parse_qs(unquote(raw_value))
        event_ids = nested_params.get("eventid")
        if event_ids:
            return event_ids[0]
    event_ids = params.get("eventid")
    if event_ids:
        return event_ids[0]
    return ""


def slugify(value):
    text = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return quote(text or "event")


def extract_phone(value):
    if not value:
        return ""
    match = re.search(r"(\+?\d[\d\s().-]{7,}\d)", str(value))
    if not match:
        return ""
    return match.group(1).strip()[:64]


def clean_text(value):
    if not value:
        return ""
    parser = LinkTextParser()
    parser.feed(str(value))
    text = parser.text() if "<" in str(value) and ">" in str(value) else str(value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
