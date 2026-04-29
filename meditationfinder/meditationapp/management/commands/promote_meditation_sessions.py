from django.core.management.base import BaseCommand
from django.utils import timezone

from meditationapp.models import CandidateRecord, CandidateStatus, ExtractionAttempt, FailureReason, FailureStage, PipelineRun, PipelineRunStatus
from meditationapp.pipeline.promotion import promote_candidate, promote_structured_candidate


class Command(BaseCommand):
    help = "Promote candidates with valid extracted sessions into pending meditation groups."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        run = PipelineRun.objects.create(source="session_promotion")
        promoted_count = 0
        failed_count = 0
        candidates = CandidateRecord.objects.filter(
            status__in=[CandidateStatus.STRUCTURED_READY, CandidateStatus.EXTRACTION_PASSED],
            promoted_group__isnull=True,
        ).order_by("created_at")[: options["limit"]]
        for candidate in candidates:
            if self.promote(candidate):
                promoted_count += 1
            else:
                failed_count += 1
        run.candidates_found = promoted_count + failed_count
        run.candidates_failed = failed_count
        run.candidates_promoted = promoted_count
        run.status = PipelineRunStatus.COMPLETED
        run.finished_at = timezone.now()
        run.save(update_fields=["candidates_found", "candidates_failed", "candidates_promoted", "status", "finished_at"])
        self.stdout.write(self.style.SUCCESS(f"Promoted {promoted_count} candidates; {failed_count} failed."))

    def promote(self, candidate):
        if candidate.status == CandidateStatus.STRUCTURED_READY:
            return self.promote_structured(candidate)
        extraction = ExtractionAttempt.objects.filter(candidate=candidate, status=CandidateStatus.EXTRACTION_PASSED).order_by("-confidence_score", "-created_at").first()
        if not extraction:
            self.fail_candidate(candidate, "No passing extraction attempt found.")
            return False
        try:
            group, sessions = promote_candidate(candidate, extraction)
            if sessions:
                return True
            group.delete()
            self.fail_candidate(candidate, "Extraction had no valid sessions to promote.")
            return False
        except Exception as exc:
            self.fail_candidate(candidate, str(exc))
            return False

    def promote_structured(self, candidate):
        try:
            group, sessions = promote_structured_candidate(candidate)
            if sessions:
                return True
            group.delete()
            self.fail_candidate(candidate, "Structured candidate had no valid session to promote.")
            return False
        except Exception as exc:
            self.fail_candidate(candidate, str(exc))
            return False

    def fail_candidate(self, candidate, message):
        candidate.status = CandidateStatus.FAILED
        candidate.failed_stage = FailureStage.PROMOTION
        candidate.reason_code = FailureReason.LOW_QUALITY
        candidate.notes = message
        candidate.save(update_fields=["status", "failed_stage", "reason_code", "notes", "updated_at"])
