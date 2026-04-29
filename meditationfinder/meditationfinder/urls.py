"""
URL configuration for meditationfinder project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.urls import include, path

urlpatterns = [
    path("meditationfinder/", include("meditationapp.urls")),
]
