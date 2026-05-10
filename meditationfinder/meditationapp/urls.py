from django.urls import include, path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("finder/", views.index, name="finder"),
    path("groups/create/", views.group_create, name="group_create"),
    path("saved/", views.saved_groups, name="saved_groups"),
    path("groups/<int:group_id>/save/", views.group_save, name="group_save"),
    path("groups/<int:group_id>/unsave/", views.group_unsave, name="group_unsave"),
    path("groups/<int:group_id>/", views.group_profile, name="group_profile"),
    path("group-dashboard/", views.group_dashboard, name="group_dashboard_root"),
    path("group-dashboard/<int:group_id>/", views.group_dashboard, name="group_dashboard"),
    path("group-dashboard/<int:group_id>/edit/", views.group_edit, name="group_edit"),
    path("group-dashboard/<int:group_id>/delete/", views.group_delete, name="group_delete"),
    path("group-dashboard/<int:group_id>/sessions/add/", views.session_create, name="session_create"),
    path("group-dashboard/<int:group_id>/sessions/scan/", views.session_scan, name="session_scan"),
    path("group-dashboard/<int:group_id>/sessions/import/", views.session_bulk_create, name="session_bulk_create"),
    path("sessions/<int:session_id>/edit/", views.session_edit, name="session_edit"),
    path("sessions/<int:session_id>/delete/", views.session_delete, name="session_delete"),
]