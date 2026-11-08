import uuid
from datetime import timedelta
from functools import wraps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from .forms import MeasurementForm, MeasurementImportForm
from .models import Measurement, ProgressPhoto
from . import services, imports
from .csv_measurements import HEADER
from .uploads import MeasurementCSVUploadLimit


IMPORT_PREVIEW_TTL = 15 * 60
IMPORT_SESSION_KEY = 'measurement_import_preview'


@require_http_methods(['GET'])
def manifest(request):
    # Public installation metadata only. No records, tokens or identity here.
    return JsonResponse({'id':'/', 'name':'CX83 Fit', 'short_name':'CX83 Fit',
        'start_url':'/', 'scope':'/', 'display':'standalone',
        'background_color':'#080E22', 'theme_color':'#080E22', 'lang':'en-US'},
        content_type='application/manifest+json')



def owner_only(view):
    @login_required
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_active or request.user.get_username() != settings.OWNER_USERNAME:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return guarded


@owner_only
@require_http_methods(['GET'])
def overview(request):
    from datetime import date
    from tracking.today import day_metrics
    today = timezone.localdate()
    is_test = request.GET.get('synthetic') == '1'
    raw = request.GET.get('day')
    if raw:
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            raise Http404
        if day > today or day < today - timedelta(days=365):
            raise Http404
    else:
        day = today
    return render(request, 'tracking/overview.html', {
        'today': today,
        'day': day,
        'prev_day': day - timedelta(days=1),
        'next_day': day + timedelta(days=1) if day < today else None,
        'metrics': day_metrics(request.user, day, include_synthetic=is_test),
        'synthetic': is_test,
    })


@owner_only
@require_http_methods(['GET'])
def progress(request):
    today = timezone.localdate()
    is_test = request.GET.get('synthetic') == '1'
    try:
        offset = int(request.GET.get('offset', '0'))
        result = services.list_measurements(
            request.user, str(today - timedelta(days=365)), str(today),
            include_synthetic=is_test, limit=50, offset=offset)
    except (ValueError, TypeError):
        raise Http404
    photos = ProgressPhoto.objects.filter(owner=request.user, deleted_at__isnull=True)
    if not is_test:
        photos = photos.filter(synthetic=False)
    measurements = Measurement.objects.filter(owner=request.user, deleted_at__isnull=True, local_date__lte=today)
    if not is_test:
        measurements = measurements.filter(synthetic=False)
    latest_weight = measurements.filter(metric='weight').order_by('-local_date', '-created_at').first()
    return render(request, 'tracking/progress.html', {
        'result': result, 'synthetic': is_test, 'next_offset': result['next_offset'],
        'latest_weight': latest_weight, 'recent_photos': photos[:6],
    })


@owner_only
@require_http_methods(['GET'])
def more(request):
    return render(request, 'tracking/more.html')


@owner_only
@require_http_methods(['GET', 'POST'])
def measurement(request, record_id=None):
    existing = None
    if record_id:
        existing = Measurement.objects.filter(pk=record_id, owner=request.user, deleted_at__isnull=True).first()
        if not existing:
            raise Http404
        if existing.source_system not in ('manual', 'mcp'):
            raise PermissionDenied
    initial = {'request_id':uuid.uuid4()}
    if existing:
        initial.update({k:getattr(existing,k) for k in ['metric','value','unit','local_date','side','location','notes','synthetic']})
        initial['expected_version'] = existing.version
    form = MeasurementForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        data = dict(form.cleaned_data)
        request_id = str(data.pop('request_id'))
        expected_version = data.pop('expected_version')
        data['value'] = str(data['value'])
        data['local_date'] = data['local_date'].isoformat()
        data['source_timezone'] = existing.source_timezone if existing else 'America/Chicago'
        if existing and existing.observed_at:
            data['observed_at'] = existing.observed_at.isoformat()
        try:
            services.put_measurement(request.user, data, request_id, record_id=str(record_id) if record_id else None, expected_version=expected_version)
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            return redirect('/?synthetic=1' if data['synthetic'] else '/')
    return render(request, 'tracking/measurement.html', {'form':form, 'editing':existing is not None})


