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


class DietEntry(models.Model):
    """One meal note inside the 90 day diary. Daily totals stay on nutrition summaries."""
    MEALS = [('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('dinner', 'Dinner'), ('snack', 'Snack')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    local_date = models.DateField()
    meal = models.CharField(max_length=12, choices=MEALS)
    description = models.TextField(max_length=500)
    calories = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    protein_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fiber_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    source_system = models.CharField(max_length=40, default='manual')
    source_record_id = models.CharField(max_length=120, blank=True)
    synthetic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-local_date', 'meal', 'id']
        indexes = [models.Index(fields=['owner', 'local_date', 'synthetic'], name='diary_owner_date')]
        constraints = [models.UniqueConstraint(fields=['owner', 'source_system', 'source_record_id'],
            condition=~models.Q(source_record_id=''), name='unique_diary_source')]


class ClinicalItem(models.Model):
    """Current labs, medications and diagnoses. These stay available past the 90 day window."""
    KINDS = [('lab', 'Lab'), ('medication', 'Medication'), ('diagnosis', 'Diagnosis')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=12, choices=KINDS)
    name = models.CharField(max_length=120)
    detail = models.TextField(blank=True, max_length=500)
    recorded_on = models.DateField()
    current = models.BooleanField(default=True)
    synthetic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['kind', 'name', '-recorded_on', 'id']
        indexes = [models.Index(fields=['owner', 'kind', 'current'], name='clinical_owner_current')]


class OuraRevision(models.Model):
    record = models.ForeignKey(OuraRecord, on_delete=models.CASCADE, related_name='revisions')
    version = models.PositiveIntegerField()
    raw_json = models.TextField()
    page = models.ForeignKey(OuraPage, on_delete=models.PROTECT)
    page_index = models.PositiveIntegerField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['record', 'version'], name='oura_unique_revision')]


