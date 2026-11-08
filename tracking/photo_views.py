import uuid

from django.core.paginator import Paginator, InvalidPage
from django.http import Http404, HttpResponseBadRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods

from .forms import PhotoUploadForm, PhotoCompareForm
from .models import ProgressPhoto
from .photos import create_photo, delete_photo, photo_names, photo_storage, FORMATS
from .uploads import PhotoUploadLimit
from .views import owner_only
from .responses import private_file_response


def _photos(request, include_synthetic=False):
    records = ProgressPhoto.objects.filter(owner=request.user, deleted_at__isnull=True)
    return records if include_synthetic else records.filter(synthetic=False)


@owner_only
@require_http_methods(['GET'])
def gallery(request):
    synthetic = request.GET.get('synthetic') == '1'
    records = _photos(request, synthetic)
    view = request.GET.get('view', '')
    if view:
        if view not in dict(ProgressPhoto.VIEWS):
            raise Http404
        records = records.filter(view=view)
    try:
        page = Paginator(records, 18).page(request.GET.get('page', '1'))
    except InvalidPage:
        raise Http404
    return render(request, 'tracking/photos.html', {'page': page, 'synthetic': synthetic,
                                                   'view': view, 'views': ProgressPhoto.VIEWS})


@csrf_exempt
@owner_only
@require_http_methods(['GET', 'POST'])
def upload(request):
    # Install the byte-counting handler before inner CSRF protection parses the form.
    request.upload_handlers.insert(0, PhotoUploadLimit(request))
    return _upload(request)


@csrf_protect
def _upload(request):
    form = PhotoUploadForm(request.POST if request.method == 'POST' else None,
                           request.FILES if request.method == 'POST' else None,
                           initial={'request_id': uuid.uuid4()})
    if request.method == 'POST':
        valid = form.is_valid()
        if getattr(request, 'photo_upload_error', None):
            form.add_error('image', request.photo_upload_error)
        elif valid:
            fields = dict(form.cleaned_data)
            content = fields.pop('image')
            try:
                result = create_photo(request.user, content, **fields)
            except ValueError as exc:
                form.add_error(None, str(exc))
            except OSError:
                form.add_error(None, 'Photo storage is unavailable. Retry this upload.')
            else:
                return redirect('photo_detail', photo_id=result['id'])
    return render(request, 'tracking/photo_upload.html', {'form': form})


@owner_only
@require_http_methods(['GET'])
def detail(request, photo_id):
    photo = get_object_or_404(_photos(request, True), pk=photo_id)
    return render(request, 'tracking/photo_detail.html', {'photo': photo})


@owner_only
@require_http_methods(['GET'])
def image(request, photo_id, original=False):
    photo = get_object_or_404(_photos(request, True), pk=photo_id)
    names = photo_names(photo)
    try:
        handle = photo_storage().open(names[0 if original else 1], 'rb')
    except OSError:
        raise Http404('Photo file unavailable.') from None
    extension = FORMATS[photo.original_format] if original else 'jpg'
    content_type = {'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}[extension]
    return private_file_response(request, handle, as_attachment=original, content_type=content_type,
                        filename=f'photo-{photo.capture_date}-{photo.view}.{extension}')


@owner_only
@require_http_methods(['POST'])
def remove(request, photo_id):
    if request.POST.get('confirm_delete') != 'yes':
        return HttpResponseBadRequest('Confirm photo deletion first.')
    # Owner and ID are checked even for repeated deletion attempts.
    get_object_or_404(ProgressPhoto, pk=photo_id, owner=request.user)
    try:
        delete_photo(request.user, photo_id)
    except OSError:
        return HttpResponse('The photo is hidden. File cleanup is incomplete; retry this deletion.', status=503)
    return redirect('photo_gallery')


@owner_only
@require_http_methods(['GET'])
def compare(request):
    form = PhotoCompareForm(request.GET or None)
    photos = []
    if form.is_valid():
        data = form.cleaned_data
        records = _photos(request, data['synthetic']).filter(view=data['view'])
        for field in ['first_date', 'second_date']:
            photo = records.filter(capture_date=data[field]).order_by('-uploaded_at', 'id').first()
            if photo is None:
                form.add_error(field, 'No photo for that date and view in the selected history.')
            else:
                photos.append(photo)
        if form.errors:
            photos = []
    return render(request, 'tracking/photo_compare.html', {'form': form, 'photos': photos})
