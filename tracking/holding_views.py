"""Owner page for Holding Space and provider reply callbacks."""
import uuid
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from tracking.holding import MESSAGE, add_partner, apply_delivery, apply_reply, partners, reach_out, remove_partner, update_partner
from tracking.sms import configured, valid_signature
from tracking.views import owner_only


def _signed(request):
    params = {key: request.POST.get(key, '') for key in request.POST}
    return valid_signature(request.build_absolute_uri(), params, request.headers.get('X-Twilio-Signature', ''))


@owner_only
@require_http_methods(['GET', 'POST'])
def page(request):
    error = ''
    request_id = request.POST.get('request_id') if request.POST.get('action') == 'reach' else str(uuid.uuid4())
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            if action == 'add':
                add_partner(request.user, request.POST.get('name', ''), request.POST.get('phone', ''))
            elif action == 'update':
                update_partner(
                    request.user, request.POST.get('partner_id'),
                    request.POST.get('name', ''), request.POST.get('phone', ''))
            elif action == 'remove':
                remove_partner(request.user, request.POST.get('partner_id'))
            elif action == 'reach':
                reach_out(request.user, request.POST.getlist('partner'), request_id)
            else:
                raise ValueError('Choose a supported update.')
        except ValueError as exc:
            error = str(exc)
        else:
            return redirect('holding')
    return render(request, 'tracking/holding.html', {
        'partners': partners(request.user),
        'message': MESSAGE,
        'sms_ready': configured(),
        'request_id': request_id,
        'error': error,
        'openings': max(0, 5 - len(partners(request.user))),
    })


@csrf_exempt
@require_http_methods(['POST'])
def inbound(request):
    if not _signed(request):
        return HttpResponse(status=403)
    apply_reply(request.POST.get('From', ''), request.POST.get('Body', ''))
    return HttpResponse('<Response></Response>', content_type='text/xml')


@csrf_exempt
@require_http_methods(['POST'])
def delivery(request):
    if not _signed(request):
        return HttpResponse(status=403)
    if request.POST.get('MessageStatus') == 'delivered':
        apply_delivery(request.POST.get('MessageSid', ''))
    return HttpResponse(status=204)
