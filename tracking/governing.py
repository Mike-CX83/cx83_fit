"""Availability of the owner's private governing document.

The document body is not in Git and is not read here. A later deployment may
mount a pointer at private storage `governing/current.json` with an id, a
version, and a sha256. Until that pointer exists, the document is unavailable.
Unavailable is not a substitute rule set and not permission to invent one.
"""
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
