"""Versioned journal domains and explicit self-report metrics.

Domains 12, 13, 14, 16, 17, 18 and 19 are the planning taxonomy. Metrics here
are slots the owner fills in. Nothing in this module infers a score, a
diagnosis, or a fact the owner did not submit. Narrative text stays text.
"""
from .domain import InvalidMeasurement

PROTOCOL_VERSION = 'journal-1'
REGISTRY_VERSION = 'registry-3'

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
    'energy': {
        'label': 'Energy',
        'type': 'rating',
        'domains': frozenset({19}),
        'states': STATES - {'conflicting'},
        'direction': 'positive',
    },
    'mood': {
        'label': 'Mood',
        'type': 'rating',
        'domains': frozenset({13}),
        'states': STATES - {'conflicting'},
        'direction': 'positive',
    },
    'focus': {
        'label': 'Focus',
        'type': 'rating',
        'domains': frozenset({14}),
        'states': STATES - {'conflicting'},
        'direction': 'positive',
    },
    'craving': {
        'label': 'Craving',
        'type': 'rating',
        'domains': frozenset({12}),
        'states': STATES - {'conflicting'},
        'direction': 'negative',
    },
    'confidence': {
        'label': 'Confidence to stay sober',
        'type': 'rating',
        'domains': frozenset({12}),
        'states': STATES - {'conflicting'},
        'direction': 'positive',
    },
    'access': {
        'label': 'Access to getting high',
        'type': 'boolean',
        'domains': frozenset({12}),
        'states': STATES | {'intention'},
    },
    'use': {
        'label': 'Used',
        'type': 'boolean',
        'domains': frozenset({12}),
        'states': STATES | {'intention'},
    },
}

STATE_METRICS = ('energy', 'mood', 'focus')
DAILY_STATE_FORMULA = 'daily-state-1'
ROUTINE_FORMULA = 'routine-alignment-1'


def validate_observation(payload):
    """Return a stored observation. Explicit false stays false. Unknown stays empty."""
    if not isinstance(payload, dict):
        raise InvalidMeasurement('An observation must be an object.')
    if set(payload) - {'domain_id', 'metric_key', 'value_state', 'narrative', 'boolean', 'subject', 'rating', 'practice_key'}:
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
    rating = payload.get('rating', None)
    practice_key = payload.get('practice_key') or ''
    if practice_key and (not isinstance(practice_key, str) or len(practice_key) > 40
                         or not practice_key.replace('_', '').isalnum()):
        raise InvalidMeasurement('Use a short practice key.')
    if spec['type'] == 'rating':
        if boolean is not None or narrative or practice_key:
            raise InvalidMeasurement('A rating does not take a note, a yes or no, or a practice key.')
        if state == 'observed':
            if type(rating) is not int or isinstance(rating, bool) or not 0 <= rating <= 10:
                raise InvalidMeasurement('A rating is a whole number from 0 to 10 that you confirm.')
            value = {'rating': rating}
        elif rating is not None:
            raise InvalidMeasurement('Only an observed rating stores a number.')
        else:
            value = None
        stored_narrative, value_type = '', 'rating'
    elif spec['type'] == 'narrative':
        if boolean is not None or rating is not None or practice_key:
            raise InvalidMeasurement('A narrative observation does not take a yes or no.')
        if state == 'observed' and not narrative:
            raise InvalidMeasurement('An observed note needs the words that were recorded.')
        if state != 'observed' and narrative:
            raise InvalidMeasurement('Only an observed note keeps narrative text.')
        stored_narrative, value = (narrative, None) if state == 'observed' else ('', None)
        value_type = 'narrative'
    else:
        if narrative or rating is not None:
            raise InvalidMeasurement('A yes or no observation does not take narrative text.')
        if state == 'observed':
            if type(boolean) is not bool:
                raise InvalidMeasurement('An observed yes or no must be true or false.')
            value = {'boolean': boolean}
            if practice_key:
                value['practice_key'] = practice_key
        elif practice_key:
            raise InvalidMeasurement('A practice key belongs on an observed yes or no.')
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
