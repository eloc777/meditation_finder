# Generated manually — drops retired ingest/scrape pipeline tables.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("meditationapp", "0011_make_scheduled_to_optional"),
    ]

    operations = [
        migrations.DeleteModel(name="ExtractionAttempt"),
        migrations.DeleteModel(name="CandidateRecord"),
        migrations.DeleteModel(name="PipelineRun"),
    ]
