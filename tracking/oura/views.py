from django import forms
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from tracking.views import owner_only
from tracking.models import OuraConnection, OuraSync
from . import auth, sync
from .catalog import COLLECTIONS, CALLBACK_PATH
from .transport import OuraError


class SyncForm(forms.Form):
    collection = forms.ChoiceField(choices=[(name, name) for name in COLLECTIONS])
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))


@owner_only
@require_GET
def page(request):
    accounts = OuraConnection.objects.filter(owner=request.user, synthetic=False).order_by('created_at')
    runs = OuraSync.objects.filter(connection__owner=request.user, connection__synthetic=False).order_by('-updated_at')[:60]
    return render(request, 'tracking/oura.html', {'enabled': auth.configured(), 'accounts': accounts,
        'runs': runs, 'form': SyncForm(initial={'start': timezone.localdate(), 'end': timezone.localdate()}),
        'collections': COLLECTIONS, 'status': sync.status(request.user)})


@owner_only
@require_POST
def start(request):
    if request.POST.get('confirm_connect') != 'yes':
        return HttpResponse('Confirm Oura access first.', status=400)
    try:
        url, nonce = auth.begin(request.user)
    except OuraError as error:
        return HttpResponse('Oura setup is unavailable: '+error.code, status=409)
    response = HttpResponseRedirect(url)
    response.oauth_callback_origin = 'https://cloud.ouraring.com'
    # This narrow cookie carries only a random browser nonce, never tokens.
    # The main login cookie remains SameSite Strict.
    response.set_cookie(auth.FLOW_COOKIE, nonce, max_age=600, secure=True, httponly=True,
                        samesite='Lax', path=CALLBACK_PATH)
    return response


@require_GET
def callback(request):
    try:
        auth.finish(request.GET, request.COOKIES.get(auth.FLOW_COOKIE, ''))
        outcome = 'Authorization saved. Sign in to review the connection and start ingestion. Data ingestion is not yet verified.'
        status = 200
    except OuraError as error:
        outcome = 'Oura authorization was not completed: '+error.code+'. Start a new authorization from the dashboard.'
        status = 400
    response = render(request, 'tracking/oura_callback.html', {'outcome': outcome}, status=status)
    response['Referrer-Policy'] = 'no-referrer'
    response.delete_cookie(auth.FLOW_COOKIE, path=CALLBACK_PATH, samesite='Lax')
    return response


@owner_only
@require_POST
def disconnect(request, connection_id):
    get_object_or_404(OuraConnection, owner=request.user, pk=connection_id)
    if request.POST.get('confirm_disconnect') != 'yes':
        return HttpResponse('Confirm disconnection first.', status=400)
    auth.disconnect(request.user, connection_id)
    return HttpResponseRedirect('/integrations/oura/')


@owner_only
@require_POST
def start_sync(request, connection_id):
    get_object_or_404(OuraConnection, owner=request.user, pk=connection_id)
    form = SyncForm(request.POST)
    if not form.is_valid() or request.POST.get('confirm_sync') != 'yes':
        return HttpResponse('Confirm ingestion and supply a valid collection and date range.', status=400)
    try:
        run = sync.new_sync(request.user, connection_id, form.cleaned_data['collection'],
            form.cleaned_data['start'].isoformat(), form.cleaned_data['end'].isoformat())
        sync.resume(request.user, run.pk, page_budget=1)
    except OuraError as error:
        return HttpResponse('Ingestion paused: '+error.code, status=409)
    return HttpResponseRedirect('/integrations/oura/')


@owner_only
@require_POST
def resume_sync(request, run_id):
    get_object_or_404(OuraSync, pk=run_id, connection__owner=request.user)
    try:
        sync.resume(request.user, run_id, page_budget=1)
    except OuraError as error:
        return HttpResponse('Ingestion paused: '+error.code, status=409)
    return HttpResponseRedirect('/integrations/oura/')


@owner_only
@require_GET
def records(request, collection):
    if collection not in COLLECTIONS:
        return HttpResponse(status=404)
    try:
        result = sync.read_records(request.user, collection, limit=10, offset=int(request.GET.get('offset', '0')))
    except (OuraError, ValueError):
        return HttpResponse('Invalid record range.', status=400)
    return render(request, 'tracking/oura_records.html', {'result': result, 'collection': collection})
