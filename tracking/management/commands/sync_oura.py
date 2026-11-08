"""Explicit operator ingestion. No scheduler or remote write is created."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from tracking.oura.catalog import COLLECTIONS
from tracking.oura.sync import new_sync, resume
from tracking.oura.transport import OuraError


class Command(BaseCommand):
    help = 'Fetch Oura collections into existing local storage; explicitly authorized real ingestion only.'

    def add_arguments(self, parser):
        parser.add_argument('--connection', required=True, help='Account UUID from the Oura page or stored connection status')
        parser.add_argument('--start', required=True, help='YYYY-MM-DD; at most 31 days per request window')
        parser.add_argument('--end', required=True)
        parser.add_argument('--collection', choices=sorted(COLLECTIONS), help='Omit to request all 19 collections')
        parser.add_argument('--pages', type=int, default=5, help='Maximum pages per collection this invocation, 1 to 20')
        parser.add_argument('--resume', help='Resume this sync UUID instead of starting new requests')

    def handle(self, *args, **options):
        owner = get_user_model().objects.get(username=settings.OWNER_USERNAME)
        try:
            if options['resume']:
                from tracking.models import OuraSync
                run = OuraSync.objects.get(pk=options['resume'], connection_id=options['connection'], connection__owner=owner)
                runs = [run]
            else:
                runs = [new_sync(owner, options['connection'], collection, options['start'], options['end'])
                        for collection in ([options['collection']] if options['collection'] else COLLECTIONS)]
            for run in runs:
                result = resume(owner, run.pk, options['pages'])
                self.stdout.write(f'{result.pk} {result.collection}: {result.status}; pages={result.pages}; error={result.error_code or "none"}')
        except OuraError as error:
            raise CommandError(error.code) from None
