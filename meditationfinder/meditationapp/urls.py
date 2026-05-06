from django.urls import include, path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("finder/", views.index, name="finder"),
    path("sign-in/", views.sign_in, name="sign_in"),
    path("groups/<int:group_id>/", views.group_profile, name="group_profile"),
    path("group-dashboard/", views.group_dashboard, name="group_dashboard_root"),
    path("group-dashboard/<int:group_id>/", views.group_dashboard, name="group_dashboard"),
    path("group-dashboard/<int:group_id>/edit/", views.group_edit, name="group_edit"),
    path("group-dashboard/<int:group_id>/sessions/add/", views.session_create, name="session_create"),
    path("sessions/<int:session_id>/edit/", views.session_edit, name="session_edit"),
    path("sessions/<int:session_id>/delete/", views.session_delete, name="session_delete"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/groups/<int:group_id>/approve/", views.approve_group, name="approve_group"),
    path("admin-dashboard/groups/<int:group_id>/reject/", views.reject_group, name="reject_group"),
]