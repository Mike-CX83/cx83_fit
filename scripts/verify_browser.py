"""Opt-in synthetic browser runner. The offline default remains scripts/verify_local.py.

Run from the repository root:

.venv/bin/python scripts/verify_browser.py --loopback \
    --playwright-module /path/to/playwright \
    --chromium /path/to/chrome-headless-shell

Playwright and Chromium are arguments for this run. They are not installed,
downloaded, or hardcoded. --loopback is required. A missing dependency or a
denied socket is a failed or blocked run, not a pass.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import zipfile

sys.dont_write_bytecode = True


PROTECTED = (
    'tracking_summaryrecord', 'tracking_summarycorrection',
    'tracking_ouraconnection', 'tracking_ourarecord',
    'tracking_ourapage', 'tracking_ourarevision',
)
WRITE_TABLES = (
    'tracking_writerequest', 'tracking_journalentry', 'tracking_journalobservation',
    'tracking_journalcorrection', 'tracking_holdingmessage',
)
CACHE_TABLES = ('tracking_journalscore', 'tracking_sobrietyday')
SNAPSHOT_TABLES = PROTECTED + WRITE_TABLES + CACHE_TABLES
EXPECTED_WRITE_ADDS = {
    'tracking_journalentry': 4,
    'tracking_journalobservation': 4,
    'tracking_journalcorrection': 8,
    'tracking_holdingmessage': 2,
    'tracking_writerequest': 10,
}
TESTED_VERSIONS = {
    'playwright': '1.65.0-alpha-2026-10-30',
    'node': 'v26.5.0',
    'chromium': 'Google Chrome for Testing 157.0.8103.15',
    'django': '5.2.19',
    'uvicorn': '0.54.0',
    'whitenoise': '6.12.0',
}
ALLOW_DIRS = ('dashboard', 'tracking', 'tests/browser')
ALLOW_FILES = {'manage.py'}
ALLOW_SUFFIXES = {'.py', '.html', '.css', '.js', '.cjs', '.svg', '.webmanifest', '.png', '.ico', '.woff', '.woff2', '.map'}
TRANSIENT_DIRS = ('source', 'data', 'home', 'tmp', 'static', 'secrets', 'profile')
REQUIRED_BROWSER_CASES = (
    'proxy rejects a foreign origin', 'proxy rejects connect',
    'desktop anonymous dashboard redirects to login', 'mobile anonymous dashboard redirects to login',
    'desktop anonymous oura redirects to login', 'mobile anonymous oura redirects to login',
    'desktop anonymous export redirects to login', 'mobile anonymous export redirects to login',
    'desktop login without csrf is rejected', 'mobile login without csrf is rejected',
    'desktop anonymous journal redirects to login', 'mobile anonymous journal redirects to login',
    'desktop wrong password stays signed out', 'mobile wrong password stays signed out',
    'desktop other user cannot open the owner dashboard', 'mobile other user cannot open the owner dashboard',
    'desktop other user cannot open an owner record', 'mobile other user cannot open an owner record',
    'desktop owner signs in', 'mobile owner signs in',
    'desktop keyboard focus moves', 'mobile keyboard focus moves',
    'desktop today has no horizontal overflow', 'mobile today has no horizontal overflow',
    'desktop shows Today', 'mobile shows Today',
    'desktop shows Journal', 'mobile shows Journal',
    'desktop shows Progress', 'mobile shows Progress',
    'desktop shows Diary', 'desktop shows Plan', 'desktop shows More', 'mobile shows More',
    'desktop diary opens', 'mobile diary opens',
    'desktop diary has no horizontal overflow', 'mobile diary has no horizontal overflow',
    'desktop plan opens', 'mobile plan opens',
    'desktop progress opens', 'mobile progress opens',
    'desktop content security policy', 'mobile content security policy',
    'desktop steady score', 'mobile steady score',
    'desktop steady value', 'mobile steady value',
    'desktop protein bar class', 'mobile protein bar class',
    'desktop steps bar class', 'mobile steps bar class',
    'desktop protein bar width', 'mobile protein bar width',
    'desktop protein chip names the metric', 'mobile protein chip names the metric',
    'desktop thin bar height', 'mobile thin bar height',
    'desktop unknown score has no value', 'mobile unknown score has no value',
    'desktop unknown score text', 'mobile unknown score text',
    'desktop known zero steps', 'mobile known zero steps',
    'desktop known zero calories', 'mobile known zero calories',
    'desktop null steps are not zero', 'mobile null steps are not zero',
    'desktop missing meal stays missing', 'mobile missing meal stays missing',
    'desktop null calories stay calories', 'mobile null calories stay calories',
    'desktop meal calories win', 'mobile meal calories win',
    'desktop alternatives has no horizontal overflow', 'mobile alternatives has no horizontal overflow',
    'desktop shows eight of ten', 'mobile shows eight of ten',
    'desktop shows eight alternative links', 'mobile shows eight alternative links',
    'desktop derived steps are not selected', 'mobile derived steps are not selected',
    'desktop omitted alternative stays off the chip', 'mobile omitted alternative stays off the chip',
    'desktop history link opens omitted alternative', 'mobile history link opens omitted alternative',
    'desktop competing sleep is not one duration', 'mobile competing sleep is not one duration',
    'desktop unique sleep states its duration', 'mobile unique sleep states its duration',
    'desktop headroom copy wraps', 'mobile headroom copy wraps',
    'desktop mixed class shows personal and test', 'mobile mixed class shows personal and test',
    'desktop long alternative wraps', 'mobile long alternative wraps',
    'prior stylesheet color is the fixture marker',
    'nutrition page one omits the oldest row', 'nutrition history link opens page two',
    'correction page one links older history', 'correction older link keeps the first revision',
    'long source and device render', 'escaped device renders', 'long device wraps',
    'long device has no horizontal overflow', 'mobile long device has no horizontal overflow',
    'legacy history stays unresolved', 'legacy inspect link opens',
    'derived history is not a token',
    'hrv method and unit render',
    'excluded controls stay unselected', 'excluded statuses stay labeled',
    'personal record stays visible without synthetic', 'synthetic record stays hidden without synthetic',
    'csv preview writes nothing',
    'desktop oura is fail closed', 'mobile oura is fail closed',
    'desktop oura page hides tokens', 'mobile oura page hides tokens',
    'desktop oura start requires confirmation', 'mobile oura start requires confirmation',
    'desktop confirmed oura start stays local', 'mobile confirmed oura start stays local',
    'desktop oura callback without state fails', 'mobile oura callback without state fails',
    'desktop export requires confirmation', 'mobile export requires confirmation',
    'desktop export download saved', 'mobile export download saved',
    'stylesheet url comes from the page',
    'old stylesheet revalidates with its validator',
    'desktop json preview writes nothing', 'mobile json preview writes nothing',
    'desktop proposal preview saves nothing', 'mobile proposal preview saves nothing',
    'desktop proposal text was not stored', 'mobile proposal text was not stored',
    'desktop intention preview saves nothing', 'mobile intention preview saves nothing',
    'desktop explicit false observation is saved', 'mobile explicit false observation is saved',
    'desktop unknown observation stays unknown', 'mobile unknown observation stays unknown',
    'desktop journal correction replaces the text', 'mobile journal correction replaces the text',
    'desktop deleted journal text leaves the list', 'mobile deleted journal text leaves the list',
    'desktop deleted journal detail is not current', 'mobile deleted journal detail is not current',
    'desktop sms is not set up', 'mobile sms is not set up',
    'desktop reach out does not send', 'mobile reach out does not send',
    'new stylesheet request carries the old validator',
    'new stylesheet etag differs', 'new stylesheet matches the current color',
    'new stylesheet revalidates with its validator',
    'cold stylesheet is an unvalidated 200',
    'desktop logout returns to login', 'mobile logout returns to login',
    'no page or console errors',
)


class UnsafeTempRoot(Exception):
    """A requested path resolves inside the source checkout."""


class MissingDependency(Exception):
    """An explicitly supplied browser tool is not usable."""


def repo_root():
    return Path(__file__).resolve().parents[1]


def _load_local():
    sys.dont_write_bytecode = True
    path = repo_root() / 'scripts' / 'verify_local.py'
    spec = importlib.util.spec_from_file_location('cx83_verify_local_for_browser', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_inherited_temps(inherited, repo):
    """Refuse every inherited temp variable that resolves inside the checkout."""
    try:
        _load_local().validated_temp_parent(inherited, repo)
    except Exception as exc:
        if exc.__class__.__name__ == 'UnsafeTempRoot':
            raise UnsafeTempRoot(str(exc)) from exc
        raise


def _no_symlink(path):
    current = Path(path.anchor)
    for part in Path(path).parts[1:]:
        current = current / part
        if current.is_symlink():
            raise UnsafeTempRoot(f'{current} is a symlink')
        if not current.exists():
            return
    if Path(path).is_symlink():
        raise UnsafeTempRoot(f'{path} is a symlink')


def fresh_root(repo, inherited, output):
    """Create one new owned root. Never chmod a preexisting or symlink path."""
    repo = Path(repo).resolve()
    assert_inherited_temps(inherited, repo)
    if output:
        requested = Path(output).expanduser()
        if requested.exists() or requested.is_symlink():
            raise UnsafeTempRoot('output directory must be a new path outside the checkout')
        _no_symlink(requested.parent)
        parent = resolved_outside(requested.parent, repo)
        if not parent.is_dir():
            raise UnsafeTempRoot('output parent is not a directory outside the checkout')
        requested.mkdir(mode=0o700)
        if requested.is_symlink() or not requested.is_dir():
            raise UnsafeTempRoot('output directory was not created as a real directory')
        return requested.resolve()
    parent = _load_local().validated_temp_parent(inherited, repo)
    root = Path(tempfile.mkdtemp(prefix='cx83-fit-browser-', dir=parent))
    if root.is_symlink():
        raise UnsafeTempRoot('temporary run root is a symlink')
    os.chmod(root, 0o700)
    return root


def _assert_source_component(repo, path):
    repo = repo.resolve()
    current = repo
    relative = path.resolve().relative_to(repo) if not path.is_symlink() else path.relative_to(repo)
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise UnsafeTempRoot(f'{current.relative_to(repo)} is a symlink and is not copied')
        resolved = current.resolve()
        if repo != resolved and repo not in resolved.parents:
            raise UnsafeTempRoot(f'{current.relative_to(repo)} resolves outside the source checkout')


def source_files(repo):
    """Copy only the bounded source files the fixture needs."""
    repo = Path(repo).resolve()
    found = []
    roots = [repo / 'manage.py']
    for relative in ALLOW_DIRS:
        directory = repo / relative
        if directory.exists():
            _assert_source_component(repo, directory)
            roots.extend(path for path in directory.rglob('*') if path.is_file() or path.is_symlink())
    for path in roots:
        if not path.exists() and not path.is_symlink():
            continue
        _assert_source_component(repo, path)
        if path.is_dir():
            continue
        relative = path.relative_to(repo)
        if path.name.startswith('.') or any(part.startswith('.') for part in relative.parts):
            continue
        if path.name not in ALLOW_FILES and path.suffix not in ALLOW_SUFFIXES:
            continue
        found.append(path)
    return sorted(found, key=lambda item: item.relative_to(repo).as_posix())


def resolved_outside(path, repo):
    resolved = Path(path).expanduser().resolve()
    if resolved == repo or repo in resolved.parents:
        raise UnsafeTempRoot(f'{path} resolves inside the source checkout')
    return resolved


def require_directory(path, label):
    resolved = Path(path).expanduser().resolve()
    package = resolved / 'package.json'
    if not package.is_file():
        raise MissingDependency(f'{label} is not an installed package directory')
    return resolved


def require_executable(path, label):
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise MissingDependency(f'{label} is not an executable file')
    return resolved


def manifest_bytes(repo, files):
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(repo).as_posix().encode()
        digest.update(relative)
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def copy_source(repo, destination, files):
    for path in files:
        target = destination / path.relative_to(repo)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if target.is_symlink() or not _same_file(path, target):
            raise UnsafeTempRoot(f'copy diverged for {path.relative_to(repo)}')


def _same_file(left, right):
    return left.read_bytes() == right.read_bytes()


def bind_loopback():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    sock.listen(64)
    sock.set_inheritable(True)
    return sock, sock.getsockname()[1]


def child_env(home, tmp, source, extra):
    env = {
        'PATH': '/usr/bin:/bin:/opt/homebrew/bin',
        'LANG': 'C.UTF-8',
        'LC_ALL': 'C.UTF-8',
        'HOME': str(home),
        'TMPDIR': str(tmp),
        'TEMP': str(tmp),
        'TMP': str(tmp),
        'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONPATH': str(source),
        'DJANGO_SETTINGS_MODULE': 'dashboard.settings',
    }
    env.update(extra)
    for key in ('NODE_OPTIONS', 'PYTHONSTARTUP', 'PYTHONINSPECT', 'PYTHONHOME'):
        env.pop(key, None)
    return env


CLEANUP = {'active': False, 'deferred': []}
CANCEL = {'defer': 0, 'pending': None}
REGISTRY = []


def begin_cleanup():
    """Ignore a repeated signal until the current owned cleanup finishes."""
    if CLEANUP['active']:
        CLEANUP['deferred'].append(True)
        return False
    CLEANUP['active'] = True
    return True


def finish_cleanup():
    CLEANUP['active'] = False


def defer_cancellation():
    CANCEL['defer'] += 1


def release_cancellation():
    CANCEL['defer'] = max(0, CANCEL['defer'] - 1)
    pending = CANCEL['pending']
    if CANCEL['defer'] == 0 and pending and not CLEANUP['active']:
        CANCEL['pending'] = None
        raise SystemExit(128 + int(pending))


def note_cancellation(signum):
    CANCEL['pending'] = signum
    CLEANUP['deferred'].append(signum)


def _ps(args, timeout):
    return subprocess.check_output(args, text=True, timeout=timeout)


def _parse_process(text):
    line = (text or '').strip()
    if not line:
        return {'state': 'absent'}
    parts = line.split(None, 2)
    if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
        return {'state': 'unknown'}
    return {'state': 'verified', 'pid': int(parts[0]), 'pgid': int(parts[1]), 'started': parts[2].strip()}


def inspect_process(pid, runner=None, timeout=3):
    """Verified identity, verified absence, or unknown inspection. Unknown is not absence."""
    runner = _ps if runner is None else runner
    try:
        text = runner(['ps', '-p', str(pid), '-o', 'pid=,pgid=,lstart='], timeout)
    except subprocess.TimeoutExpired:
        return {'state': 'unknown'}
    except subprocess.CalledProcessError as exc:
        output = exc.output or ''
        if exc.returncode == 1 and not str(output).strip():
            return {'state': 'absent'}
        return {'state': 'unknown'}
    except OSError:
        return {'state': 'unknown'}
    return _parse_process(text)


def inspect_group(pgid, runner=None, timeout=3):
    """Members of one owned group. None means the inspection failed."""
    runner = _ps if runner is None else runner
    try:
        text = runner(['ps', '-g', str(pgid), '-o', 'pid=,pgid=,lstart='], timeout)
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError as exc:
        output = exc.output or ''
        if exc.returncode == 1 and not str(output).strip():
            return []
        return None
    except OSError:
        return None
    members = []
    for line in (text or '').splitlines():
        parsed = _parse_process(line)
        if parsed['state'] == 'verified' and parsed['pgid'] == pgid:
            members.append(parsed)
    return members


def _member_map(record):
    raw = record.get('members') or {}
    if isinstance(raw, dict):
        return raw
    return {item['pid']: item for item in raw if isinstance(item, dict) and item.get('pid')}


def refresh_members(record, group=None):
    """Record current members of a still-pinned group, including children created after startup."""
    if not record.get('lease', True):
        return False
    listing = inspect_group(record.get('owned_pgid', record.get('pgid'))) if group is None else group(record.get('owned_pgid', record.get('pgid')))
    if listing is None:
        record['members_state'] = 'unknown'
        return False
    members = _member_map(record)
    for item in listing:
        pid = item.get('pid')
        prior = members.get(pid)
        if prior is None:
            members[pid] = item
        elif prior.get('started') != item.get('started') or prior.get('pgid') != item.get('pgid'):
            record.setdefault('blocked_pids', [])
            if pid not in record['blocked_pids']:
                record['blocked_pids'].append(pid)
    record['members'] = members
    record['members_state'] = 'verified'
    return True


def remember_members(record, group=None):
    return refresh_members(record, group=group)


def child_exited(proc):
    """Observe a direct child without reaping it, so its pid cannot be reused."""
    if proc is None:
        return False
    try:
        info = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except OSError:
        return False
    return info is not None


def start_logged(args, env, cwd, log_path, pass_fds=(), inspect=None, registry=None, after_register=None, group=None):
    """Register the child before log close or inspection. A local variable is not ownership."""
    registry = REGISTRY if registry is None else registry
    log = open(log_path, 'ab')
    defer_cancellation()
    proc = None
    try:
        proc = subprocess.Popen(
            args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, pass_fds=pass_fds, start_new_session=True)
        record = {
            'proc': proc, 'pid': proc.pid, 'pgid': proc.pid, 'owned_pgid': proc.pid, 'started': None,
            'members': {}, 'members_state': 'unverified', 'listeners': [proc.pid] if pass_fds else [],
            'identity': 'unverified', 'state': 'spawned', 'lease': True, 'spontaneous': False,
        }
        registry.append(record)
        if after_register is not None:
            after_register(record)
    finally:
        log.close()
        release_cancellation()
    if proc is None:
        raise RuntimeError('child was not started')
    try:
        info = inspect_process(proc.pid) if inspect is None else inspect(proc.pid)
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        info = {'state': 'unknown'}
    if not isinstance(info, dict):
        info = {'state': 'unknown'}
    if info.get('state') == 'verified' and info.get('started') and info.get('pgid') == proc.pid:
        record['started'] = info['started']
        record['identity'] = 'verified'
        refresh_members(record, group=group)
    elif info.get('state') == 'absent':
        record['identity'] = 'absent'
    else:
        record['identity'] = 'unknown'
    return record


def register_detached(registry, pid, pgid, started):
    """Register one launcher-acknowledged group. Never search for an unregistered group."""
    record = {
        'proc': None, 'pid': pid, 'pgid': pgid, 'owned_pgid': pgid, 'started': started,
        'members': {pid: {'state': 'verified', 'pid': pid, 'pgid': pgid, 'started': started}},
        'members_state': 'verified', 'listeners': [], 'identity': 'verified',
        'state': 'spawned', 'lease': True, 'spontaneous': False, 'detached': True,
    }
    registry.append(record)
    return record


def pid_alive(pid):
    """True when the pid still exists. This does not reap it."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _collect_direct_child(pid):
    """Reap one exited direct child. A grandchild or a live process returns immediately."""
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return
    except OSError:
        return


