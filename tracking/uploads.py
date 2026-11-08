"""A bounded Django upload filter for the measurement CSV endpoint only."""
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from .csv_measurements import MAX_BYTES


class MeasurementCSVUploadLimit(FileUploadHandler):
    chunk_size = 8192

    def __init__(self, request):
        super().__init__(request)
        self.total_bytes = 0
        self.file_count = 0

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.file_count += 1
        if self.file_count > 1 or self.field_name != 'csv_file':
            self.request.import_upload_error = 'Upload one measurement CSV file.'
            raise StopUpload(connection_reset=True)

    def receive_data_chunk(self, raw_data, start):
        self.total_bytes += len(raw_data)
        if self.total_bytes > MAX_BYTES:
            self.request.import_upload_error = 'CSV input exceeds the 64 KiB limit.'
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


class PhotoUploadLimit(FileUploadHandler):
    chunk_size = 65536

    def __init__(self, request):
        super().__init__(request)
        self.total_bytes = 0
        self.file_count = 0

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.file_count += 1
        if self.file_count > 1 or self.field_name != 'image':
            self.request.photo_upload_error = 'Upload one photo at a time.'
            raise StopUpload(connection_reset=True)

    def receive_data_chunk(self, raw_data, start):
        from .photos import MAX_PHOTO_BYTES
        self.total_bytes += len(raw_data)
        if self.total_bytes > MAX_PHOTO_BYTES:
            self.request.photo_upload_error = 'Choose an image no larger than 12 MiB.'
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


class SummaryCSVUploadLimit(MeasurementCSVUploadLimit):
    def receive_data_chunk(self, raw_data, start):
        from .summary_imports import MAX_BYTES as SUMMARY_MAX_BYTES
        self.total_bytes += len(raw_data)
        if self.total_bytes > SUMMARY_MAX_BYTES:
            self.request.import_upload_error = 'Summary CSV exceeds the 256 KiB limit.'
            raise StopUpload(connection_reset=True)
        return raw_data
