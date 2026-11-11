"""Observation charts, without source merging, interpolation or zero-filled gaps."""
from collections import defaultdict
from datetime import timedelta

from django import forms
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .domain import bounded_range, METRICS
from .models import Measurement, SummaryRecord
from .summaries import SCHEMAS
from .summary_evidence import HISTORY_HREF, partition_records, summary_series_identity, summary_series_token
from .views import owner_only


OPTIONS = {**{'measurements:'+key: (key.title(), None) for key in METRICS},
    **{kind+':'+key: (kind.title()+' · '+label, unit) for kind, fields in SCHEMAS.items() for key, label, unit in fields}}


class TrendForm(forms.Form):
    metric = forms.ChoiceField(choices=[(key, value[0]) for key, value in OPTIONS.items()])
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    synthetic = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end'):
            try:
                bounded_range(str(data['start']), str(data['end']))
            except ValueError as exc:
                raise forms.ValidationError(str(exc))
        return data


def observations(owner, metric, start, end, synthetic=False):
    bounded_range(str(start), str(end))
    kind, key = metric.split(':')
    if metric not in OPTIONS:
        raise ValueError('Unsupported metric.')
    query = (Measurement.objects.filter(metric=key) if kind=='measurements' else SummaryRecord.objects.filter(kind=kind))
    query = query.filter(owner=owner, deleted_at__isnull=True, local_date__range=(start, end))
    if not synthetic:
        query = query.filter(synthetic=False)
    total = query.count()
    ordered = query.order_by('local_date', 'pk')
    if kind == 'measurements':
        rows, groups = [], defaultdict(list)
        for record in ordered[:2000]:
            value = record.value
            if value is None:
                continue
            unit = record.unit
            attributes = [record.source_system, unit, record.side, record.location, 'test' if record.synthetic else '']
            group = tuple(attributes)
            groups[group].append({'x': (record.local_date-start).days, 'y': float(value)})
            rows.append({'date': record.local_date, 'value': str(value), 'unit': unit,
                         'source': ' · '.join(item for item in attributes if item)})
        datasets = [{'label': ' · '.join(item for item in group if item), 'data': points,
                     'yAxisID': 'unit'+str(list(dict.fromkeys(g[1] for g in groups)).index(group[1]))}
                    for group, points in groups.items()]
        units = list(dict.fromkeys(group[1] for group in groups))
        evidence = {'eligible_count': len(rows), 'unresolved_count': 0, 'unavailable_count': 0,
                    'ambiguous_days': 0, 'boundary_excluded': 0, 'history_href': HISTORY_HREF, 'notice': ''}
        return {'datasets': datasets, 'units': units, 'dates': [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)],
                'rows': rows, 'count': len(rows), 'truncated': total>2000, 'title': OPTIONS[metric][0], 'evidence': evidence}
    stored = list(ordered.select_related('connection')[:2000])
    truncated = total > 2000
    boundary_date = stored[-1].local_date if truncated and stored else None
    eligible, evidence = partition_records(stored)
    evidence['ambiguous_days'] = 0
    evidence['boundary_excluded'] = 0
    provisional = []
    for record in eligible:
        values = record.values if isinstance(record.values, dict) else {}
        value = values.get(key)
        if boundary_date is not None and record.local_date == boundary_date:
            if value is not None:
                evidence['boundary_excluded'] += 1
            continue
        if value is None:
            continue
        unit = values['unit'] if kind=='health' else OPTIONS[metric][1]
        identity = summary_series_identity(record, key)
        token = summary_series_token(identity)
        label_parts = [record.source_system, unit, record.device, record.entry_method, record.completeness,
                       'test' if record.synthetic else 'personal']
        if key=='hrv_ms':
            label_parts.append(values.get('hrv_method', 'source_unspecified'))
        if kind=='health':
            label_parts += [values.get('name', ''), values.get('reference_range', '')]
        label = ' · '.join(item for item in label_parts if item)
        provisional.append((token, label, unit, {'x': (record.local_date-start).days, 'y': float(value)},
            {'date': record.local_date, 'value': str(value), 'unit': unit, 'source': label, 'series_id': token}))
    counts = defaultdict(int)
    for token, _label, _unit, point, _row in provisional:
        counts[(token, point['x'])] += 1
    rows, groups, labels, units_by_token = [], defaultdict(list), {}, {}
    ambiguous = set()
    for token, label, unit, point, row in provisional:
        if counts[(token, point['x'])] > 1:
            ambiguous.add((token, point['x']))
            continue
        labels[token] = label
        units_by_token[token] = unit
        groups[token].append(point)
        rows.append(row)
    evidence['ambiguous_days'] = len(ambiguous)
    unit_order = list(dict.fromkeys(units_by_token[token] for token in groups))
    datasets = [{'label': labels[token], 'data': points, 'series_id': token,
                 'yAxisID': 'unit'+str(unit_order.index(units_by_token[token]))}
                for token, points in groups.items()]
    return {'datasets': datasets, 'units': unit_order, 'dates': [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)],
            'rows': rows, 'count': len(rows), 'truncated': truncated, 'title': OPTIONS[metric][0], 'evidence': evidence}


@owner_only
@require_http_methods(['GET'])
def page(request):
    today = timezone.localdate()
    form = TrendForm(request.GET or {'metric':'measurements:weight', 'start':str(today-timedelta(days=89)), 'end':str(today)})
    result = None
    if form.is_valid():
        result = observations(request.user, **form.cleaned_data)
    return render(request, 'tracking/trends.html', {'form': form, 'result': result})
