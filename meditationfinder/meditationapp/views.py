import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MeditationGroupForm, SessionEditForm
from .models import (
    CostType,
    GroupStatus,
    MeditationGroup,
    Role,
    SavedGroup,
    Session,
    Source,
    Style,
    UserRole,
)
from .services.session_import import (
    SessionImportError,
    compute_display_end_time,
    import_sessions_from_url,
    prepare_session_for_save,
)

logger = logging.getLogger(__name__)


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


SESSION_LIST_PAGE_SIZE = 30


def paginate_queryset(request, queryset, per_page):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return page_obj, query_params.urlencode()


def paginate_group_dashboard_sessions(request, group):
    sessions_qs = Session.objects.filter(group=group).order_by("scheduled_from", "title")
    return paginate_queryset(request, sessions_qs, SESSION_LIST_PAGE_SIZE)


def group_dashboard_import_context(request):
    return {
        "imported_sessions": request.session.get("imported_sessions"),
        "scan_url": request.session.get("scan_url", ""),
    }


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
    selected_religion = request.GET.get("religion", "")
    selected_q = request.GET.get("q", "")

    sessions = Session.objects.select_related("group") # start building the query

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

    if selected_religion:
        sessions = sessions.filter(group__religion__iexact=selected_religion)

    if request.GET.get("beginner_friendly"):
        sessions = sessions.filter(beginner_friendly=True)

    sessions = sessions.order_by("scheduled_from", "title")
    paginated_sessions, pagination_query = paginate_queryset(
        request, sessions, SESSION_LIST_PAGE_SIZE
    )

    approved_sessions = Session.objects.select_related("group")
    suburb_values = sorted(
        {
            session.suburb or session.group.suburb
            for session in approved_sessions
            if session.suburb or session.group.suburb
        }
    )
    religion_values = sorted(
        {
            session.group.religion
            for session in approved_sessions
            if session.group.religion
        }
    )
    context = {
        "sessions": paginated_sessions,
        "result_count": paginated_sessions.paginator.count,
        "suburbs": suburb_values,
        "religion_options": religion_values,
        "day_options": DAY_OPTIONS,
        "time_options": TIME_OPTIONS,
        "style_options": Style.choices,
        "cost_options": CostType.choices,
        "selected_days": selected_days,
        "selected_time": selected_time,
        "selected_suburb": selected_suburb,
        "selected_style": selected_style,
        "selected_cost": selected_cost,
        "selected_religion": selected_religion,
        "selected_q": selected_q,
        "recurring_only": bool(request.GET.get("recurring")),
        "beginner_friendly": bool(request.GET.get("beginner_friendly")),
        "more_filters_open": bool(selected_style or selected_cost or selected_religion or request.GET.get("beginner_friendly")),
        "pagination_query": pagination_query,
    }
    return render(request, "meditationapp/finder.html", context)


@login_required(login_url="account_login")
def saved_groups(request):
    saves_qs = SavedGroup.objects.filter(user=request.user).select_related("group").order_by("-saved_at")
    paginator = Paginator(saves_qs, 25)
    paginated_saves = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "meditationapp/saved_groups.html",
        {"saved_groups": paginated_saves},
    )


@login_required(login_url="account_login")
def group_create(request):
    if request.method == "POST":
        form = MeditationGroupForm(request.POST, prefix="group")
        if form.is_valid():
            manager_role, _ = Role.objects.get_or_create(name="group_manager")
            group = form.save(commit=False)
            group.owner = request.user
            group.source = Source.SELF
            group.status = GroupStatus.APPROVED
            group.save()
            UserRole.objects.get_or_create(user=request.user, role=manager_role, group=group)
            messages.success(request, "Group created. You can now manage details and sessions.")
            return redirect("group_dashboard", group_id=group.id)
    else:
        form = MeditationGroupForm(prefix="group")
    return render(request, "meditationapp/group_create.html", {"form": form})


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
    paginated_sessions, pagination_query = paginate_group_dashboard_sessions(request, group)
    group_form = MeditationGroupForm(instance=group, prefix="group")
    session_form = SessionEditForm(prefix="session")
    return render(request, "meditationapp/group_dashboard.html", {
        "groups": groups,
        "group": group,
        "sessions": paginated_sessions,
        "pagination_query": pagination_query,
        "group_form": group_form,
        "session_form": session_form,
        **group_dashboard_import_context(request),
    })


@login_required(login_url="account_login")
@require_POST
def group_edit(request, group_id):
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    form = MeditationGroupForm(request.POST, instance=group, prefix="group")
    if form.is_valid():
        form.save()
        messages.success(request, "Group details saved.")
        return redirect("group_dashboard", group_id=group_id)
    groups = get_managed_groups(request.user)
    paginated_sessions, pagination_query = paginate_group_dashboard_sessions(request, group)
    return render(request, "meditationapp/group_dashboard.html", {
        "groups": groups,
        "group": group,
        "sessions": paginated_sessions,
        "pagination_query": pagination_query,
        "group_form": form,
        "session_form": SessionEditForm(prefix="session"),
        **group_dashboard_import_context(request),
    })


