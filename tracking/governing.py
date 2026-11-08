"""Private governing document for the authorized owner and connected clients.

The body is not in Git. Private storage holds `governing/current.json` and
`governing/body.txt`. Status never returns the text. The document call returns
the text only after the checksum matches. Unavailable is not a substitute rule set.
"""
import hashlib
import json
from pathlib import Path

from django.conf import settings

UNAVAILABLE = {'available': False, 'document_id': None, 'version': None, 'sha256': None}
_KEYS = ('document_id', 'version', 'sha256')


def _token(value, limit):
    return (isinstance(value, str) and 1 <= len(value) <= limit and value.isascii()
            and all(character.isalnum() or character in '-_.' for character in value))


def governing_status():
    """Return identity metadata, or unavailable. Never return document text."""
    root = Path(settings.PRIVATE_ROOT).resolve()
    pointer = root / 'governing' / 'current.json'
    if pointer.is_symlink() or not pointer.is_file():
        return dict(UNAVAILABLE)
    resolved = pointer.resolve()
    if not resolved.is_relative_to(root) or pointer.stat().st_size > 512:
        return dict(UNAVAILABLE)
    try:
        data = json.loads(pointer.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return dict(UNAVAILABLE)
    digest = data.get('sha256') if isinstance(data, dict) else None
    if (not isinstance(data, dict) or set(data) != set(_KEYS) or not _token(data.get('document_id'), 64)
            or not _token(data.get('version'), 32) or not (isinstance(digest, str) and len(digest) == 64
            and all(character in '0123456789abcdef' for character in digest))):
        return dict(UNAVAILABLE)
    return {'available': True, 'document_id': data['document_id'], 'version': data['version'], 'sha256': digest}


def governing_document():
    """Return the private text for an already authorized caller, or unavailable."""
    status = governing_status()
    if not status['available']:
        return {**status, 'text': None}
    root = Path(settings.PRIVATE_ROOT).resolve()
    body = root / 'governing' / 'body.txt'
    if body.is_symlink() or not body.is_file():
        return {**dict(UNAVAILABLE), 'text': None}
    resolved = body.resolve()
    if not resolved.is_relative_to(root) or body.stat().st_size > 200_000:
        return {**dict(UNAVAILABLE), 'text': None}
    try:
        text = body.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return {**dict(UNAVAILABLE), 'text': None}
    if hashlib.sha256(text.encode()).hexdigest() != status['sha256']:
        return {**dict(UNAVAILABLE), 'text': None}
    return {**status, 'text': text}
