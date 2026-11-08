"""Owner page for current labs, medications, and diagnoses."""
import uuid
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from tracking.clinical import current_items, save_clinical, stop_clinical
from tracking.views import owner_only


def _with_stop_ids(groups):
    for rows in groups.values():
        for row in rows:
            row['stop_request_id'] = str(uuid.uuid4())
    return groups


@owner_only
@require_http_methods(['GET', 'POST'])
def page(request):
    error = ''
    request_id = request.POST.get('request_id') if request.POST.get('action') == 'save' else str(uuid.uuid4())
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            if action == 'save':
                save_clinical(
                    request.user, request.POST.get('kind', ''), request.POST.get('name', ''),
                    request.POST.get('detail', ''), request.POST.get('recorded_on'), request_id)
            elif action == 'stop':
                stop_clinical(request.user, request.POST.get('item_id'), request.POST.get('request_id'))
            else:
                raise ValueError('Choose a supported update.')
        except ValueError as exc:
            error = str(exc)
        else:
            return redirect('clinical')
    return render(request, 'tracking/clinical.html', {
        'items': _with_stop_ids(current_items(request.user, request.GET.get('synthetic') == '1')),
        'today': timezone.localdate().isoformat(),
        'request_id': request_id,
        'error': error,
    })
