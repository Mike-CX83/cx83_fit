"""Reproducible local verification with disposable synthetic data and no services.

Run .venv/bin/python scripts/verify_local.py. The default needs no network or
listening socket. --loopback additionally requires permission to open loopback
ports, and deliberately fails if the real transport cannot be exercised.
Inherited SMS configuration and site edits are forced off. Private data and
collected static files stay in a temporary directory, outside the checkout.
An inherited temporary directory that resolves inside the checkout is refused
before any verification directory is created.
"""
import argparse
import importlib.metadata
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile


INHERITED_PREFIXES = ('MCP_', 'DASHBOARD_', 'DJANGO_', 'OWNER_', 'OURA_', 'HEALTH_CONCURRENCY_', 'SMS_')
TEMP_ENV_NAMES = ('TMPDIR', 'TEMP', 'TMP')


class UnsafeTempRoot(Exception):
    """The inherited temporary directory would write inside the source checkout."""


def _resolved(path):
    return Path(path).expanduser().resolve()


def _inside_checkout(path, repo):
    return path == repo or repo in path.parents


def validated_temp_parent(inherited, repo):
    """Return an existing temp parent outside the checkout, before any write.

    TMPDIR, TEMP, and TMP are checked in the order tempfile uses. Any value
    that resolves inside the checkout, including through a symlink or a
    relative path, refuses the run. A later variable is not used as a fallback.
    """
    repo = _resolved(repo)
    specified = [(name, inherited[name]) for name in TEMP_ENV_NAMES if inherited.get(name)]
    for name, value in specified:
        if _inside_checkout(_resolved(value), repo):
            raise UnsafeTempRoot(f'{name} resolves inside the source checkout')
    if specified:
        name = specified[0][0]
        resolved = _resolved(specified[0][1])
        if not resolved.is_dir():
            raise UnsafeTempRoot(f'{name} is not an existing directory outside the source checkout')
        return resolved
    resolved = _resolved('/tmp')
    if _inside_checkout(resolved, repo) or not resolved.is_dir():
        raise UnsafeTempRoot('no temporary directory outside the source checkout')
    return resolved


def verification_environment(inherited, root, *, loopback, temp_dir):
    """Return a child environment that cannot inherit provider or site-edit access."""
    root = _resolved(root)
    temp_dir = _resolved(temp_dir)
    if _inside_checkout(temp_dir, root):
        raise UnsafeTempRoot('temporary directory resolves inside the disposable data root')
    env = {
        key: value for key, value in inherited.items()
        if not key.startswith(INHERITED_PREFIXES)
        and key not in ('SITE_EDITS_ENABLED', *TEMP_ENV_NAMES)
    }
    safe_temp = str(temp_dir)
    env.update({
        'DASHBOARD_LOCAL_ONLY': '1',
        'DASHBOARD_ALLOWED_HOSTS': '127.0.0.1,localhost,testserver',
        'DASHBOARD_PRIVATE_ROOT': str(root),
        'DASHBOARD_STATIC_ROOT': str(root / 'staticfiles'),
        'OWNER_USERNAME': 'synthetic-owner',
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
        'PYTHONDONTWRITEBYTECODE': '1',
        'SMS_ENABLED': '0',
        'SITE_EDITS_ENABLED': '0',
        'TMPDIR': safe_temp,
        'TEMP': safe_temp,
        'TMP': safe_temp,
    })
    if loopback:
        env['DASHBOARD_TEST_LOOPBACK'] = '1'
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loopback', action='store_true', help='Also test actual Uvicorn sockets')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        temp_parent = validated_temp_parent(os.environ, repo)
    except UnsafeTempRoot as exc:
        print(f'Local verification refused: {exc}', file=sys.stderr)
        return 1
    lock = repo / 'requirements.lock'
    if not lock.is_file():
        parser.error('Resolve requirements.lock and install it in the project virtual environment first.')
    mismatches = []
    for name, version in re.findall(r'^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^\s;]+)', lock.read_text(), re.M):
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = 'missing'
        if installed != version:
            mismatches.append(f'{name}: installed {installed}; lock requires {version}')
    if mismatches:
        parser.error('Use the installed project environment:\n' + '\n'.join(mismatches))

    with tempfile.TemporaryDirectory(prefix='health-local-verification-', dir=temp_parent) as created:
        root = _resolved(created)
        if _inside_checkout(root, _resolved(repo)):
            print('Local verification refused: disposable root resolves inside the source checkout', file=sys.stderr)
            return 1
        env = verification_environment(os.environ, root, loopback=args.loopback, temp_dir=temp_parent)
        checks = [
            ('Installed dependency compatibility', ['-m', 'pip', 'check']),
            ('Django configuration', ['manage.py', 'check']),
            ('Migration consistency', ['manage.py', 'makemigrations', '--check', '--dry-run']),
            ('Static asset collection', ['manage.py', 'collectstatic', '--noinput', '--verbosity', '0']),
            ('Synthetic local acceptance and security suite',
             ['manage.py', 'test', 'tracking', 'tests', '--verbosity', '2']),
        ]
        for label, command in checks:
            print(f'\n{label}', flush=True)
            result = subprocess.run([sys.executable, *command], cwd=repo, env=env)
            if result.returncode:
                return result.returncode
    print('\nLocal application checks passed. The separate OAuth process proof, actual ChatGPT,')
    print('rendered browser/device checks, dependency advisories and deployment have separate evidence.')
    if args.loopback:
        print('Internal ASGI and actual loopback HTTP transport tests passed.')
    else:
        print('Actual socket tests were skipped. Use --loopback only where local ports are permitted.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