def _same_member(prior, current):
    return prior and current.get('state') == 'verified' and current.get('started') == prior.get('started') and current.get('pgid') == prior.get('pgid')


def mark_stopping(record):
    """Intentional stop. An exit that already happened is spontaneous and stays a failure."""
    if child_exited(record.get('proc')) and record.get('state') not in ('waited', 'stopping', 'reaped'):
        record['spontaneous'] = True
        return False
    record['state'] = 'stopping'
    return True


def reap_owned(records, kill=None, inspect=None, group=None):
    """Stop verified members of registered groups. Unknown inspection cannot report success."""
    kill = os.kill if kill is None else kill
    inspect = inspect_process if inspect is None else inspect
    group = inspect_group if group is None else group
    uncertain = False
    targets = {}
    owned_groups = []
    for raw in records:
        record = raw if isinstance(raw, dict) else {'pid': raw, 'pgid': raw, 'owned_pgid': raw, 'started': None, 'members': {}, 'lease': False, 'state': 'spawned'}
        if record.get('state') == 'reaped':
            continue
        pid = record.get('pid')
        pgid = record.get('owned_pgid', record.get('pgid', pid))
        proc = record.get('proc')
        pinned = proc is not None and proc.returncode is None
        if record.get('state') not in ('stopping', 'waited', 'reaped') and child_exited(proc):
            record['spontaneous'] = True
        if not pid or pid == os.getpid():
            continue
        info = inspect(pid)
        if info.get('state') == 'unknown':
            uncertain = True
            record['lease'] = False
            continue
        reused = bool(record.get('started')) and info.get('state') == 'verified' and info.get('started') != record.get('started')
        if reused or (info.get('state') == 'verified' and not pinned and not record.get('started')):
            record['lease'] = False
            continue
        leader_live = info.get('state') == 'verified' and info.get('started') == record.get('started') and info.get('pgid') == pgid
        if record.get('detached') and not leader_live:
            record['lease'] = False
            blocked = set(record.get('blocked_pids') or [])
            for member_pid, birth in _member_map(record).items():
                if member_pid == os.getpid() or member_pid in blocked:
                    continue
                current = inspect(member_pid)
                if current.get('state') == 'unknown':
                    uncertain = True
                    continue
                if current.get('state') != 'verified':
                    continue
                if current.get('started') != birth.get('started') or current.get('pgid') != birth.get('pgid'):
                    continue
                targets[member_pid] = current
            continue
        if info.get('state') == 'verified':
            if not record.get('started'):
                record['started'] = info.get('started')
            again = inspect(pid)
            if again.get('state') != 'verified' or again.get('started') != record.get('started') or again.get('pgid') != pgid:
                uncertain = True
                record['lease'] = False
                continue
            targets[pid] = again
        if record.get('lease', True) and leader_live:
            if not refresh_members(record, group=group):
                uncertain = True
            owned_groups.append(pgid)
            blocked = set(record.get('blocked_pids') or [])
            for member_pid, birth in _member_map(record).items():
                if member_pid == pid or member_pid == os.getpid() or member_pid in blocked:
                    continue
                current = inspect(member_pid)
                if current.get('state') == 'unknown':
                    uncertain = True
                    continue
                if current.get('state') != 'verified':
                    continue
                if current.get('pgid') != pgid or current.get('started') != birth.get('started'):
                    continue
                confirm = inspect(member_pid)
                if confirm.get('state') == 'verified' and confirm.get('started') == birth.get('started') and confirm.get('pgid') == pgid:
                    targets[member_pid] = confirm
                else:
                    uncertain = True
    for item in targets.values():
        if item.get('pid') == os.getpid():
            continue
        try:
            kill(item['pid'], signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 5
    while time.time() < deadline:
        alive = False
        for item in targets.values():
            _collect_direct_child(item['pid'])
            again = inspect(item['pid'])
            if again.get('state') == 'verified' and again.get('started') == item.get('started'):
                alive = True
                break
        if not alive:
            break
        time.sleep(0.1)
    for item in targets.values():
        again = inspect(item['pid'])
        if again.get('state') == 'verified' and again.get('started') == item.get('started'):
            try:
                kill(item['pid'], signal.SIGKILL)
            except OSError:
                pass
    time.sleep(0.2)
    for item in targets.values():
        _collect_direct_child(item['pid'])
    for pgid in owned_groups:
        remaining = group(pgid)
        leader = next((record.get('pid') for record in records if isinstance(record, dict) and record.get('owned_pgid', record.get('pgid')) == pgid), None)
        if remaining is None:
            uncertain = True
            continue
        if any(member.get('pid') not in (os.getpid(), leader) for member in remaining):
            uncertain = True
    for raw in records:
        proc = raw.get('proc') if isinstance(raw, dict) else None
        if proc is None or proc.returncode is not None:
            continue
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            uncertain = True
    for pgid in owned_groups:
        remaining = group(pgid)
        if remaining is None or any(member.get('pid') != os.getpid() for member in remaining):
            uncertain = True
    for raw in records:
        if not isinstance(raw, dict):
            continue
        for listener in raw.get('listeners') or []:
            heard = inspect(listener)
            if heard.get('state') != 'absent':
                uncertain = True
        if not raw.get('spontaneous'):
            heard = inspect(raw.get('pid')) if raw.get('pid') else {'state': 'absent'}
            if heard.get('state') == 'absent':
                raw['state'] = 'reaped'
                raw['lease'] = False
            else:
                uncertain = True
    return not uncertain and not any(isinstance(raw, dict) and raw.get('spontaneous') for raw in records)


def stop_owned(records):
    normalized = []
    for record in records:
        if isinstance(record, dict):
            normalized.append(record)
        else:
            info = inspect_process(record)
            normalized.append({
                'pid': record,
                'pgid': info.get('pgid', record) if info.get('state') == 'verified' else record,
                'started': info.get('started') if info.get('state') == 'verified' else None,
                'members': [],
            })
    return reap_owned(normalized)


def owned_ports_closed(ports, connect=None):
    """True only when each owned loopback port refuses a connection. A timeout is not absence."""
    connect = socket.create_connection if connect is None else connect
    for port in ports:
        if port is None:
            continue
        try:
            sock = connect(('127.0.0.1', int(port)), timeout=0.2)
        except ConnectionRefusedError:
            continue
        except OSError:
            return False
        else:
            try:
                sock.close()
            except OSError:
                pass
            return False
    return True


LAUNCHES = {'root': None, 'ack': True, 'failures': []}
LAUNCHER_SCRIPT = r'''
import json
import os
import signal
import subprocess
import sys
import time


def started(pid):
    try:
        text = subprocess.check_output(['ps', '-p', str(pid), '-o', 'lstart='], text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    text = text.strip()
    return text or None


def fd_open(number):
    try:
        os.fstat(number)
    except OSError:
        return False
    return True


def main():
    path = os.environ.get('CX83_LAUNCH_FILE') or ''
    try:
        launch = json.loads(open(path, encoding='utf-8').read())
    except (OSError, json.JSONDecodeError):
        return 78
    pid = os.getpid()
    try:
        pgid = os.getpgid(pid)
    except OSError:
        return 78
    birth = started(pid)
    if not birth:
        return 78
    payload = {
        'pid': pid, 'pgid': pgid, 'started': birth,
        'nonce': launch.get('nonce'), 'launch_id': launch.get('id'),
    }
    register_path = str(launch.get('register_path') or '')
    ack_path = str(launch.get('ack_path') or '')
    if not register_path or not ack_path or not payload['nonce'] or not payload['launch_id']:
        return 78
    os.makedirs(os.path.dirname(register_path), mode=0o700, exist_ok=True)
    temporary = register_path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)
        handle.write('\n')
    os.chmod(temporary, 0o600)
    os.replace(temporary, register_path)
    parent = int(launch.get('parent_pid') or 0)
    parent_birth = launch.get('parent_started')
    deadline = time.monotonic() + float(launch.get('deadline') or 15)
    while time.monotonic() < deadline:
        if started(parent) != parent_birth:
            return 79
        if os.path.exists(ack_path):
            try:
                ack = json.loads(open(ack_path, encoding='utf-8').read())
            except (OSError, json.JSONDecodeError):
                ack = None
            if ack == payload:
                return run_target(launch, parent, parent_birth)
        time.sleep(0.05)
    return 80


CAUGHT = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
CHILD = {'pid': None, 'forward': False, 'reaped': False, 'pending': []}


def direct_child_exited(pid):
    """Observe one direct child without reaping it, so its pid cannot be reused."""
    if not pid:
        return False
    try:
        info = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except OSError:
        return False
    return info is not None


def on_launcher_signal(signum, _frame):
    """Forward only while the direct child is still the unreaped owned pid."""
    CHILD['pending'].append(signum)
    if not CHILD['forward'] or CHILD['reaped'] or not CHILD['pid']:
        return
    try:
        os.kill(CHILD['pid'], signum)
    except OSError:
        pass


def disarm_forwarding():
    """Stop forwarding before the reap. A signal in this window is deferred."""
    CHILD['forward'] = False
    for signum in CAUGHT:
        signal.signal(signum, on_launcher_signal)


def reap_direct_child(proc):
    disarm_forwarding()
    try:
        code = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = proc.wait(timeout=5)
    CHILD['reaped'] = True
    return int(code)


def parse_process(line):
    parts = (line or '').strip().split(None, 2)
    if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
        return {'state': 'unknown'}
    return {'state': 'verified', 'pid': int(parts[0]), 'pgid': int(parts[1]), 'started': parts[2].strip()}


def inspect_member(pid):
    """Current birth and group for one pid. Unknown is not absence."""
    try:
        proc = subprocess.Popen(
            ['ps', '-p', str(pid), '-o', 'pid=,pgid=,lstart='],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        text, _unused = proc.communicate(timeout=2)
    except OSError:
        return {'state': 'unknown'}
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return {'state': 'unknown'}
    if proc.returncode == 1 and not (text or '').strip():
        return {'state': 'absent'}
    if proc.returncode != 0:
        return {'state': 'unknown'}
    parsed = parse_process(text)
    if parsed.get('state') != 'verified' or parsed.get('pid') != pid:
        return {'state': 'unknown'}
    return parsed


def group_members():
    """Verified members of this leader's group, each with the birth just observed."""
    try:
        pgid = os.getpgid(os.getpid())
        proc = subprocess.Popen(
            ['ps', '-g', str(pgid), '-o', 'pid=,pgid=,lstart='],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        text, _unused = proc.communicate(timeout=2)
    except OSError:
        return None
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return None
    if proc.returncode == 1 and not (text or '').strip():
        return []
    if proc.returncode not in (0, 1):
        return None
    members = []
    for line in (text or '').splitlines():
        if not line.strip():
            continue
        parsed = parse_process(line)
        if parsed.get('state') != 'verified':
            return None
        if parsed['pid'] in (os.getpid(), proc.pid) or parsed['pgid'] != pgid:
            continue
        members.append(parsed)
    return members


def signal_verified(signum):
    """Signal a member only after a fresh birth and group check. Never use a stale pid."""
    members = group_members()
    if members is None:
        return 'unknown'
    if not members:
        return 'empty'
    for item in members:
        current = inspect_member(item['pid'])
        if current.get('state') == 'unknown':
            return 'unknown'
        if current.get('state') != 'verified':
            continue
        if current.get('started') != item.get('started') or current.get('pgid') != item.get('pgid'):
            continue
        try:
            os.kill(item['pid'], signum)
        except OSError:
            pass
    return 'signaled'


def next_drain_action(signum):
    outcome = signal_verified(signum)
    if outcome == 'unknown':
        return 'hold'
    if outcome == 'empty':
        return 'clear'
    return 'retry'


def run_target(launch, parent, parent_birth):
    target = str(launch.get('target') or '')
    if not target or not os.path.isfile(target):
        return 78
    pending = []

    def defer(signum, _frame):
        pending.append(signum)

    for signum in CAUGHT:
        signal.signal(signum, defer)
    pause = os.environ.get('CX83_LAUNCH_PAUSE') or ''
    if pause:
        try:
            open(pause, 'w', encoding='utf-8').write('ready\n')
        except OSError:
            return 78
        gate = pause + '.go'
        limit = time.monotonic() + 10
        while not os.path.exists(gate) and time.monotonic() < limit:
            time.sleep(0.02)
    extra = tuple(number for number in (3, 4) if fd_open(number))
    child = subprocess.Popen(
        [target, *sys.argv[1:]], stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,
        pass_fds=extra, start_new_session=False)
    CHILD['pid'] = child.pid
    CHILD['reaped'] = False
    CHILD['forward'] = False
    CHILD['pending'] = []
    queued = list(pending)
    pending.clear()
    CHILD['forward'] = True
    for signum in CAUGHT:
        signal.signal(signum, on_launcher_signal)
    for signum in queued:
        if CHILD['reaped'] or not CHILD['forward']:
            break
        try:
            os.kill(child.pid, signum)
        except OSError:
            pass
    while not direct_child_exited(child.pid):
        if started(parent) != parent_birth:
            if not CHILD['reaped'] and CHILD['forward']:
                try:
                    os.kill(child.pid, signal.SIGTERM)
                except OSError:
                    pass
            break
        time.sleep(0.05)
    return drain_owned(reap_direct_child(child))


def hold_anchor(code):
    """Stay the group leader when drain is unverified. A failure code is not a successful exit."""
    path = os.environ.get('CX83_LAUNCH_STATUS') or ''
    if path:
        try:
            temporary = path + '.tmp'
            with open(temporary, 'w', encoding='utf-8') as handle:
                json.dump({'state': 'held', 'code': int(code)}, handle)
                handle.write('\n')
            os.replace(temporary, path)
        except OSError:
            pass
    disarm_forwarding()
    for signum in CAUGHT:
        signal.signal(signum, signal.SIG_IGN)
    while True:
        action = next_drain_action(signal.SIGKILL)
        if action == 'clear':
            return int(code)
        time.sleep(0.2)


def drain_owned(code):
    """TERM, then KILL, and leave only after the owned group is verified empty."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        action = next_drain_action(signal.SIGTERM)
        if action == 'hold':
            return hold_anchor(81)
        if action == 'clear':
            return int(code)
        time.sleep(0.05)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        action = next_drain_action(signal.SIGKILL)
        if action == 'hold':
            return hold_anchor(81)
        if action == 'clear':
            return int(code)
        time.sleep(0.05)
    action = next_drain_action(signal.SIGKILL)
    if action == 'clear':
        return int(code)
    return hold_anchor(81 if action == 'hold' else 82)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
'''


def prepare_browser_launches(root, target, parent_pid=None, deadline=20):
    """Write the disposable launcher and two distinct launch records. The target path is parent-owned."""
    root = Path(root)
    evidence = root / 'evidence'
    register = evidence / 'register'
    ack = evidence / 'ack'
    register.mkdir(mode=0o700, parents=True, exist_ok=True)
    ack.mkdir(mode=0o700, exist_ok=True)
    launcher = root / 'browser-launcher.py'
    interpreter = Path(sys.executable)
    if not interpreter.is_absolute() or ' ' in str(interpreter) or not interpreter.is_file():
        raise UnsafeTempRoot('browser launcher interpreter is not an absolute executable')
    script = f'#!{interpreter}\n{LAUNCHER_SCRIPT.lstrip(chr(10))}'
    if not script.startswith('#!'):
        raise UnsafeTempRoot('browser launcher shebang is not at byte zero')
    launcher.write_text(script, encoding='utf-8')
    os.chmod(launcher, 0o700)
    parent_pid = os.getpid() if parent_pid is None else int(parent_pid)
    parent = inspect_process(parent_pid)
    if parent.get('state') != 'verified':
        raise UnsafeTempRoot('browser launch parent identity is not verified')
    slots = {}
    for slot in ('warm', 'cold'):
        payload = {
            'id': slot,
            'nonce': __import__('secrets').token_hex(32),
            'register_path': str(register / f'{slot}.json'),
            'ack_path': str(ack / f'{slot}.json'),
            'parent_pid': parent_pid,
            'parent_started': parent.get('started'),
            'target': str(target),
            'deadline': deadline,
        }
        path = evidence / f'launch-{slot}.json'
        path.write_text(json.dumps(payload) + '\n', encoding='utf-8')
        os.chmod(path, 0o600)
        slots[slot] = path
    LAUNCHES['root'] = root
    LAUNCHES['ack'] = True
    LAUNCHES['failures'] = []
    return {'launcher': launcher, 'slots': slots}


def _refresh_pinned_launcher(record):
    """Refresh members only while this leader birth still owns the group."""
    if record.get('state') == 'reaped' or not record.get('lease', True):
        return
    info = inspect_process(record.get('pid'))
    if info.get('state') != 'verified':
        return
    pgid = record.get('owned_pgid', record.get('pgid'))
    if info.get('started') != record.get('started') or info.get('pgid') != pgid:
        record['lease'] = False
        return
    refresh_members(record)


def service_browser_launches():
    """Record a verified launcher before its acknowledgement. An owned exit is not a new failure."""
    root = LAUNCHES.get('root')
    if root is None:
        return []
    evidence = Path(root) / 'evidence'
    recorded = []
    for slot in ('warm', 'cold'):
        existing = next((item for item in REGISTRY if isinstance(item, dict) and item.get('launch_id') == slot), None)
        if existing is not None:
            _refresh_pinned_launcher(existing)
            continue
        path = evidence / f'launch-{slot}.json'
        if not path.exists():
            continue
        try:
            launch = json.loads(path.read_text(encoding='utf-8'))
            found = json.loads(Path(str(launch.get('register_path') or '')).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if found.get('nonce') != launch.get('nonce') or found.get('launch_id') != slot:
            if slot not in LAUNCHES['failures']:
                LAUNCHES['failures'].append(slot)
            continue
        try:
            pid = int(found.get('pid') or 0)
            pgid = int(found.get('pgid') or 0)
        except (TypeError, ValueError):
            if slot not in LAUNCHES['failures']:
                LAUNCHES['failures'].append(slot)
            continue
        info = inspect_process(pid)
        if info.get('state') == 'unknown':
            if slot not in LAUNCHES['failures']:
                LAUNCHES['failures'].append(slot)
            continue
        same = info.get('state') == 'verified' and info.get('pid') == pid and info.get('pgid') == pgid and info.get('started') == found.get('started')
        if not same:
            if slot not in LAUNCHES['failures']:
                LAUNCHES['failures'].append(slot)
            continue
        if any(isinstance(item, dict) and item.get('launch_id') == slot for item in REGISTRY):
            continue
        record = register_detached(REGISTRY, pid, pgid, info.get('started'))
        record['launch_id'] = slot
        recorded.append(record)
        if not LAUNCHES.get('ack'):
            continue
        ack = Path(str(launch.get('ack_path') or ''))
        ack.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = ack.with_suffix('.tmp')
        temporary.write_text(json.dumps({
            'pid': pid, 'pgid': pgid, 'started': info.get('started'),
            'nonce': launch.get('nonce'), 'launch_id': slot,
        }) + '\n', encoding='utf-8')
        os.chmod(temporary, 0o600)
        os.replace(temporary, ack)
    return recorded


def browser_launches_registered():
    found = {item.get('launch_id') for item in REGISTRY if isinstance(item, dict)}
    return {'warm', 'cold'} <= found and not LAUNCHES.get('failures')


def cache_windows(manifest):
    """Separate synthetic score windows from the exact personal routes that score today and the mixed day."""
    owner = manifest.get('owner_id')
    true_dates = list(manifest.get('journal_score_dates') or [])
    dates = manifest.get('dates') if isinstance(manifest.get('dates'), dict) else {}
    false_dates = []
    for value in (manifest.get('root_score_date'), dates.get('mixed'), dates.get('sleep')):
        if value and value not in false_dates:
            false_dates.append(value)
    windows = []
    for synthetic, days in ((True, true_dates), (False, false_dates)):
        windows.append({'owner_id': owner, 'dates': list(days), 'kind': 'daily_state', 'formula': 'daily-state-1', 'synthetic': synthetic})
        windows.append({'owner_id': owner, 'dates': list(days), 'kind': 'routine_alignment', 'formula': 'routine-alignment-1', 'synthetic': synthetic})
    return windows


PHASE_ERROR_NAMES = ('reads', 'preview', 'write', 'cache', 'runner')
_PHASE_SECRET = re.compile(r'(?i)\b(password|cookie|token|authorization|secret|session)\b\s*[:=]?\s*\S+')
_PHASE_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_PHASE_BLOB = re.compile(r'\b(?:eyJ[A-Za-z0-9_-]{8,}|[A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{40,}={0,2})\b')


class PhaseFailure(RuntimeError):
    """A checks phase wrote its terminal error. The parent stops through cleanup."""

    def __init__(self, payload):
        self.payload = payload
        super().__init__(payload.get('phase', 'runner'))


def sanitize_phase_error(payload):
    """Keep one short phase description. Drop secrets, markup, stacks, and extra fields."""
    source = payload if isinstance(payload, dict) else {}
    phase = source.get('phase')
    if phase not in PHASE_ERROR_NAMES:
        phase = 'runner'
    text = source.get('error')
    if not isinstance(text, str) or not text.strip():
        text = 'phase failed'
    text = text.split('\n', 1)[0]
    if '<' in text:
        text = text.split('<', 1)[0]
    text = _PHASE_EMAIL.sub('[redacted]', text)
    text = _PHASE_SECRET.sub(lambda match: match.group(1).lower() + '=[redacted]', text)
    text = _PHASE_BLOB.sub('[redacted]', text)
    text = ' '.join(text.split())[:180]
    if not text:
        text = 'phase failed'
    return {'phase': phase, 'error': text}


def owned_phase_error(evidence):
    """Read the one owned phase-error file. A symlink or unreadable file fails closed."""
    path = Path(evidence) / 'phase-error.json'
    if path.is_symlink():
        return sanitize_phase_error({})
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_bytes()[:4096].decode('utf-8', 'replace'))
    except (OSError, json.JSONDecodeError, UnicodeError):
        payload = {}
    clean = sanitize_phase_error(payload)
    text = json.dumps(clean) + '\n'
    if path.read_bytes()[:4096] != text.encode('utf-8'):
        temporary = path.with_name('phase-error.json.tmp')
        temporary.write_text(text, encoding='utf-8')
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    return clean


def wait_json(path, deadline, predicate, evidence=None):
    while time.time() < deadline:
        service_browser_launches()
        if evidence is not None:
            failure = owned_phase_error(evidence)
            if failure is not None:
                raise PhaseFailure(failure)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                payload = None
            if payload is not None and predicate(payload):
                return payload
        time.sleep(0.2)
    if evidence is not None:
        failure = owned_phase_error(evidence)
        if failure is not None:
            raise PhaseFailure(failure)
    return None


def _narrow_fields(table, columns, payload):
    data = {column: payload[index] for index, column in enumerate(columns)}
    if table == 'tracking_journalentry':
        body = data.get('body') or ''
        deleted = bool(data.get('deleted_at'))
        if deleted and body == '' and not (data.get('body_sha256') or ''):
            kind = 'tombstone'
        elif not deleted and body in {'Browser unknown stays unknown.', 'Mobile unknown stays unknown.'}:
            kind = 'unknown'
        else:
            kind = 'other'
        return {
            'id': str(data.get('id') or ''), 'owner_id': data.get('owner_id'), 'request_id': str(data.get('request_id') or ''),
            'synthetic': bool(data.get('synthetic')), 'deleted': deleted, 'body_class': kind, 'body_blank': body == '',
            'local_date': str(data.get('local_date') or ''), 'version': data.get('version'),
        }
    if table == 'tracking_journalobservation':
        raw = data.get('value_json')
        boolean = None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = None
        if isinstance(raw, dict) and isinstance(raw.get('boolean'), bool):
            boolean = raw['boolean']
        deleted = bool(data.get('deleted_at'))
        return {
            'id': str(data.get('id') or ''), 'owner_id': data.get('owner_id'), 'entry_id': str(data.get('entry_id') or ''),
            'metric_key': data.get('metric_key'), 'value_state': data.get('value_state'),
            'boolean': boolean, 'deleted': deleted, 'value_blank': raw in (None, '', {}),
        }
    if table == 'tracking_journalcorrection':
        return {
            'operation': data.get('operation'), 'entry_id': str(data.get('entry_id') or ''),
            'request_id': str(data.get('request_id') or ''), 'after_version': data.get('after_version'),
            'observation_id': str(data.get('observation_id') or ''),
        }
    if table == 'tracking_holdingmessage':
        return {'owner_id': data.get('owner_id'), 'state': data.get('state'), 'request_id': str(data.get('request_id') or '')}
    if table == 'tracking_writerequest':
        return {'id': str(data.get('id') or ''), 'owner_id': data.get('owner_id')}
    if table == 'tracking_journalscore':
        return {
            'owner_id': data.get('owner_id'), 'local_date': str(data.get('local_date') or ''),
            'formula_version': data.get('formula_version'), 'synthetic': bool(data.get('synthetic')), 'kind': data.get('kind'),
        }
    if table == 'tracking_sobrietyday':
        return {
            'owner_id': data.get('owner_id'), 'local_date': str(data.get('local_date') or ''),
            'formula_version': data.get('formula_version'), 'synthetic': bool(data.get('synthetic')),
        }
    return {}


def snapshot_db(path):
    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=5)
    try:
        found = {}
        for table in SNAPSHOT_TABLES:
            columns = [row[1] for row in con.execute(f'pragma table_info("{table}")')]
            rows = con.execute(f'select rowid, * from "{table}" order by rowid').fetchall()
            identities = {}
            for row in rows:
                payload = row[1:]
                date = ''
                if 'local_date' in columns:
                    date = str(payload[columns.index('local_date')])
                identities[str(row[0])] = {
                    'sha256': hashlib.sha256(repr(payload).encode()).hexdigest(),
                    'local_date': date,
                    'fields': _narrow_fields(table, columns, payload),
                }
            found[table] = identities
        return found
    finally:
        con.close()


