#!/usr/bin/env python3
"""
Experiment: fetch one URL, suggest schedule pages, extract sessions via OpenAI — print sessions as JSON.

Same idea as the retired ingest pipeline: homepage plus a few suggested internal pages, then LLM session extraction.

  cd djangoapps/meditationfinder/meditationfinder
  python experiment_fetch_url.py
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import os

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meditationfinder.settings")

import django

django.setup()

from meditationapp.pipeline.fetching import compact_html, extract_internal_links, fetch_html
from meditationapp.pipeline.llm import LLMExtractionError, get_llm_client

FETCH_URL = "https://asmy.org.au/west-end/"
CANDIDATE_NAME = "Experiment"
# How many extra internal pages to fetch after URL suggestion
MAX_EXTRA_PAGES = 3


def fetched_page_text(page_url):
    try:
        _status, html = fetch_html(page_url)
    except Exception:
        return ""
    return compact_html(html)


def combined_page_text(homepage_url, homepage_text, suggested_urls):
    parts = [f"URL: {homepage_url}\n{homepage_text}"]
    for suggested_url in suggested_urls:
        page_text = fetched_page_text(suggested_url)
        if page_text:
            parts.append(f"URL: {suggested_url}\n{page_text}")
    return "\n\n---\n\n".join(parts)


def main():
    url = FETCH_URL.strip()
    if not url:
        print("Set FETCH_URL in experiment_fetch_url.py", file=sys.stderr)
        sys.exit(1)

    _status, html = fetch_html(url)
    homepage_text = compact_html(html)
    links = extract_internal_links(url, html)
    candidate = SimpleNamespace(raw_name=CANDIDATE_NAME, raw_address="", raw_website=url)
    client = get_llm_client()

    try:
        suggested = client.suggest_urls(candidate, homepage_text, links, MAX_EXTRA_PAGES)
    except LLMExtractionError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    compact_text = combined_page_text(url, homepage_text, suggested)

    try:
        _raw, parsed = client.extract_sessions(candidate, compact_text)
    except LLMExtractionError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    sessions = parsed.get("sessions") or []
    if not sessions:
        print("No sessions returned.", file=sys.stderr)
        sys.exit(2)

    for session in sessions[:10]:
        if hasattr(session, "model_dump"):
            session = session.model_dump()
        print(json.dumps(session, indent=2))


if __name__ == "__main__":
    main()
