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
    APPROVED = "approved", "Approved"


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
    status = models.CharField(max_length=8, choices=GroupStatus.choices, default=GroupStatus.APPROVED, db_index=True)
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
    scheduled_to = models.DateTimeField(blank=True, null=True)
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


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    archived_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.is_archived and self.archived_at is None:
            self.archived_at = timezone.now()
        elif not self.is_archived:
            self.archived_at = None
        self.is_archived = self.archived_at is not None
        super().save(*args, **kwargs)

    def __str__(self):
        state = "archived" if self.is_archived else "active"
        return f"{self.user.username} ({state})"


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
