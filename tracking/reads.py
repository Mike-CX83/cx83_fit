"""Bounded owner reads shared by MCP and exports; source text is untrusted data."""
from django.db.models import Max, Count, Q

from .domain import bounded_range, InvalidMeasurement, request_uuid
from .models import Measurement, SummaryRecord, ProgressPhoto, NutritionTargets, ReviewNote
from .reviews import serialize_review
from .photos import photo_metadata, photo_names, photo_storage
from .services import _owner, list_measurements
from .summaries import SCHEMAS, serialize_summary
from .summary_evidence import evidence_counts, evidence_envelope


def read_tracking(owner, kind, start, end, include_synthetic=False, limit=100, offset=0):
    _owner(owner)
    first, last = bounded_range(start, end)
    if type(include_synthetic) is not bool or type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
        raise InvalidMeasurement('Use an explicit synthetic flag, limit 1 to 100 and offset 0 to 100000.')
    if kind == 'measurements':
        return list_measurements(owner, start, end, include_synthetic, limit, offset)
    if kind not in {*SCHEMAS, 'photos', 'reviews'}:
        raise InvalidMeasurement('Choose a supported record kind.')
    photos = kind == 'photos'
    model, day = (ProgressPhoto, 'capture_date') if photos else (ReviewNote if kind=='reviews' else SummaryRecord, 'local_date')
    query = model.objects.filter(owner=owner, deleted_at__isnull=True, **{day+'__range': (first, last)})
    if kind in SCHEMAS:
        query = query.filter(kind=kind)
    if not include_synthetic:
        query = query.filter(synthetic=False)
    count = query.count()
    serializer = photo_metadata if photos else (serialize_review if kind=='reviews' else serialize_summary)
    page = list(query.order_by(day, 'pk')[offset:offset+limit])
    items = [serializer(row) for row in page]
    if kind in SCHEMAS:
        for item, row in zip(items, page):
            item['evidence'] = evidence_envelope(row)
    coverage = {'start': first.isoformat(), 'end': last.isoformat(), 'requested_days': (last-first).days+1,
                'days_with_observations': query.order_by().values(day).distinct().count()}
    if kind in SCHEMAS:
        coverage.update(evidence_counts(query))
        coverage['history_notice'] = 'Historical rows and latest dates are not current evidence. include_synthetic filters the stored flag only.'
    if kind in SCHEMAS:
        groups = list(query.values('source_system', 'device', 'synthetic', 'values__hrv_method').annotate(
            observations=Count('pk'), observed_days=Count('local_date', distinct=True),
            complete_days=Count('local_date', distinct=True, filter=Q(completeness='complete')))
            .order_by('source_system', 'device', 'synthetic', 'values__hrv_method')[:101])
        coverage['by_source'] = groups[:100]
        coverage['sources_truncated'] = len(groups)>100
    return {'items': items, 'count': count, 'returned': len(items),
            'next_offset': offset+limit if offset+limit<count else None,
            'coverage': coverage, 'includes_synthetic': include_synthetic}


def read_overview(owner, start, end, include_synthetic=False):
    """Per-source freshness. Stored records are not proof of a live connection."""
    _owner(owner)
    first, last = bounded_range(start, end)
    if type(include_synthetic) is not bool:
        raise InvalidMeasurement('include_synthetic must be true or false.')
    sections = {}
    for kind in ['measurements', *SCHEMAS, 'photos', 'reviews']:
        result = read_tracking(owner, kind, start, end, include_synthetic, 1, 0)
        sections[kind] = {key: result[key] for key in ('count', 'coverage')}
    sources = []
    sources_truncated = False
    for model, category, date_field, time_field in [(Measurement, 'measurements', 'local_date', 'imported_at'),
            (SummaryRecord, 'summaries', 'local_date', 'created_at')]:
        query = model.objects.filter(owner=owner, deleted_at__isnull=True)
        if not include_synthetic:
            query = query.filter(synthetic=False)
        fields = ['source_system'] + (['kind', 'device'] if category == 'summaries' else [])
        groups = list(query.values(*fields).annotate(latest_date=Max(date_field), last_recorded=Max(time_field)).order_by(*fields)[:101])
        sources_truncated = sources_truncated or len(groups)>100
        for row in groups[:100]:
            sources.append({**row, 'category': category, 'latest_date': row['latest_date'].isoformat(),
                'last_recorded': row['last_recorded'].isoformat(), 'last_successful_sync': None,
                'connection_state': 'Implemented with synthetic tests', 'live_sync_connected': False})
    from .oura.sync import status as oura_status
    external = {name: {'connected': False, 'last_successful_sync': None}
                for name in ('MyFitnessPal', 'Oura', 'Apple Health', 'Clinical provider')}
    external['Oura'] = oura_status(owner, include_synthetic)
    targets = NutritionTargets.objects.filter(owner=owner).first()
    summary_window = SummaryRecord.objects.filter(owner=owner, deleted_at__isnull=True, local_date__range=(first, last))
    if not include_synthetic:
        summary_window = summary_window.filter(synthetic=False)
    evidence = evidence_counts(summary_window)
    evidence.update({
        'includes_synthetic': include_synthetic,
        'notice': 'Historical latest dates are stored history, not current evidence. include_synthetic filters the stored flag and does not prove personal or test attribution.',
    })
    return {'start': first.isoformat(), 'end': last.isoformat(), 'sections': sections, 'sources': sources, 'sources_truncated': sources_truncated,
            'evidence': evidence,
            'targets': targets.values if targets else {}, 'includes_synthetic': include_synthetic,
            'external_connections': external,
            'notice': 'Manual and reviewed CSV records do not establish live source connectivity. Missing days are unknown.'}


def read_photo(owner, photo_id, include_synthetic=False):
    _owner(owner)
    photo_id = request_uuid(photo_id)
    if type(include_synthetic) is not bool:
        raise InvalidMeasurement('include_synthetic must be true or false.')
    query = ProgressPhoto.objects.filter(owner=owner, pk=photo_id, deleted_at__isnull=True)
    if not include_synthetic:
        query = query.filter(synthetic=False)
    photo = query.first()
    if photo is None:
        raise InvalidMeasurement('Photo not found.')
    try:
        with photo_storage().open(photo_names(photo)[1], 'rb') as handle:
            content = handle.read(8*1024*1024+1)
    except OSError:
        raise InvalidMeasurement('Photo file is unavailable.') from None
    if len(content)>8*1024*1024:
        raise InvalidMeasurement('Photo is too large for this response.')
    return photo_metadata(photo), content