def _same_rows(left, right):
    return left == right


def _added(before, after):
    return [key for key in after if key not in before]


def _changed(before, after):
    return [key for key, row in before.items() if after.get(key) != row]


def _new_fields(before, after):
    return [after[key].get('fields') or {} for key in after if key not in before]


def _new_rows(before, after):
    return [(key, after[key].get('fields') or {}) for key in after if key not in before]


def _journal_semantics(after_preview, after_all, contract):
    owner = contract.get('owner_id')
    if owner is None:
        return False
    entries = [row for _key, row in _new_rows(after_preview['tracking_journalentry'], after_all['tracking_journalentry'])]
    observations = [row for _key, row in _new_rows(after_preview['tracking_journalobservation'], after_all['tracking_journalobservation'])]
    corrections = [row for _key, row in _new_rows(after_preview['tracking_journalcorrection'], after_all['tracking_journalcorrection'])]
    holding = [row for _key, row in _new_rows(after_preview['tracking_holdingmessage'], after_all['tracking_holdingmessage'])]
    receipts = _new_rows(after_preview['tracking_writerequest'], after_all['tracking_writerequest'])
    tombstones = [row for row in entries if row.get('body_class') == 'tombstone' and row.get('body_blank') and row.get('synthetic') is True and row.get('owner_id') == owner]
    unknowns = [row for row in entries if row.get('body_class') == 'unknown' and row.get('synthetic') is True and row.get('owner_id') == owner]
    entry_ids = {row.get('id') for row in entries}
    if len(entries) != 4 or len(tombstones) != 2 or len(unknowns) != 2 or len(entry_ids) != 4 or '' in entry_ids:
        return False
    tomb_ids = {row['id'] for row in tombstones}
    unknown_ids = {row['id'] for row in unknowns}
    if len(observations) != 4 or any(row.get('owner_id') != owner or row.get('entry_id') not in entry_ids for row in observations):
        return False
    deleted_facts = [row for row in observations if row.get('deleted')]
    live_facts = [row for row in observations if not row.get('deleted')]
    if len(deleted_facts) != 2 or len(live_facts) != 2:
        return False
    if any(row.get('entry_id') not in tomb_ids or not row.get('value_blank') or row.get('boolean') is not None for row in deleted_facts):
        return False
    if any(row.get('entry_id') not in unknown_ids or row.get('metric_key') != 'explicit_choice' or row.get('value_state') != 'unknown' or row.get('boolean') is not None for row in live_facts):
        return False
    by_entry = {}
    for row in corrections:
        if row.get('entry_id') not in entry_ids:
            return False
        by_entry.setdefault(row['entry_id'], []).append(row)
    for entry_id in tomb_ids:
        chain = by_entry.get(entry_id) or []
        if [item.get('operation') for item in chain] != ['create', 'update', 'delete']:
            return False
        if [item.get('after_version') for item in chain] != [1, 2, 3]:
            return False
    for entry_id in unknown_ids:
        chain = by_entry.get(entry_id) or []
        if [item.get('operation') for item in chain] != ['create'] or chain[0].get('after_version') != 1:
            return False
    if len(holding) != 2 or any(row.get('state') != 'failed' or row.get('owner_id') != owner for row in holding):
        return False
    receipt_ids = {key for key, _row in receipts}
    if len(receipt_ids) != 10 or any(row.get('owner_id') != owner for _key, row in receipts):
        return False
    linked = {row.get('request_id') for row in entries}
    linked.update(row.get('request_id') for row in corrections)
    linked.update(row.get('request_id') for row in holding)
    return '' not in linked and linked == receipt_ids