@login_required(login_url="account_login")
@require_POST
def group_delete(request, group_id):
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    group_name = group.name
    group.delete()
    messages.success(request, f"{group_name} and its sessions were deleted.")
    return redirect("group_dashboard_root")


@login_required(login_url="account_login")
@require_POST
def session_create(request, group_id):
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    form = SessionEditForm(request.POST, prefix="session")
    if form.is_valid():
        session = form.save(commit=False)
        session.group = group
        session.save()
        messages.success(request, "Session added.")
        return redirect("group_dashboard", group_id=group_id)
    groups = get_managed_groups(request.user)
    paginated_sessions, pagination_query = paginate_group_dashboard_sessions(request, group)
    return render(request, "meditationapp/group_dashboard.html", {
        "groups": groups,
        "group": group,
        "sessions": paginated_sessions,
        "pagination_query": pagination_query,
        "group_form": MeditationGroupForm(instance=group, prefix="group"),
        "session_form": form,
        **group_dashboard_import_context(request),
    })


@login_required(login_url="account_login")
def session_edit(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    if not user_manages_group(request.user, session.group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    # post if we are trying to submit the edit, get if we are opening a session form (different from group form because it is rendered already)
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


@login_required(login_url="account_login")
@require_POST
def session_scan(request, group_id):
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    url = request.POST.get("scan_url", "").strip()
    if not url:
        messages.warning(request, "Please enter a URL to scan.")
        return redirect("group_dashboard", group_id=group_id)
    try:
        found_sessions = import_sessions_from_url(url, group.name)
        for s in found_sessions:
            s["display_end_time"] = compute_display_end_time(s)
        request.session["imported_sessions"] = found_sessions
        request.session["scan_url"] = url
        messages.success(request, f"Found {len(found_sessions)} session(s). Review and save the ones you want.")
    except SessionImportError as exc:
        messages.warning(request, str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during session scan for group %s", group_id)
        messages.error(request, "Something went wrong while scanning. Please try again.")
    return redirect("group_dashboard", group_id=group_id)


@login_required(login_url="account_login")
@require_POST
def session_bulk_create(request, group_id):
    if not user_manages_group(request.user, group_id):
        return HttpResponseForbidden("You do not have permission to manage this group.")
    group = get_object_or_404(MeditationGroup, id=group_id)
    imported_sessions = request.session.get("imported_sessions")
    if not imported_sessions:
        messages.warning(request, "No imported sessions to save. Try scanning a URL first.")
        return redirect("group_dashboard", group_id=group_id)
    selected_indices = request.POST.getlist("selected_sessions")
    if not selected_indices:
        messages.warning(request, "No sessions selected. Please tick at least one session to save.")
        return redirect("group_dashboard", group_id=group_id)
    saved_count = 0
    for index_str in selected_indices:
        try:
            index = int(index_str)
        except ValueError:
            continue
        if index < 0 or index >= len(imported_sessions):
            continue
        session_kwargs = prepare_session_for_save(imported_sessions[index], group)
        if session_kwargs:
            Session.objects.create(**session_kwargs)
            saved_count += 1
    if saved_count:
        messages.success(request, f"Saved {saved_count} session(s).")
        request.session.pop("imported_sessions", None)
        request.session.pop("scan_url", None)
    else:
        messages.warning(request, "Could not save any sessions. The day/time data may not have been parseable.")
    return redirect("group_dashboard", group_id=group_id)


def group_profile(request, group_id):
    group = get_object_or_404(MeditationGroup, id=group_id)
    sessions = Session.objects.filter(group=group).order_by("scheduled_from", "title")
    is_saved = False
    if request.user.is_authenticated:
        is_saved = SavedGroup.objects.filter(user=request.user, group=group).exists()
    return render(
        request,
        "meditationapp/group_profile.html",
        {"group": group, "sessions": sessions, "is_saved": is_saved},
    )


@login_required(login_url="account_login")
@require_POST
def group_save(request, group_id):
    group = get_object_or_404(MeditationGroup, id=group_id)
    _, created = SavedGroup.objects.get_or_create(user=request.user, group=group)
    if created:
        messages.success(request, "Group saved to your list. View it anytime under Saved groups.")
    else:
        messages.info(request, "This group is already on your saved list.")
    return redirect("group_profile", group_id=group_id)


@login_required(login_url="account_login")
@require_POST
def group_unsave(request, group_id):
    group = get_object_or_404(MeditationGroup, id=group_id)
    SavedGroup.objects.filter(user=request.user, group=group).delete()
    messages.success(request, "Removed from your saved groups.")
    return redirect("group_profile", group_id=group_id)