"""Holding Space partners and one manual check-in text.

Automatic threshold alerts are not part of this path. A text never includes a
score, a diagnosis, or a health record. Reply STOP opts that number out.
"""
import hashlib
import json
from django.db import IntegrityError, transaction
from django.utils import timezone
from .domain import InvalidMeasurement, request_uuid
from .models import HoldingMessage, HoldingPartner, WriteRequest
from .services import Conflict, _owner, _replay
from .sms import SmsError, send_text

LIMIT = 5
MESSAGE = 'Mike could use a check in. Do you have a moment to connect? Reply STOP to opt out.'
STOP_WORDS = {'STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT'}


def normalize_phone(raw):
    text = ''.join(ch for ch in (raw or '') if ch.isdigit() or ch == '+')
    digits = ''.join(ch for ch in text if ch.isdigit())
    if len(digits) == 10:
        return '+1' + digits
    if len(digits) == 11 and digits.startswith('1'):
        return '+' + digits
    if text.startswith('+') and digits == text[1:] and 8 <= len(digits) <= 15 and not digits.startswith('0'):
        return '+' + digits
    raise InvalidMeasurement('Use a phone number with an area code.')


def _name(raw):
    clean = ' '.join((raw or '').split())
    if not clean or len(clean) > 80:
        raise InvalidMeasurement('Enter a name up to 80 characters.')
    return clean


def _active(owner):
    return HoldingPartner.objects.filter(owner=owner, removed_at__isnull=True)


def add_partner(owner, name, phone):
    _owner(owner)
    clean = _name(name)
    number = normalize_phone(phone)
    rows = _active(owner)
    if rows.filter(phone_e164=number).exists():
        raise InvalidMeasurement('That number is already in Holding Space.')
    if rows.count() >= LIMIT:
        raise InvalidMeasurement('Holding Space holds five people.')
    return HoldingPartner.objects.create(owner=owner, name=clean, phone_e164=number, status='active')


def update_partner(owner, partner_id, name, phone):
    _owner(owner)
    partner = _active(owner).filter(pk=partner_id).first()
    if partner is None:
        raise InvalidMeasurement('That person is not in Holding Space.')
    clean = _name(name)
    number = normalize_phone(phone)
    if _active(owner).exclude(pk=partner.pk).filter(phone_e164=number).exists():
        raise InvalidMeasurement('That number is already in Holding Space.')
    partner.name = clean
    partner.phone_e164 = number
    partner.save(update_fields=['name', 'phone_e164'])
    return partner


def remove_partner(owner, partner_id):
    _owner(owner)
    updated = _active(owner).filter(pk=partner_id).update(removed_at=timezone.now())
    if not updated:
        raise InvalidMeasurement('That person is not in Holding Space.')


def partners(owner):
    _owner(owner)
    rows = list(_active(owner).prefetch_related('messages'))
    result = []
    for row in rows:
        latest = next(iter(row.messages.all()), None)
        result.append({
            'id': str(row.id), 'name': row.name, 'phone': row.display_phone(),
            'status': row.status, 'opted_in': row.status == 'active',
            'latest': None if latest is None else {
                'state': latest.state, 'label': latest.get_state_display(),
                'error_code': latest.error_code,
            },
        })
    return result


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def reach_out(owner, partner_ids, request_id, sender=None):
    """Text the selected active partners. The same request id does not send twice."""
    _owner(owner)
    if not isinstance(partner_ids, (list, tuple)) or not partner_ids:
        raise InvalidMeasurement('Choose at least one person.')
    if len(partner_ids) > LIMIT:
        raise InvalidMeasurement('Choose up to five people.')
    ids = []
    for item in partner_ids:
        cleaned = request_uuid(item)
        if cleaned not in ids:
            ids.append(cleaned)
    request_id = request_uuid(request_id)
    digest = _digest({'operation': 'holding_reach_out', 'partners': ids})
    sender = send_text if sender is None else sender
    try:
        with transaction.atomic():
            prior = _replay(owner, request_id, digest)
            if prior is not None:
                return prior
            chosen = list(_active(owner).filter(pk__in=ids))
            if len(chosen) != len(ids):
                raise InvalidMeasurement('Choose people who are still in Holding Space.')
            receipt = WriteRequest.objects.create(
                owner=owner, request_id=request_id, payload_hash=digest, response={})
            messages = []
            for partner in chosen:
                if partner.status != 'active':
                    messages.append(HoldingMessage.objects.create(
                        owner=owner, partner=partner, request=receipt, body=MESSAGE,
                        state='failed', error_code='opted_out'))
                    continue
                message = HoldingMessage.objects.create(
                    owner=owner, partner=partner, request=receipt, body=MESSAGE, state='failed')
                try:
                    message.provider_id = sender(partner.phone_e164, MESSAGE)
                    message.state = 'accepted'
                    message.error_code = ''
                except SmsError as exc:
                    message.error_code = exc.code
                message.save(update_fields=['provider_id', 'state', 'error_code', 'updated_at'])
                messages.append(message)
            result = {
                'operation': 'reach_out',
                'messages': [{
                    'id': str(item.id), 'partner_id': str(item.partner_id),
                    'state': item.state, 'error_code': item.error_code,
                } for item in messages],
            }
            receipt.response = result
            receipt.save(update_fields=['response'])
            return result
    except IntegrityError:
        prior = _replay(owner, request_id, digest)
        if prior is not None:
            return prior
        raise Conflict('A conflicting write occurred. Retry the same request.') from None


def apply_reply(phone, body):
    """Record STOP as opt out, and any other reply as acknowledgment. No health text is stored."""
    try:
        number = normalize_phone(phone)
    except InvalidMeasurement:
        return
    word = ' '.join((body or '').split()).upper()
    rows = HoldingPartner.objects.filter(phone_e164=number, removed_at__isnull=True)
    if word in STOP_WORDS:
        rows.update(status='unsubscribed')
        return
    if not word:
        return
    for partner in rows.filter(status='active'):
        latest = partner.messages.exclude(state='failed').order_by('-created_at').first()
        if latest is not None and latest.state != 'acknowledged':
            latest.state = 'acknowledged'
            latest.save(update_fields=['state', 'updated_at'])


def apply_delivery(provider_id):
    if not provider_id:
        return
    HoldingMessage.objects.filter(provider_id=provider_id, state='accepted').update(state='delivered')
