from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import CandidateRecord, CandidateStatus, CostType, ExtractionAttempt, GroupStatus, MeditationGroup, Session, Style


DAY_OPTIONS = [
    {"value": "mon", "label": "Mon", "week_day": 2},
    {"value": "tue", "label": "Tue", "week_day": 3},
    {"value": "wed", "label": "Wed", "week_day": 4},
    {"value": "thu", "label": "Thu", "week_day": 5},
    {"value": "fri", "label": "Fri", "week_day": 6},
    {"value": "sat", "label": "Sat", "week_day": 7},
    {"value": "sun", "label": "Sun", "week_day": 1},
]

TIME_OPTIONS = [
    {"value": "morning", "label": "Morning"},
    {"value": "afternoon", "label": "Afternoon"},
    {"value": "evening", "label": "Evening"},
]


def index(request):
    selected_days = request.GET.getlist("day")
    selected_time = request.GET.get("time_of_day", "")
    selected_suburb = request.GET.get("suburb", "")
    selected_style = request.GET.get("style", "")
    selected_cost = request.GET.get("cost", "")
    selected_q = request.GET.get("q", "")

    sessions = Session.objects.select_related("group").filter(group__status=GroupStatus.APPROVED)

    if selected_q:
        sessions = sessions.filter(
            Q(title__icontains=selected_q)
            | Q(description__icontains=selected_q)
            | Q(group__name__icontains=selected_q)
            | Q(group__description__icontains=selected_q)
        )

    if selected_suburb:
        sessions = sessions.filter(
            Q(suburb__iexact=selected_suburb)
            | Q(suburb="", group__suburb__iexact=selected_suburb)
            | Q(suburb__isnull=True, group__suburb__iexact=selected_suburb)
        )

    if selected_days:
        selected_week_days = [option["week_day"] for option in DAY_OPTIONS if option["value"] in selected_days]
        sessions = sessions.filter(scheduled_from__week_day__in=selected_week_days)

    if selected_time == "morning":
        sessions = sessions.filter(scheduled_from__hour__gte=5, scheduled_from__hour__lt=12)
    elif selected_time == "afternoon":
        sessions = sessions.filter(scheduled_from__hour__gte=12, scheduled_from__hour__lt=17)
    elif selected_time == "evening":
        sessions = sessions.filter(scheduled_from__hour__gte=17, scheduled_from__hour__lt=22)

    if request.GET.get("recurring"):
        sessions = sessions.filter(is_recurring=True)

    if selected_style:
        sessions = sessions.filter(
            Q(style=selected_style)
            | Q(style="", group__style=selected_style)
            | Q(style__isnull=True, group__style=selected_style)
        )

    if selected_cost:
        sessions = sessions.filter(group__cost_type=selected_cost)

    if request.GET.get("beginner_friendly"):
        sessions = sessions.filter(beginner_friendly=True)

    approved_sessions = Session.objects.select_related("group").filter(group__status=GroupStatus.APPROVED)
    suburb_values = sorted(
        {
            session.suburb or session.group.suburb
            for session in approved_sessions
            if session.suburb or session.group.suburb
        }
    )
    context = {
        "sessions": sessions.order_by("scheduled_from", "title"),
        "suburbs": suburb_values,
        "day_options": DAY_OPTIONS,
        "time_options": TIME_OPTIONS,
        "style_options": Style.choices,
        "cost_options": CostType.choices,
        "selected_days": selected_days,
        "selected_time": selected_time,
        "selected_suburb": selected_suburb,
        "selected_style": selected_style,
        "selected_cost": selected_cost,
        "selected_q": selected_q,
        "recurring_only": bool(request.GET.get("recurring")),
        "beginner_friendly": bool(request.GET.get("beginner_friendly")),
        "more_filters_open": bool(selected_style or selected_cost or request.GET.get("beginner_friendly") or request.GET.get("radius")),
    }
    return render(request, "meditationapp/finder.html", context)


def sign_in(request):
    return render(request, "meditationapp/sign_in.html")


def group_dashboard(request):
    return render(request, "meditationapp/group_dashboard.html")


def admin_dashboard(request):
    pending_groups = MeditationGroup.objects.filter(status=GroupStatus.PENDING).order_by("created_at", "name")
    approved_groups = MeditationGroup.objects.filter(status=GroupStatus.APPROVED).order_by("name")
    failed_candidates = CandidateRecord.objects.filter(status__in=[CandidateStatus.FAILED, CandidateStatus.NEEDS_REVIEW]).order_by("-updated_at")[:25]
    recent_extractions = ExtractionAttempt.objects.select_related("candidate").order_by("-created_at")[:25]
    return render(
        request,
        "meditationapp/admin_dashboard.html",
        {
            "pending_groups": pending_groups,
            "approved_groups": approved_groups,
            "failed_candidates": failed_candidates,
            "recent_extractions": recent_extractions,
        },
    )


@require_POST
def approve_group(request, group_id):
    group = get_object_or_404(MeditationGroup, id=group_id, status=GroupStatus.PENDING)
    group.status = GroupStatus.APPROVED
    group.save(update_fields=["status", "updated_at"])
    return redirect("admin_dashboard")


@require_POST
def reject_group(request, group_id):
    group = get_object_or_404(MeditationGroup, id=group_id, status=GroupStatus.PENDING)
    group.status = GroupStatus.REJECTED
    group.save(update_fields=["status", "updated_at"])
    return redirect("admin_dashboard")


def group_profile(request, group_id):
    group = get_object_or_404(MeditationGroup, id=group_id, status=GroupStatus.APPROVED)
    sessions = Session.objects.filter(group=group).order_by("scheduled_from", "title")
    return render(request, "meditationapp/group_profile.html", {"group": group, "sessions": sessions})