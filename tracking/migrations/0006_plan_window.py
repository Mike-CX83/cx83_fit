import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0005_oura_integration'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DietEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('local_date', models.DateField()),
                ('meal', models.CharField(choices=[('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('dinner', 'Dinner'), ('snack', 'Snack')], max_length=12)),
                ('description', models.TextField(max_length=500)),
                ('calories', models.DecimalField(blank=True, decimal_places=1, max_digits=7, null=True)),
                ('protein_g', models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True)),
                ('fiber_g', models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True)),
                ('source_system', models.CharField(default='manual', max_length=40)),
                ('source_record_id', models.CharField(blank=True, max_length=120)),
                ('synthetic', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-local_date', 'meal', 'id']},
        ),
        migrations.CreateModel(
            name='ClinicalItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('lab', 'Lab'), ('medication', 'Medication'), ('diagnosis', 'Diagnosis')], max_length=12)),
                ('name', models.CharField(max_length=120)),
                ('detail', models.TextField(blank=True, max_length=500)),
                ('recorded_on', models.DateField()),
                ('current', models.BooleanField(default=True)),
                ('synthetic', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['kind', 'name', '-recorded_on', 'id']},
        ),
        migrations.AddIndex(model_name='dietentry', index=models.Index(fields=['owner', 'local_date', 'synthetic'], name='diary_owner_date')),
        migrations.AddConstraint(model_name='dietentry', constraint=models.UniqueConstraint(fields=('owner', 'source_system', 'source_record_id'), condition=~models.Q(source_record_id=''), name='unique_diary_source')),
        migrations.AddIndex(model_name='clinicalitem', index=models.Index(fields=['owner', 'kind', 'current'], name='clinical_owner_current')),
    ]
