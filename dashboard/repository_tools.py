"""Repository edits for the ChatGPT connector.

Read a text file, search the checkout, and replace one exact unique span.
commit_and_publish records those source files and asks the host to reload
only this dashboard. Credential and private data paths are refused. There is
no shell, no new file, and no push.
"""
import json
import time
from pathlib import Path

_BLOCKED_SEGMENTS = {
    '.git', '.venv', 'secrets', 'private', 'runtime', 'node_modules', '__pycache__', 'output',
}
_COMMIT_PREFIXES = ('dashboard/', 'tracking/', 'docs/')
_BLOCKED_NAMES = {'.env', 'credentials.json', 'mcp.json', 'rclone.conf'}
_BLOCKED_SUFFIXES = ('.pem', '.key', '.sqlite', '.sqlite3', '.local')


def repository_root() -> Path:
    from django.conf import settings
    root = getattr(settings, 'REPOSITORY_ROOT', None)
    if root is None:
        raise ValueError('Repository edits are not configured.')
    return Path(root).resolve()


def resolve_repository_file(relative_path: str) -> Path:
    trimmed = (relative_path or '').strip()
    if not trimmed or trimmed.startswith(('/', '\\')):
        raise ValueError('Use a path relative to the repository root.')
    segments = [segment for segment in Path(trimmed).parts if segment not in {'', '.'}]
    if not segments or '..' in segments or any(segment in _BLOCKED_SEGMENTS for segment in segments):
        raise ValueError('That path is outside the repository or is not available to this tool.')
    name = segments[-1]
    lowered = name.lower()
    if (name in _BLOCKED_NAMES or lowered.startswith('.env') or lowered.endswith(_BLOCKED_SUFFIXES)
            or 'password' in lowered or 'secret' in lowered or 'token' in lowered):
        raise ValueError('Credential files are not available to this tool.')
    root = repository_root()
    absolute = (root.joinpath(*segments)).resolve()
    if not absolute.is_relative_to(root) or absolute.is_symlink():
        raise ValueError('That path is outside the repository.')
    return absolute


def read_repository_source(relative_path: str, limit: int = 100_000) -> str:
    absolute = resolve_repository_file(relative_path)
    data = absolute.read_bytes()
    if b'\0' in data:
        raise ValueError('That file is binary. Read a text source file.')
    text = data.decode('utf-8')
    if len(text) > limit:
        return text[:limit] + '\n\n[truncated]'
    return text


def search_repository_source(pattern: str, limit: int = 80) -> str:
    query = (pattern or '').strip()
    if not query or len(query) > 200:
        raise ValueError('Provide a search pattern of at most 200 characters.')
    root = repository_root()
    lines = []
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        try:
            resolve_repository_file(relative)
        except ValueError:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if query in line:
                lines.append(f'{relative}:{number}:{line[:240]}')
                if len(lines) >= limit:
                    return '\n'.join(lines) + '\n[truncated]'
    return '\n'.join(lines)


def apply_repository_edit(relative_path: str, old_text: str, new_text: str) -> str:
    if not old_text:
        raise ValueError('The text to replace cannot be empty.')
    if len(old_text) > 20000 or len(new_text) > 20000:
        raise ValueError('The replacement text is too large.')
    absolute = resolve_repository_file(relative_path)
    current = read_repository_source(relative_path, limit=1_000_000)
    matches = current.count(old_text)
    if matches != 1:
        raise ValueError(f'Expected one match in {relative_path}, found {matches}.')
    absolute.write_text(current.replace(old_text, new_text, 1), encoding='utf-8')
    return f'Updated {relative_path}. Call commit_and_publish to record it and reload the live site.'


def commit_paths(paths: list[str]) -> list[str]:
    """Return the source paths allowed into a site commit."""
    if not isinstance(paths, list) or not paths or len(paths) > 20:
        raise ValueError('Provide one to twenty repository paths to commit.')
    cleaned = []
    for path in paths:
        if not isinstance(path, str):
            raise ValueError('Each commit path must be text.')
        absolute = resolve_repository_file(path)
        relative = absolute.relative_to(repository_root()).as_posix()
        if not relative.startswith(_COMMIT_PREFIXES) or not absolute.is_file():
            raise ValueError('Only existing dashboard, tracking, and docs files can be committed.')
        cleaned.append(relative)
    return cleaned


def commit_and_publish(paths: list[str], message: str) -> str:
    """Ask the host to commit the named source files and reload this dashboard."""
    cleaned = commit_paths(paths)
    summary = ' '.join((message or '').split())
    if not summary or len(summary) > 200:
        raise ValueError('Provide a commit message of at most 200 characters.')
    runtime = repository_root() / 'runtime'
    request = runtime / 'publish-request.json'
    result = runtime / 'publish-result.json'
    request_id = f'{time.time_ns()}'
    payload = json.dumps({'id': request_id, 'paths': cleaned, 'message': summary})
    temporary = runtime / 'publish-request.tmp'
    temporary.write_text(payload, encoding='utf-8')
    temporary.replace(request)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            recorded = json.loads(result.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            time.sleep(0.2)
            continue
        if recorded.get('id') != request_id:
            time.sleep(0.2)
            continue
        if recorded.get('error'):
            raise ValueError(str(recorded['error'])[:300])
        return str(recorded.get('message') or 'Committed. The site is reloading.')
    return 'Commit and publish were requested. The live site reloads after the commit is recorded.'