def saved_false_lineage(after_preview, midpoint, after_all, owner):
    """The saved false observation is linked to the entry that later becomes a blank tombstone."""
    if owner is None or not midpoint:
        return False
    mid_facts = [row for _key, row in _new_rows(after_preview['tracking_journalobservation'], midpoint['tracking_journalobservation'])]
    false_rows = [row for row in mid_facts if row.get('boolean') is False and not row.get('deleted') and row.get('metric_key') == 'explicit_choice' and row.get('value_state') == 'observed' and row.get('owner_id') == owner]
    final_entries = {row.get('id'): row for _key, row in _new_rows(after_preview['tracking_journalentry'], after_all['tracking_journalentry'])}
    return len(false_rows) == 2 and all(final_entries.get(row.get('entry_id'), {}).get('body_class') == 'tombstone' for row in false_rows)


def _cache_allowed(table, fields, windows):
    for window in windows:
        if fields.get('owner_id') != window.get('owner_id'):
            continue
        if str(fields.get('local_date') or '') not in {str(item) for item in window.get('dates') or []}:
            continue
        if table == 'tracking_sobrietyday' and fields.get('formula_version') == window.get('formula') and fields.get('synthetic') is window.get('synthetic'):
            return True
        if table == 'tracking_journalscore' and fields.get('kind') == window.get('kind') and fields.get('formula_version') == window.get('formula') and fields.get('synthetic') is window.get('synthetic'):
            return True
    return False


