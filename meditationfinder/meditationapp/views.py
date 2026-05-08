from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MeditationGroupForm, SessionEditForm
from .models import CandidateRecord, CandidateStatus, CostType, ExtractionAttempt, GroupStatus, MeditationGroup, Session, Style, UserRole


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


def is_staff_user(user):
    return user.is_authenticated and user.is_staff


def user_manages_group(user, group_id):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return UserRole.objects.filter(
        user=user,
        role__name="group_manager",
        group_id=group_id,
    ).exists()


def get_managed_groups(user):
    if user.is_staff:
        return MeditationGroup.objects.order_by("name")
    return MeditationGroup.objects.filter(
        userrole__user=user,
        userrole__role__name="group_manager",
    ).order_by("name")


# request.method (GET, POST, etc.)
# request.GET (query params like ?q=zen&page=2)
# request.POST (submitted form data)
# request.user (current authenticated user)
# request.path (URL path)
# headers, cookies, session, files, etc.

def index(request):
    selected_days = request.GET.getlist("day")
    selected_time = request.GET.get("time_of_day", "")
    selected_suburb = request.GET.get("suburb", "")
    selected_style = request.GET.get("style", "")
    selected_cost = request.GET.get("cost", "")
    selected_q = request.GET.get("q", "")

    sessions = Session.objects.select_related("group").filter(group__status=GroupStatus.APPROVED) # start building the query

    if selected_q:
        sessions = sessions.filter( # we use Q() to build compound boolean expressions
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

    sessions = sessions.order_by("scheduled_from", "title")
    paginator = Paginator(sessions, 30)
    current_page_number = request.GET.get("page")
    paginated_sessions = paginator.get_page(current_page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)

    approved_sessions = Session.objects.select_related("group").filter(group__status=GroupStatus.APPROVED)
    suburb_values = sorted(
        {
            session.suburb or session.group.suburb
            for session in approved_sessions
            if session.suburb or session.group.suburb
        }
    )
    context = {
        "sessions": paginated_sessions,
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
        "pagination_query": query_params.urlencode(),
    }
    return render(request, "meditationapp/finder.html", context)


@login_required(login_url="account_login")
def group_dashboard(request, group_id=None):
    groups = get_managed_groups(request.user)
    if group_id is None:
        first = groups.first()
        if first:
            return redirect("group_dashboard", group_id=first.id) # gives a canonical url /group-dashboard/<id>/
        return render(request, "meditationapp/group_dashboard.html", {"groups": groups})
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    sessions = Session.objects.filter(group=group).order_by("scheduled_from", "title")
    group_form = MeditationGroupForm(instance=group)
    session_form = SessionEditForm()
    return render(request, "meditationapp/group_dashboard.html", {
        "groups": groups,
        "group": group,
        "sessions": sessions,
        "group_form": group_form,
        "session_form": session_form,
    })


@login_required(login_url="account_login")
@require_POST
def group_edit(request, group_id):
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    form = MeditationGroupForm(request.POST, instance=group)
    if form.is_valid():
        form.save()
        messages.success(request, "Group details saved.")
        return redirect("group_dashboard", group_id=group_id)
    groups = get_managed_groups(request.user)
    sessions = Session.objects.filter(group=group).order_by("scheduled_from", "title")
    return render(request, "meditationapp/group_dashboard.html", {
        "groups": groups,
        "group": group,
        "sessions": sessions,
        "group_form": form,
        "session_form": SessionEditForm(),
    })


@login_required(login_url="account_login")
@require_POST
def session_create(request, group_id):
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    form = SessionEditForm(request.POST) # read the submitted data
    if form.is_valid(): # fills in form.errors so the html contains this info
        session = form.save(commit=False)
        session.group = group
        session.save() #insert/update in db
        messages.success(request, "Session added.")
        return redirect("group_dashboard", group_id=group_id)
    groups = get_managed_groups(request.user)
    sessions = Session.objects.filter(group=group).order_by("scheduled_from", "title")
    return render(request, "meditationapp/group_dashboard.html", {
        "groups": groups,
        "group": group,
        "sessions": sessions,
        "group_form": MeditationGroupForm(instance=group),
        "session_form": form,
    })


@login_required(login_url="account_login")
def session_edit(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    if not user_manages_group(request.user, session.group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    if request.method == "POST":
        form = SessionEditForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, "Session updated.")
            return redirect("group_dashboard", group_id=session.group_id)
    else:
        form = SessionEditForm(instance=session)
    return render(request, "meditationapp/session_form.html", {
        "form": form,
        "session": session,
        "group": session.group,
    })

# not the redirect instead of render. We just delter the session and then redirect the browser
@login_required(login_url="account_login")
@require_POST
def session_delete(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    if not user_manages_group(request.user, session.group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group_id = session.group_id
    session.delete()
    messages.success(request, "Session deleted.")
    return redirect("group_dashboard", group_id=group_id)


@user_passes_test(is_staff_user, login_url="account_login")
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


@user_passes_test(is_staff_user, login_url="account_login")
@require_POST
def approve_group(request, group_id):
    group = get_object_or_404(MeditationGroup, id=group_id, status=GroupStatus.PENDING)
    group.status = GroupStatus.APPROVED
    group.save(update_fields=["status", "updated_at"])
    return redirect("admin_dashboard")


@user_passes_test(is_staff_user, login_url="account_login")
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