import json
import os
from typing import List

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


PROMPT_VERSION = "session_extract_openai_v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class LLMExtractionError(Exception):
    pass


class UrlSuggestions(BaseModel):
    urls: List[str] = Field(description="Internal URLs likely to contain class or session schedules")


class SessionItem(BaseModel):
    day: str = ""
    start_time: str = ""
    end_time: str = ""
    session_type: str = ""
    recurrence: str = ""
    recurrence_note: str = ""
    recurrence_end_date: str = ""
    cost: str = ""
    beginner_friendly: bool = False
    notes: str = ""


class SessionExtractionOutput(BaseModel):
    group_name: str = ""
    style: str = ""
    sessions: List[SessionItem] = Field(default_factory=list)
    address: str = ""
    contact: str = ""
    website: str = ""
    confidence_score: float = 0.0


SESSION_EXTRACT_TEMPLATE = """Extract recurring or upcoming meditation and mindfulness session details from the page text.

{format_instructions}

Use an empty sessions array when no real session is found. Do not invent times.
If the page lists many identical weekly occurrences, return one session with recurrence set to "weekly".

Candidate:
Name: {raw_name}
Address: {raw_address}
Website: {raw_website}

Page text:
{page_text}
"""


URL_SUGGEST_TEMPLATE = """Pick up to {max_urls} internal URLs most likely to contain meditation class times, sessions, calendars, timetables, events, or booking schedules.

{format_instructions}

Prefer pages about classes, timetable, schedule, events, meditation, yoga, sessions, booking, calendar, retreats, programs, or weekly practice.
Do not choose generic privacy, contact, shop, blog, donation, login, cart, or social media pages unless no better schedule-like page exists.

Candidate:
Name: {raw_name}
Website: {raw_website}

Homepage text:
{homepage_text}

Internal links:
{link_lines}
"""


class OpenAIClient:
    provider_name = "openai"

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    def _chat_llm(self, temperature=0.0):
        if not self.api_key:
            raise LLMExtractionError("OPENAI_API_KEY is not set")
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model_name,
            temperature=temperature,
            timeout=120,
        )

    def extract_sessions(self, candidate, page_text):
        parser = JsonOutputParser(pydantic_object=SessionExtractionOutput) 
        # the parser givs parsing instructions to the model. The model should (hence try except) return json, the parser turns it into python dict 
        prompt = PromptTemplate(
            template=SESSION_EXTRACT_TEMPLATE,
            input_variables=["raw_name", "raw_address", "raw_website", "page_text"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | self._chat_llm(0.0) | parser
        try:
            result = chain.invoke(
                {
                    "raw_name": candidate.raw_name,
                    "raw_address": getattr(candidate, "raw_address", "") or "",
                    "raw_website": candidate.raw_website or "",
                    "page_text": page_text,
                }
            )
        except Exception as exc:
            raise LLMExtractionError(str(exc)) from exc
        if not isinstance(result, dict):
            result = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        raw_response = json.dumps(result)
        return raw_response, result

    def suggest_urls(self, candidate, homepage_text, links, max_urls):
        parser = JsonOutputParser(pydantic_object=UrlSuggestions)
        link_lines = "\n".join(links[:80])
        prompt = PromptTemplate(
            template=URL_SUGGEST_TEMPLATE,
            input_variables=["max_urls", "raw_name", "raw_website", "homepage_text", "link_lines"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | self._chat_llm(0.0) | parser
        try:
            result = chain.invoke(
                {
                    "max_urls": max_urls,
                    "raw_name": candidate.raw_name,
                    "raw_website": candidate.raw_website or "",
                    "homepage_text": homepage_text[:5000],
                    "link_lines": link_lines,
                }
            )
        except Exception as exc:
            raise LLMExtractionError(str(exc)) from exc
        if not isinstance(result, dict):
            result = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        urls = result.get("urls") or []
        return cleaned_suggested_urls(urls, links, max_urls)


def get_llm_client():
    return OpenAIClient()


def cleaned_suggested_urls(urls, allowed_links, max_urls):
    allowed_set = set(allowed_links)
    cleaned_urls = []
    for url in urls:
        if url in allowed_set and url not in cleaned_urls:
            cleaned_urls.append(url)
    return cleaned_urls[:max_urls]