def _cache_identity(table, before, after, windows):
    def logical(row):
        fields = row.get('fields') or {}
        return (fields.get('owner_id'), str(fields.get('local_date') or ''), fields.get('formula_version'), fields.get('synthetic'), fields.get('kind'))

    for key, row in before.items():
        fields = row.get('fields') or {}
        if not _cache_allowed(table, fields, windows):
            if after.get(key) != row:
                return False
            continue
        later = after.get(key)
        if later is not None and logical(later) != logical(row):
            return False
        if later is None:
            replaced = table == 'tracking_sobrietyday' and any(logical(other) == logical(row) for other in after.values())
            if not replaced:
                return False
    for key, row in after.items():
        if key not in before and not _cache_allowed(table, row.get('fields') or {}, windows):
            return False
    return True


def mutation_gate(before, after_reads, after_preview, after_all, contract):
    """Exact row identity, including deleted cache rows and new write semantics."""
    cases = []
    for table in PROTECTED + WRITE_TABLES:
        read_same = _same_rows(before[table], after_reads[table]) and _same_rows(after_reads[table], after_preview[table])
        cases.append({'name': f'{table} rows stay unchanged through preview', 'ok': read_same})
    for table in PROTECTED:
        cases.append({'name': f'{table} rows stay unchanged after writes', 'ok': _same_rows(before[table], after_all[table])})
    expected = contract.get('added', {})
    for table, count in expected.items():
        old_changed = _changed(after_preview[table], after_all[table])
        added = _added(after_preview[table], after_all[table])
        removed = _added(after_all[table], after_preview[table])
        cases.append({'name': f'{table} write delta is exact', 'ok': not old_changed and not removed and len(added) == count})
    windows = {
        'tracking_journalscore': contract.get('journal_score_windows') or [],
        'tracking_sobrietyday': contract.get('sobriety_windows') or [],
    }
    cache_ok = True
    for table in CACHE_TABLES:
        for snapshot in (after_reads, after_preview, after_all):
            if not _cache_identity(table, before.get(table, {}), snapshot.get(table, {}), windows[table]):
                cache_ok = False
    cases.append({'name': 'cache changes stay inside the visited dates', 'ok': cache_ok})
    if contract.get('semantics'):
        cases.append({'name': 'new journal rows match the owned write contract', 'ok': _journal_semantics(after_preview, after_all, contract)})
    if contract.get('false_snapshot'):
        cases.append({'name': 'saved false observation precedes its tombstone', 'ok': saved_false_lineage(after_preview, contract['false_snapshot'], after_all, contract.get('owner_id'))})
    return cases


