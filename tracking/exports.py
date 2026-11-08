"""Private portable exports. No accounts, sessions, tokens or configuration."""
import csv
import hashlib
import io
import json
import tempfile
import zipfile
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (Measurement, SummaryRecord, ProgressPhoto, NutritionTargets, ReviewNote,
                     DietEntry, ClinicalItem, JournalEntry, JournalObservation, JournalCorrection,
                     JournalMemory, JournalQuestion, JournalScore, SobrietyDay)
from .reviews import serialize_review
from .photos import photo_metadata, photo_names, photo_storage
from .services import serialize, _owner
from .summaries import serialize_summary
from .views import owner_only
from .responses import private_file_response

MAX_EXPORT_BYTES = 512*1024*1024
MAX_EXPORT_RECORDS = 100000


def csv_bytes(rows, fields):
    """CSV is spreadsheet safe; JSON retains exact original text and values."""
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        safe = {}
        for key in fields:
            value = row.get(key)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return output.getvalue().encode('utf-8-sig')


def _iso(value):
    return value.isoformat() if value else None


def _number(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, 'f')
    return value


def _owned_rows(model, owner, include_synthetic):
    query = model.objects.filter(owner=owner).order_by('pk')
    if not include_synthetic:
        query = query.filter(synthetic=False)
    if query.count() > MAX_EXPORT_RECORDS:
        raise ValueError('Export exceeds the local record limit. Use an operator backup.')
    return list(query)


