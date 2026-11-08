"""Current labs, medications, and diagnoses.

Receipts identify the row. They do not keep the name or the detail.
"""
import hashlib
import json
from django.db import IntegrityError, transaction
from django.utils import timezone
from .domain import InvalidMeasurement, parse_day, request_uuid
from .models import ClinicalItem, WriteRequest
from .plan import replace_current_lab
from .services import RecordNotFound, _owner, _replay

_GROUPS = {'lab': 'labs', 'medication': 'medications', 'diagnosis': 'diagnoses'}


def current_items(owner, include_synthetic=False):
    _owner(owner)
    rows = ClinicalItem.objects.filter(owner=owner, current=True)
    if not include_synthetic:
        rows = rows.filter(synthetic=False)
    grouped = {'labs': [], 'medications': [], 'diagnoses': []}
    for row in rows:
        grouped[_GROUPS[row.kind]].append({
            'id': str(row.id),
            'kind': row.kind,
            'name': row.name,
            'detail': row.detail,
            'recorded_on': row.recorded_on.isoformat(),
            'current': True,
        })
    return grouped


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _finish(owner, request_id, digest, build):
    try:
        with transaction.atomic():
            prior = _replay(owner, request_id, digest)
            if prior is not None:
                return prior
            receipt = WriteRequest.objects.create(
                owner=owner, request_id=request_id, payload_hash=digest, response={})
            result = build()
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except IntegrityError:
        prior = _replay(owner, request_id, digest)
        if prior is not None:
            return prior
        raise


def save_clinical(owner, kind, name, detail, recorded_on, request_id, *, synthetic=False):
    """Save one current item. A repeated request id with the same content replays."""
    _owner(owner)
    if type(synthetic) is not bool:
        raise InvalidMeasurement('synthetic must be true or false.')
    if kind not in _GROUPS:
        raise InvalidMeasurement('Choose a lab, medication, or diagnosis.')
    clean_name = ' '.join((name or '').split())
    clean_detail = ' '.join((detail or '').split())
    if not clean_name or len(clean_name) > 120 or len(clean_detail) > 500:
        raise InvalidMeasurement('Enter a name, and keep the detail within 500 characters.')
    day = parse_day(recorded_on)
    if day > timezone.localdate():
        raise InvalidMeasurement('The recorded date cannot be in the future.')
    request_id = request_uuid(request_id)
    digest = _digest({
        'operation': 'save_clinical', 'kind': kind, 'name': clean_name, 'detail': clean_detail,
        'recorded_on': day.isoformat(), 'synthetic': synthetic,
    })

    def build():
        if kind == 'lab':
            replace_current_lab(owner, clean_name, synthetic)
        row = ClinicalItem.objects.create(
            owner=owner, kind=kind, name=clean_name, detail=clean_detail,
            recorded_on=day, current=True, synthetic=synthetic)
        return {'id': str(row.id), 'kind': kind, 'recorded_on': day.isoformat(),
                'current': True, 'operation': 'create'}

    return _finish(owner, request_id, digest, build)


def stop_clinical(owner, item_id, request_id):
    """Mark one current item as no longer current. The row stays in the record."""
    _owner(owner)
    item_id = request_uuid(item_id)
    request_id = request_uuid(request_id)
    digest = _digest({'operation': 'stop_clinical', 'item_id': item_id})

    def build():
        row = ClinicalItem.objects.filter(owner=owner, pk=item_id, current=True).first()
        if row is None:
            raise RecordNotFound('That current item was not found.')
        row.current = False
        row.save(update_fields=['current'])
        return {'id': str(row.id), 'kind': row.kind, 'current': False, 'operation': 'stop'}

    return _finish(owner, request_id, digest, build)
