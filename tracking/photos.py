"""Private photo validation and storage. Callers authenticate and authorize first."""
import hashlib
import io
import json
import warnings
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .domain import InvalidMeasurement, parse_day, request_uuid
from .models import ProgressPhoto, WriteRequest
from .services import Conflict, RecordNotFound, _owner


MAX_PHOTO_BYTES = 12 * 1024 * 1024
MAX_PHOTO_PIXELS = 25_000_000
MAX_PHOTO_EDGE = 10_000
FORMATS = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}


def photo_storage():
    return FileSystemStorage(location=Path(settings.PRIVATE_ROOT) / 'photos',
                             file_permissions_mode=0o600, directory_permissions_mode=0o700)


def photo_names(photo):
    # Names are derived only from validated database UUIDs and format enums.
    return (f'{photo.id}/original.{FORMATS[photo.original_format]}',
            f'{photo.id}/display.jpg')


def decode_photo(content):
    """Decode supported still images, apply orientation and emit a metadata-free JPEG."""
    if not isinstance(content, bytes) or not content or len(content) > MAX_PHOTO_BYTES:
        raise InvalidMeasurement('Choose an image no larger than 12 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content), formats=list(FORMATS)) as source:
                original_format = source.format
                width, height = source.size
                if (width * height > MAX_PHOTO_PIXELS or max(width, height) > MAX_PHOTO_EDGE):
                    raise InvalidMeasurement('Images must be at most 25 million pixels and 10000 pixels per side.')
                if getattr(source, 'n_frames', 1) != 1:
                    raise InvalidMeasurement('Choose a still image, not an animation.')
                source.verify()
            with Image.open(io.BytesIO(content), formats=list(FORMATS)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                # A fresh canvas carries no EXIF, GPS, comments, ICC or XMP from the source.
                rgba = oriented.convert('RGBA')
                display = Image.new('RGB', rgba.size, 'white')
                display.paste(rgba, mask=rgba.getchannel('A'))
                output = io.BytesIO()
                display.save(output, format='JPEG', quality=88, optimize=True)
                return {'format': original_format, 'width': display.width,
                        'height': display.height, 'display': output.getvalue()}
    except InvalidMeasurement:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise InvalidMeasurement('Choose a valid JPEG, PNG or WebP still image. HEIC is not supported yet.') from None


def photo_metadata(photo):
    return {'id': str(photo.id), 'capture_date': photo.capture_date.isoformat(),
            'view': photo.view, 'notes': photo.notes, 'synthetic': photo.synthetic,
            'uploaded_at': photo.uploaded_at.isoformat(), 'width': photo.width,
            'height': photo.height, 'original_format': photo.original_format,
            'source_system': 'manual_photo'}


def create_photo(owner, content, capture_date, view, notes, synthetic, request_id):
    _owner(owner)
    capture_date = parse_day(capture_date)
    request_id = request_uuid(request_id)
    if view not in dict(ProgressPhoto.VIEWS):
        raise InvalidMeasurement('Choose front, side or back.')
    if not isinstance(notes, str) or len(notes) > 2000 or type(synthetic) is not bool:
        raise InvalidMeasurement('Use at most 2000 characters for notes and an explicit synthetic flag.')
    if not isinstance(content, bytes) or len(content) > MAX_PHOTO_BYTES:
        raise InvalidMeasurement('Choose an image no larger than 12 MiB.')
    original_hash = hashlib.sha256(content).hexdigest()
    digest = hashlib.sha256(json.dumps({'operation': 'photo_upload',
        'capture_date': capture_date.isoformat(), 'view': view, 'notes': notes,
        'synthetic': synthetic, 'original_sha256': original_hash}, sort_keys=True).encode()).hexdigest()
    # Validate before opening the write transaction; all file and DB writes stay together.
    decoded = decode_photo(content)
    storage, written = photo_storage(), []
    try:
        with transaction.atomic():
            receipt = WriteRequest.objects.filter(owner=owner, request_id=request_id).first()
            if receipt:
                if receipt.payload_hash != digest:
                    raise Conflict('This request was already used with different content.')
                if not ProgressPhoto.objects.filter(request=receipt, owner=owner, deleted_at__isnull=True).exists():
                    raise Conflict('This photo was deleted. Retrying cannot restore it.')
                return receipt.response
            receipt = WriteRequest.objects.create(owner=owner, request_id=request_id, payload_hash=digest)
            photo = ProgressPhoto(owner=owner, request=receipt, capture_date=capture_date,
                                  view=view, notes=notes, synthetic=synthetic,
                                  original_sha256=original_hash, original_format=decoded['format'],
                                  width=decoded['width'], height=decoded['height'])
            photo.full_clean()
            photo.save(force_insert=True)
            original_name, display_name = photo_names(photo)
            written.append(storage.save(original_name, ContentFile(content)))
            written.append(storage.save(display_name, ContentFile(decoded['display'])))
            # UUID paths must not be silently renamed if unexpected files already exist.
            if written != [original_name, display_name]:
                raise Conflict('Photo storage conflict. Retry the upload.')
            result = photo_metadata(photo)
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except Exception as exc:
        for name in written:
            storage.delete(name)
        if isinstance(exc, (IntegrityError, OperationalError)):
            raise Conflict('Storage is busy. Retry the same upload.') from None
        raise


def delete_photo(owner, photo_id):
    """Tombstone first so access is denied even if removal is interrupted."""
    _owner(owner)
    with transaction.atomic():
        photo = ProgressPhoto.objects.filter(owner=owner, id=photo_id).first()
        if not photo:
            raise RecordNotFound('Photo not found.')
        if photo.deleted_at is None:
            photo.deleted_at = timezone.now()
            photo.notes = ''
            photo.save(update_fields=['deleted_at', 'notes'])
            # Retain a minimal retry tombstone, not copies of deleted notes in the receipt.
            photo.request.response = {'id': str(photo.id), 'deleted': True}
            photo.request.save(update_fields=['response'])
    # Removing already absent files is safe, so an interrupted deletion can be retried.
    storage = photo_storage()
    for name in photo_names(photo):
        storage.delete(name)
