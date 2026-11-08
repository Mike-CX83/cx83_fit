from django import forms
from django.utils import timezone
from .csv_measurements import MAX_BYTES, parse_measurement_csv
from .domain import InvalidMeasurement


class MeasurementForm(forms.Form):
    metric = forms.ChoiceField(choices=[(x, x.title()) for x in ['weight','waist','chest','hip','arm','thigh','calf']])
    value = forms.DecimalField(max_digits=10, decimal_places=3, min_value=0.001)
    unit = forms.ChoiceField(choices=[('lb','lb'),('kg','kg'),('cm','cm'),('in','in')])
    local_date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={'type':'date'}))
    side = forms.ChoiceField(choices=[('','Not applicable'),('left','Left'),('right','Right')], required=False)
    location = forms.CharField(max_length=120, required=False, help_text='Use the same measurement location each time. For limbs, select a side.')
    notes = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows':3}))
    synthetic = forms.BooleanField(required=False, label='Synthetic test entry (excluded from personal history)')
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_version = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)


class MeasurementImportForm(forms.Form):
    namespace = forms.CharField(
        max_length=32, label='Source name',
        help_text='Choose a stable name such as home-scale. Reuse it for later files from the same source.')
    csv_file = forms.FileField(
        label='Measurement CSV', widget=forms.FileInput(attrs={'accept': '.csv,text/csv'}),
        help_text='UTF-8 CSV, up to 64 KiB and 200 measurements.')

    def clean_namespace(self):
        from .imports import validate_namespace
        try:
            return validate_namespace(self.cleaned_data['namespace'])
        except InvalidMeasurement as exc:
            raise forms.ValidationError(str(exc)) from None

    def clean_csv_file(self):
        # Bound the real read, independently of filename, MIME type and declared size.
        upload = self.cleaned_data['csv_file']
        try:
            return parse_measurement_csv(upload.read(MAX_BYTES + 1))
        except InvalidMeasurement as exc:
            raise forms.ValidationError(str(exc)) from None
        except (OSError, ValueError):
            raise forms.ValidationError('The upload was interrupted. Choose one CSV file and try again.') from None


class PhotoUploadForm(forms.Form):
    capture_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}),
                                  help_text='The date the photo was taken, not the upload date.')
    view = forms.ChoiceField(choices=[('front', 'Front'), ('side', 'Side'), ('back', 'Back')])
    image = forms.FileField(widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
                            help_text='JPEG, PNG or WebP. Up to 12 MiB and 25 million pixels. HEIC is not supported yet.')
    notes = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 3}))
    synthetic = forms.BooleanField(required=False, label='Synthetic test image (excluded from personal history)')
    request_id = forms.UUIDField(widget=forms.HiddenInput)

    def clean_image(self):
        from .photos import MAX_PHOTO_BYTES
        try:
            content = self.cleaned_data['image'].read(MAX_PHOTO_BYTES + 1)
        except (OSError, ValueError):
            raise forms.ValidationError('The upload was interrupted. Choose one photo and try again.') from None
        if len(content) > MAX_PHOTO_BYTES:
            raise forms.ValidationError('Choose an image no larger than 12 MiB.')
        return content


class PhotoCompareForm(forms.Form):
    first_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    second_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    view = forms.ChoiceField(choices=[('front', 'Front'), ('side', 'Side'), ('back', 'Back')])
    synthetic = forms.BooleanField(required=False, label='Include synthetic test images')

    def clean(self):
        values = super().clean()
        if values.get('first_date') and values.get('first_date') == values.get('second_date'):
            raise forms.ValidationError('Choose two different capture dates.')
        return values


class SummaryForm(forms.Form):
    local_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    source_system = forms.RegexField(r'^[a-z0-9][a-z0-9_.-]{0,31}$', max_length=32,
        label='Source name', help_text='Name the source you reviewed, such as mfp-export or lab-report. This does not connect that source.')
    source_timezone = forms.CharField(max_length=64, initial='America/Chicago')
    completeness = forms.ChoiceField(choices=[('unknown', 'Unknown coverage'), ('partial', 'Partial record'), ('complete', 'Complete record')])
    device = forms.CharField(max_length=120, required=False, help_text='Required when entering HRV. Keep different device baselines separate.')
    notes = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 3}))
    synthetic = forms.BooleanField(required=False, label='Synthetic test record (excluded from personal history)')
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_version = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def __init__(self, kind, *args, **kwargs):
        from .summaries import SCHEMAS, TEXT_FIELDS
        super().__init__(*args, **kwargs)
        self.kind = kind
        for key, label, unit in SCHEMAS[kind]:
            self.fields['value_' + key] = forms.DecimalField(
                label=f'{label} ({unit})' if unit else label, required=False,
                max_digits=15, decimal_places=6 if kind == 'health' else 3,
                min_value=None if kind == 'health' else 0,
                help_text='Leave blank when unknown. Enter zero only when explicitly reported.')
        for key, maximum in TEXT_FIELDS[kind].items():
            if key == 'hrv_method':
                field = forms.ChoiceField(choices=[('', 'No HRV recorded'), ('RMSSD', 'RMSSD'), ('SDNN', 'SDNN'), ('source_unspecified', 'Source did not specify the method')], required=False)
            else:
                field = forms.CharField(label=key.replace('_', ' ').title(), max_length=maximum,
                                        required=kind == 'health' and key in ['name', 'unit'])
            self.fields['value_' + key] = field

    def payload(self):
        fields = {key: value for key, value in self.cleaned_data.items()
                  if key not in {'request_id', 'expected_version'} and not key.startswith('value_')}
        values = {key[6:]: str(value) if value is not None and not isinstance(value, str) else value
                  for key, value in self.cleaned_data.items() if key.startswith('value_')}
        return {**fields, 'kind': self.kind, 'values': values}


class NutritionTargetForm(forms.Form):
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        from .summaries import SCHEMAS
        super().__init__(*args, **kwargs)
        for key, label, unit in SCHEMAS['nutrition']:
            self.fields[key] = forms.DecimalField(label=f'{label} ({unit})', required=False,
                min_value=0, max_digits=12, decimal_places=3,
                help_text='Leave blank for no target. These are your settings, not recommendations.')


class SummaryImportForm(MeasurementImportForm):
    csv_file = forms.FileField(label='Summary CSV',
        widget=forms.FileInput(attrs={'accept': '.csv,text/csv'}),
        help_text='The dashboard summary format, UTF-8, up to 256 KiB and 200 rows.')

    def clean_csv_file(self):
        from .summary_imports import MAX_BYTES as SUMMARY_MAX_BYTES, parse_summary_csv
        try:
            return parse_summary_csv(self.cleaned_data['csv_file'].read(SUMMARY_MAX_BYTES + 1))
        except InvalidMeasurement as exc:
            raise forms.ValidationError(str(exc)) from None
        except (OSError, ValueError):
            raise forms.ValidationError('The upload was interrupted. Choose one summary CSV file and try again.') from None
