from django.core.management.base import BaseCommand
from django.utils import timezone

from meditationapp.models import CandidateRecord, CandidateStatus, PipelineRun, PipelineRunStatus
from meditationapp.pipeline.quality import pass_keyword_check, pass_structured_quality_check
from meditationapp.pipeline.recurrence import collapse_recurring_candidates


class Command(BaseCommand):
    help = "Run keyword, geography, duplicate, and structured quality checks for candidate records."

    def add_arguments(self, parser):
        parser.add_argument("--location", default="Brisbane")
        parser.add_argument("--limit", type=int, default=0, help="Maximum candidates to evaluate. Use 0 to process all.")

    def handle(self, *args, **options):
        run = PipelineRun.objects.create(source="candidate_evaluation", target_location=options["location"])
        candidates_query = CandidateRecord.objects.filter(status__in=[CandidateStatus.NEW, CandidateStatus.KEYWORD_PASSED]).order_by("created_at")
        candidates = list(candidates_query[: options["limit"]]) if options["limit"] else list(candidates_query)
        candidates = collapse_recurring_candidates(candidates)
        passed_count = 0
        failed_count = 0
        structured_count = 0
        enrichment_count = 0
        for candidate in candidates:
            passed = pass_keyword_check(candidate)
            if passed:
                passed = pass_structured_quality_check(candidate, options["location"])
            if passed:
                passed_count += 1
                if candidate.status == CandidateStatus.STRUCTURED_READY:
                    structured_count += 1
                if candidate.status == CandidateStatus.EXTRACTION_READY:
                    enrichment_count += 1
            else:
                failed_count += 1
        run.candidates_found = passed_count + failed_count
        run.candidates_failed = failed_count
        run.status = PipelineRunStatus.COMPLETED
        run.finished_at = timezone.now()
        run.save(update_fields=["candidates_found", "candidates_failed", "status", "finished_at"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Evaluated {passed_count + failed_count} candidates; {structured_count} structured ready; {enrichment_count} need enrichment."
            )
        )