def inspect_export(path, cases):
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        sidecar = json.loads(archive.read('summary-provenance-v1.json').decode('utf-8'))
        history = json.loads(archive.read('history.json').decode('utf-8'))
        blob = b''.join(archive.read(name) for name in archive.namelist())
    selection = sidecar.get('selection') if isinstance(sidecar, dict) else None
    summaries = sidecar.get('summaries') if isinstance(sidecar, dict) else None
    personal_id = cases.get('personal_id', '')
    expected_ids = set(cases.get('export_summary_ids') or [])
    history_ids = {row.get('id') for row in (history.get('summaries') or []) if isinstance(row, dict)}
    sidecar_ids = set(summaries) if isinstance(summaries, dict) else set()
    stored_personal = isinstance(summaries, dict) and all(item.get('stored_synthetic') is False for item in summaries.values())
    label = path.stem
    checks = [
        (f'{label} export sidecar is present', sidecar.get('format') == 'summary-provenance-v1' if isinstance(sidecar, dict) else False),
        (f'{label} export selection excludes synthetic', isinstance(selection, dict) and selection.get('includes_synthetic') is False and selection.get('filter') == 'stored_synthetic_flag'),
        (f'{label} export sidecar joins the personal summary', isinstance(summaries, dict) and personal_id in summaries),
        (f'{label} export history joins the owner summaries', history_ids == expected_ids and sidecar_ids == expected_ids and stored_personal),
        (f'{label} export keeps the personal marker', cases['personal_marker'].encode() in blob),
        (f'{label} export omits the synthetic marker', cases['synthetic_marker'].encode() not in blob),
        (f'{label} export omits the other owner', cases['other_marker'].encode() not in blob),
        (f'{label} export omits the disconnected token', cases['token_sentinel'].encode() not in blob),
        (f'{label} export omits the derived token', cases['derived_token_sentinel'].encode() not in blob),
        (f'{label} export omits the account key', cases['account_key_sentinel'].encode() not in blob),
        (f'{label} export omits the derived account key', cases['derived_account_key_sentinel'].encode() not in blob),
    ]
    return [{'name': name, 'ok': bool(ok)} for name, ok in checks]


def scrub(text, secrets):
    leaked = False
    for secret in secrets:
        if secret and secret in text:
            leaked = True
            text = text.replace(secret, '[redacted]')
    return text, leaked


def versions_match(found):
    return all(found.get(key) == value for key, value in TESTED_VERSIONS.items())


def case_names(results):
    assertions = results.get('assertions') if isinstance(results, dict) else None
    if not isinstance(assertions, list):
        return []
    return [item.get('name') for item in assertions]


def run_status(exit_code, results, required=REQUIRED_BROWSER_CASES):
    if exit_code != 0 or not isinstance(results, dict):
        return False
    if results.get('failures') or not results.get('ok'):
        return False
    names = case_names(results)
    if not names or len(names) != len(set(names)):
        return False
    if set(names) != set(required):
        return False
    return all(item.get('ok') and item.get('name') for item in results['assertions'])


def logical_outcome(summary):
    cases = [
        (item['name'], item['ok']) for item in summary.get('cases', [])
        if item.get('name') != 'logical outcome matches the compared run'
    ]
    return {
        'inventory_complete': summary.get('inventory_complete') is True,
        'cases': cases,
        'fixture': summary.get('fixture_outcome'),
        'source_unchanged': summary.get('source_unchanged'),
        'cleanup': summary.get('cleanup'),
    }


def outcomes_match(left, right):
    first, second = logical_outcome(left), logical_outcome(right)
    if not first['inventory_complete'] or not second['inventory_complete']:
        return False
    return first == second


def unexpected_output(text):
    if 'browser fixture startup injection' in text:
        return False
    for line in text.splitlines():
        if line.startswith('Traceback (most recent call last)') or line.startswith('ERROR ') or 'CRITICAL' in line:
            return True
    return False


EXPECTED_PROXY_REJECTS = (
    'REJECT 403 host GET /probe',
    'REJECT 403 connect CONNECT /',
)


def proxy_log_expected(text, stylesheet):
    """Accept only the two planned rejections and an exact stylesheet path."""
    if not text.strip() or not stylesheet:
        return False
    rejects = []
    saw_stylesheet = False
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith('REJECT '):
            if line not in EXPECTED_PROXY_REJECTS:
                return False
            rejects.append(line)
            continue
        if not line.startswith('FORWARD '):
            return False
        parts = line.split(' ')
        if len(parts) < 4:
            return False
        path = parts[2]
        if path == stylesheet:
            saw_stylesheet = True
            continue
        if not path.startswith('/') or '://' in path or '?' in path:
            return False
    return saw_stylesheet and set(rejects) == set(EXPECTED_PROXY_REJECTS)


def manifest_contract(payload, evidence, port):
    """Validate the generated fixture origin, dates, ids, and owned secret paths."""
    if not isinstance(payload, dict) or not isinstance(port, int):
        return False
    origin = str(payload.get('origin') or '')
    parsed = urlsplit(origin)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.port != port:
        return False
    if parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        return False
    if payload.get('timezone') != 'America/Chicago' or payload.get('owner') != 'synthetic-browser-owner':
        return False
    if payload.get('write_adds') != EXPECTED_WRITE_ADDS or not isinstance(payload.get('owner_id'), int):
        return False
    required_dates = {'positive', 'unknown', 'no_meal', 'null_food', 'meal', 'zero', 'null_steps', 'ambiguous', 'sleep', 'short_sleep', 'controls', 'csv', 'mixed'}
    dates = payload.get('dates') if isinstance(payload.get('dates'), dict) else None
    if not dates or not required_dates <= set(dates):
        return False
    score_dates = payload.get('journal_score_dates') if isinstance(payload.get('journal_score_dates'), list) else None
    sobriety_dates = payload.get('sobriety_dates') if isinstance(payload.get('sobriety_dates'), list) else None
    if not score_dates or len(sobriety_dates or []) != 14:
        return False
    seen = []
    for value in list(dates.values()) + score_dates + sobriety_dates + [payload.get('cache_sentinel'), payload.get('root_score_date')]:
        if not isinstance(value, str):
            return False
        try:
            parsed_day = __import__('datetime').date.fromisoformat(value)
        except ValueError:
            return False
        if parsed_day.isoformat() != value:
            return False
        seen.append(value)
    if payload.get('cache_sentinel') in set(score_dates) | set(sobriety_dates):
        return False
    for key in ('personal_id', 'legacy_id', 'mixed_personal_id', 'sleep_personal_id', 'csv_id', 'hrv_id', 'hrv_alt_id', 'unique_sleep_id'):
        if not isinstance(payload.get(key), str) or len(payload.get(key)) < 8:
            return False
    export_ids = payload.get('export_summary_ids')
    expected_export = [
        payload.get('sleep_personal_id'), payload.get('mixed_personal_id'),
        payload.get('legacy_id'), payload.get('personal_id'),
    ]
    if export_ids != expected_export:
        return False
    if not isinstance(payload.get('root_score_date'), str):
        return False
    root = Path(evidence).resolve().parent
    expected_secrets = {'owner_password_file': root / 'secrets' / 'owner-password', 'other_password_file': root / 'secrets' / 'other-password'}
    for key, expected in expected_secrets.items():
        path = Path(str(payload.get(key) or ''))
        if path.resolve() != expected.resolve() or root not in path.resolve().parents:
            return False
    return True


def injection_inventory(results, required=REQUIRED_BROWSER_CASES):
    assertions = results.get('assertions') if isinstance(results, dict) else None
    if not isinstance(assertions, list):
        return False
    required_rows = [item for item in assertions if item.get('name') in required]
    extra = [item for item in assertions if item.get('name') not in required]
    names = [item.get('name') for item in required_rows]
    return (
        set(names) == set(required) and len(names) == len(required)
        and all(item.get('ok') for item in required_rows)
        and len(extra) == 1 and extra[0].get('name') == 'injected-assertion' and not extra[0].get('ok')
    )


def write_summary(path, summary, secrets):
    text = json.dumps(summary, indent=2)
    text, leaked = scrub(text, secrets)
    path.write_text(text + '\n', encoding='utf-8')
    os.chmod(path, 0o600)
    return leaked


def prove_timeout(root):
    root = Path(root)
    evidence = root / 'evidence'
    evidence.mkdir(mode=0o700)
    home = root / 'home'
    tmp = root / 'tmp'
    home.mkdir(mode=0o700)
    tmp.mkdir(mode=0o700)
    registry = []
    record = start_logged(['sleep', '30'], child_env(home, tmp, root, {}), root, evidence / 'timeout.log', registry=registry)
    time.sleep(0.2)
    still_running = pid_alive(record['pid'])
    mark_stopping(record)
    cleanup = reap_owned(registry)
    summary = {
        'ok': False,
        'cases': [{'name': 'timeout', 'ok': False}],
        'failures': ['timeout'] if still_running and cleanup else ['timeout-cleanup'],
        'assertion_count': 1,
        'source_unchanged': True,
        'cleanup': 'ok' if cleanup and not pid_alive(record['pid']) else 'failed',
        'limitations': ['timeout proof uses the owned process group and identity, with a harmless sleep child'],
    }
    write_summary(root / 'summary.json', summary, [])
    try:
        remove_transient(root)
    except (OSError, UnsafeTempRoot):
        summary['cleanup'] = 'failed'
        summary['failures'] = ['timeout-cleanup']
        write_summary(root / 'summary.json', summary, [])
    return 1


def prove_startup(root, python, fixture):
    evidence = root / 'evidence'
    evidence.mkdir(mode=0o700)
    home = root / 'home'
    tmp = root / 'tmp'
    home.mkdir(mode=0o700)
    tmp.mkdir(mode=0o700)
    env = child_env(home, tmp, root, {'BROWSER_INJECT_FAILURE': 'startup'})
    registry = []
    record = start_logged([python, str(fixture)], env, root, evidence / 'startup.log', registry=registry)
    try:
        code = record['proc'].wait(timeout=20)
        record['state'] = 'waited'
    except subprocess.TimeoutExpired:
        code = 1
        mark_stopping(record)
    cleanup = reap_owned(registry)
    named = code == 3 and cleanup and not (root / 'data').exists()
    summary = {
        'ok': False,
        'cases': [{'name': 'startup', 'ok': False}],
        'failures': ['startup'] if named else ['startup-cleanup'],
        'assertion_count': 1,
        'source_unchanged': True,
        'cleanup': 'ok' if cleanup else 'failed',
        'exit_code': code,
        'limitations': ['startup injection exits before Django and before a database, under the sanitized child environment'],
    }
    write_summary(root / 'summary.json', summary, [])
    try:
        remove_transient(root)
    except (OSError, UnsafeTempRoot):
        summary['cleanup'] = 'failed'
        summary['failures'] = ['startup-cleanup']
        write_summary(root / 'summary.json', summary, [])
    return 1


