"""
URL configuration for meditationfinder project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("meditationfinder/admin/", admin.site.urls),
    path("meditationfinder/", include("meditationapp.urls")),
    # Auth (django-allauth): login, logout, Google OAuth callback, etc.
    path("meditationfinder/accounts/", include("allauth.urls")),
]
