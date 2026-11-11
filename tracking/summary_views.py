import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.core.paginator import Paginator, InvalidPage
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseBadRequest, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from .forms import SummaryForm, NutritionTargetForm, SummaryImportForm
from .models import SummaryRecord, NutritionTargets
from .summaries import SCHEMAS, display_values, put_summary, delete_summary
from .summary_evidence import evidence_counts, evidence_envelope, partition_records, unresolved_history
from .views import owner_only
from .summary_imports import HEADER as SUMMARY_HEADER, preview_summaries, confirm_summaries
from .uploads import SummaryCSVUploadLimit
from .domain import net_carbohydrates


def _kind(kind):
    if kind not in SCHEMAS:
        raise Http404


def _records(request, kind):
    query = SummaryRecord.objects.filter(owner=request.user, kind=kind, deleted_at__isnull=True)
    return query if request.GET.get('synthetic') == '1' else query.filter(synthetic=False)


def _single_day_rows(rows):
    """A day with more than one row in this series is not daily evidence."""
    by_day = defaultdict(list)
    for row in rows:
        by_day[row.local_date].append(row)
    clean = [items[0] for items in by_day.values() if len(items) == 1]
    ambiguous = sum(len(items) != 1 for items in by_day.values())
    return clean, ambiguous


def weekly_averages(records, kind):
    """Eligible complete values only. Sources, methods, and stored classes stay separate."""
    eligible, _evidence = partition_records(records)
    groups = defaultdict(list)
    for record in eligible:
        values = record.values if isinstance(record.values, dict) else {}
        key = (record.source_system, record.device, record.entry_method,
               values.get('hrv_method', ''), record.synthetic is True)
        groups[key].append(record)
    result = []
    for (source, device, entry_method, method, synthetic), rows in groups.items():
        averages = []
        clean_rows, ambiguous_days = _single_day_rows(rows)
        for key, label, unit in SCHEMAS[kind]:
            values = [Decimal(row.values[key]) for row in clean_rows
                      if row.completeness == 'complete' and row.values.get(key) is not None]
            averages.append({'label': label, 'unit': unit, 'count': len(values),
                'value': (sum(values) / len(values)).quantize(Decimal('0.01')) if values else None})
        if kind == 'nutrition':
            nets = [net_carbohydrates(row.values.get('total_carbohydrates'), row.values.get('fiber'))
                    for row in clean_rows if row.completeness == 'complete']
            values = [Decimal(net['value']) for net in nets if net['status'] == 'calculated']
            averages.append({'label': 'Net carbohydrates', 'unit': 'g', 'count': len(values),
                'value': (sum(values)/len(values)).quantize(Decimal('0.01')) if values else None})
        result.append({'source': source, 'device': device, 'entry_method': entry_method,
                       'method': method, 'synthetic': synthetic,
                       'class_label': 'test' if synthetic else 'personal',
                       'observed': len(rows), 'observed_days': len({row.local_date for row in rows}),
                       'complete': sum(row.completeness == 'complete' for row in rows),
                       'complete_days': sum(row.completeness == 'complete' for row in clean_rows),
                       'ambiguous_days': ambiguous_days, 'averages': averages})
    return result


@owner_only
@require_http_methods(['GET'])
def listing(request, kind):
    _kind(kind)
    records = _records(request, kind)
    try:
        page = Paginator(records, 30).page(request.GET.get('page', '1'))
    except InvalidPage:
        raise Http404
    today = timezone.localdate()
    start = today - timedelta(days=6)
    week_records = records.filter(local_date__range=(start, today))
    weekly = weekly_averages(week_records, kind) if kind != 'health' else []
    week_evidence = evidence_counts(week_records) if kind != 'health' else None
    target = NutritionTargets.objects.filter(owner=request.user).first() if kind == 'nutrition' else None
    target_values = [{'label': label, 'unit': unit, 'value': target.values.get(key) if target else None}
                     for key, label, unit in SCHEMAS['nutrition']] if kind == 'nutrition' else []
    return render(request, 'tracking/summaries.html', {
        'kind': kind, 'title': 'Lab results' if kind == 'health' else dict(SummaryRecord.KINDS)[kind], 'page': page,
        'entries': [{'record': record, 'fields': display_values(record), 'evidence': evidence_envelope(record)} for record in page],
        'synthetic': request.GET.get('synthetic') == '1', 'weekly': weekly, 'week_evidence': week_evidence,
        'week_start': start, 'week_end': today, 'target_values': target_values,
        'unresolved_history_count': unresolved_history(request.user).count(),
    })


