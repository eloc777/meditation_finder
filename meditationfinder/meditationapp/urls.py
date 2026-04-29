from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("finder/", views.index, name="finder"),
    path("sign-in/", views.sign_in, name="sign_in"),
    path("groups/<int:group_id>/", views.group_profile, name="group_profile"),
    path("group-dashboard/", views.group_dashboard, name="group_dashboard"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/groups/<int:group_id>/approve/", views.approve_group, name="approve_group"),
    path("admin-dashboard/groups/<int:group_id>/reject/", views.reject_group, name="reject_group"),
]