@owner_only
@require_http_methods(['GET'])
def measurement_history(request, record_id):
    record = Measurement.objects.filter(pk=record_id, owner=request.user,
                                        deleted_at__isnull=True).first()
    if record is None:
        raise Http404
    paginator = Paginator(record.corrections.order_by('-created_at', '-id'), 25)
    try:
        page = paginator.page(request.GET.get('page', '1'))
    except (EmptyPage, PageNotAnInteger):
        raise Http404
    fields = [('metric', 'Measurement'), ('value', 'Value'), ('unit', 'Unit'),
              ('local_date', 'Measurement date'), ('observed_at', 'Time observed'),
              ('source_timezone', 'Source timezone'), ('side', 'Side'),
              ('location', 'Location'), ('notes', 'Notes')]
    entries = []
    for change in page:
        before = change.before or {}
        entries.append({'created_at': change.created_at, 'operation': change.operation,
                        'actor_source': change.actor_source, 'version': change.after['version'],
                        'changes': [{'label': label, 'before': before.get(key),
                                     'after': change.after.get(key)} for key, label in fields
                                    if before.get(key) != change.after.get(key)]})
    return render(request, 'tracking/history.html', {'record': services.serialize(record),
        'entries': entries, 'page': page, 'can_correct': record.source_system in ('manual', 'mcp'),
        'delete_request_id': uuid.uuid4()})


@owner_only
@require_http_methods(['POST'])
def measurement_delete(request, record_id):
    if request.POST.get('confirm_delete') != 'yes':
        return HttpResponseBadRequest('Confirm deletion first.')
    try:
        version = int(request.POST.get('expected_version', ''))
        services.delete_measurement(request.user, str(record_id), version, request.POST.get('request_id'))
    except services.RecordNotFound:
        raise Http404
    except ValueError as exc:
        # Fixed service messages only; no submitted measurement or note is echoed.
        return HttpResponse('Deletion could not be completed. Reload the record and try again.', status=409)
    return redirect('overview')


@csrf_exempt
@owner_only
@require_http_methods(['GET', 'POST'])
def measurement_import(request):
    # Django requires installing handlers before CSRF middleware parses POST.
    # The inner view immediately restores CSRF protection for every upload.
    request.upload_handlers.insert(0, MeasurementCSVUploadLimit(request))
    return _measurement_import(request)


@csrf_protect
def _measurement_import(request):
    form = MeasurementImportForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None)
    if request.method == 'POST':
        valid = form.is_valid()
        if getattr(request, 'import_upload_error', None):
            form.add_error('csv_file', request.import_upload_error)
        elif valid:
            preview_id = str(uuid.uuid4())
            request.session[IMPORT_SESSION_KEY] = {
                'id': preview_id, 'owner_id': str(request.user.pk),
                'expires_at': timezone.now().timestamp() + IMPORT_PREVIEW_TTL,
                'namespace': form.cleaned_data['namespace'],
                'rows': form.cleaned_data['csv_file'],
            }
            return redirect('measurement_import_review', preview_id=preview_id)
    return render(request, 'tracking/import_upload.html', {'form': form, 'csv_header': ','.join(HEADER)})


def _import_preview(request, preview_id):
    preview = request.session.get(IMPORT_SESSION_KEY)
    if not preview or preview.get('owner_id') != str(request.user.pk):
        raise Http404('This import review is unavailable. Upload the file again.')
    if preview.get('expires_at', 0) <= timezone.now().timestamp():
        request.session.pop(IMPORT_SESSION_KEY, None)
        raise Http404('This import review has expired. Upload the file again.')
    if preview.get('id') != str(preview_id):
        raise Http404('This import review is unavailable. Upload the file again.')
    return preview


@owner_only
@require_http_methods(['GET', 'POST'])
def measurement_import_review(request, preview_id):
    preview = _import_preview(request, preview_id)
    error, status = '', 200
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'cancel':
            request.session.pop(IMPORT_SESSION_KEY, None)
            return redirect('measurement_import')
        if action != 'confirm':
            return HttpResponseBadRequest('Choose confirm or cancel.')
        if 'receipt' not in preview:
            try:
                receipt = imports.confirm_rows(request.user, preview['namespace'],
                                               preview['rows'], preview['id'])
            except ValueError as exc:
                error, status = str(exc), 409
            else:
                # Keep only the receipt for safe retries; discard reviewed health fields.
                preview = {key: value for key, value in preview.items() if key != 'rows'}
                preview['receipt'] = receipt
                request.session[IMPORT_SESSION_KEY] = preview
        if not error:
            return redirect('measurement_import_review', preview_id=preview_id)
    rows = imports.preview_rows(request.user, preview['namespace'], preview['rows']) if 'rows' in preview else []
    return render(request, 'tracking/import_review.html', {
        'preview': preview, 'rows': rows, 'receipt': preview.get('receipt'),
        'has_conflicts': any(row['status'] == 'conflict' for row in rows),
        'error': error,
    }, status=status)