def tool_versions(python, node, playwright, chromium, home, tmp):
    """Version probes use the same owned process record and deadline as other children."""
    env = child_env(home, tmp, tmp, {})
    versions = {}
    package = json.loads((Path(playwright) / 'package.json').read_text(encoding='utf-8'))
    versions['playwright'] = package.get('version', '')
    root = Path(tmp)
    log = root / 'version.log'

    def run_owned(args):
        before = log.stat().st_size if log.exists() else 0
        record = start_logged(args, env, root, log, registry=REGISTRY)
        code = 1
        try:
            code = record['proc'].wait(timeout=10)
            record['state'] = 'waited'
        except subprocess.TimeoutExpired:
            mark_stopping(record)
            code = 1
        cleaned = reap_owned([record])
        if not cleaned or code != 0:
            return []
        return log.read_bytes()[before:].decode('utf-8', 'replace').strip().splitlines()

    node_line = run_owned([node, '--version'])
    versions['node'] = node_line[0] if node_line else ''
    chrome_line = run_owned([str(chromium), '--version'])
    versions['chromium'] = chrome_line[0] if chrome_line else ''
    code = 'import importlib.metadata as meta\nfor name in ("django", "uvicorn", "whitenoise"):\n print(name + "=" + meta.version(name))'
    listed = run_owned([python, '-c', code])
    for line in listed:
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key in {'django', 'uvicorn', 'whitenoise'}:
            versions[key] = value
    return versions


def remove_transient(root):
    root = root.resolve()
    for name in TRANSIENT_DIRS:
        target = root / name
        if not target.exists() and not target.is_symlink():
            continue
        if target.is_symlink():
            raise UnsafeTempRoot(f'{name} is a symlink and was not removed')
        resolved = target.resolve()
        if root != resolved and root not in resolved.parents:
            raise UnsafeTempRoot(f'{name} resolves outside the run root')
        shutil.rmtree(resolved)


def release_launch_controls(evidence):
    """Remove expected launcher handshake files. They are not password leaks."""
    evidence = Path(evidence)
    for name in ('launch-warm.json', 'launch-cold.json'):
        path = evidence / name
        if path.is_file() and not path.is_symlink():
            path.unlink()
    for directory in (evidence / 'register', evidence / 'ack'):
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in directory.iterdir():
            if path.is_file() and not path.is_symlink():
                path.unlink()


def scrub_tree(evidence, secrets, quiet=()):
    """Redact secrets. Only an unexpected secret in an ordinary file is leakage."""
    leaked = False
    if not evidence.exists():
        return False
    passwords = [item for item in secrets if item]
    for path in evidence.rglob('*'):
        if not path.is_file() or path.is_symlink() or path.suffix == '.zip':
            continue
        raw = path.read_text(encoding='utf-8', errors='replace')
        text, found = scrub(raw, list(passwords) + [item for item in quiet if item])
        if any(item in raw for item in passwords):
            leaked = True
        if found:
            path.write_text(text, encoding='utf-8')
    return leaked


