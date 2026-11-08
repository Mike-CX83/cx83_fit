"""Owner journal pages. Writes go through the journal service, never raw model edits."""
import json
from uuid import uuid4
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .domain import InvalidMeasurement
from .journal import delete_journal, governing_line, preview_journal_extraction, save_journal
from .journal_registry import DOMAINS, METRICS, STATES
from .models import JournalEntry
from .services import Conflict, RecordNotFound
from .views import owner_only


def _flag(request):
    return request.POST.get('synthetic') == 'on' or request.GET.get('synthetic') == '1'


def _boolean(value):
    if value in (None, ''):
        return None
    if value == 'true':
        return True
    if value == 'false':
        return False
    raise InvalidMeasurement('Choose yes, no, or leave that choice blank.')


def _observation(post):
    if not post.get('domain_id') and not post.get('metric_key') and not post.get('value_state'):
        return None
    try:
        domain_id = int(post.get('domain_id', ''))
    except (TypeError, ValueError):
        raise InvalidMeasurement('Choose a journal domain.') from None
    return {'domain_id': domain_id, 'metric_key': post.get('metric_key', ''),
            'value_state': post.get('value_state', ''), 'narrative': post.get('narrative', ''),
            'boolean': _boolean(post.get('boolean')), 'subject': 'self'}


def _proposals(post):
    """One dashboard proposal. A check writes nothing. Saving uses the explicit fields."""
    if not post.get('domain_id') and not post.get('metric_key') and not post.get('value_state') and not post.get('support_span'):
        return []
    proposal = _observation(post) or {}
    proposal['support_span'] = post.get('support_span', '')
    proposal['temporal_scope'] = post.get('temporal_scope') or 'unspecified'
    proposal['subject'] = 'self'
    return [proposal]


def _version(value, label):
    if value in (None, ''):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise InvalidMeasurement(f'A current {label} version is required.') from None
    if number < 1:
        raise InvalidMeasurement(f'A current {label} version is required.')
    return number


def _context(request, **extra):
    return {'domains': DOMAINS.items(), 'metrics': METRICS.items(), 'states': sorted(STATES | {'intention'}),
            'governing_line': governing_line(), 'synthetic': _flag(request),
            'request_id': request.POST.get('request_id') or str(uuid4()), **extra}


def _location(entry_id, synthetic):
    url = reverse('journal_detail', args=[entry_id])
    return url + ('?synthetic=1' if synthetic else '')


@owner_only
@require_http_methods(['GET', 'POST'])
def page(request):
    error, status = '', 200
    if request.method == 'POST':
        synthetic = request.POST.get('synthetic') == 'on'
        if 'check_proposal' in request.POST:
            try:
                preview = preview_journal_extraction(request.POST.get('body', ''), _proposals(request.POST))
            except InvalidMeasurement as exc:
                error, status, preview = str(exc), 400, None
            else:
                error, status = '', 200
            query = JournalEntry.objects.filter(owner=request.user, deleted_at__isnull=True).prefetch_related('observations')
            if not synthetic:
                query = query.filter(synthetic=False)
            return render(request, 'tracking/journal.html', _context(
                request, entries=query[:50], error=error, posted=request.POST, preview=preview), status=status)
        try:
            result = save_journal(
                request.user, request.POST.get('body', ''), request.POST.get('local_date', ''),
                request.POST.get('request_id') or str(uuid4()), _observation(request.POST),
                source_timezone=request.POST.get('source_timezone') or 'America/Chicago',
                occurred_at=request.POST.get('occurred_at') or None, synthetic=synthetic)
        except InvalidMeasurement as exc:
            error, status = str(exc), 400
        except Conflict as exc:
            error, status = str(exc), 409
        except RecordNotFound as exc:
            raise Http404(str(exc)) from exc
        else:
            return redirect(_location(result['id'], synthetic))
    query = JournalEntry.objects.filter(owner=request.user, deleted_at__isnull=True).prefetch_related('observations')
    if not _flag(request):
        query = query.filter(synthetic=False)
    return render(request, 'tracking/journal.html', _context(
        request, entries=query[:50], error=error, posted=request.POST), status=status)


@owner_only
@require_http_methods(['POST'])
def preview(request):
    """Validate a client's proposed observations. This endpoint writes nothing."""
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError):
        return JsonResponse({'persisted': False, 'error': 'Send a JSON object.'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'persisted': False, 'error': 'Send a JSON object.'}, status=400)
    try:
        result = preview_journal_extraction(payload.get('body', ''), payload.get('proposals', []))
    except InvalidMeasurement as exc:
        return JsonResponse({'persisted': False, 'error': str(exc)}, status=400)
    return JsonResponse(result)


@owner_only
@require_http_methods(['GET', 'POST'])
def detail(request, entry_id):
    entry = get_object_or_404(JournalEntry, owner=request.user, id=entry_id, deleted_at__isnull=True)
    if entry.synthetic and not _flag(request):
        raise Http404
    observation = entry.observations.filter(deleted_at__isnull=True).first()
    error, status = '', 200
    if request.method == 'POST':
        synthetic = request.POST.get('synthetic') == 'on'
        try:
            save_journal(
                request.user, request.POST.get('body', ''), request.POST.get('local_date', ''),
                request.POST.get('request_id') or str(uuid4()), _observation(request.POST),
                source_timezone=request.POST.get('source_timezone') or 'America/Chicago',
                occurred_at=request.POST.get('occurred_at') or None, synthetic=synthetic,
                record_id=entry.id, expected_version=_version(request.POST.get('expected_version'), 'entry'),
                expected_observation_version=_version(request.POST.get('expected_observation_version'), 'observation'))
        except InvalidMeasurement as exc:
            error, status = str(exc), 400
        except Conflict as exc:
            error, status = str(exc), 409
        except RecordNotFound as exc:
            raise Http404(str(exc)) from exc
        else:
            return redirect(_location(entry.id, synthetic or entry.synthetic))
        entry.refresh_from_db()
        observation = entry.observations.filter(deleted_at__isnull=True).first()
    return render(request, 'tracking/journal_detail.html', _context(
        request, entry=entry, observation=observation, error=error), status=status)


@owner_only
@require_http_methods(['POST'])
def remove(request, entry_id):
    if request.POST.get('confirm_delete') != 'yes':
        return HttpResponseBadRequest('Confirm deletion first.')
    entry = get_object_or_404(JournalEntry, owner=request.user, id=entry_id, deleted_at__isnull=True)
    observation = entry.observations.filter(deleted_at__isnull=True).first()
    try:
        delete_journal(request.user, entry.id, entry.version, request.POST.get('request_id') or str(uuid4()),
                       None if observation is None else observation.version)
    except (InvalidMeasurement, Conflict, RecordNotFound):
        return HttpResponseBadRequest('The journal entry changed. Review it before deleting.')
    return redirect('/journal/?synthetic=1' if entry.synthetic else 'journal')
