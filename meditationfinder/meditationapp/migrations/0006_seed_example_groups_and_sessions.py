from datetime import datetime

from django.db import migrations
from django.utils import timezone


def seed_examples(apps, schema_editor):
    meditation_group = apps.get_model("meditationapp", "MeditationGroup")
    session = apps.get_model("meditationapp", "Session")

    brisbane_group, _ = meditation_group.objects.update_or_create(
        name="Brisbane Mindfulness Circle",
        defaults={
            "description": "Weekly guided sits and occasional half-day retreats. Beginners welcome; cushions provided.",
            "style": "mindfulness",
            "religion": "Secular",
            "suburb": "St Lucia",
            "postcode": "4067",
            "link": "https://example.org/mindful-brisbane",
            "cost_type": "donation",
            "source": "self",
            "status": "approved",
        },
    )
    west_end_group, _ = meditation_group.objects.update_or_create(
        name="West End Zen Sit",
        defaults={
            "description": "A quiet Zen sitting group for regular practice and shared discussion.",
            "style": "zen",
            "religion": "Buddhist",
            "suburb": "West End",
            "postcode": "4101",
            "link": "https://example.org/west-end-zen",
            "cost_type": "free",
            "source": "scrape",
            "status": "approved",
        },
    )
    new_farm_group, _ = meditation_group.objects.update_or_create(
        name="New Farm Rest & Breathe",
        defaults={
            "description": "Restorative guided relaxation and yoga nidra sessions in a community setting.",
            "style": "yoga_nidra",
            "religion": "",
            "suburb": "New Farm",
            "postcode": "4005",
            "link": "https://example.org/new-farm-breathe",
            "cost_type": "free",
            "source": "scrape",
            "status": "approved",
        },
    )
    camp_hill_group, _ = meditation_group.objects.update_or_create(
        name="Camp Hill Community Sit",
        defaults={
            "description": "Beginner-friendly breathing and mindfulness sessions for the local community.",
            "style": "guided_breathing",
            "religion": "Secular",
            "suburb": "Camp Hill",
            "postcode": "4152",
            "link": "https://example.org/camp-hill-sit",
            "cost_type": "free",
            "source": "self",
            "status": "approved",
        },
    )
    meditation_group.objects.update_or_create(
        name="Sunshine Coast Breath & Stillness",
        defaults={
            "description": "Guided breathing and stillness sessions submitted for review.",
            "style": "guided_breathing",
            "religion": "Secular",
            "suburb": "Maroochydore",
            "postcode": "4558",
            "link": "https://example.org/sunshine-breath",
            "cost_type": "donation",
            "source": "scrape",
            "status": "pending",
        },
    )

    session.objects.update_or_create(
        group=brisbane_group,
        title="Wednesday sit",
        defaults={
            "description": "Guided mindfulness practice with time for quiet sitting and a short group reflection.",
            "style": "mindfulness",
            "is_recurring": True,
            "recurrence_pattern": "Weekly on Wednesdays",
            "beginner_friendly": True,
            "scheduled_from": timezone.make_aware(datetime(2026, 5, 6, 19, 0)),
            "scheduled_to": timezone.make_aware(datetime(2026, 5, 6, 20, 0)),
            "suburb": "St Lucia",
            "postcode": "4067",
            "meeting_link": "",
            "cost": None,
        },
    )
    session.objects.update_or_create(
        group=brisbane_group,
        title="Sunday open sit",
        defaults={
            "description": "A longer weekly sitting practice with optional online attendance.",
            "style": "mindfulness",
            "is_recurring": True,
            "recurrence_pattern": "Weekly on Sundays",
            "beginner_friendly": False,
            "scheduled_from": timezone.make_aware(datetime(2026, 5, 3, 9, 0)),
            "scheduled_to": timezone.make_aware(datetime(2026, 5, 3, 10, 30)),
            "suburb": "",
            "postcode": "",
            "meeting_link": "https://zoom.example/abc",
            "cost": None,
        },
    )
    session.objects.update_or_create(
        group=west_end_group,
        title="Tuesday Zen sitting",
        defaults={
            "description": "Silent sitting, walking meditation, and a short reading from the Zen tradition.",
            "style": "zen",
            "is_recurring": True,
            "recurrence_pattern": "Weekly on Tuesdays",
            "beginner_friendly": False,
            "scheduled_from": timezone.make_aware(datetime(2026, 5, 5, 18, 30)),
            "scheduled_to": timezone.make_aware(datetime(2026, 5, 5, 20, 0)),
            "suburb": "West End",
            "postcode": "4101",
            "meeting_link": "",
            "cost": None,
        },
    )
    session.objects.update_or_create(
        group=new_farm_group,
        title="Thursday yoga nidra",
        defaults={
            "description": "A guided rest practice for relaxation, body awareness, and calmer sleep.",
            "style": "yoga_nidra",
            "is_recurring": True,
            "recurrence_pattern": "Weekly on Thursdays",
            "beginner_friendly": True,
            "scheduled_from": timezone.make_aware(datetime(2026, 5, 7, 17, 30)),
            "scheduled_to": timezone.make_aware(datetime(2026, 5, 7, 18, 30)),
            "suburb": "New Farm",
            "postcode": "4005",
            "meeting_link": "",
            "cost": None,
        },
    )
    session.objects.update_or_create(
        group=camp_hill_group,
        title="Beginners breathwork morning",
        defaults={
            "description": "An introductory guided breathing session for people new to meditation and mindfulness practice.",
            "style": "guided_breathing",
            "is_recurring": False,
            "recurrence_pattern": "",
            "beginner_friendly": True,
            "scheduled_from": timezone.make_aware(datetime(2026, 5, 2, 10, 0)),
            "scheduled_to": timezone.make_aware(datetime(2026, 5, 2, 11, 30)),
            "suburb": "Camp Hill",
            "postcode": "4152",
            "meeting_link": "",
            "cost": None,
        },
    )


def remove_examples(apps, schema_editor):
    meditation_group = apps.get_model("meditationapp", "MeditationGroup")
    names = [
        "Brisbane Mindfulness Circle",
        "West End Zen Sit",
        "New Farm Rest & Breathe",
        "Camp Hill Community Sit",
        "Sunshine Coast Breath & Stillness",
    ]
    meditation_group.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("meditationapp", "0005_session_beginner_friendly_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_examples, remove_examples),
    ]