def run_browser(repo, root, args, tools):
    evidence = root / 'evidence'
    source = root / 'source'
    private = root / 'data'
    static_root = root / 'static'
    home = root / 'home'
    tmp = root / 'tmp'
    app_sock = proxy_sock = None
    app_port = proxy_port = None
    REGISTRY.clear()
    processes = REGISTRY
    secrets = []
    files = source_files(repo)
    before = manifest_bytes(repo, files)
    anchor = args.anchor_date or __import__('datetime').datetime.now(
        __import__('zoneinfo').ZoneInfo('America/Chicago')).date().isoformat()
    summary = {
        'ok': False, 'cases': [], 'failures': [], 'assertion_count': 0,
        'source_unchanged': False, 'cleanup': 'failed', 'anchor': anchor,
        'timezone': 'America/Chicago', 'versions': {}, 'limitations': [
            'This is a local synthetic browser run, not hosted ChatGPT, iPhone, Safari, or a provider acceptance.',
            'The anchor is the America/Chicago date because the overview route rejects a future local date.',
            'Measurement history uses a page of 25 and is not this 30 plus 20 sample.',
            'Headroom can update JournalScore during a read. Summary, correction, Oura, receipt, journal, and holding bytes are checked separately.',
            'The app network guard is a language boundary. The Chromium sandbox stays enabled.',
        ],
    }
    node_code = 1
    previous_signals = {}
    def _stop(signum, _frame):
        if CANCEL['defer'] or CLEANUP['active']:
            note_cancellation(signum)
            return
        if not begin_cleanup():
            return
        try:
            reap_owned(processes)
        finally:
            finish_cleanup()
        raise SystemExit(128 + signum)
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_signals[signum] = signal.signal(signum, _stop)
    try:
        for path in (evidence, private, static_root, home, tmp):
            path.mkdir(mode=0o700)
        copy_source(repo, source, files)
        app_sock, app_port = bind_loopback()
        proxy_sock, proxy_port = bind_loopback()
        summary['versions'] = tool_versions(tools['python'], tools['node'], tools['playwright'], tools['chromium'], home, tmp)
        if not versions_match(summary['versions']):
            summary['failures'].append('version-contract')
            return 1
        proxy_env = child_env(home, tmp, source, {
            'PROXY_LISTEN_FD': str(proxy_sock.fileno()),
            'APP_PORT': str(app_port),
            'PROXY_LOG': str(evidence / 'proxy.log'),
        })
        start_logged(
            [tools['python'], str(source / 'tests' / 'browser' / 'loopback_proxy.py')],
            proxy_env, source, evidence / 'proxy-process.log', (proxy_sock.fileno(),), registry=processes)
        app_env = child_env(home, tmp, source, {
            'DASHBOARD_LOCAL_ONLY': '1',
            'DASHBOARD_ALLOWED_HOSTS': '127.0.0.1,localhost,testserver',
            'DASHBOARD_PRIVATE_ROOT': str(private),
            'DASHBOARD_STATIC_ROOT': str(static_root),
            'OWNER_USERNAME': 'synthetic-browser-owner',
            'DJANGO_SECRET_KEY': __import__('secrets').token_urlsafe(64),
            'SMS_ENABLED': '0',
            'SITE_EDITS_ENABLED': '0',
            'OURA_ENABLED': '0',
            'MCP_WRITES_ENABLED': '0',
            'MCP_AUTH_MODE': 'external',
            'BROWSER_EVIDENCE': str(evidence),
            'BROWSER_APP_GENERATION': '1',
            'BROWSER_ANCHOR': anchor,
            'APP_PORT': str(app_port),
            'APP_LISTEN_FD': str(app_sock.fileno()),
            'BROWSER_INJECT_FAILURE': args.inject_failure or '',
        })
        app = start_logged(
            [tools['python'], str(source / 'tests' / 'browser' / 'fixture_app.py')],
            app_env, source, evidence / 'app.log', (app_sock.fileno(),), registry=processes)
        deadline = time.time() + min(args.timeout, 120)
        ready = wait_json(evidence / 'ready.json', deadline, lambda item: item.get('generation') == '1')
        if ready is None:
            summary['failures'].append('startup')
            return 1
        db_path = private / 'dashboard.sqlite3'
        before_sql = snapshot_db(db_path)
        (evidence / 'sql-before.json').write_text(json.dumps(before_sql, indent=2), encoding='utf-8')
        manifest_path = evidence / 'fixture-cases.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
        if not manifest_contract(manifest, evidence, app_port):
            summary['failures'].append('manifest-contract')
            return 1
        node_env = child_env(home, tmp, source, {
            'PLAYWRIGHT_MODULE': str(tools['playwright']),
            'CX83_BROWSER_LAUNCHER': str(prepare_browser_launches(root, tools['chromium'])['launcher']),
            'PROXY_SERVER': f'http://127.0.0.1:{proxy_port}',
            'PROXY_PORT': str(proxy_port),
            'MANIFEST': str(evidence / 'fixture-cases.json'),
            'EVIDENCE': str(evidence),
            'BROWSER_INJECT_FAILURE': args.inject_failure or '',
        })
        node = start_logged(
            [tools['node'], str(source / 'tests' / 'browser' / 'checks.cjs')],
            node_env, source, evidence / 'node.log', registry=processes)
        run_deadline = time.time() + args.timeout
        reads = wait_json(evidence / 'reads-done.json', run_deadline, lambda item: item.get('phase') == 'reads-done', evidence)
        if reads is None:
            summary['failures'].append('reads-timeout')
            return 1
        after_reads = snapshot_db(db_path)
        (evidence / 'sql-reads.json').write_text(json.dumps(after_reads, indent=2), encoding='utf-8')
        (evidence / 'continue.json').write_text(json.dumps({'phase': 'continue'}), encoding='utf-8')
        preview = wait_json(evidence / 'preview-done.json', run_deadline, lambda item: item.get('phase') == 'preview-done', evidence)
        if preview is None:
            summary['failures'].append('preview-timeout')
            return 1
        after_preview = snapshot_db(db_path)
        (evidence / 'sql-preview.json').write_text(json.dumps(after_preview, indent=2), encoding='utf-8')
        (evidence / 'writes-continue.json').write_text(json.dumps({'phase': 'writes'}), encoding='utf-8')
        false_saved = wait_json(evidence / 'false-saved.json', run_deadline, lambda item: item.get('phase') == 'false-saved', evidence)
        if false_saved is None:
            summary['failures'].append('false-snapshot-timeout')
            return 1
        false_snapshot = snapshot_db(db_path)
        (evidence / 'sql-false.json').write_text(json.dumps(false_snapshot, indent=2), encoding='utf-8')
        (evidence / 'false-continue.json').write_text(json.dumps({'phase': 'false-continue'}), encoding='utf-8')
        cache = wait_json(evidence / 'cache-ready.json', run_deadline, lambda item: item.get('phase') == 'revalidated', evidence)
        if cache is None:
            summary['failures'].append('cache-timeout')
            return 1
        current_css = (evidence / 'css-current.bin').read_bytes()
        css_path = static_root / 'tracking' / 'app.css'
        css_path.write_bytes(current_css)
        os.utime(css_path, (1700000000, 1700000000))
        if not mark_stopping(app) or not reap_owned([app]):
            summary['failures'].append('restart-cleanup')
            return 1
        if evidence.joinpath('ready.json').exists():
            evidence.joinpath('ready.json').unlink()
        app_env['BROWSER_APP_GENERATION'] = '2'
        app = start_logged(
            [tools['python'], str(source / 'tests' / 'browser' / 'fixture_app.py')],
            app_env, source, evidence / 'app-restart.log', (app_sock.fileno(),), registry=processes)
        restarted = wait_json(evidence / 'ready.json', time.time() + 60, lambda item: item.get('generation') == '2', evidence)
        if restarted is None:
            summary['failures'].append('restart')
            return 1
        (evidence / 'cache-swapped.json').write_text(json.dumps({'phase': 'swapped'}), encoding='utf-8')
        refresh_members(node)
        node['state'] = 'waited'
        while node['proc'].poll() is None:
            if time.time() > run_deadline:
                raise subprocess.TimeoutExpired(node['proc'].args, args.timeout)
            failure = owned_phase_error(evidence)
            if failure is not None:
                raise PhaseFailure(failure)
            service_browser_launches()
            time.sleep(0.05)
        node_code = node['proc'].returncode
        if not browser_launches_registered():
            summary['failures'].append('browser-registration')
        results = {}
        results_path = evidence / 'results.json'
        if results_path.exists():
            results = json.loads(results_path.read_text(encoding='utf-8'))
        summary['cases'].extend(results.get('assertions') or [])
        summary['failures'].extend(results.get('failures') or [])
        summary['inventory_complete'] = run_status(node_code, results)
        if not summary['inventory_complete']:
            if args.inject_failure == 'assertion' and injection_inventory(results):
                pass
            elif 'browser-checks' not in summary['failures']:
                summary['failures'].append('browser-checks')
        for log_name in ('app.log', 'app-restart.log', 'node.log', 'proxy-process.log'):
            log_path = evidence / log_name
            if log_path.exists() and unexpected_output(log_path.read_text(encoding='utf-8', errors='replace')):
                summary['failures'].append('unexpected-stderr')
                break
        summary['fixture_outcome'] = {
            'anchor': manifest.get('anchor'),
            'timezone': manifest.get('timezone'),
            'write_adds': manifest.get('write_adds'),
        }
        exports = sorted(path for path in evidence.glob('export*.zip') if path.is_file() and not path.is_symlink())
        if len(exports) < 2:
            summary['cases'].append({'name': 'both export zips downloaded', 'ok': False})
        for export in exports:
            summary['cases'].extend(inspect_export(export, manifest))
            export.unlink()
        if not mark_stopping(app) or not reap_owned([app]):
            summary['failures'].append('app-cleanup')
        after_all = snapshot_db(db_path)
        (evidence / 'sql-after.json').write_text(json.dumps(after_all, indent=2), encoding='utf-8')
        contract = {
            'added': EXPECTED_WRITE_ADDS,
            'owner_id': manifest.get('owner_id'),
            'semantics': True,
            'false_snapshot': false_snapshot,
            'journal_score_windows': cache_windows(manifest),
            'sobriety_windows': [
                {'owner_id': manifest.get('owner_id'), 'dates': manifest.get('sobriety_dates') or [], 'formula': 'sobriety-pattern-1', 'synthetic': True},
            ],
        }
        if manifest.get('write_adds') != EXPECTED_WRITE_ADDS:
            summary['failures'].append('write-contract')
        summary['cases'].extend(mutation_gate(before_sql, after_reads, after_preview, after_all, contract))
        proxy_log = (evidence / 'proxy.log').read_text(encoding='utf-8') if (evidence / 'proxy.log').exists() else ''
        stylesheet = ''
        style_path = evidence / 'stylesheet.json'
        if style_path.exists():
            stylesheet = json.loads(style_path.read_text(encoding='utf-8')).get('path', '')
        summary['cases'].append({'name': 'proxy log matches the discovered stylesheet', 'ok': proxy_log_expected(proxy_log, stylesheet)})
    except subprocess.TimeoutExpired:
        summary['failures'].append('timeout')
        node_code = 1
        return 1
    except PhaseFailure as failure:
        summary['failures'].append('phase-error')
        summary['phase_error'] = {'phase': failure.payload['phase'], 'error': failure.payload['error']}
        node_code = 1
        return 1
    finally:
        defer_cancellation()
        try:
            LAUNCHES['ack'] = False
            service_browser_launches()
            for record in processes:
                if isinstance(record, dict) and record.get('spontaneous'):
                    summary['failures'].append('unexpected-child-exit')
                    break
            if begin_cleanup():
                try:
                    cleanup = reap_owned(processes)
                finally:
                    finish_cleanup()
            else:
                cleanup = False
            for path in evidence.glob('export*.zip'):
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            for sock in (app_sock, proxy_sock):
                if sock is None:
                    continue
                try:
                    sock.close()
                except OSError:
                    pass
            ports_closed = owned_ports_closed([app_port, proxy_port])
            for name in ('owner-password', 'other-password'):
                secret_path = root / 'secrets' / name
                if secret_path.exists() and not secret_path.is_symlink():
                    secrets.append(secret_path.read_text(encoding='utf-8').strip())
            nonces = []
            for slot in ('warm', 'cold'):
                launch_path = evidence / f'launch-{slot}.json'
                if launch_path.exists() and not launch_path.is_symlink():
                    try:
                        nonces.append(str(json.loads(launch_path.read_text(encoding='utf-8')).get('nonce') or ''))
                    except (OSError, json.JSONDecodeError):
                        pass
            release_launch_controls(evidence)
            leaked = scrub_tree(evidence, secrets, nonces)
            try:
                remove_transient(root)
                removed = True
            except (OSError, UnsafeTempRoot):
                removed = False
            after = manifest_bytes(repo, source_files(repo))
            summary['source_unchanged'] = after == before
            summary['cases'].append({'name': 'source bytes unchanged', 'ok': summary['source_unchanged']})
            summary['cases'].append({'name': 'evidence does not retain passwords', 'ok': not leaked})
            summary['cases'].append({'name': 'owned ports are closed', 'ok': ports_closed})
            summary['cleanup'] = 'ok' if cleanup and removed and ports_closed and not any(pid_alive(item['pid']) for item in processes) else 'failed'
            summary['cases'].append({'name': 'owned processes cleaned up', 'ok': summary['cleanup'] == 'ok'})
            summary['cases'].append({'name': 'transient artifacts removed', 'ok': removed})
            if summary['cleanup'] != 'ok':
                summary['failures'].append('cleanup')
            if not summary['source_unchanged']:
                summary['failures'].append('source-mutation')
            failed_cases = [item['name'] for item in summary['cases'] if not item['ok']]
            summary['failures'].extend(name for name in failed_cases if name not in summary['failures'])
            forced = args.inject_failure == 'assertion' and 'injected-assertion' in summary['failures']
            other_failures = [name for name in summary['failures'] if name != 'injected-assertion']
            if forced and not other_failures and summary['cleanup'] == 'ok' and summary['source_unchanged']:
                summary['ok'] = False
                summary['injected'] = True
            else:
                summary['ok'] = not summary['failures'] and summary['cleanup'] == 'ok' and summary['source_unchanged'] and node_code == 0
            if args.compare:
                compared = json.loads(Path(args.compare).read_text(encoding='utf-8'))
                matched = outcomes_match(compared, summary)
                summary['cases'].append({'name': 'logical outcome matches the compared run', 'ok': matched})
                if not matched:
                    summary['ok'] = False
                    summary['failures'].append('compare')
            summary['assertion_count'] = len(summary['cases'])
            write_summary(root / 'summary.json', summary, secrets + nonces)
            print('browser runner: ' + ('pass' if summary['ok'] else 'fail'))
            print(root / 'summary.json')
            if summary['failures']:
                print('failures: ' + ', '.join(summary['failures']))
        finally:
            for signum, previous in previous_signals.items():
                signal.signal(signum, previous)
            release_cancellation()

def command(argv):
    parser = argparse.ArgumentParser(description='Synthetic loopback browser checks')
    parser.add_argument('--loopback', action='store_true')
    parser.add_argument('--playwright-module', default='')
    parser.add_argument('--chromium', default='')
    parser.add_argument('--node', default='')
    parser.add_argument('--output-dir', default='')
    parser.add_argument('--anchor-date', default='')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--inject-failure', choices=['assertion', 'startup', 'timeout'], default='')
    parser.add_argument('--compare', default='')
    args = parser.parse_args(argv)
    if not args.loopback:
        print('Pass --loopback to run the synthetic browser checks. scripts/verify_local.py stays the offline default.', file=sys.stderr)
        return 2
    if not 1 <= args.timeout <= 300:
        print('timeout must be between 1 and 300 seconds', file=sys.stderr)
        return 2
    repo = repo_root()
    python = repo / '.venv' / 'bin' / 'python'
    if not python.is_file():
        print('the project virtualenv python is missing', file=sys.stderr)
        return 2
    try:
        if args.inject_failure == 'timeout':
            root = fresh_root(repo, os.environ, args.output_dir)
            code = prove_timeout(root)
            print(root / 'summary.json')
            return code
        if args.inject_failure == 'startup':
            root = fresh_root(repo, os.environ, args.output_dir)
            code = prove_startup(root, str(python), repo / 'tests' / 'browser' / 'fixture_app.py')
            print(root / 'summary.json')
            return code
        node = args.node or shutil.which('node') or ''
        tools = {
            'python': str(python),
            'node': str(require_executable(node, 'node')) if node else '',
            'playwright': require_directory(args.playwright_module, 'playwright'),
            'chromium': require_executable(args.chromium, 'chromium'),
        }
        if not tools['node']:
            raise MissingDependency('node is not on PATH and was not supplied')
    except (MissingDependency, UnsafeTempRoot, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        root = fresh_root(repo, os.environ, args.output_dir)
    except UnsafeTempRoot as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        code = run_browser(repo, root, args, tools)
    except Exception as exc:
        print(f'browser runner failed: {exc.__class__.__name__}: {exc}', file=sys.stderr)
        return 1
    summary = json.loads((root / 'summary.json').read_text(encoding='utf-8'))
    if args.inject_failure == 'assertion':
        print('injection: ' + ('named failure with cleanup' if summary.get('injected') else 'not isolated'))
        return 1
    return 0 if summary.get('ok') else (code or 1)


if __name__ == '__main__':
    raise SystemExit(command(sys.argv[1:]))
