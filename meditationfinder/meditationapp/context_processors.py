from meditationapp.models import MeditationGroup


def show_group_dashboard_link(request):
    user = request.user
    if not user.is_authenticated:
        return {"show_group_dashboard_link": False}
    if user.is_staff:
        return {"show_group_dashboard_link": True}
    visible = MeditationGroup.objects.filter(
        userrole__user=user,
        userrole__role__name="group_manager",
    ).exists()
    return {"show_group_dashboard_link": visible}
