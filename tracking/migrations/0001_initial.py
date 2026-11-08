import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Measurement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("metric", models.CharField(choices=[("weight", "Weight"), ("waist", "Waist"), ("chest", "Chest"), ("hip", "Hip"), ("arm", "Arm"), ("thigh", "Thigh"), ("calf", "Calf")], max_length=20)),
                ("value", models.DecimalField(decimal_places=3, max_digits=8)),
                ("unit", models.CharField(max_length=8)),
                ("side", models.CharField(blank=True, max_length=5)),
                ("location", models.CharField(blank=True, max_length=120)),
                ("local_date", models.DateField()),
                ("observed_at", models.DateTimeField(blank=True, null=True)),
                ("source_timezone", models.CharField(default="America/Chicago", max_length=64)),
                ("source_system", models.CharField(max_length=40)),
                ("source_record_id", models.CharField(max_length=120)),
                ("entry_method", models.CharField(default="manually_reported", max_length=20)),
                ("notes", models.TextField(blank=True, max_length=2000)),
                ("synthetic", models.BooleanField(default=False)),
                ("version", models.PositiveIntegerField(default=1)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["local_date", "created_at", "id"],
                     "indexes": [models.Index(fields=["owner", "local_date", "synthetic"], name="measurement_owner_date")],
                     "constraints": [models.UniqueConstraint(fields=("owner", "source_system", "source_record_id"), name="unique_measurement_source"),
                                     models.CheckConstraint(condition=models.Q(("value__gt", 0)), name="measurement_positive"),
                                     models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="measurement_version_positive")]},
        ),
        migrations.CreateModel(
            name="WriteRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.UUIDField()),
                ("payload_hash", models.CharField(max_length=64)),
                ("response", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("owner", "request_id"), name="unique_owner_request")]},
        ),
        migrations.CreateModel(
            name="Correction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_source", models.CharField(max_length=40)),
                ("operation", models.CharField(max_length=10)),
                ("before", models.JSONField(null=True)),
                ("after", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("measurement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="corrections", to="tracking.measurement")),
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to="tracking.writerequest")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
