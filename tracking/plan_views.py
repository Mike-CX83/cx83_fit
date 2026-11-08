"""Owner page for the 90 day plan. Meals live on Diary. Clinical records have their own page."""
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from tracking.plan import fitness_plan
from tracking.views import owner_only


@owner_only
@require_http_methods(['GET'])
def page(request):
    return render(request, 'tracking/plan.html', {
        'plan': fitness_plan(request.user, timezone.localdate()),
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

