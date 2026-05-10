from django.apps import AppConfig


class MeditationappConfig(AppConfig):
    name = "meditationapp"

    def ready(self):
        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
        from django.contrib import admin
        from django.contrib.auth.models import Group

        for model in [Group, EmailAddress, SocialAccount, SocialApp, SocialToken]:
            try:
                admin.site.unregister(model)
            except admin.sites.NotRegistered:
                pass
