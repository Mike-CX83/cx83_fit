"""Versioned journal domains and explicit self-report metrics.

Domains 12, 13, 14, 16, 17, 18 and 19 are the planning taxonomy. Metrics here
are slots the owner fills in. Nothing in this module infers a score, a
diagnosis, or a fact the owner did not submit. Narrative text stays text.
"""
from .domain import InvalidMeasurement

PROTOCOL_VERSION = 'journal-1'
REGISTRY_VERSION = 'registry-1'

DOMAINS = {
    12: 'Sobriety',
    13: 'Mental health',
    14: 'Cognitive health',
    16: 'Relationships',
    17: 'Life circumstances',
    18: 'Spirituality and identity',
    19: 'Habits and symptoms',
}

STATES = frozenset({'observed', 'unknown', 'declined', 'not_applicable', 'pending', 'conflicting'})

METRICS = {
    'note': {
        'label': 'Note',
        'type': 'narrative',
        'domains': frozenset(DOMAINS),
        'states': STATES - {'conflicting'},
    },
    'explicit_choice': {
        'label': 'Explicit yes or no',
        'type': 'boolean',
        'domains': frozenset(DOMAINS),
        'states': STATES | {'intention'},
    },
}


def validate_observation(payload):
    """Return a stored observation. Explicit false stays false. Unknown stays empty."""
    if not isinstance(payload, dict):
        raise InvalidMeasurement('An observation must be an object.')
    if set(payload) - {'domain_id', 'metric_key', 'value_state', 'narrative', 'boolean', 'subject'}:
        raise InvalidMeasurement('Unsupported observation fields.')
    if payload.get('subject', 'self') != 'self':
        raise InvalidMeasurement('An observation can only be recorded for the owner.')
    domain_id = payload.get('domain_id')
    if type(domain_id) is not int or domain_id not in DOMAINS:
        raise InvalidMeasurement('Use one of the journal domains.')
    spec = METRICS.get(payload.get('metric_key'))
    if spec is None or domain_id not in spec['domains']:
        raise InvalidMeasurement('That metric is not defined for this domain.')
    state = payload.get('value_state')
    if state not in spec['states']:
        raise InvalidMeasurement('That value state is not valid for this metric.')
    narrative = payload.get('narrative', '')
    if not isinstance(narrative, str) or len(narrative) > 2000:
        raise InvalidMeasurement('Narrative must contain at most 2000 characters.')
    narrative = narrative.strip()
    boolean = payload.get('boolean', None)
    if spec['type'] == 'narrative':
        if boolean is not None:
            raise InvalidMeasurement('A narrative observation does not take a yes or no.')
        if state == 'observed' and not narrative:
            raise InvalidMeasurement('An observed note needs the words that were recorded.')
        if state != 'observed' and narrative:
            raise InvalidMeasurement('Only an observed note keeps narrative text.')
        stored_narrative, value = (narrative, None) if state == 'observed' else ('', None)
        value_type = 'narrative'
    else:
        if narrative:
            raise InvalidMeasurement('A yes or no observation does not take narrative text.')
        if state == 'observed':
            if type(boolean) is not bool:
                raise InvalidMeasurement('An observed yes or no must be true or false.')
            value = {'boolean': boolean}
        elif boolean is not None:
            raise InvalidMeasurement('Only an observed yes or no stores true or false.')
        else:
            value = None
        stored_narrative, value_type = '', 'boolean'
    return {
        'domain_id': domain_id, 'metric_key': payload['metric_key'], 'value_state': state,
        'value_type': value_type, 'value_json': value, 'narrative': stored_narrative,
        'subject': 'self', 'registry_version': REGISTRY_VERSION,
    }
