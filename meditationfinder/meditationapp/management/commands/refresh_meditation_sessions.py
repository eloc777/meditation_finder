from django.core.management.base import BaseCommand
from django.utils import timezone

from meditationapp.models import CandidateRecord, CandidateStatus, ExtractionAttempt, PipelineRun, PipelineRunStatus
from meditationapp.pipeline.fetching import compact_html, fetch_html, sha256_text


class Command(BaseCommand):
    help = "Re-fetch promoted candidate websites and flag content changes for review."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        run = PipelineRun.objects.create(source="session_refresh")
        changed_count = 0
        failed_count = 0
        candidates = CandidateRecord.objects.filter(status=CandidateStatus.PROMOTED, promoted_group__isnull=False).order_by("updated_at")[: options["limit"]]
        for candidate in candidates:
            changed = self.refresh_candidate(candidate, run)
            if changed is True:
                changed_count += 1
            elif changed is None:
                failed_count += 1
        run.candidates_found = len(candidates)
        run.candidates_failed = failed_count
        run.status = PipelineRunStatus.COMPLETED
        run.notes = f"{changed_count} promoted candidates changed."
        run.finished_at = timezone.now()
        run.save(update_fields=["candidates_found", "candidates_failed", "status", "notes", "finished_at"])
        self.stdout.write(self.style.SUCCESS(f"Checked {len(candidates)} promoted candidates; {changed_count} changed."))

    def refresh_candidate(self, candidate, run):
        if not candidate.raw_website:
            return False
        try:
            status, html = fetch_html(candidate.raw_website)
            compact_text = compact_html(html)
            content_hash = sha256_text(compact_text)
            latest_attempt = ExtractionAttempt.objects.filter(candidate=candidate, content_hash__gt="").order_by("-created_at").first()
            if latest_attempt and latest_attempt.content_hash == content_hash:
                return False
            ExtractionAttempt.objects.create(
                candidate=candidate,
                run=run,
                url=candidate.raw_website,
                http_status=status,
                content_hash=content_hash,
                compact_text=compact_text,
                status=CandidateStatus.EXTRACTION_READY,
                error_message="Content changed; rerun extraction before auto-updating sessions.",
            )
            candidate.status = CandidateStatus.EXTRACTION_READY
            candidate.notes = "Refresh detected changed source content."
            candidate.save(update_fields=["status", "notes", "updated_at"])
            return True
        except Exception as exc:
            candidate.notes = f"Refresh failed: {exc}"
            candidate.save(update_fields=["notes", "updated_at"])
            return None
