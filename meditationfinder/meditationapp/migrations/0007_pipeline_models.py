from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("meditationapp", "0006_seed_example_groups_and_sessions"),
    ]

    operations = [
        migrations.CreateModel(
            name="PipelineRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(max_length=64)),
                ("target_location", models.CharField(blank=True, default="", max_length=128)),
                ("status", models.CharField(choices=[("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], db_index=True, default="running", max_length=16)),
                ("candidates_found", models.PositiveIntegerField(default=0)),
                ("candidates_failed", models.PositiveIntegerField(default=0)),
                ("candidates_promoted", models.PositiveIntegerField(default=0)),
                ("notes", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="CandidateRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(db_index=True, max_length=64)),
                ("source_id", models.CharField(blank=True, default="", max_length=255)),
                ("raw_name", models.CharField(max_length=255)),
                ("raw_address", models.TextField(blank=True, default="")),
                ("raw_website", models.URLField(blank=True, null=True)),
                ("raw_phone", models.CharField(blank=True, default="", max_length=64)),
                ("raw_description", models.TextField(blank=True, default="")),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("normalized_name", models.CharField(blank=True, default="", max_length=255)),
                ("normalized_address", models.TextField(blank=True, default="")),
                ("normalized_website", models.URLField(blank=True, null=True)),
                ("status", models.CharField(choices=[("new", "New"), ("keyword_passed", "Keyword passed"), ("quality_passed", "Quality passed"), ("extraction_ready", "Extraction ready"), ("extraction_passed", "Extraction passed"), ("promoted", "Promoted"), ("failed", "Failed")], db_index=True, default="new", max_length=32)),
                ("failed_stage", models.CharField(blank=True, choices=[("ingestion", "Ingestion"), ("keyword_check", "Keyword check"), ("quality_check", "Quality check"), ("session_extraction", "Session extraction"), ("session_quality", "Session quality"), ("promotion", "Promotion")], db_index=True, default="", max_length=64)),
                ("reason_code", models.CharField(blank=True, choices=[("duplicate", "Duplicate"), ("invalid_geography", "Invalid geography"), ("missing_contact", "Missing contact"), ("missing_description", "Missing description"), ("no_website", "No website"), ("no_sessions_found", "No sessions found"), ("site_inaccessible", "Site inaccessible"), ("ambiguous_content", "Ambiguous content"), ("low_confidence", "Low confidence"), ("low_quality", "Low quality"), ("not_meditation_related", "Not meditation related")], db_index=True, default="", max_length=64)),
                ("confidence_score", models.FloatField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("promoted_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="meditationapp.meditationgroup")),
                ("run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="candidates", to="meditationapp.pipelinerun")),
            ],
        ),
        migrations.CreateModel(
            name="ExtractionAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField()),
                ("http_status", models.PositiveIntegerField(blank=True, null=True)),
                ("content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("compact_text", models.TextField(blank=True, default="")),
                ("llm_provider", models.CharField(blank=True, default="", max_length=64)),
                ("llm_model", models.CharField(blank=True, default="", max_length=128)),
                ("prompt_version", models.CharField(blank=True, default="", max_length=32)),
                ("raw_response", models.TextField(blank=True, default="")),
                ("parsed_response", models.JSONField(blank=True, default=dict)),
                ("confidence_score", models.FloatField(blank=True, null=True)),
                ("status", models.CharField(choices=[("new", "New"), ("keyword_passed", "Keyword passed"), ("quality_passed", "Quality passed"), ("extraction_ready", "Extraction ready"), ("extraction_passed", "Extraction passed"), ("promoted", "Promoted"), ("failed", "Failed")], db_index=True, default="new", max_length=32)),
                ("failed_stage", models.CharField(blank=True, choices=[("ingestion", "Ingestion"), ("keyword_check", "Keyword check"), ("quality_check", "Quality check"), ("session_extraction", "Session extraction"), ("session_quality", "Session quality"), ("promotion", "Promotion")], db_index=True, default="", max_length=64)),
                ("reason_code", models.CharField(blank=True, choices=[("duplicate", "Duplicate"), ("invalid_geography", "Invalid geography"), ("missing_contact", "Missing contact"), ("missing_description", "Missing description"), ("no_website", "No website"), ("no_sessions_found", "No sessions found"), ("site_inaccessible", "Site inaccessible"), ("ambiguous_content", "Ambiguous content"), ("low_confidence", "Low confidence"), ("low_quality", "Low quality"), ("not_meditation_related", "Not meditation related")], db_index=True, default="", max_length=64)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="extraction_attempts", to="meditationapp.candidaterecord")),
                ("run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="extraction_attempts", to="meditationapp.pipelinerun")),
            ],
        ),
        migrations.AddIndex(
            model_name="candidaterecord",
            index=models.Index(fields=["source", "source_id"], name="meditationa_source_9c2e22_idx"),
        ),
        migrations.AddIndex(
            model_name="candidaterecord",
            index=models.Index(fields=["normalized_name"], name="meditationa_normali_4f4505_idx"),
        ),
    ]
