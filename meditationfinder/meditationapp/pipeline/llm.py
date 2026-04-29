import json
import os
from urllib.request import Request, urlopen


PROMPT_VERSION = "session_extract_v1"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


class LLMExtractionError(Exception):
    pass


class LLMClient:
    provider_name = ""
    model_name = ""

    def extract_sessions(self, candidate, page_text):
        raise NotImplementedError

    def suggest_urls(self, candidate, homepage_text, links, max_urls):
        return heuristic_schedule_urls(links, max_urls)


class AnthropicClient(LLMClient):
    provider_name = "anthropic"

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model_name = os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)

    def extract_sessions(self, candidate, page_text):
        if not self.api_key:
            raise LLMExtractionError("ANTHROPIC_API_KEY is not set")
        url = "https://api.anthropic.com/v1/messages"
        body = {
            "model": self.model_name,
            "max_tokens": 1600,
            "temperature": 0,
            "messages": [{"role": "user", "content": build_prompt(candidate, page_text)}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = post_json(url, headers, body)
        text = "".join(item.get("text", "") for item in payload.get("content", []) if item.get("type") == "text")
        return text, parse_json_response(text)


class OpenAIClient(LLMClient):
    provider_name = "openai"

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    def extract_sessions(self, candidate, page_text):
        if not self.api_key:
            raise LLMExtractionError("OPENAI_API_KEY is not set")
        url = "https://api.openai.com/v1/chat/completions"
        body = {
            "model": self.model_name,
            "temperature": 0,
            "messages": [{"role": "user", "content": build_prompt(candidate, page_text)}],
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload = post_json(url, headers, body)
        text = payload["choices"][0]["message"]["content"]
        return text, parse_json_response(text)


class GeminiClient(LLMClient):
    provider_name = "gemini"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    def extract_sessions(self, candidate, page_text):
        if not self.api_key:
            raise LLMExtractionError("GEMINI_API_KEY is not set")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_prompt(candidate, page_text)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 1600,
                "responseMimeType": "application/json",
            },
        }
        headers = {"Content-Type": "application/json"}
        payload = post_json(url, headers, body)
        text = gemini_response_text(payload)
        return text, parse_json_response(text)

    def suggest_urls(self, candidate, homepage_text, links, max_urls):
        if not self.api_key:
            raise LLMExtractionError("GEMINI_API_KEY is not set")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_url_suggestion_prompt(candidate, homepage_text, links, max_urls)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 800,
                "responseMimeType": "application/json",
            },
        }
        payload = post_json(url, {"Content-Type": "application/json"}, body)
        text = gemini_response_text(payload)
        parsed = parse_json_response(text)
        return cleaned_suggested_urls(parsed.get("urls", []), links, max_urls)


def get_llm_client():
    provider = os.getenv("MEDITATION_PIPELINE_LLM_PROVIDER", "anthropic").lower()
    if provider == "gemini":
        return GeminiClient()
    if provider == "openai":
        return OpenAIClient()
    return AnthropicClient()


def build_prompt(candidate, page_text):
    return f"""
Extract recurring or upcoming meditation session details from the page text.

Return only valid JSON matching this schema:
{{
  "group_name": "string",
  "style": "string",
  "sessions": [
    {{
      "day": "string",
      "start_time": "string",
      "end_time": "string",
      "session_type": "string",
      "recurrence": "one_off | weekly | fortnightly | monthly | irregular",
      "recurrence_note": "string",
      "recurrence_end_date": "YYYY-MM-DD or empty string",
      "cost": "string",
      "beginner_friendly": true,
      "notes": "string"
    }}
  ],
  "address": "string",
  "contact": "string",
  "website": "string",
  "confidence_score": 0.0
}}

Use an empty sessions array when no real session is found. Do not invent times.
If the page lists many identical weekly occurrences, return one session with recurrence set to "weekly".

Candidate:
Name: {candidate.raw_name}
Address: {candidate.raw_address}
Website: {candidate.raw_website or ""}

Page text:
{page_text}
""".strip()


def build_url_suggestion_prompt(candidate, homepage_text, links, max_urls):
    link_lines = "\n".join(links[:80])
    return f"""
Pick up to {max_urls} internal URLs most likely to contain meditation class times, sessions, calendars, timetables, events, or booking schedules.

Return only JSON:
{{"urls": ["https://example.com/schedule"]}}

Prefer pages about classes, timetable, schedule, events, meditation, yoga, sessions, booking, calendar, retreats, programs, or weekly practice.
Do not choose generic privacy, contact, shop, blog, donation, login, cart, or social media pages unless no better schedule-like page exists.

Candidate:
Name: {candidate.raw_name}
Website: {candidate.raw_website or ""}

Homepage text:
{homepage_text[:5000]}

Internal links:
{link_lines}
""".strip()


def post_json(url, headers, body):
    request = Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def gemini_response_text(payload):
    candidates = payload.get("candidates") or []
    if not candidates:
        raise LLMExtractionError("Gemini response did not include candidates")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = "".join(part.get("text", "") for part in parts)
    if not text:
        raise LLMExtractionError("Gemini response did not include text")
    return text


def parse_json_response(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return json.loads(extract_json_object(stripped))


def extract_json_object(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMExtractionError("No JSON object found in LLM response")
    return text[start : end + 1]


def heuristic_schedule_urls(links, max_urls):
    keywords = ["class", "classes", "event", "events", "schedule", "timetable", "session", "sessions", "calendar", "booking", "meditation", "yoga", "retreat", "program"]
    scored_links = []
    for link in links:
        score = sum(1 for keyword in keywords if keyword in link.lower())
        if score:
            scored_links.append((score, link))
    scored_links.sort(reverse=True)
    return [link for _score, link in scored_links[:max_urls]]


def cleaned_suggested_urls(urls, allowed_links, max_urls):
    allowed_set = set(allowed_links)
    cleaned_urls = []
    for url in urls:
        if url in allowed_set and url not in cleaned_urls:
            cleaned_urls.append(url)
    return cleaned_urls[:max_urls]
