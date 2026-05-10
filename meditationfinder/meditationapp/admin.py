from django.contrib import admin

from .models import MeditationGroup, Session, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "archived_at", "is_archived", "notes_short", "created_at"]
    list_filter = ["is_archived"]
    search_fields = ["user__username", "user__email", "notes"]
    list_per_page = 25
    readonly_fields = ["created_at", "archived_at"]

    def notes_short(self, obj):
        text = (obj.notes or "").strip()
        if len(text) > 60:
            return text[:57] + "..."
        return text

    notes_short.short_description = "Notes"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MeditationGroup)
class MeditationGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "suburb", "style", "source", "created_at"]
    list_filter = ["source", "style", "cost_type"]
    search_fields = ["name", "description", "suburb", "postcode"]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["title", "group", "scheduled_from", "is_recurring", "beginner_friendly"]
    list_filter = ["is_recurring", "beginner_friendly", "style"]
    search_fields = ["title", "description", "group__name"]
