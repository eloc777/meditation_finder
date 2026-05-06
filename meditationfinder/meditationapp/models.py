from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# OAuth / social login: use Django's User; call user.set_unusable_password() when there is no password.


class UserIdentity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    provider = models.CharField(max_length=64)
    provider_user_id = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                name="meditationapp_useridentity_provider_uid_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.provider_user_id} ({self.user.username})"


class GroupStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class CostType(models.TextChoices):
    FREE = "free", "Free"
    PAID = "paid", "Paid"
    DONATION = "donation", "Donation"


class Source(models.TextChoices):
    SCRAPE = "scrape", "Scrape"
    SELF = "self", "Self"


class Style(models.TextChoices):
    MINDFULNESS = "mindfulness", "Mindfulness"
    ZEN = "zen", "Zen"
    GUIDED_BREATHING = "guided_breathing", "Guided breathing"
    YOGA_NIDRA = "yoga_nidra", "Yoga nidra"


class PipelineRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class CandidateStatus(models.TextChoices):
    NEW = "new", "New"
    KEYWORD_PASSED = "keyword_passed", "Keyword passed"
    STRUCTURED_READY = "structured_ready", "Structured ready"
    EXTRACTION_READY = "extraction_ready", "Needs enrichment"
    EXTRACTION_PASSED = "extraction_passed", "Extraction passed"
    NEEDS_REVIEW = "needs_review", "Needs review"
    PROMOTED = "promoted", "Promoted"
    FAILED = "failed", "Failed"


class FailureStage(models.TextChoices):
    INGESTION = "ingestion", "Ingestion"
    KEYWORD_CHECK = "keyword_check", "Keyword check"
    QUALITY_CHECK = "quality_check", "Quality check"
    SESSION_EXTRACTION = "session_extraction", "Session extraction"
    SESSION_QUALITY = "session_quality", "Session quality"
    PROMOTION = "promotion", "Promotion"


class FailureReason(models.TextChoices):
    DUPLICATE = "duplicate", "Duplicate"
    INVALID_GEOGRAPHY = "invalid_geography", "Invalid geography"
    MISSING_CONTACT = "missing_contact", "Missing contact"
    MISSING_DESCRIPTION = "missing_description", "Missing description"
    NO_WEBSITE = "no_website", "No website"
    NO_SESSIONS_FOUND = "no_sessions_found", "No sessions found"
    SITE_INACCESSIBLE = "site_inaccessible", "Site inaccessible"
    AMBIGUOUS_CONTENT = "ambiguous_content", "Ambiguous content"
    LOW_CONFIDENCE = "low_confidence", "Low confidence"
    LOW_QUALITY = "low_quality", "Low quality"
    NOT_MEDITATION_RELATED = "not_meditation_related", "Not meditation related"


class RecurrenceType(models.TextChoices):
    ONE_OFF = "one_off", "One-off"
    WEEKLY = "weekly", "Weekly"
    FORTNIGHTLY = "fortnightly", "Fortnightly"
    MONTHLY = "monthly", "Monthly"
    IRREGULAR = "irregular", "Irregular"


