from django.core.management.base import BaseCommand
from django.utils import timezone

from meditationapp.models import CandidateRecord, CandidateStatus, PipelineRun, PipelineRunStatus
from meditationapp.pipeline.sources import brisbane_council_candidates, eventbrite_candidates, google_places_candidates, manual_meetup_candidates


class Command(BaseCommand):
    help = "Seed raw meditation candidates from configured external sources."

    def add_arguments(self, parser):
        parser.add_argument("--location", default="Brisbane")
        parser.add_argument("--query", default="meditation and mindfulness groups")
        parser.add_argument("--meetup-seed", default="")
        parser.add_argument("--source", choices=["all", "google_places", "eventbrite", "brisbane_council", "manual_meetup"], default="all")

    def handle(self, *args, **options):
        run = PipelineRun.objects.create(source=options["source"], target_location=options["location"])
        try:
            candidates = self.collect_candidates(options)
            created_count = self.save_candidates(candidates, run)
            run.candidates_found = created_count
            run.status = PipelineRunStatus.COMPLETED
            run.finished_at = timezone.now()
            run.save(update_fields=["candidates_found", "status", "finished_at"])
            self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} candidate records."))
        except Exception as exc:
            run.status = PipelineRunStatus.FAILED
            run.notes = str(exc)
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "notes", "finished_at"])
            raise

    def collect_candidates(self, options):
        candidates = []
        source = options["source"]
        if source in ["all", "google_places"]:
            candidates.extend(google_places_candidates(options["location"], options["query"]))
        if source in ["all", "eventbrite"]:
            candidates.extend(eventbrite_candidates())
        if source in ["all", "brisbane_council"]:
            candidates.extend(brisbane_council_candidates(["yoga", "tai chi", "meditation", "mindfulness", "zen", "buddhist"]))
        if source in ["all", "manual_meetup"] and options["meetup_seed"]:
            candidates.extend(manual_meetup_candidates(options["meetup_seed"]))
        return candidates

    def save_candidates(self, candidates, run):
        created_count = 0
        for candidate in candidates:
            if not candidate.get("raw_name"):
                continue
            candidate_record, _created = CandidateRecord.objects.update_or_create(
                source=candidate["source"],
                source_id=candidate.get("source_id", ""),
                defaults={
                    "run": run,
                    "raw_name": candidate["raw_name"],
                    "raw_address": candidate.get("raw_address", ""),
                    "raw_website": candidate.get("raw_website"),
                    "raw_phone": candidate.get("raw_phone", ""),
                    "raw_description": candidate.get("raw_description", ""),
                    "raw_payload": candidate.get("raw_payload", {}),
                },
            )
            if candidate_record.status in [CandidateStatus.FAILED, CandidateStatus.NEEDS_REVIEW]:
                candidate_record.status = CandidateStatus.NEW
                candidate_record.failed_stage = ""
                candidate_record.reason_code = ""
                candidate_record.notes = ""
                candidate_record.save(update_fields=["status", "failed_stage", "reason_code", "notes", "updated_at"])
            created_count += 1
        return created_count
