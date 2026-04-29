from django.core.management.base import BaseCommand
from django.utils import timezone

from meditationapp.models import CandidateRecord, CandidateStatus, ExtractionAttempt, FailureReason, FailureStage, PipelineRun, PipelineRunStatus
from meditationapp.pipeline.fetching import compact_html, extract_internal_links, fetch_html, sha256_text
from meditationapp.pipeline.llm import PROMPT_VERSION, get_llm_client
from meditationapp.pipeline.quality import session_passes_quality


class Command(BaseCommand):
    help = "Fetch candidate websites and use a cheap hosted LLM to extract meditation session data."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--confidence-threshold", type=float, default=0.7)
        parser.add_argument("--max-attempts", type=int, default=3)

    def handle(self, *args, **options):
        run = PipelineRun.objects.create(source="session_extraction")
        client = get_llm_client()
        candidates = CandidateRecord.objects.filter(status=CandidateStatus.EXTRACTION_READY, raw_website__isnull=False).order_by("created_at")[: options["limit"]]
        passed_count = 0
        failed_count = 0
        for candidate in candidates:
            attempt = self.extract_candidate(candidate, run, client, options)
            if attempt and attempt.status == CandidateStatus.EXTRACTION_PASSED:
                passed_count += 1
            else:
                failed_count += 1
        run.candidates_found = passed_count + failed_count
        run.candidates_failed = failed_count
        run.status = PipelineRunStatus.COMPLETED
        run.finished_at = timezone.now()
        run.save(update_fields=["candidates_found", "candidates_failed", "status", "finished_at"])
        self.stdout.write(self.style.SUCCESS(f"Extracted sessions for {passed_count} candidates; {failed_count} failed."))

    def extract_candidate(self, candidate, run, client, options):
        attempt = self.extract_guided(candidate, run, client, options["confidence_threshold"], options["max_attempts"])
        if attempt.status == CandidateStatus.EXTRACTION_PASSED:
            candidate.status = CandidateStatus.EXTRACTION_PASSED
            candidate.confidence_score = attempt.confidence_score
            candidate.save(update_fields=["status", "confidence_score", "updated_at"])
            return attempt
        self.fail_candidate_extraction(candidate, attempt)
        return attempt

    def extract_guided(self, candidate, run, client, threshold, max_pages):
        attempt = ExtractionAttempt.objects.create(
            candidate=candidate,
            run=run,
            url=candidate.raw_website,
            llm_provider=client.provider_name,
            llm_model=client.model_name,
            prompt_version=PROMPT_VERSION,
        )
        try:
            status, html = fetch_html(candidate.raw_website)
            homepage_text = compact_html(html)
            links = extract_internal_links(candidate.raw_website, html)
            suggested_urls = client.suggest_urls(candidate, homepage_text, links, max_pages)
            compact_text = combined_page_text(candidate.raw_website, homepage_text, suggested_urls)
            raw_response, parsed_response = client.extract_sessions(candidate, compact_text)
            confidence = float(parsed_response.get("confidence_score") or 0)
            attempt.http_status = status
            attempt.content_hash = sha256_text(compact_text)
            attempt.compact_text = compact_text
            attempt.raw_response = raw_response
            attempt.parsed_response = parsed_response
            attempt.confidence_score = confidence
            if session_passes_quality(parsed_response, threshold):
                attempt.status = CandidateStatus.EXTRACTION_PASSED
            else:
                attempt.status = CandidateStatus.FAILED
                attempt.failed_stage = FailureStage.SESSION_QUALITY
                attempt.reason_code = FailureReason.NO_SESSIONS_FOUND if parsed_response.get("sessions") == [] else FailureReason.LOW_CONFIDENCE
            attempt.save()
        except Exception as exc:
            attempt.status = CandidateStatus.FAILED
            attempt.failed_stage = FailureStage.SESSION_EXTRACTION
            attempt.reason_code = FailureReason.SITE_INACCESSIBLE
            attempt.error_message = str(exc)
            attempt.save()
        return attempt

    def fail_candidate_extraction(self, candidate, attempt):
        candidate.status = CandidateStatus.FAILED
        candidate.failed_stage = FailureStage.SESSION_EXTRACTION
        candidate.reason_code = FailureReason.NO_SESSIONS_FOUND
        if attempt and attempt.reason_code:
            candidate.failed_stage = attempt.failed_stage
            candidate.reason_code = attempt.reason_code
            candidate.notes = attempt.error_message
        candidate.save(update_fields=["status", "failed_stage", "reason_code", "notes", "updated_at"])


def combined_page_text(homepage_url, homepage_text, suggested_urls):
    parts = [f"URL: {homepage_url}\n{homepage_text}"]
    for url in suggested_urls:
        page_text = fetched_page_text(url)
        if page_text:
            parts.append(f"URL: {url}\n{page_text}")
    return "\n\n---\n\n".join(parts)


def fetched_page_text(url):
    try:
        _status, html = fetch_html(url)
    except Exception:
        return ""
    return compact_html(html)