class JournalEntry(models.Model):
    """Authorized journal text. Structured facts live on JournalObservation.

    Later memory, question, and score rows can reference this id. Those tables
    are not created until their behavior is specified. Channel values mcp and
    voice are reserved and rejected by the service until those clients exist.
    """
    CHANNELS = [('dashboard', 'Dashboard'), ('mcp', 'MCP'), ('voice', 'Voice')]
    PROCESSING = [('stored', 'Stored'), ('pending_extraction', 'Pending extraction'),
                  ('extracted', 'Extracted'), ('extraction_failed', 'Extraction failed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request = models.OneToOneField(WriteRequest, on_delete=models.PROTECT, related_name='journal_entry')
    channel = models.CharField(max_length=16, choices=CHANNELS, default='dashboard')
    local_date = models.DateField()
    occurred_at = models.DateTimeField(null=True, blank=True)
    time_precision = models.CharField(max_length=8, default='date')
    source_timezone = models.CharField(max_length=64, default='America/Chicago')
    captured_at = models.DateTimeField(auto_now_add=True)
    body = models.TextField(blank=True, max_length=10000)
    body_sha256 = models.CharField(max_length=64, blank=True)
    processing_state = models.CharField(max_length=24, choices=PROCESSING, default='stored')
    protocol_version = models.CharField(max_length=32, default='journal-1')
    lineage_id = models.UUIDField(default=uuid.uuid4, editable=False)
    synthetic = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-local_date', '-captured_at', 'id']
        indexes = [models.Index(fields=['owner', 'local_date', 'synthetic'], name='journal_owner_date')]
        constraints = [models.CheckConstraint(condition=models.Q(version__gte=1), name='journal_entry_version')]


class JournalObservation(models.Model):
    """One supported fact linked to its journal entry. Unknown stays null."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='observations')
    domain_id = models.PositiveSmallIntegerField()
    metric_key = models.CharField(max_length=40)
    value_state = models.CharField(max_length=20)
    value_type = models.CharField(max_length=16)
    value_json = models.JSONField(null=True, blank=True)
    narrative = models.TextField(blank=True, max_length=2000)
    subject = models.CharField(max_length=16, default='self')
    local_date = models.DateField()
    source_timezone = models.CharField(max_length=64)
    confirmation_status = models.CharField(max_length=16, default='confirmed')
    registry_version = models.CharField(max_length=32, default='registry-1')
    lineage_id = models.UUIDField(default=uuid.uuid4, editable=False)
    synthetic = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['local_date', 'id']
        indexes = [models.Index(fields=['owner', 'domain_id', 'local_date'], name='journal_obs_domain')]
        constraints = [
            models.CheckConstraint(condition=models.Q(domain_id__in=[12, 13, 14, 16, 17, 18, 19]), name='journal_obs_domain_id'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='journal_obs_version'),
        ]

    def domain_label(self):
        from .journal_registry import DOMAINS
        return DOMAINS.get(self.domain_id, 'Recorded')


class JournalMemory(models.Model):
    """Bounded durable context. A hypothesis stays a candidate until the owner confirms it."""
    KINDS = [('preference', 'Preference'), ('context', 'Context'), ('concern', 'Concern'),
             ('commitment', 'Commitment'), ('milestone', 'Milestone')]
    STATUSES = [('candidate', 'Candidate'), ('confirmed', 'Confirmed'), ('active', 'Active'),
                ('resolved', 'Resolved'), ('superseded', 'Superseded'), ('deleted', 'Deleted')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request = models.OneToOneField(WriteRequest, on_delete=models.PROTECT, related_name='journal_memory')
    kind = models.CharField(max_length=16, choices=KINDS)
    status = models.CharField(max_length=16, choices=STATUSES, default='active')
    domain_id = models.PositiveSmallIntegerField(null=True, blank=True)
    practice_key = models.CharField(max_length=40, blank=True)
    text = models.TextField(blank=True, max_length=2000)
    review_on = models.DateField(null=True, blank=True)
    source_entry = models.ForeignKey(JournalEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name='memories')
    synthetic = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at', 'id']
        indexes = [models.Index(fields=['owner', 'status', 'kind'], name='journal_memory_status')]


class JournalQuestion(models.Model):
    """One asked, skipped, or deferred check-in question. Silence is not an answer."""
    STATUSES = [('asked', 'Asked'), ('answered', 'Answered'), ('skipped', 'Skipped'),
                ('deferred', 'Deferred'), ('suppressed', 'Suppressed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    topic = models.CharField(max_length=80)
    prompt = models.TextField(max_length=500)
    reason = models.CharField(max_length=40)
    status = models.CharField(max_length=16, choices=STATUSES)
    domain_id = models.PositiveSmallIntegerField(null=True, blank=True)
    asked_at = models.DateTimeField(null=True, blank=True)
    next_eligible = models.DateTimeField(null=True, blank=True)
    synthetic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'id']
        indexes = [models.Index(fields=['owner', 'status', 'topic'], name='journal_question_topic')]


class JournalScore(models.Model):
    """A versioned personal summary. A null result means the coverage gate was not met."""
    KINDS = [('daily_state', 'Daily state'), ('routine_alignment', 'Routine alignment')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=24, choices=KINDS)
    local_date = models.DateField()
    formula_version = models.CharField(max_length=32)
    result = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    coverage = models.JSONField(default=dict)
    input_ids = models.JSONField(default=list)
    synthetic = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['owner', 'kind', 'local_date', 'formula_version', 'synthetic'], name='journal_score_day')]


class JournalCorrection(models.Model):
    """Field names and versions only. Journal text is never copied here."""
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='corrections')
    observation = models.ForeignKey(JournalObservation, null=True, blank=True, on_delete=models.SET_NULL, related_name='corrections')
    request = models.OneToOneField(WriteRequest, on_delete=models.PROTECT, related_name='journal_correction')
    operation = models.CharField(max_length=10)
    before_version = models.PositiveIntegerField(null=True, blank=True)
    after_version = models.PositiveIntegerField()
    observation_before_version = models.PositiveIntegerField(null=True, blank=True)
    observation_after_version = models.PositiveIntegerField(null=True, blank=True)
    changed_fields = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