def build_export(owner, include_synthetic=False):
    _owner(owner)
    if type(include_synthetic) is not bool:
        raise ValueError('Choose whether to include synthetic data.')
    output = tempfile.TemporaryFile(mode='w+b')
    try:
        # IMMEDIATE SQLite transaction prevents concurrent photo metadata changes
        # while originals are read; files themselves are never modified in place.
        with transaction.atomic(), zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            data = {'format': 'private-health-export-v1', 'exported_at': timezone.now().isoformat(),
                    'includes_synthetic': include_synthetic,
                    'deletion_policy': 'Deleted measurements and summaries retain tombstones and audit history. Deleted photo bytes are absent. Deleted journal text and observation values are removed from the active export. Diet and clinical rows are included as currently stored.'}
            selected = []
            for model in [Measurement, SummaryRecord, ProgressPhoto]:
                query = model.objects.filter(owner=owner).order_by('pk')
                if not include_synthetic:
                    query = query.filter(synthetic=False)
                if query.count()>MAX_EXPORT_RECORDS:
                    raise ValueError('Export exceeds the local record limit. Use an operator backup.')
                selected.append(list(query))
            measurements, summaries, photos = selected
            data['measurements'] = [serialize(row) for row in measurements]
            data['summaries'] = [serialize_summary(row) for row in summaries]
            data['photos'] = [{**photo_metadata(row), 'original_sha256': row.original_sha256,
                'deleted_at': row.deleted_at.isoformat() if row.deleted_at else None,
                'original_file': 'photos/'+photo_names(row)[0] if not row.deleted_at else None} for row in photos]
            data['corrections'] = []
            for kind, rows in [('measurement', measurements), ('summary', summaries)]:
                for row in rows:
                    for event in row.corrections.select_related('request').order_by('created_at', 'pk'):
                        data['corrections'].append({'kind': kind, 'record_id': str(row.pk),
                            'request_id': str(event.request.request_id), 'before': event.before,
                            'after': event.after, 'created_at': event.created_at.isoformat()})
                        if len(data['corrections'])>MAX_EXPORT_RECORDS:
                            raise ValueError('Export exceeds the local audit limit. Use an operator backup.')
            targets = NutritionTargets.objects.filter(owner=owner).first()
            data['nutrition_targets'] = targets.values if targets else {}
            reviews = ReviewNote.objects.filter(owner=owner).order_by('pk')
            if not include_synthetic:
                reviews = reviews.filter(synthetic=False)
            if reviews.count()>MAX_EXPORT_RECORDS:
                raise ValueError('Export exceeds the local review limit.')
            data['reviews'] = [serialize_review(note) for note in reviews]
            data['diet_entries'] = [{
                'id': str(row.pk), 'local_date': row.local_date.isoformat(), 'meal': row.meal,
                'description': row.description, 'calories': _number(row.calories), 'protein_g': _number(row.protein_g),
                'fiber_g': _number(row.fiber_g), 'source_system': row.source_system,
                'source_record_id': row.source_record_id, 'synthetic': row.synthetic,
                'created_at': _iso(row.created_at), 'deleted_at': _iso(row.deleted_at),
            } for row in _owned_rows(DietEntry, owner, include_synthetic)]
            data['clinical_items'] = [{
                'id': str(row.pk), 'kind': row.kind, 'name': row.name, 'detail': row.detail,
                'recorded_on': row.recorded_on.isoformat(), 'current': row.current, 'synthetic': row.synthetic,
                'created_at': _iso(row.created_at),
            } for row in _owned_rows(ClinicalItem, owner, include_synthetic)]
            journal_entries = _owned_rows(JournalEntry, owner, include_synthetic)
            data['journal_entries'] = [{
                'id': str(row.pk), 'channel': row.channel, 'local_date': row.local_date.isoformat(),
                'occurred_at': _iso(row.occurred_at), 'time_precision': row.time_precision,
                'source_timezone': row.source_timezone, 'captured_at': _iso(row.captured_at),
                'body': None if row.deleted_at else row.body, 'processing_state': row.processing_state,
                'protocol_version': row.protocol_version, 'lineage_id': str(row.lineage_id),
                'synthetic': row.synthetic, 'version': row.version, 'deleted_at': _iso(row.deleted_at),
            } for row in journal_entries]
            observations = JournalObservation.objects.filter(entry__in=journal_entries).order_by('pk')
            if observations.count() > MAX_EXPORT_RECORDS:
                raise ValueError('Export exceeds the local journal limit. Use an operator backup.')
            data['journal_observations'] = [{
                'id': str(row.pk), 'entry_id': str(row.entry_id), 'domain_id': row.domain_id,
                'metric_key': row.metric_key, 'value_state': row.value_state, 'value_type': row.value_type,
                'value_json': None if row.deleted_at else row.value_json,
                'narrative': None if row.deleted_at else row.narrative, 'subject': row.subject,
                'local_date': row.local_date.isoformat(), 'source_timezone': row.source_timezone,
                'confirmation_status': row.confirmation_status, 'registry_version': row.registry_version,
                'lineage_id': str(row.lineage_id), 'synthetic': row.synthetic, 'version': row.version,
                'deleted_at': _iso(row.deleted_at),
            } for row in observations]
            corrections = JournalCorrection.objects.filter(entry__in=journal_entries).select_related('request').order_by('pk')
            if corrections.count() > MAX_EXPORT_RECORDS:
                raise ValueError('Export exceeds the local journal limit. Use an operator backup.')
            data['journal_memories'] = [{
                'id': str(row.pk), 'kind': row.kind, 'status': row.status, 'domain_id': row.domain_id,
                'practice_key': row.practice_key, 'text': None if row.deleted_at else row.text,
                'review_on': _iso(row.review_on), 'synthetic': row.synthetic, 'version': row.version,
                'deleted_at': _iso(row.deleted_at),
            } for row in _owned_rows(JournalMemory, owner, include_synthetic)]
            data['journal_questions'] = [{
                'id': str(row.pk), 'topic': row.topic, 'prompt': row.prompt, 'reason': row.reason,
                'status': row.status, 'domain_id': row.domain_id, 'asked_at': _iso(row.asked_at),
                'next_eligible': _iso(row.next_eligible), 'synthetic': row.synthetic,
            } for row in _owned_rows(JournalQuestion, owner, include_synthetic)]
            scores = JournalScore.objects.filter(owner=owner).order_by('pk')
            if not include_synthetic:
                scores = scores.filter(synthetic=False)
            data['journal_scores'] = [{
                'id': str(row.pk), 'kind': row.kind, 'local_date': row.local_date.isoformat(),
                'formula_version': row.formula_version, 'result': None if row.result is None else format(row.result, 'f'),
                'coverage': row.coverage, 'synthetic': row.synthetic,
            } for row in scores]
            pattern = SobrietyDay.objects.filter(owner=owner).order_by('local_date', 'pk')
            if not include_synthetic:
                pattern = pattern.filter(synthetic=False)
            data['sobriety_pattern'] = [{
                'local_date': row.local_date.isoformat(), 'formula_version': row.formula_version,
                'potential': row.potential, 'use_recorded': row.use_recorded, 'wear': row.wear,
                'drivers': row.drivers, 'run_started': None if row.run_started is None else row.run_started.isoformat(),
                'days_in_run': row.days_in_run, 'synthetic': row.synthetic,
            } for row in pattern]
            data['journal_corrections'] = [{
                'entry_id': str(row.entry_id), 'observation_id': None if row.observation_id is None else str(row.observation_id),
                'request_id': str(row.request.request_id), 'operation': row.operation,
                'before_version': row.before_version, 'after_version': row.after_version,
                'observation_before_version': row.observation_before_version,
                'observation_after_version': row.observation_after_version,
                'changed_fields': row.changed_fields, 'created_at': _iso(row.created_at),
            } for row in corrections]
            total = 0
            def write(name, content):
                nonlocal total
                total += len(content)
                if total>MAX_EXPORT_BYTES:
                    raise ValueError('Export exceeds 512 MiB. Use an operator backup.')
                archive.writestr(name, content)
            from .models import OuraRecord, OuraPage, OuraRevision
            records = OuraRecord.objects.select_related('connection').filter(connection__owner=owner)
            pages = OuraPage.objects.filter(connection__owner=owner)
            revisions = OuraRevision.objects.filter(record__connection__owner=owner)
            if not include_synthetic:
                records = records.filter(connection__synthetic=False)
                pages = pages.filter(connection__synthetic=False)
                revisions = revisions.filter(record__connection__synthetic=False)
            if any(q.count() > MAX_EXPORT_RECORDS for q in (records, pages, revisions)):
                raise ValueError('Oura export exceeds the local record limit. Use an operator backup.')
            for row in records.iterator():
                meta = {'id': str(row.pk), 'source_system': 'oura', 'collection': row.collection,
                    'account': str(row.connection_id), 'source_account_id': row.connection.source_account_id,
                    'source_record_id': row.source_record_id, 'identity_kind': row.identity_kind,
                    'version': row.version, 'synthetic': row.connection.synthetic, 'raw_json': row.raw_json}
                write('oura/records/'+str(row.pk)+'.json', json.dumps(meta, ensure_ascii=False).encode())
            for row in revisions.iterator():
                write('oura/revisions/'+str(row.pk)+'.json', json.dumps({
                    'record_id': str(row.record_id), 'version': row.version, 'page_id': row.page_id,
                    'page_index': row.page_index, 'received_at': row.received_at.isoformat(),
                    'raw_json': row.raw_json}, ensure_ascii=False).encode())
            for row in pages.iterator():
                write('oura/pages/'+str(row.pk)+'.json', row.raw_json.encode('utf-8'))
            write('history.json', json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
            write('measurements.csv', csv_bytes(data['measurements'], ['id', 'metric', 'value', 'unit', 'side', 'location',
                'local_date', 'observed_at', 'source_timezone', 'source_system', 'source_record_id', 'entry_method',
                'notes', 'synthetic', 'version', 'imported_at', 'deleted_at']))
            write('summaries.csv', csv_bytes(data['summaries'], ['id', 'kind', 'local_date', 'source_timezone',
                'source_system', 'source_record_id', 'entry_method', 'device', 'completeness', 'values', 'notes', 'synthetic', 'version', 'deleted_at']))
            write('diet.csv', csv_bytes(data['diet_entries'], ['id', 'local_date', 'meal', 'description', 'calories',
                'protein_g', 'fiber_g', 'source_system', 'source_record_id', 'synthetic', 'created_at', 'deleted_at']))
            write('clinical.csv', csv_bytes(data['clinical_items'], ['id', 'kind', 'name', 'detail', 'recorded_on',
                'current', 'synthetic', 'created_at']))
            write('journal.csv', csv_bytes(data['journal_entries'], ['id', 'channel', 'local_date', 'occurred_at',
                'time_precision', 'source_timezone', 'captured_at', 'body', 'processing_state', 'protocol_version',
                'synthetic', 'version', 'deleted_at']))
            write('README.txt', b'Private health export v1\nContains sensitive data. Store privately.\nJSON preserves exact values, nulls, provenance, corrections and tombstones. CSV text beginning with spreadsheet formula characters has a protective apostrophe. Summary values are JSON objects with schema units documented in README.md.\nDiet entries and clinical items are included. Journal JSON keeps the entry, observations, and correction field names. Deleted journal text is omitted.\nOriginal photo bytes may contain original metadata including location; normalized display images remove it. Deleted photo bytes are omitted. This export is not encrypted and is not a database backup.\n')
            storage = photo_storage()
            for photo in photos:
                if photo.deleted_at:
                    continue
                for index, name in enumerate(photo_names(photo)):
                    with storage.open(name, 'rb') as handle:
                        content = handle.read(MAX_EXPORT_BYTES-total+1)
                    if index == 0 and hashlib.sha256(content).hexdigest()!=photo.original_sha256:
                        raise ValueError('A photo could not be verified. No partial export was returned.')
                    write('photos/'+name, content)
        output.seek(0)
        return output
    except Exception:
        output.close()
        raise


@owner_only
@require_http_methods(['GET', 'POST'])
def download(request):
    if request.method == 'GET':
        return render(request, 'tracking/export.html')
    if request.POST.get('confirm_export') != 'yes':
        return HttpResponse('Confirm the private export first.', status=400)
    try:
        output = build_export(request.user, False)
    except (ValueError, OSError):
        return HttpResponse('Export could not be completed. Check private photo storage and the 512 MiB export limit. No partial export was returned.', status=409)
    return private_file_response(request, output, as_attachment=True, filename='private-health-'+timezone.localdate().isoformat()+'.zip')