@owner_only
@require_http_methods(['GET', 'POST'])
def entry(request, kind, record_id=None):
    _kind(kind)
    record = None
    initial = {'request_id': uuid.uuid4(), 'completeness': 'unknown'}
    if record_id:
        record = get_object_or_404(SummaryRecord, pk=record_id, owner=request.user,
                                  kind=kind, deleted_at__isnull=True, entry_method='manually_reported')
        initial.update({key: getattr(record, key) for key in ['local_date', 'source_system', 'source_timezone', 'completeness', 'device', 'notes', 'synthetic']})
        initial.update({'value_' + key: value for key, value in record.values.items()})
        initial['expected_version'] = record.version
    form = SummaryForm(kind, request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            result = put_summary(request.user, form.payload(), str(form.cleaned_data['request_id']),
                                 str(record.id) if record else None, form.cleaned_data['expected_version'])
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            return redirect('summary_detail', kind=kind, record_id=result['id'])
    return render(request, 'tracking/summary_entry.html', {'form': form, 'kind': kind,
        'title': dict(SummaryRecord.KINDS)[kind], 'editing': record is not None})


@owner_only
@require_http_methods(['GET'])
def detail(request, kind, record_id):
    _kind(kind)
    record = get_object_or_404(SummaryRecord, pk=record_id, owner=request.user, kind=kind, deleted_at__isnull=True)
    try:
        history = Paginator(record.corrections.order_by('-created_at', '-id'), 20).page(request.GET.get('page', '1'))
    except InvalidPage:
        raise Http404
    return render(request, 'tracking/summary_detail.html', {'record': record, 'fields': display_values(record),
        'history': history, 'kind': kind, 'title': dict(SummaryRecord.KINDS)[kind], 'delete_request_id': uuid.uuid4(),
        'evidence': evidence_envelope(record), 'unresolved_history_count': unresolved_history(request.user).count()})


@owner_only
@require_http_methods(['GET'])
def provenance(request):
    """Owner inventory of unresolved and derived history, including both stored flags and tombstones."""
    try:
        page = Paginator(unresolved_history(request.user), 30).page(request.GET.get('page', '1'))
    except InvalidPage:
        raise Http404
    return render(request, 'tracking/summary_provenance.html', {
        'page': page,
        'entries': [{'record': record, 'fields': display_values(record), 'evidence': evidence_envelope(record)} for record in page],
        'unresolved_history_count': unresolved_history(request.user).count(),
    })


@owner_only
@require_http_methods(['GET'])
def provenance_detail(request, record_id):
    """Read-only inspection of one retained unresolved or derived original, including tombstones."""
    record = unresolved_history(request.user).filter(pk=record_id).first()
    if record is None:
        raise Http404
    try:
        history = Paginator(record.corrections.order_by('-created_at', '-id'), 20).page(request.GET.get('page', '1'))
    except InvalidPage:
        raise Http404
    return render(request, 'tracking/summary_provenance_detail.html', {
        'record': record, 'fields': display_values(record), 'history': history,
        'evidence': evidence_envelope(record),
    })


@owner_only
@require_http_methods(['POST'])
def remove(request, kind, record_id):
    _kind(kind)
    if request.POST.get('confirm_delete') != 'yes':
        return HttpResponseBadRequest('Confirm deletion first.')
    get_object_or_404(SummaryRecord, pk=record_id, owner=request.user, kind=kind)
    try:
        version = int(request.POST.get('expected_version', ''))
        delete_summary(request.user, str(record_id), version, request.POST.get('request_id'))
    except ValueError:
        return HttpResponse('Deletion could not be completed. Reload the record and try again.', status=409)
    return redirect('summary_list', kind=kind)


@owner_only
@require_http_methods(['GET', 'POST'])
def targets(request):
    current = NutritionTargets.objects.filter(owner=request.user).first()
    form = NutritionTargetForm(request.POST if request.method == 'POST' else None,
        initial={**(current.values if current else {}), 'expected_version': current.version if current else 0})
    if request.method == 'POST' and form.is_valid():
        data = dict(form.cleaned_data)
        expected = data.pop('expected_version')
        values = {key: str(value) if value is not None else None for key, value in data.items()}
        try:
            with transaction.atomic():
                if expected == 0:
                    NutritionTargets.objects.create(owner=request.user, values=values)
                else:
                    changed = NutritionTargets.objects.filter(owner=request.user, version=expected).update(
                        values=values, version=expected+1, updated_at=timezone.now())
                    if not changed:
                        raise IntegrityError
        except IntegrityError:
            form.add_error(None, 'Targets changed in another session. Reload before saving.')
        else:
            return redirect('summary_list', kind='nutrition')
    return render(request, 'tracking/targets.html', {'form': form})


SUMMARY_PREVIEW_KEY = 'summary_import_preview'


@csrf_exempt
@owner_only
@require_http_methods(['GET', 'POST'])
def import_upload(request):
    request.upload_handlers.insert(0, SummaryCSVUploadLimit(request))
    return _import_upload(request)


@csrf_protect
def _import_upload(request):
    form = SummaryImportForm(request.POST if request.method == 'POST' else None,
                             request.FILES if request.method == 'POST' else None)
    if request.method == 'POST':
        valid = form.is_valid()
        if getattr(request, 'import_upload_error', None):
            form.add_error('csv_file', request.import_upload_error)
        elif valid:
            preview_id = str(uuid.uuid4())
            request.session[SUMMARY_PREVIEW_KEY] = {'id': preview_id, 'owner_id': str(request.user.pk),
                'expires_at': timezone.now().timestamp()+900, 'namespace': form.cleaned_data['namespace'],
                'rows': form.cleaned_data['csv_file']}
            return redirect('summary_import_review', preview_id=preview_id)
    return render(request, 'tracking/summary_import.html', {'form': form, 'header': ','.join(SUMMARY_HEADER)})


@owner_only
@require_http_methods(['GET', 'POST'])
def import_review(request, preview_id):
    preview = request.session.get(SUMMARY_PREVIEW_KEY)
    if not preview or preview.get('owner_id') != str(request.user.pk):
        raise Http404
    if preview.get('expires_at', 0) <= timezone.now().timestamp():
        request.session.pop(SUMMARY_PREVIEW_KEY, None)
        raise Http404
    if preview['id'] != str(preview_id):
        raise Http404
    error, status = '', 200
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'cancel':
            request.session.pop(SUMMARY_PREVIEW_KEY, None)
            return redirect('summary_import')
        if action != 'confirm':
            return HttpResponseBadRequest('Choose confirm or cancel.')
        if 'receipt' not in preview:
            try:
                receipt = confirm_summaries(request.user, preview['namespace'], preview['rows'], preview['id'])
            except ValueError as exc:
                error, status = str(exc), 409
            else:
                preview = {key: value for key, value in preview.items() if key != 'rows'}
                preview['receipt'] = receipt
                request.session[SUMMARY_PREVIEW_KEY] = preview
        if not error:
            return redirect('summary_import_review', preview_id=preview_id)
    rows = preview_summaries(request.user, preview['namespace'], preview['rows']) if 'rows' in preview else []
    for row in rows:
        row['fields'] = display_values(SimpleNamespace(**row['summary']))
    return render(request, 'tracking/summary_import_review.html', {'preview': preview, 'rows': rows,
        'receipt': preview.get('receipt'), 'error': error,
        'has_conflicts': any(row['status'] == 'conflict' for row in rows)}, status=status)
