"""Owner page for the 90 day plan and current clinical list. Meal entry lives on Diary."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from tracking.models import ClinicalItem, DietEntry
from tracking.plan import fitness_plan, plan_window, replace_current_lab
from tracking.views import owner_only


def _decimal(raw, label):
    text = (raw or '').strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        raise ValueError(f'{label} must be a number.') from None
    if number < 0 or number > Decimal('99999'):
        raise ValueError(f'{label} is outside the supported range.')
    return number.quantize(Decimal('0.1'))


def _day(raw):
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        raise ValueError('Use a YYYY-MM-DD date.') from None


@owner_only
@require_http_methods(['GET', 'POST'])
def page(request):
    error = ''
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            if action == 'clinical':
                _save_clinical(request)
            elif action == 'stop':
                _stop(request)
            else:
                raise ValueError('Choose a supported update.')
        except ValueError as exc:
            error = str(exc)
        else:
            return redirect('plan')
    return render(request, 'tracking/plan.html', {
        'plan': fitness_plan(request.user, timezone.localdate()),
        'error': error,
    })

def _save_diary(request):
    from tracking.meals import save_meal
    save_meal(
        request.user, request.POST.get('local_date'), request.POST.get('meal', ''),
        request.POST.get('description', ''), calories=request.POST.get('calories'),
        protein_g=request.POST.get('protein_g'), fiber_g=request.POST.get('fiber_g'))


def _save_myfitnesspal(request):
    from tracking.diary_push import parse_diary_push, store_diary_push
    rows = parse_diary_push(request.POST.get('diary_text', ''))
    store_diary_push(request.user, rows)


def _save_clinical(request):
    kind = request.POST.get('kind', '')
    if kind not in dict(ClinicalItem.KINDS):
        raise ValueError('Choose a lab, medication, or diagnosis.')
    name = (request.POST.get('name') or '').strip()
    detail = (request.POST.get('detail') or '').strip()
    if not name or len(name) > 120 or len(detail) > 500:
        raise ValueError('Enter a name, and keep the detail within 500 characters.')
    recorded_on = _day(request.POST.get('recorded_on'))
    if recorded_on > timezone.localdate():
        raise ValueError('The recorded date cannot be in the future.')
    if kind == 'lab':
        replace_current_lab(request.user, name, False)
    ClinicalItem.objects.create(
        owner=request.user, kind=kind, name=name, detail=detail, recorded_on=recorded_on, current=True,
    )


def _stop(request):
    updated = ClinicalItem.objects.filter(
        owner=request.user, pk=request.POST.get('item_id'), current=True,
    ).update(current=False)
    if not updated:
        raise ValueError('That current item was not found.')
