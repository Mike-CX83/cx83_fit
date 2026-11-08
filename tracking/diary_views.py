"""Owner meal diary. Paste and manual entry live here, not on Plan."""
from datetime import timedelta

from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from tracking.models import DietEntry
from tracking.plan_views import _save_diary, _save_myfitnesspal
from tracking.views import owner_only

MEALS = set(dict(DietEntry.MEALS))


@owner_only
@require_http_methods(['GET', 'POST'])
def page(request):
    error = ''
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            if action == 'diary':
                _save_diary(request)
            elif action == 'myfitnesspal':
                _save_myfitnesspal(request)
            else:
                raise ValueError('Choose a supported diary update.')
        except ValueError as exc:
            error = str(exc)
        else:
            return redirect('diary')
    today = timezone.localdate()
    start = today - timedelta(days=14)
    meals = DietEntry.objects.filter(
        owner=request.user, deleted_at__isnull=True, synthetic=False,
        local_date__gte=start, local_date__lte=today,
    ).order_by('-local_date', 'meal', '-created_at')[:60]
    form_date = request.GET.get('local_date') or today.isoformat()
    form_meal = request.GET.get('meal') or 'breakfast'
    if form_meal not in MEALS:
        form_meal = 'breakfast'
    return render(request, 'tracking/diary.html', {
        'meals': meals, 'today': today.isoformat(), 'error': error,
        'form_date': form_date, 'form_meal': form_meal,
    })
