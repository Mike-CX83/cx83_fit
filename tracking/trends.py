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
from .views import owner_only


OPTIONS = {**{'measurements:'+key: (key.title(), None) for key in METRICS},
    **{kind+':'+key: (kind.title()+' · '+label, unit) for kind, fields in SCHEMAS.items() for key, label, unit in fields}}


class TrendForm(forms.Form):
    metric = forms.ChoiceField(choices=[(key, value[0]) for key, value in OPTIONS.items()])
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    synthetic = forms.BooleanField(required=False, label='Include synthetic tests')

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
    rows, groups = [], defaultdict(list)
    for record in query.order_by('local_date', 'pk')[:2000]:
        value = record.value if kind=='measurements' else record.values.get(key)
        if value is None:
            continue
        unit = record.unit if kind=='measurements' else (record.values['unit'] if kind=='health' else OPTIONS[metric][1])
        attributes = [record.source_system, unit]
        if kind=='measurements':
            attributes += [record.side, record.location]
        else:
            attributes += [record.device, record.completeness]
            if key=='hrv_ms':
                attributes += [record.values.get('hrv_method', 'source_unspecified')]
            if kind=='health':
                attributes += [record.values['name'], record.values.get('reference_range', '')]
        attributes += ['Synthetic' if record.synthetic else 'Personal']
        group = tuple(attributes)
        groups[group].append({'x': (record.local_date-start).days, 'y': float(value)})
        rows.append({'date': record.local_date, 'value': str(value), 'unit': unit,
                     'source': ' · '.join(item for item in attributes if item)})
    datasets = [{'label': ' · '.join(item for item in group if item), 'data': points,
                 'yAxisID': 'unit'+str(list(dict.fromkeys(g[1] for g in groups)).index(group[1]))}
                for group, points in groups.items()]
    units = list(dict.fromkeys(group[1] for group in groups))
    return {'datasets': datasets, 'units': units, 'dates': [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)],
            'rows': rows, 'count': len(rows), 'truncated': total>2000, 'title': OPTIONS[metric][0]}


@owner_only
@require_http_methods(['GET'])
def page(request):
    today = timezone.localdate()
    form = TrendForm(request.GET or {'metric':'measurements:weight', 'start':str(today-timedelta(days=89)), 'end':str(today)})
    result = None
    if form.is_valid():
        result = observations(request.user, **form.cleaned_data)
    return render(request, 'tracking/trends.html', {'form': form, 'result': result})
