import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .domain import METRICS, InvalidMeasurement, validate_measurement


class Measurement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    metric = models.CharField(max_length=20, choices=[(x, x.title()) for x in METRICS])
    value = models.DecimalField(max_digits=8, decimal_places=3)
    unit = models.CharField(max_length=8)
    side = models.CharField(max_length=5, blank=True)
    location = models.CharField(max_length=120, blank=True)
    local_date = models.DateField()
    observed_at = models.DateTimeField(null=True, blank=True)
    source_timezone = models.CharField(max_length=64, default="America/Chicago")
    source_system = models.CharField(max_length=40)
    source_record_id = models.CharField(max_length=120)
    entry_method = models.CharField(max_length=20, default="manually_reported")
    notes = models.TextField(blank=True, max_length=2000)
    synthetic = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    imported_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["local_date", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "source_system", "source_record_id"], name="unique_measurement_source"),
            models.CheckConstraint(condition=models.Q(value__gt=0), name="measurement_positive"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="measurement_version_positive"),
        ]
        indexes = [models.Index(fields=["owner", "local_date", "synthetic"], name="measurement_owner_date")]

    def clean(self):
        try:
            validate_measurement({k: getattr(self, k) for k in (
                "metric", "value", "unit", "side", "location", "local_date", "observed_at",
                "source_timezone", "notes", "synthetic")})
        except InvalidMeasurement as exc:
            raise ValidationError(str(exc)) from exc


class WriteRequest(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request_id = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "request_id"], name="unique_owner_request")]


class Correction(models.Model):
    measurement = models.ForeignKey(Measurement, on_delete=models.CASCADE, related_name="corrections")
    request = models.OneToOneField(WriteRequest, on_delete=models.PROTECT)
    actor_source = models.CharField(max_length=40)
    operation = models.CharField(max_length=10)
    before = models.JSONField(null=True)
    after = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ProgressPhoto(models.Model):
    VIEWS = [('front', 'Front'), ('side', 'Side'), ('back', 'Back')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request = models.OneToOneField(WriteRequest, on_delete=models.PROTECT)
    capture_date = models.DateField()
    view = models.CharField(max_length=5, choices=VIEWS)
    notes = models.TextField(blank=True, max_length=2000)
    synthetic = models.BooleanField(default=False)
    original_format = models.CharField(max_length=4, choices=[('JPEG', 'JPEG'), ('PNG', 'PNG'), ('WEBP', 'WebP')])
    original_sha256 = models.CharField(max_length=64)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-capture_date', '-uploaded_at', 'id']
        indexes = [models.Index(fields=['owner', 'synthetic', 'capture_date'], name='photo_owner_date')]


class SummaryRecord(models.Model):
    KINDS = [('nutrition', 'Nutrition'), ('recovery', 'Recovery'), ('activity', 'Activity'), ('health', 'Health')]
    COMPLETENESS = [('unknown', 'Unknown'), ('partial', 'Partial'), ('complete', 'Complete')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=12, choices=KINDS)
    local_date = models.DateField()
    source_timezone = models.CharField(max_length=64)
    source_system = models.CharField(max_length=40)
    source_record_id = models.CharField(max_length=120)
    entry_method = models.CharField(max_length=20, default='manually_reported')
    device = models.CharField(max_length=120, blank=True)
    completeness = models.CharField(max_length=10, choices=COMPLETENESS, default='unknown')
    values = models.JSONField()
    notes = models.TextField(blank=True, max_length=2000)
    synthetic = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-local_date', '-created_at', 'id']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'kind', 'source_system', 'source_record_id'], name='unique_summary_source'),
            models.UniqueConstraint(fields=['owner', 'kind', 'source_system', 'local_date'],
                                    condition=models.Q(kind__in=['nutrition', 'recovery', 'activity']), name='unique_daily_summary_source'),
        ]
        indexes = [models.Index(fields=['owner', 'kind', 'local_date', 'synthetic'], name='summary_owner_kind_date')]


class SummaryCorrection(models.Model):
    record = models.ForeignKey(SummaryRecord, on_delete=models.CASCADE, related_name='corrections')
    request = models.OneToOneField(WriteRequest, on_delete=models.PROTECT)
    before = models.JSONField(null=True)
    after = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class NutritionTargets(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    values = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class ReviewNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request = models.OneToOneField(WriteRequest, on_delete=models.PROTECT)
    local_date = models.DateField()
    text = models.TextField(max_length=10000)
    source_system = models.CharField(max_length=10, choices=[('manual','Manual'),('mcp','MCP')])
    record_kind = models.CharField(max_length=12, blank=True)
    record_id = models.UUIDField(null=True, blank=True)
    synthetic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-local_date', '-created_at', 'id']
        indexes = [models.Index(fields=['owner', 'local_date', 'synthetic'], name='review_owner_date')]


class OuraConnection(models.Model):
    """One provider account; credentials never appear in a serializer or export."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account_key = models.CharField(max_length=80)
    source_account_id = models.TextField(null=True)
    synthetic = models.BooleanField(default=False)
    generation = models.UUIDField(default=uuid.uuid4)
    token_ciphertext = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True)
    scopes = models.JSONField(null=True)
    state = models.CharField(max_length=24, default='authorized')
    refresh_lease = models.UUIDField(null=True)
    refresh_until = models.DateTimeField(null=True)
    sync_lease = models.UUIDField(null=True)
    sync_until = models.DateTimeField(null=True)
    last_successful_sync = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'account_key', 'synthetic'], name='oura_owner_account')]


class OuraAuthorization(models.Model):
    state_hash = models.CharField(max_length=64, primary_key=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nonce_hash = models.CharField(max_length=64)
    secret_ciphertext = models.TextField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)


class OuraSync(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(OuraConnection, on_delete=models.CASCADE, related_name='syncs')
    collection = models.CharField(max_length=40)
    parameters = models.JSONField(default=dict)
    next_token = models.TextField(blank=True)
    seen_tokens = models.JSONField(default=list)
    status = models.CharField(max_length=24, default='pending')
    pages = models.PositiveIntegerField(default=0)
    records_seen = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True)
    retry_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OuraPage(models.Model):
    """Exact UTF-8 JSON response, deduplicated within account and collection."""
    connection = models.ForeignKey(OuraConnection, on_delete=models.CASCADE)
    collection = models.CharField(max_length=40)
    sha256 = models.CharField(max_length=64)
    raw_json = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'collection', 'sha256'], name='oura_unique_page')]


class OuraRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(OuraConnection, on_delete=models.CASCADE, related_name='records')
    collection = models.CharField(max_length=40)
    identity_key = models.CharField(max_length=64)
    source_record_id = models.TextField(null=True)
    identity_kind = models.CharField(max_length=24)
    # Text holds lossless JSON numbers, nulls, field absence, original dates/units.
    raw_json = models.TextField()
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'collection', 'identity_key'], name='oura_unique_record')]


class OuraRevision(models.Model):
    record = models.ForeignKey(OuraRecord, on_delete=models.CASCADE, related_name='revisions')
    version = models.PositiveIntegerField()
    raw_json = models.TextField()
    page = models.ForeignKey(OuraPage, on_delete=models.PROTECT)
    page_index = models.PositiveIntegerField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['record', 'version'], name='oura_unique_revision')]
