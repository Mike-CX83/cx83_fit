"""Public informational pages contain no owner identity, secrets or private records."""
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def privacy(request):
    return render(request, 'tracking/privacy.html')


@require_GET
def terms(request):
    return render(request, 'tracking/terms.html')
