# Generated for Holding Space partners and outbound check-in texts.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0009_sobrietyday'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HoldingPartner',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=80)),
                ('phone_e164', models.CharField(max_length=16)),
                ('status', models.CharField(choices=[('active', 'Active'), ('unsubscribed', 'Unsubscribed')], default='active', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('removed_at', models.DateTimeField(blank=True, null=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name', 'created_at', 'id']},
        ),
        migrations.AddConstraint(
            model_name='holdingpartner',
            constraint=models.UniqueConstraint(condition=models.Q(removed_at__isnull=True), fields=('owner', 'phone_e164'), name='holding_active_phone'),
        ),
        migrations.CreateModel(
            name='HoldingMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('body', models.CharField(max_length=320)),
                ('state', models.CharField(choices=[('failed', 'Not sent'), ('accepted', 'Sent'), ('delivered', 'Delivered'), ('acknowledged', 'Replied')], default='failed', max_length=16)),
                ('provider_id', models.CharField(blank=True, max_length=64)),
                ('error_code', models.CharField(blank=True, max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='tracking.holdingpartner')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='holding_messages', to='tracking.writerequest')),
            ],
            options={'ordering': ['-created_at', 'id']},
        ),
        migrations.AddIndex(
            model_name='holdingmessage',
            index=models.Index(fields=['owner', 'created_at'], name='holding_message_owner'),
        ),
    ]
