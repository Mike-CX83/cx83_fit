"""Explicitly saved reviews and separate annotations; never modifies source records."""
import hashlib
import json
from uuid import uuid4
from django import forms
from django.core.paginator import Paginator, InvalidPage
from django.db import transaction, IntegrityError, OperationalError
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .domain import parse_day, request_uuid, InvalidMeasurement
from .models import ReviewNote, WriteRequest, Measurement, SummaryRecord
from .services import _owner, _replay, Conflict
from .views import owner_only


def serialize_review(note):
    return {'id':str(note.id), 'local_date':note.local_date.isoformat(), 'text':note.text,
        'source_system':note.source_system, 'record_kind':note.record_kind,
        'record_id':str(note.record_id) if note.record_id else None, 'synthetic':note.synthetic,
        'created_at':note.created_at.isoformat(), 'deleted_at':note.deleted_at.isoformat() if note.deleted_at else None}


def save_review(owner, text, local_date, request_id, synthetic=False, record_kind='', record_id=None, *, source_system='manual'):
    _owner(owner)
    if source_system not in {'manual','mcp'} or type(synthetic) is not bool:
        raise InvalidMeasurement('Use a supported source and explicit synthetic flag.')
    if not isinstance(text,str) or not text.strip() or len(text)>10000:
        raise InvalidMeasurement('Provide review text of 1 to 10000 characters.')
    local_date, request_id = parse_day(local_date), request_uuid(request_id)
    if record_kind:
        if record_kind not in {'measurement','summary'}:
            raise InvalidMeasurement('Unsupported annotation target.')
        record_id=request_uuid(record_id)
    elif record_id is not None:
        raise InvalidMeasurement('Choose a target type for the annotation.')
    payload={'operation':'save_review','text':text,'local_date':str(local_date),'synthetic':synthetic,
        'record_kind':record_kind,'record_id':record_id,'source_system':source_system}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    try:
        with transaction.atomic():
            prior=_replay(owner,request_id,digest)
            if prior is not None:
                if not ReviewNote.objects.filter(owner=owner,id=prior['id'],deleted_at__isnull=True).exists():
                    raise Conflict('This review was deleted. A retry cannot restore it.')
                return prior
            if record_kind:
                model=Measurement if record_kind=='measurement' else SummaryRecord
                record=model.objects.filter(owner=owner,id=record_id,deleted_at__isnull=True).first()
                if record is None or record.synthetic != synthetic:
                    raise InvalidMeasurement('Target not found or synthetic status does not match.')
            request=WriteRequest.objects.create(owner=owner,request_id=request_id,payload_hash=digest)
            note=ReviewNote.objects.create(owner=owner,request=request,text=text,local_date=local_date,
                synthetic=synthetic,record_kind=record_kind,record_id=record_id,source_system=source_system)
            result=serialize_review(note)
            request.response=result;request.save(update_fields=['response'])
            return result
    except (IntegrityError,OperationalError):
        raise Conflict('Storage is busy. Retry the same request.') from None


class ReviewForm(forms.Form):
    local_date=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    text=forms.CharField(max_length=10000,widget=forms.Textarea, label='Review or annotation')
    record_kind=forms.ChoiceField(choices=[('','General review'),('measurement','Measurement annotation'),('summary','Source summary annotation')],required=False,widget=forms.HiddenInput)
    record_id=forms.UUIDField(required=False,widget=forms.HiddenInput)
    synthetic=forms.BooleanField(required=False,label='Synthetic test note')
    request_id=forms.UUIDField(widget=forms.HiddenInput)


@owner_only
@require_http_methods(['GET','POST'])
def page(request):
    initial={'local_date':timezone.localdate(),'request_id':uuid4(),
        'record_kind':request.GET.get('record_kind',''),'record_id':request.GET.get('record_id')}
    annotation=None
    if request.method=='GET' and (initial['record_kind'] or initial['record_id']):
        if initial['record_kind'] not in {'measurement','summary'}:
            raise Http404
        try:
            target_id=request_uuid(initial['record_id'])
        except ValueError:
            raise Http404
        model=Measurement if initial['record_kind']=='measurement' else SummaryRecord
        annotation=get_object_or_404(model,owner=request.user,id=target_id,deleted_at__isnull=True)
        initial['synthetic']=annotation.synthetic
    form=ReviewForm(request.POST if request.method=='POST' else None,initial=initial)
    if request.method=='POST' and form.is_valid():
        data=dict(form.cleaned_data)
        data['request_id']=str(data['request_id'])
        if data['record_id'] is not None:
            data['record_id']=str(data['record_id'])
        data['local_date']=str(data['local_date'])
        try:
            result=save_review(request.user,**data)
        except ValueError as exc:
            form.add_error(None,str(exc))
        else:
            return redirect('/reviews/?synthetic=1' if result['synthetic'] else '/reviews/')
    query=ReviewNote.objects.filter(owner=request.user,deleted_at__isnull=True)
    synthetic=request.GET.get('synthetic')=='1'
    if not synthetic:
        query=query.filter(synthetic=False)
    try:
        page=Paginator(query,20).page(request.GET.get('page','1'))
    except InvalidPage:
        raise Http404
    return render(request,'tracking/reviews.html',{'form':form,'page':page,'synthetic':synthetic,'annotation':annotation})


@owner_only
@require_http_methods(['POST'])
def remove(request,note_id):
    if request.POST.get('confirm_delete')!='yes':
        return HttpResponseBadRequest('Confirm deletion first.')
    with transaction.atomic():
        note=get_object_or_404(ReviewNote,owner=request.user,id=note_id)
        note.deleted_at=timezone.now();note.text='';note.save(update_fields=['deleted_at','text'])
        note.request.response={'id':str(note.id),'deleted':True};note.request.save(update_fields=['response'])
    return redirect('reviews')