class MeditationGroup(models.Model):
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    style = models.CharField(max_length=16, choices=Style.choices, db_index=True)
    religion = models.CharField(max_length=128, blank=True, null=True)
    suburb = models.CharField(max_length=128, db_index=True)
    postcode = models.CharField(max_length=16, db_index=True)
    link = models.URLField(blank=True, null=True)
    cost_type = models.CharField(max_length=8, choices=CostType.choices)
    source = models.CharField(max_length=6, choices=Source.choices)
    status = models.CharField(max_length=8, choices=GroupStatus.choices, default=GroupStatus.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Session(models.Model):
    group = models.ForeignKey(MeditationGroup, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    style = models.CharField(max_length=16, choices=Style.choices, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_recurring = models.BooleanField(default=False)
    recurrence = models.CharField(max_length=16, choices=RecurrenceType.choices, default=RecurrenceType.ONE_OFF, db_index=True)
    recurrence_pattern = models.CharField(max_length=255, blank=True, default="")
    recurrence_note = models.CharField(max_length=255, blank=True, default="")
    recurrence_end_date = models.DateField(blank=True, null=True)
    beginner_friendly = models.BooleanField(default=False)
    scheduled_from = models.DateTimeField()
    scheduled_to = models.DateTimeField()
    suburb = models.CharField(max_length=128, blank=True, null=True)
    postcode = models.CharField(max_length=16, blank=True, null=True)
    meeting_link = models.URLField(blank=True, null=True)
    max_participants = models.IntegerField(blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.group.name})"

    @property
    def display_location(self):
        suburb = self.suburb or self.group.suburb
        postcode = self.postcode or self.group.postcode
        if suburb and postcode:
            return f"{suburb} {postcode}"
        return suburb or postcode or "Location to be confirmed"

    @property
    def display_style(self):
        return self.get_style_display() if self.style else self.group.get_style_display()

    @property
    def recurrence_label(self):
        return "Recurring" if self.is_recurring else "One-off"

    @property
    def recurrence_badge_class(self):
        return "text-bg-success" if self.is_recurring else "text-bg-secondary"

    @property
    def next_occurrence(self):
        if not self.is_recurring or self.recurrence != RecurrenceType.WEEKLY:
            return self.scheduled_from
        today = timezone.localdate()
        days_ahead = (self.scheduled_from.weekday() - today.weekday()) % 7
        next_date = today + timedelta(days=days_ahead)
        if self.recurrence_end_date and next_date > self.recurrence_end_date:
            return None
        next_time = self.scheduled_from.timetz().replace(tzinfo=None)
        return timezone.make_aware(datetime.combine(next_date, next_time))


class PipelineRun(models.Model):
    source = models.CharField(max_length=64)
    target_location = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=16, choices=PipelineRunStatus.choices, default=PipelineRunStatus.RUNNING, db_index=True)
    candidates_found = models.PositiveIntegerField(default=0)
    candidates_failed = models.PositiveIntegerField(default=0)
    candidates_promoted = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.source} {self.target_location} ({self.status})"


class CandidateRecord(models.Model):
    run = models.ForeignKey(PipelineRun, on_delete=models.SET_NULL, blank=True, null=True, related_name="candidates")
    source = models.CharField(max_length=64, db_index=True)
    source_id = models.CharField(max_length=255, blank=True, default="")
    raw_name = models.CharField(max_length=255)
    raw_address = models.TextField(blank=True, default="")
    raw_website = models.URLField(blank=True, null=True)
    raw_phone = models.CharField(max_length=64, blank=True, default="")
    raw_description = models.TextField(blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    normalized_name = models.CharField(max_length=255, blank=True, default="")
    normalized_address = models.TextField(blank=True, default="")
    normalized_website = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=32, choices=CandidateStatus.choices, default=CandidateStatus.NEW, db_index=True)
    failed_stage = models.CharField(max_length=64, choices=FailureStage.choices, blank=True, default="", db_index=True)
    reason_code = models.CharField(max_length=64, choices=FailureReason.choices, blank=True, default="", db_index=True)
    confidence_score = models.FloatField(blank=True, null=True)
    promoted_group = models.ForeignKey(MeditationGroup, on_delete=models.SET_NULL, blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "source_id"]),
            models.Index(fields=["normalized_name"]),
        ]

    def __str__(self):
        return f"{self.raw_name} ({self.source})"


class ExtractionAttempt(models.Model):
    candidate = models.ForeignKey(CandidateRecord, on_delete=models.CASCADE, related_name="extraction_attempts")
    run = models.ForeignKey(PipelineRun, on_delete=models.SET_NULL, blank=True, null=True, related_name="extraction_attempts")
    url = models.URLField()
    http_status = models.PositiveIntegerField(blank=True, null=True)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    compact_text = models.TextField(blank=True, default="")
    llm_provider = models.CharField(max_length=64, blank=True, default="")
    llm_model = models.CharField(max_length=128, blank=True, default="")
    prompt_version = models.CharField(max_length=32, blank=True, default="")
    raw_response = models.TextField(blank=True, default="")
    parsed_response = models.JSONField(default=dict, blank=True)
    confidence_score = models.FloatField(blank=True, null=True)
    status = models.CharField(max_length=32, choices=CandidateStatus.choices, default=CandidateStatus.NEW, db_index=True)
    failed_stage = models.CharField(max_length=64, choices=FailureStage.choices, blank=True, default="", db_index=True)
    reason_code = models.CharField(max_length=64, choices=FailureReason.choices, blank=True, default="", db_index=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.candidate.raw_name} extraction ({self.status})"


class SavedGroup(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(MeditationGroup, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group"],
                name="meditationapp_savedgroup_user_group_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} saved {self.group.name}"


class Role(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    group = models.ForeignKey(MeditationGroup, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "group"],
                name="meditationapp_userrole_user_role_group_uniq",
            ),
        ]

    def __str__(self):
        extra = f" ({self.group.name})" if self.group_id else ""
        return f"{self.user.username} — {self.role.name}{extra}"
