from django.contrib import admin

from .models import CandidateRecord, ExtractionAttempt, MeditationGroup, PipelineRun, Session


@admin.register(MeditationGroup)
class MeditationGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "suburb", "style", "source", "status", "created_at"]
    list_filter = ["status", "source", "style", "cost_type"]
    search_fields = ["name", "description", "suburb", "postcode"]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["title", "group", "scheduled_from", "is_recurring", "beginner_friendly"]
    list_filter = ["is_recurring", "beginner_friendly", "style"]
    search_fields = ["title", "description", "group__name"]


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ["source", "target_location", "status", "candidates_found", "candidates_failed", "candidates_promoted", "started_at"]
    list_filter = ["status", "source"]


@admin.register(CandidateRecord)
class CandidateRecordAdmin(admin.ModelAdmin):
    list_display = ["raw_name", "source", "status", "failed_stage", "reason_code", "confidence_score", "updated_at"]
    list_filter = ["source", "status", "failed_stage", "reason_code"]
    search_fields = ["raw_name", "raw_address", "raw_description"]
    readonly_fields = ["raw_payload"]


@admin.register(ExtractionAttempt)
class ExtractionAttemptAdmin(admin.ModelAdmin):
    list_display = ["candidate", "url", "status", "confidence_score", "http_status", "created_at"]
    list_filter = ["status", "failed_stage", "reason_code", "llm_provider"]
    search_fields = ["candidate__raw_name", "url", "error_message"]
    readonly_fields = ["parsed_response", "raw_response", "compact_text"]
