"""Offline safety checks for the synthetic browser runner. No browser and no socket."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import signal

from django.test import SimpleTestCase


REPO = Path(__file__).resolve().parents[1]


def load(name, relative):
    path = REPO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load('cx83_verify_browser_under_test', 'scripts/verify_browser.py')
PROXY = load('cx83_browser_proxy_under_test', 'tests/browser/loopback_proxy.py')
FIXTURE = load('cx83_browser_fixture_under_test', 'tests/browser/fixture_app.py')
REAL_SOCKETS = (
    socket.create_connection,
    socket.getaddrinfo,
    socket.socket.connect,
    socket.socket.connect_ex,
)


class BrowserRunnerSafetyTests(SimpleTestCase):
    def setUp(self):
        self._restore_sockets()
        self._clear_runtime()

    def tearDown(self):
        self._restore_sockets()
        self._clear_runtime()

    def _clear_runtime(self):
        RUNNER.CLEANUP['active'] = False
        RUNNER.CLEANUP['deferred'].clear()
        RUNNER.CANCEL['defer'] = 0
        RUNNER.CANCEL['pending'] = None
        RUNNER.LAUNCHES['root'] = None
        RUNNER.LAUNCHES['ack'] = True
        RUNNER.LAUNCHES['failures'] = []
        leaked = list(RUNNER.REGISTRY)
        RUNNER.REGISTRY.clear()
        if leaked:
            RUNNER.reap_owned(leaked)

    def _restore_sockets(self):
        socket.create_connection = REAL_SOCKETS[0]
        socket.getaddrinfo = REAL_SOCKETS[1]
        socket.socket.connect = REAL_SOCKETS[2]
        socket.socket.connect_ex = REAL_SOCKETS[3]
        self.assertIs(socket.create_connection, REAL_SOCKETS[0])
        self.assertIs(socket.getaddrinfo, REAL_SOCKETS[1])
        self.assertIs(socket.socket.connect, REAL_SOCKETS[2])
        self.assertIs(socket.socket.connect_ex, REAL_SOCKETS[3])
    def test_missing_loopback_does_not_start(self):
        self.assertEqual(RUNNER.command([]), 2)

    def test_output_inside_the_checkout_creates_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / 'repo'
            repo.mkdir()
            target = repo / 'run'
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.fresh_root(repo, {}, str(target))
            self.assertFalse(target.exists())

    def test_symlink_temp_root_creates_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'repo'
            outside = root / 'outside'
            repo.mkdir()
            outside.mkdir()
            link = outside / 'link'
            link.symlink_to(repo)
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.fresh_root(repo, {'TMPDIR': str(link)}, '')
            self.assertEqual(list(repo.iterdir()), [])
            self.assertEqual([item.name for item in outside.iterdir()], ['link'])

    def test_missing_browser_tools_are_explicit(self):
        with self.assertRaises(RUNNER.MissingDependency):
            RUNNER.require_executable('/no/such/chromium', 'chromium')
        with self.assertRaises(RUNNER.MissingDependency):
            RUNNER.require_directory('/no/such/playwright', 'playwright')

    def _decide(self, method, target, headers, port=9, version='HTTP/1.1'):
        lines = [f'{name}: {value}' for name, value in headers.items()]
        return PROXY.decide([method, target, version], lines, port)

    def test_proxy_rejects_malformed_and_foreign_requests(self):
        self.assertEqual(self._decide('CONNECT', 'example.invalid:443', {'Host': 'example.invalid:443'})[0], 'reject')
        self.assertEqual(self._decide('GET', 'http://example.invalid/probe', {'Host': 'example.invalid'})[1], 403)
        self.assertEqual(self._decide('GET', 'http://127.0.0.1:9/login/', {'Host': '127.0.0.1:9', 'Upgrade': 'websocket'})[1], 403)
        self.assertEqual(self._decide('GET', 'http://127.0.0.1:9/login/', {'Host': '127.0.0.1:9', 'Content-Length': 'nope'})[1], 400)
        self.assertEqual(self._decide('POST', 'http://127.0.0.1:9/export/', {'Host': '127.0.0.1:9', 'Content-Length': '2000000'})[1], 413)
        self.assertEqual(self._decide('GET', 'http://127.0.0.1:8/login/', {'Host': '127.0.0.1:8'})[1], 403)
        self.assertEqual(PROXY.decide(['GET', '/only-two'], ['Host: 127.0.0.1:9'], 9)[1], 400)
        self.assertEqual(self._decide('GET', 'http://127.0.0.1:9/login/', {})[1], 400)
        self.assertEqual(self._decide('GET', 'http://127.0.0.1:9/login/', {'Host': 'example.invalid'})[1], 403)
        duplicate = PROXY.decide(
            ['POST', 'http://127.0.0.1:9/export/', 'HTTP/1.1'],
            ['Host: 127.0.0.1:9', 'Content-Length: 1', 'Content-Length: 2'], 9)
        self.assertEqual(duplicate[1], 400)
        bad_port = PROXY.decide(
            ['GET', 'http://127.0.0.1:notaport/login/', 'HTTP/1.1'],
            ['Host: 127.0.0.1:9'], 9)
        self.assertEqual(bad_port[0], 'reject')
        forwarded = self._decide(
            'GET', 'http://127.0.0.1:9/static/tracking/app.css?v=discovered', {'Host': '127.0.0.1:9'})
        self.assertEqual(forwarded[0], 'forward')
        self.assertEqual(forwarded[1], '/static/tracking/app.css?v=discovered')

    def test_network_guard_denies_calls_before_the_underlying_connect(self):
        import socket
        calls = []

        def create_connection(address, *args, **kwargs):
            calls.append(('create_connection', address))

        def getaddrinfo(host, *args, **kwargs):
            calls.append(('getaddrinfo', host))
            return []

        def connect(self, address):
            calls.append(('connect', address))

        def connect_ex(self, address):
            calls.append(('connect_ex', address))
            return 0

        saved = FIXTURE.install_network_guard(originals={
            'create_connection': create_connection,
            'getaddrinfo': getaddrinfo,
            'connect': connect,
            'connect_ex': connect_ex,
        })
        try:
            with self.assertRaises(OSError):
                socket.getaddrinfo('example.invalid', 80)
            with self.assertRaises(OSError):
                socket.create_connection(('10.1.2.3', 443))
            denied = socket.socket()
            allowed = socket.socket()
            try:
                with self.assertRaises(OSError):
                    denied.connect(('10.1.2.3', 443))
                self.assertEqual(allowed.connect_ex(('10.1.2.3', 443)), 13)
            finally:
                denied.close()
                allowed.close()
            self.assertEqual(calls, [])
        finally:
            FIXTURE.restore_network_guard(saved)
        self.assertEqual(calls, [])
        self._restore_sockets()

    def test_allowed_owned_endpoint_reaches_the_supplied_original(self):
        import socket
        calls = []
        saved = FIXTURE.install_network_guard(
            allowed=(('127.0.0.1', 9),),
            originals={
                'create_connection': lambda address, *args, **kwargs: calls.append(address),
                'getaddrinfo': socket.getaddrinfo,
                'connect': lambda self, address: calls.append(address),
                'connect_ex': lambda self, address: calls.append(address) or 0,
            })
        try:
            owned = socket.socket()
            denied = socket.socket()
            try:
                owned.connect(('127.0.0.1', 9))
                self.assertEqual(denied.connect_ex(('10.9.8.7', 80)), 13)
            finally:
                owned.close()
                denied.close()
        finally:
            FIXTURE.restore_network_guard(saved)
        self.assertEqual(calls, [('127.0.0.1', 9)])
        self._restore_sockets()

    def test_closed_environment_rejects_provider_settings_before_django(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / 'private'
            static_root = root / 'static'
            private.mkdir()
            static_root.mkdir()
            env = {
                'DASHBOARD_LOCAL_ONLY': '1', 'SMS_ENABLED': '0', 'SITE_EDITS_ENABLED': '0',
                'OURA_ENABLED': '0', 'MCP_WRITES_ENABLED': '0', 'MCP_AUTH_MODE': 'external',
                'OWNER_USERNAME': 'synthetic-browser-owner', 'DJANGO_SECRET_KEY': 'fabricated-test-secret',
                'DASHBOARD_PRIVATE_ROOT': str(private), 'DASHBOARD_STATIC_ROOT': str(static_root),
            }
            FIXTURE.assert_closed_environment(env, REPO)
            leaked = dict(env)
            leaked['OURA_CLIENT_SECRET_FILE'] = str(root / 'fabricated-secret')
            with self.assertRaises(SystemExit):
                FIXTURE.assert_closed_environment(leaked, REPO)

    def test_empty_or_failed_results_cannot_pass(self):
        self.assertFalse(RUNNER.run_status(0, {'ok': True, 'assertions': [], 'failures': []}))
        self.assertFalse(RUNNER.run_status(0, {'ok': False, 'assertions': [{'name': 'one', 'ok': False}], 'failures': ['one']}))
        self.assertFalse(RUNNER.run_status(1, {'ok': True, 'assertions': [{'name': 'one', 'ok': True}], 'failures': []}))
        self.assertFalse(RUNNER.run_status(0, {'ok': True, 'assertions': [{'name': 'one', 'ok': True}], 'failures': []}))
        complete = [{'name': name, 'ok': True} for name in RUNNER.REQUIRED_BROWSER_CASES]
        self.assertTrue(RUNNER.run_status(0, {'ok': True, 'assertions': complete, 'failures': []}))
        self.assertFalse(RUNNER.run_status(0, {'ok': True, 'assertions': complete + [complete[0]], 'failures': []}))

    def test_two_incomplete_runs_are_not_repeatable(self):
        partial = {
            'inventory_complete': False,
            'cases': [{'name': 'one', 'ok': True}],
            'fixture_outcome': {'rows': 1},
            'source_unchanged': True,
            'cleanup': 'ok',
        }
        self.assertFalse(RUNNER.outcomes_match(partial, dict(partial)))

    def test_version_contract_is_exact(self):
        self.assertTrue(RUNNER.versions_match(dict(RUNNER.TESTED_VERSIONS)))
        changed = dict(RUNNER.TESTED_VERSIONS)
        changed['django'] = '0.0.0'
        self.assertFalse(RUNNER.versions_match(changed))
        self.assertFalse(RUNNER.versions_match({}))

    def test_child_environment_drops_inherited_interpreters(self):
        env = RUNNER.child_env(
            Path('/tmp/cx83-fit-home'), Path('/tmp/cx83-fit-tmp'), Path('/tmp/cx83-fit-source'),
            {'NODE_OPTIONS': '--require /tmp/injected.js', 'PYTHONSTARTUP': '/tmp/startup.py'})
        self.assertNotIn('NODE_OPTIONS', env)
        self.assertNotIn('PYTHONSTARTUP', env)
        self.assertEqual(env['PYTHONPATH'], '/tmp/cx83-fit-source')
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')

    def test_source_allowlist_rejects_private_files_and_symlinks(self):
        relatives = [path.relative_to(REPO).as_posix() for path in RUNNER.source_files(REPO)]
        self.assertTrue(relatives)
        self.assertTrue(all(
            item == 'manage.py' or item.startswith(('dashboard/', 'tracking/', 'tests/browser/'))
            for item in relatives))
        self.assertFalse(any(
            item.startswith(('docs/', 'private/', 'secrets/')) or item.endswith(('.json', '.sqlite3', '.env'))
            for item in relatives))
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / 'repo'
            dashboard = repo / 'dashboard'
            dashboard.mkdir(parents=True)
            (repo / 'manage.py').write_text('print("synthetic")\n', encoding='utf-8')
            (dashboard / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
            (repo / 'docs').mkdir()
            (repo / 'docs' / 'Personal_Health.txt').write_text('fabricated\n', encoding='utf-8')
            (repo / 'credentials.json').write_text('{}\n', encoding='utf-8')
            (repo / '.env.local').write_text('TOKEN=fabricated\n', encoding='utf-8')
            copied = [path.relative_to(repo).as_posix() for path in RUNNER.source_files(repo)]
            self.assertEqual(copied, ['dashboard/app.py', 'manage.py'])
            outside = Path(temporary) / 'outside.py'
            outside.write_text('print("outside")\n', encoding='utf-8')
            (dashboard / 'linked.py').symlink_to(outside)
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.source_files(repo)
            self.assertTrue(outside.exists())

    def test_explicit_output_still_checks_inherited_temp_and_existing_dirs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'repo'
            parent = root / 'outside'
            repo.mkdir()
            parent.mkdir(mode=0o755)
            existing = parent / 'existing'
            existing.mkdir(mode=0o755)
            before = stat.S_IMODE(existing.stat().st_mode)
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.fresh_root(repo, {}, str(existing))
            self.assertEqual(stat.S_IMODE(existing.stat().st_mode), before)
            nested = repo / 'tmp'
            nested.mkdir()
            requested = parent / 'fresh-run'
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.fresh_root(repo, {'TMPDIR': str(nested)}, str(requested))
            self.assertFalse(requested.exists())

    def test_mutation_gate_rejects_changed_receipts_and_extra_rows(self):
        def blank():
            return {name: {} for name in RUNNER.SNAPSHOT_TABLES}

        before = blank()
        before['tracking_writerequest'] = {'1': {'sha256': 'receipt-a', 'local_date': ''}}
        changed = blank()
        changed['tracking_writerequest'] = {'1': {'sha256': 'receipt-b', 'local_date': ''}}
        cases = RUNNER.mutation_gate(before, changed, changed, changed, {'added': {}, 'cache_dates': []})
        receipt = next(item for item in cases if item['name'] == 'tracking_writerequest rows stay unchanged through preview')
        self.assertFalse(receipt['ok'])

        preview = blank()
        preview['tracking_journalentry'] = {'1': {'sha256': 'seed', 'local_date': '2026-01-01'}}
        after = blank()
        after['tracking_journalentry'] = {'1': {'sha256': 'seed', 'local_date': '2026-01-01'}}
        after['tracking_journalentry'].update({
            str(index): {'sha256': 'added', 'local_date': '2026-01-01'} for index in range(2, 901)
        })
        contract = {'added': dict(RUNNER.EXPECTED_WRITE_ADDS), 'cache_dates': ['2026-01-01']}
        added = RUNNER.mutation_gate(preview, preview, preview, after, contract)
        journal = next(item for item in added if item['name'] == 'tracking_journalentry write delta is exact')
        self.assertFalse(journal['ok'])

    def test_cleanup_refuses_a_symlink_outside_the_run_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            outside = Path(temporary) / 'outside.txt'
            root.mkdir()
            outside.write_text('keep\n', encoding='utf-8')
            (root / 'source').symlink_to(outside)
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.remove_transient(root)
            self.assertEqual(outside.read_text(encoding='utf-8'), 'keep\n')
            self.assertTrue((root / 'source').is_symlink())

    def test_reap_keeps_a_pid_whose_identity_changed_and_fails_when_ps_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            evidence = root / 'evidence'
            evidence.mkdir(parents=True)
            record = RUNNER.start_logged(['sleep', '30'], {'PATH': '/usr/bin:/bin'}, root, evidence / 'sleep.log')
            try:
                killed = []

                def reused(pid):
                    return {'state': 'verified', 'pid': pid, 'pgid': record['pgid'], 'started': 'different-start'}

                self.assertFalse(RUNNER.reap_owned([record], kill=lambda pid, sig: killed.append(pid), inspect=reused, group=lambda pgid: []))
                self.assertEqual(killed, [])
                self.assertTrue(RUNNER.pid_alive(record['pid']))
                original = subprocess.check_output

                def fail(*args, **kwargs):
                    raise OSError('ps failed')

                subprocess.check_output = fail
                try:
                    self.assertFalse(RUNNER.reap_owned([record]))
                finally:
                    subprocess.check_output = original
                self.assertTrue(RUNNER.pid_alive(record['pid']))
            finally:
                self.assertTrue(RUNNER.reap_owned([record]))
                self.assertFalse(RUNNER.pid_alive(record['pid']))

    def test_browser_inventory_matches_the_runner(self):
        text = (REPO / 'tests' / 'browser' / 'checks.cjs').read_text(encoding='utf-8')
        start = text.index('const REQUIRED_CASES = ')
        end = text.index('];', start)
        cases = __import__('json').loads(text[start + len('const REQUIRED_CASES = '):end + 1])
        self.assertEqual(cases, list(RUNNER.REQUIRED_BROWSER_CASES))
        self.assertEqual(len('D&<>"\'' + ('x' * 114)), 120)
        self.assertIn("'x' * 114", (REPO / 'tests' / 'browser' / 'fixture_app.py').read_text(encoding='utf-8'))

    def test_startup_injection_exits_before_a_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            root.mkdir()
            code = RUNNER.prove_startup(
                root, sys.executable, REPO / 'tests' / 'browser' / 'fixture_app.py')
            summary = __import__('json').loads((root / 'summary.json').read_text(encoding='utf-8'))
            log = (root / 'evidence' / 'startup.log').read_text(encoding='utf-8')
            self.assertEqual(code, 1)
            self.assertEqual(summary['exit_code'], 3)
            self.assertEqual(summary['failures'], ['startup'])
            self.assertEqual(summary['cleanup'], 'ok')
            self.assertIn('startup injection', log)
            self.assertFalse((root / 'data').exists())

    def test_timeout_cleanup_reaps_only_the_owned_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            root.mkdir()
            code = RUNNER.prove_timeout(root)
            summary = __import__('json').loads((root / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(code, 1)
            self.assertEqual(summary['failures'], ['timeout'])
            self.assertEqual(summary['cleanup'], 'ok')
            self.assertFalse(summary['ok'])
            self.assertEqual(stat.S_IMODE((root / 'summary.json').stat().st_mode) & 0o077, 0)

    def test_registration_timeout_still_owns_the_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            evidence = root / 'evidence'
            evidence.mkdir(parents=True)

            def timed_out(pid):
                raise subprocess.TimeoutExpired(['ps'], 1)

            record = RUNNER.start_logged(
                ['sleep', '30'], {'PATH': '/usr/bin:/bin'}, root, evidence / 'sleep.log', inspect=timed_out)
            try:
                self.assertEqual(record['identity'], 'unknown')
                self.assertEqual(record['pid'], record['proc'].pid)
                self.assertTrue(RUNNER.pid_alive(record['pid']))
            finally:
                self.assertTrue(RUNNER.reap_owned([record]))
                self.assertFalse(RUNNER.pid_alive(record['pid']))

    def test_leader_exit_still_reaps_the_owned_child(self):
        script = (
            'import os, signal, time\n'
            'signal.signal(signal.SIGHUP, signal.SIG_IGN)\n'
            'pid = os.fork()\n'
            'if pid == 0:\n'
            '    os.execv("/bin/sleep", ["sleep", "30"])\n'
            'time.sleep(1.2)\n'
            'os._exit(0)\n'
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            evidence = root / 'evidence'
            evidence.mkdir(parents=True)
            record = RUNNER.start_logged(
                [sys.executable, '-c', script], {'PATH': '/usr/bin:/bin'}, root, evidence / 'orphan.log')
            child = None
            try:
                deadline = time.time() + 5
                members = []
                while time.time() < deadline:
                    members = RUNNER.inspect_group(record['pgid']) or []
                    if len(members) >= 2:
                        break
                    time.sleep(0.05)
                self.assertGreaterEqual(len(members), 2)
                child = next(item['pid'] for item in members if item['pid'] != record['pid'])
                deadline = time.time() + 5
                while time.time() < deadline and RUNNER.inspect_process(record['pid']).get('state') != 'absent':
                    time.sleep(0.05)
                self.assertTrue(RUNNER.pid_alive(child))
                self.assertFalse(RUNNER.reap_owned([record]))
                self.assertFalse(RUNNER.pid_alive(child))
            finally:
                RUNNER.reap_owned([record])
                if child:
                    RUNNER.reap_owned([{'pid': child, 'pgid': record['pgid'], 'started': None, 'members': []}])

    def test_second_cleanup_signal_is_deferred(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            evidence = root / 'evidence'
            evidence.mkdir(parents=True)
            record = RUNNER.start_logged(['sleep', '30'], {'PATH': '/usr/bin:/bin'}, root, evidence / 'sleep.log')
            try:
                self.assertTrue(RUNNER.begin_cleanup())
                self.assertFalse(RUNNER.begin_cleanup())
                self.assertTrue(RUNNER.reap_owned([record]))
            finally:
                RUNNER.finish_cleanup()
                RUNNER.reap_owned([record])
            self.assertFalse(RUNNER.pid_alive(record['pid']))

    def test_deleted_cache_and_wrong_journal_semantics_fail(self):
        def blank():
            return {name: {} for name in RUNNER.SNAPSHOT_TABLES}

        before = blank()
        before['tracking_journalscore'] = {'sentinel': {'sha256': 'old', 'local_date': '2020-01-01', 'fields': {}}}
        later = blank()
        cases = RUNNER.mutation_gate(before, later, later, later, {'added': {}, 'cache_dates': []})
        cache = next(item for item in cases if item['name'] == 'cache changes stay inside the visited dates')
        self.assertFalse(cache['ok'])

        preview = blank()
        after = blank()
        after['tracking_journalentry'] = {
            str(index): {'sha256': 'x', 'local_date': '2026-01-01', 'fields': {'body_class': 'other', 'synthetic': True, 'deleted': False, 'owner_id': 7}}
            for index in range(4)
        }
        contract = {'added': dict(RUNNER.EXPECTED_WRITE_ADDS), 'cache_dates': ['2026-01-01'], 'semantics': True, 'owner_id': 7}
        semantic = next(item for item in RUNNER.mutation_gate(preview, preview, preview, after, contract) if item['name'] == 'new journal rows match the owned write contract')
        self.assertFalse(semantic['ok'])

        def blank_row(digest, owner, day, formula, synthetic, kind=''):
            return {'sha256': digest, 'local_date': day, 'fields': {
                'owner_id': owner, 'local_date': day, 'formula_version': formula,
                'synthetic': synthetic, 'kind': kind,
            }}

        day = '2026-01-02'
        sobriety = {
            'owner_id': 7, 'dates': [day], 'formula': 'sobriety-pattern-1', 'synthetic': True,
        }
        score = {
            'owner_id': 7, 'dates': [day], 'kind': 'daily_state',
            'formula': 'daily-state-1', 'synthetic': True,
        }
        replaced = blank()
        replaced['tracking_sobrietyday'] = {'1': blank_row('old', 7, day, 'sobriety-pattern-1', True)}
        recreated = blank()
        recreated['tracking_sobrietyday'] = {'2': blank_row('new', 7, day, 'sobriety-pattern-1', True)}
        allowed = RUNNER.mutation_gate(replaced, recreated, recreated, recreated, {'added': {}, 'sobriety_windows': [sobriety]})
        self.assertTrue(next(item for item in allowed if item['name'] == 'cache changes stay inside the visited dates')['ok'])
        redated = blank()
        redated['tracking_sobrietyday'] = {'1': blank_row('moved', 7, day, 'sobriety-pattern-1', True)}
        outside = blank()
        outside['tracking_sobrietyday'] = {'1': blank_row('old', 7, '2020-01-01', 'sobriety-pattern-1', True)}
        blocked = RUNNER.mutation_gate(outside, redated, redated, redated, {'added': {}, 'sobriety_windows': [sobriety]})
        self.assertFalse(next(item for item in blocked if item['name'] == 'cache changes stay inside the visited dates')['ok'])
        score_before = blank()
        score_before['tracking_journalscore'] = {'1': blank_row('old', 7, day, 'daily-state-1', True, 'daily_state')}
        score_after = blank()
        score_after['tracking_journalscore'] = {'2': blank_row('new', 7, day, 'daily-state-1', True, 'daily_state')}
        score_gate = RUNNER.mutation_gate(score_before, score_after, score_after, score_after, {'added': {}, 'journal_score_windows': [score]})
        self.assertFalse(next(item for item in score_gate if item['name'] == 'cache changes stay inside the visited dates')['ok'])

    def test_proxy_proof_is_exact_and_bounded(self):
        stylesheet = '/static/tracking/app.css?v=discovered'
        host = PROXY.decide(
            ['GET', 'http://example.invalid/probe', 'HTTP/1.1'],
            ['Host: example.invalid'], 9)
        connect = PROXY.decide(
            ['CONNECT', 'example.invalid:443', 'HTTP/1.1'],
            ['Host: example.invalid:443'], 9)
        host_line = f'REJECT {host[1]} {host[2]} GET {PROXY.public_target("http://example.invalid/probe")}'
        connect_line = f'REJECT {connect[1]} {connect[2]} CONNECT {PROXY.public_target("example.invalid:443")}'
        self.assertEqual((host_line, connect_line), RUNNER.EXPECTED_PROXY_REJECTS)
        good = host_line + '\n' + connect_line + '\n' + f'FORWARD 200 {stylesheet} 200\n'
        self.assertTrue(RUNNER.proxy_log_expected(good, stylesheet))
        self.assertFalse(RUNNER.proxy_log_expected(good + 'REJECT 502 socket TimeoutError\n', stylesheet))
        self.assertFalse(RUNNER.proxy_log_expected(good.replace(stylesheet, '/static/tracking/app.css'), stylesheet))
        self.assertEqual(PROXY.public_target('http://127.0.0.1:9/callback?code=synthetic_token'), '/callback')
        self.assertEqual(PROXY.public_target(stylesheet), stylesheet)
        self.assertEqual(PROXY._header_lines(['Host: 127.0.0.1:9', 'X-Bad: bad\nvalue'])[1], 400)

        class Closed:
            def recv(self, count):
                raise AssertionError('deadline closed before a read')

        self.assertIsNone(PROXY._read_headers(Closed(), time.monotonic() - PROXY.DEADLINE - 1))

        class Short:
            def settimeout(self, value):
                return None

            def recv(self, count):
                if self.sent:
                    return b''
                self.sent = True
                return b'ab'

            sent = False

        class Exact:
            def settimeout(self, value):
                return None

            def recv(self, count):
                return b'abcdefghij'

        self.assertIsNone(PROXY.read_counted_body(Short(), b'', 10, time.monotonic()))
        self.assertEqual(PROXY.read_counted_body(Exact(), b'', 10, time.monotonic()), b'abcdefghij')
        held = 0
        try:
            while PROXY.SLOTS.acquire(blocking=False):
                held += 1
            self.assertEqual(held, 4)
            self.assertFalse(PROXY.SLOTS.acquire(blocking=False))
        finally:
            for _ in range(held):
                PROXY.SLOTS.release()

    def test_manifest_and_injection_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / 'evidence'
            evidence.mkdir()
            secrets = Path(temporary) / 'secrets'
            secrets.mkdir()
            dates = {
                'positive': '2026-01-02', 'unknown': '2026-01-03', 'no_meal': '2026-01-04',
                'null_food': '2026-01-05', 'meal': '2026-01-06', 'zero': '2026-01-07',
                'null_steps': '2026-01-08', 'ambiguous': '2026-01-09', 'sleep': '2026-01-10',
                'short_sleep': '2026-01-11', 'controls': '2026-01-12', 'csv': '2026-01-13',
                'mixed': '2026-01-14',
            }
            score_dates = list(dates.values())
            sobriety_dates = [f'2026-01-{day:02d}' for day in range(1, 15)]
            payload = {
                'origin': 'http://127.0.0.1:9',
                'timezone': 'America/Chicago',
                'owner': 'synthetic-browser-owner',
                'owner_id': 7,
                'write_adds': dict(RUNNER.EXPECTED_WRITE_ADDS),
                'dates': dates,
                'journal_score_dates': score_dates,
                'sobriety_dates': sobriety_dates,
                'cache_sentinel': '2020-01-01',
                'personal_id': 'personal1',
                'legacy_id': 'legacy001',
                'mixed_personal_id': 'mixed0001',
                'sleep_personal_id': 'sleeppers',
                'csv_id': 'csv000001',
                'hrv_id': 'hrv000001',
                'hrv_alt_id': 'hrvalt001',
                'unique_sleep_id': 'sleep0001',
                'export_summary_ids': ['sleeppers', 'mixed0001', 'legacy001', 'personal1'],
                'root_score_date': '2026-11-10',
                'owner_password_file': str(secrets / 'owner-password'),
                'other_password_file': str(secrets / 'other-password'),
            }
            self.assertTrue(RUNNER.manifest_contract(payload, evidence, 9))
            bad = dict(payload)
            bad['origin'] = 'http://127.0.0.1:9@other-host'
            self.assertFalse(RUNNER.manifest_contract(bad, evidence, 9))
            short = dict(payload)
            short['dates'] = dict(dates)
            short['dates']['positive'] = '2026-1-2'
            self.assertFalse(RUNNER.manifest_contract(short, evidence, 9))
        complete = [{'name': name, 'ok': True} for name in RUNNER.REQUIRED_BROWSER_CASES]
        complete.append({'name': 'injected-assertion', 'ok': False})
        self.assertTrue(RUNNER.injection_inventory({'assertions': complete}))
        self.assertFalse(RUNNER.injection_inventory({'assertions': complete[:-2]}))

    def test_cancellation_is_registered_before_inspection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            evidence = root / 'evidence'
            evidence.mkdir(parents=True)
            owned = []

            def cancel(record):
                RUNNER.note_cancellation(signal.SIGTERM)

            try:
                with self.assertRaises(SystemExit) as raised:
                    RUNNER.start_logged(
                        ['sleep', '30'], {'PATH': '/usr/bin:/bin'}, root, evidence / 'sleep.log',
                        registry=owned, after_register=cancel)
                self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
                self.assertEqual(len(owned), 1)
                self.assertEqual(owned[0]['identity'], 'unverified')
                self.assertTrue(RUNNER.pid_alive(owned[0]['pid']))
            finally:
                self.assertTrue(RUNNER.reap_owned(owned))
                if owned:
                    self.assertFalse(RUNNER.pid_alive(owned[0]['pid']))

    def test_detached_group_does_not_adopt_an_unregistered_peer(self):
        first = subprocess.Popen(['sleep', '30'], start_new_session=True)
        second = subprocess.Popen(['sleep', '30'], start_new_session=True)
        owned = []
        try:
            info = RUNNER.inspect_process(first.pid)
            self.assertEqual(info['state'], 'verified')
            RUNNER.register_detached(owned, info['pid'], info['pgid'], info['started'])
            self.assertTrue(RUNNER.reap_owned(owned))
            self.assertFalse(RUNNER.pid_alive(first.pid))
            self.assertTrue(RUNNER.pid_alive(second.pid))
        finally:
            for proc in (first, second):
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)

    def test_intentional_stop_is_distinct_from_a_spontaneous_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            evidence = root / 'evidence'
            evidence.mkdir(parents=True)
            live = RUNNER.start_logged(['sleep', '30'], {'PATH': '/usr/bin:/bin'}, root, evidence / 'live.log')
            try:
                self.assertTrue(RUNNER.mark_stopping(live))
                self.assertFalse(live['spontaneous'])
                self.assertTrue(RUNNER.reap_owned([live]))
            finally:
                RUNNER.reap_owned([live])
            done = RUNNER.start_logged(
                [sys.executable, '-c', 'raise SystemExit(0)'], {'PATH': '/usr/bin:/bin'}, root, evidence / 'done.log')
            try:
                deadline = time.time() + 5
                while time.time() < deadline and not RUNNER.child_exited(done['proc']):
                    time.sleep(0.05)
                self.assertTrue(RUNNER.child_exited(done['proc']))
                self.assertFalse(RUNNER.mark_stopping(done))
                self.assertTrue(done['spontaneous'])
                self.assertFalse(RUNNER.reap_owned([done]))
            finally:
                RUNNER.reap_owned([done])

    def test_linked_journal_contract_passes_and_false_lineage_is_midpoint(self):
        def blank():
            return {name: {} for name in RUNNER.SNAPSHOT_TABLES}

        def wrapped(fields):
            return {'sha256': 'row', 'local_date': '', 'fields': fields}

        preview = blank()
        after = blank()
        entries = {
            'e1': wrapped({'id': 'e1', 'owner_id': 7, 'request_id': '1', 'synthetic': True, 'deleted': True, 'body_class': 'tombstone', 'body_blank': True}),
            'e2': wrapped({'id': 'e2', 'owner_id': 7, 'request_id': '2', 'synthetic': True, 'deleted': True, 'body_class': 'tombstone', 'body_blank': True}),
            'e3': wrapped({'id': 'e3', 'owner_id': 7, 'request_id': '3', 'synthetic': True, 'deleted': False, 'body_class': 'unknown', 'body_blank': False}),
            'e4': wrapped({'id': 'e4', 'owner_id': 7, 'request_id': '4', 'synthetic': True, 'deleted': False, 'body_class': 'unknown', 'body_blank': False}),
        }
        observations = {
            'o1': wrapped({'owner_id': 7, 'entry_id': 'e1', 'metric_key': 'explicit_choice', 'value_state': 'observed', 'boolean': None, 'deleted': True, 'value_blank': True}),
            'o2': wrapped({'owner_id': 7, 'entry_id': 'e2', 'metric_key': 'explicit_choice', 'value_state': 'observed', 'boolean': None, 'deleted': True, 'value_blank': True}),
            'o3': wrapped({'owner_id': 7, 'entry_id': 'e3', 'metric_key': 'explicit_choice', 'value_state': 'unknown', 'boolean': None, 'deleted': False, 'value_blank': False}),
            'o4': wrapped({'owner_id': 7, 'entry_id': 'e4', 'metric_key': 'explicit_choice', 'value_state': 'unknown', 'boolean': None, 'deleted': False, 'value_blank': False}),
        }
        corrections = {}
        for entry_id, operations in (
            ('e1', [('create', 1, '1'), ('update', 2, '5'), ('delete', 3, '6')]),
            ('e2', [('create', 1, '2'), ('update', 2, '7'), ('delete', 3, '8')]),
            ('e3', [('create', 1, '3')]),
            ('e4', [('create', 1, '4')]),
        ):
            for operation, version, request_id in operations:
                corrections[f'{entry_id}-{operation}'] = wrapped({
                    'operation': operation, 'entry_id': entry_id, 'request_id': request_id, 'after_version': version,
                })
        holding = {
            'h1': wrapped({'owner_id': 7, 'state': 'failed', 'request_id': '9'}),
            'h2': wrapped({'owner_id': 7, 'state': 'failed', 'request_id': '10'}),
        }
        receipts = {str(index): wrapped({'id': str(index), 'owner_id': 7}) for index in range(1, 11)}
        after['tracking_journalentry'] = entries
        after['tracking_journalobservation'] = observations
        after['tracking_journalcorrection'] = corrections
        after['tracking_holdingmessage'] = holding
        after['tracking_writerequest'] = receipts
        midpoint = blank()
        midpoint['tracking_journalobservation'] = {
            'o1': wrapped({'owner_id': 7, 'entry_id': 'e1', 'metric_key': 'explicit_choice', 'value_state': 'observed', 'boolean': False, 'deleted': False}),
            'o2': wrapped({'owner_id': 7, 'entry_id': 'e2', 'metric_key': 'explicit_choice', 'value_state': 'observed', 'boolean': False, 'deleted': False}),
        }
        contract = {
            'added': dict(RUNNER.EXPECTED_WRITE_ADDS), 'semantics': True, 'owner_id': 7, 'false_snapshot': midpoint,
        }
        cases = RUNNER.mutation_gate(preview, preview, preview, after, contract)
        self.assertTrue(next(item for item in cases if item['name'] == 'new journal rows match the owned write contract')['ok'])
        self.assertTrue(next(item for item in cases if item['name'] == 'saved false observation precedes its tombstone')['ok'])
        broken = blank()
        broken.update(after)
        broken['tracking_journalobservation'] = {
            key: wrapped({**row['fields'], 'entry_id': 'unrelated', 'boolean': True})
            for key, row in observations.items()
        }
        failed = RUNNER.mutation_gate(preview, preview, preview, broken, contract)
        self.assertFalse(next(item for item in failed if item['name'] == 'new journal rows match the owned write contract')['ok'])

    def test_launcher_protocol_registers_before_the_target_starts(self):
        target = (
            'import os, sys, time\n'
            'with open(sys.argv[1], "a", encoding="utf-8") as handle:\n'
            '    handle.write(" ".join(sys.argv[2:]) + "\\n")\n'
            'if "--fork" in sys.argv:\n'
            '    pid = os.fork()\n'
            '    if pid == 0:\n'
            '        os.execv("/bin/sleep", ["sleep", "30"])\n'
            'if "--exit" in sys.argv:\n'
            '    raise SystemExit(0)\n'
            'time.sleep(30)\n'
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            root.mkdir()
            script = root / 'target.py'
            script.write_text(target, encoding='utf-8')
            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=2)
            launcher = prepared['launcher']
            self.assertTrue(launcher.read_bytes().startswith(f'#!{sys.executable}\n'.encode()))
            marker = root / 'marker.txt'
            env = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'CX83_LAUNCH_FILE': str(prepared['slots']['warm'])}

            def clear_handshake():
                for directory in (root / 'evidence' / 'register', root / 'evidence' / 'ack'):
                    if directory.exists():
                        for item in directory.iterdir():
                            item.unlink()
                RUNNER.LAUNCHES['failures'] = []

            def start(slot, *args):
                return subprocess.Popen(
                    [str(launcher), str(script), str(marker), *args],
                    env={**env, 'CX83_LAUNCH_FILE': str(prepared['slots'][slot])},
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

            clear_handshake()
            missing = start('warm', 'exact-arg')
            try:
                code = missing.wait(timeout=5)
                self.assertNotEqual(code, 0)
                self.assertFalse(marker.exists())
            finally:
                if missing.poll() is None:
                    missing.kill()
                    missing.wait(timeout=5)

            clear_handshake()
            wrong = json.loads(prepared['slots']['warm'].read_text(encoding='utf-8'))
            ack = Path(wrong['ack_path'])
            ack.write_text(json.dumps({'pid': 1, 'pgid': 1, 'started': 'stale', 'nonce': 'wrong', 'launch_id': 'warm'}) + '\n', encoding='utf-8')
            stale = start('warm', 'exact-arg')
            try:
                self.assertNotEqual(stale.wait(timeout=5), 0)
                self.assertFalse(marker.exists())
            finally:
                if stale.poll() is None:
                    stale.kill()
                    stale.wait(timeout=5)
            ack.unlink()

            parent = subprocess.Popen(['sleep', '30'], stdout=subprocess.DEVNULL)
            try:
                lost = RUNNER.prepare_browser_launches(root, sys.executable, parent_pid=parent.pid, deadline=2)
                parent.kill()
                parent.wait(timeout=5)
                clear_handshake()
                child = subprocess.Popen(
                    [str(lost['launcher']), str(script), str(marker), 'exact-arg'],
                    env={**env, 'CX83_LAUNCH_FILE': str(lost['slots']['warm'])},
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                self.assertEqual(child.wait(timeout=5), 79)
                self.assertFalse(marker.exists())
            finally:
                if parent.poll() is None:
                    parent.kill()
                    parent.wait(timeout=5)

            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=3)
            clear_handshake()
            held = start('warm', 'exact-arg')
            try:
                RUNNER.LAUNCHES['ack'] = False
                deadline = time.time() + 3
                while time.time() < deadline and not any(item.get('launch_id') == 'warm' for item in RUNNER.REGISTRY):
                    RUNNER.service_browser_launches()
                    time.sleep(0.05)
                self.assertTrue(any(item.get('launch_id') == 'warm' for item in RUNNER.REGISTRY))
                self.assertFalse(marker.exists())
                self.assertFalse(Path(json.loads(prepared['slots']['warm'].read_text(encoding='utf-8'))['ack_path']).exists())
                self.assertTrue(RUNNER.reap_owned(RUNNER.REGISTRY))
                self.assertFalse(marker.exists())
            finally:
                if held.poll() is None:
                    held.kill()
                    held.wait(timeout=5)
                RUNNER.reap_owned(list(RUNNER.REGISTRY))
                RUNNER.REGISTRY.clear()

            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=3)
            clear_handshake()
            env['CX83_LAUNCH_FILE'] = str(prepared['slots']['warm'])
            warm = start('warm', 'exact-arg')
            cold = start('cold', 'other-arg')
            peer = subprocess.Popen(['sleep', '30'], start_new_session=True, stdout=subprocess.DEVNULL)
            try:
                deadline = time.time() + 3
                while time.time() < deadline and not RUNNER.browser_launches_registered():
                    RUNNER.service_browser_launches()
                    time.sleep(0.05)
                self.assertTrue(RUNNER.browser_launches_registered())
                self.assertEqual({item.get('launch_id') for item in RUNNER.REGISTRY}, {'warm', 'cold'})
                self.assertNotEqual(RUNNER.REGISTRY[0]['pid'], RUNNER.REGISTRY[1]['pid'])
                text = ''
                seen = time.time() + 3
                while time.time() < seen:
                    if marker.exists():
                        text = marker.read_text(encoding='utf-8')
                        if 'exact-arg' in text and 'other-arg' in text:
                            break
                    time.sleep(0.05)
                self.assertIn('exact-arg', text)
                self.assertIn('other-arg', text)
                self.assertTrue(RUNNER.reap_owned(RUNNER.REGISTRY))
                self.assertFalse(RUNNER.pid_alive(warm.pid))
                self.assertFalse(RUNNER.pid_alive(cold.pid))
                self.assertTrue(RUNNER.pid_alive(peer.pid))
                nonce = json.loads(prepared['slots']['warm'].read_text(encoding='utf-8'))['nonce']
                summary = root / 'summary.json'
                RUNNER.write_summary(summary, {'ok': True, 'pids': [item['pid'] for item in RUNNER.REGISTRY]}, [nonce])
                self.assertNotIn(nonce, summary.read_text(encoding='utf-8'))
            finally:
                for proc in (warm, cold, peer):
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=5)
                RUNNER.reap_owned(list(RUNNER.REGISTRY))
                RUNNER.REGISTRY.clear()

            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=3)
            clear_handshake()
            forked = subprocess.Popen(
                [str(prepared['launcher']), str(script), str(marker), '--fork'],
                env={**env, 'CX83_LAUNCH_FILE': str(prepared['slots']['warm'])},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                deadline = time.time() + 3
                while time.time() < deadline and not any(item.get('launch_id') == 'warm' for item in RUNNER.REGISTRY):
                    RUNNER.service_browser_launches()
                    time.sleep(0.05)
                record = next(item for item in RUNNER.REGISTRY if item.get('launch_id') == 'warm')
                deadline = time.time() + 3
                members = []
                while time.time() < deadline:
                    members = RUNNER.inspect_group(record['pgid']) or []
                    if len(members) >= 2:
                        break
                    time.sleep(0.05)
                self.assertGreaterEqual(len(members), 2)
                self.assertTrue(RUNNER.reap_owned([record]))
                self.assertFalse(any(RUNNER.pid_alive(item['pid']) for item in members))
            finally:
                if forked.poll() is None:
                    forked.kill()
                    forked.wait(timeout=5)
                RUNNER.reap_owned(list(RUNNER.REGISTRY))
                RUNNER.REGISTRY.clear()

            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=3)
            original = RUNNER.inspect_process

            def unknown(pid, runner=None, timeout=3):
                return {'state': 'unknown'}

            RUNNER.inspect_process = unknown
            clear_handshake()
            marker.unlink(missing_ok=True)
            blocked = subprocess.Popen(
                [str(prepared['launcher']), str(script), str(marker), 'exact-arg'],
                env={**env, 'CX83_LAUNCH_FILE': str(prepared['slots']['warm'])},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                time.sleep(0.2)
                RUNNER.service_browser_launches()
                self.assertFalse(any(item.get('launch_id') == 'warm' for item in RUNNER.REGISTRY))
                self.assertIn('warm', RUNNER.LAUNCHES['failures'])
                self.assertNotEqual(blocked.wait(timeout=5), 0)
                self.assertFalse(marker.exists())
            finally:
                RUNNER.inspect_process = original
                if blocked.poll() is None:
                    blocked.kill()
                    blocked.wait(timeout=5)

            RUNNER.defer_cancellation()
            try:
                RUNNER.note_cancellation(signal.SIGTERM)
                self.assertEqual(RUNNER.CANCEL['pending'], signal.SIGTERM)
            finally:
                with self.assertRaises(SystemExit):
                    RUNNER.release_cancellation()

            windows = RUNNER.cache_windows({
                'owner_id': 7,
                'journal_score_dates': ['2026-01-02'],
                'dates': {'mixed': '2026-01-03', 'sleep': '2026-01-04'},
                'root_score_date': '2026-11-10',
            })
            personal = [item for item in windows if item['synthetic'] is False]
            synthetic = [item for item in windows if item['synthetic'] is True]
            self.assertEqual(personal[0]['dates'], ['2026-11-10', '2026-01-03', '2026-01-04'])
            self.assertEqual(personal[1]['dates'], ['2026-11-10', '2026-01-03', '2026-01-04'])
            self.assertEqual(synthetic[0]['dates'], ['2026-01-02'])
            self.assertTrue(all(item['kind'] in {'daily_state', 'routine_alignment'} for item in windows))

            def refuse(address, timeout):
                raise ConnectionRefusedError

            def accept(address, timeout):
                class Open:
                    def close(self):
                        return None
                return Open()

            self.assertTrue(RUNNER.owned_ports_closed([9], connect=refuse))
            self.assertFalse(RUNNER.owned_ports_closed([9], connect=accept))

    def test_direct_launcher_keeps_the_group_until_drain_is_verified(self):
        target = (
            'import os, signal, sys, time\n'
            'with open(sys.argv[1], "a", encoding="utf-8") as handle:\n'
            '    handle.write(" ".join(sys.argv[2:]) + "\\n")\n'
            'if "--resist" in sys.argv:\n'
            '    pid = os.fork()\n'
            '    if pid == 0:\n'
            '        signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
            '        time.sleep(60)\n'
            '        os._exit(0)\n'
            '    open(sys.argv[1] + ".child", "w", encoding="utf-8").write(str(pid))\n'
            '    os._exit(0)\n'
            'if "--exit" in sys.argv:\n'
            '    raise SystemExit(0)\n'
            'time.sleep(30)\n'
        )

        def group_gone(pgid):
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    text = subprocess.check_output(['ps', '-g', str(pgid), '-o', 'pid='], text=True)
                except subprocess.CalledProcessError as exc:
                    if exc.returncode == 1 and not (exc.output or '').strip():
                        return True
                    return False
                if not text.strip():
                    return True
                time.sleep(0.05)
            return False

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            root.mkdir()
            script = root / 'target.py'
            script.write_text(target, encoding='utf-8')
            marker = root / 'marker.txt'
            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=4)
            launcher = prepared['launcher']
            self.assertEqual(launcher.read_bytes()[:2], b'#!')
            env = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}

            def clear_handshake():
                for directory in (root / 'evidence' / 'register', root / 'evidence' / 'ack'):
                    if directory.exists():
                        for item in directory.iterdir():
                            item.unlink()
                RUNNER.LAUNCHES['failures'] = []
                RUNNER.REGISTRY.clear()

            def start(slot, *args, extra=None):
                return subprocess.Popen(
                    [str(launcher), str(script), str(marker), *args],
                    env={**env, 'CX83_LAUNCH_FILE': str(prepared['slots'][slot]), **(extra or {})},
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

            def service_until(predicate, seconds=5):
                deadline = time.time() + seconds
                while time.time() < deadline and not predicate():
                    RUNNER.service_browser_launches()
                    time.sleep(0.05)
                return predicate()

            clear_handshake()
            warm = start('warm', '--exit', 'exact arg')
            cold = start('cold', '--exit', 'other arg')
            peer = subprocess.Popen(['sleep', '40'], start_new_session=True, stdout=subprocess.DEVNULL)
            try:
                self.assertTrue(service_until(RUNNER.browser_launches_registered))
                self.assertEqual(warm.wait(timeout=10), 0)
                self.assertEqual(cold.wait(timeout=10), 0)
                for _ in range(5):
                    RUNNER.service_browser_launches()
                self.assertFalse(RUNNER.LAUNCHES['failures'])
                self.assertEqual({item.get('launch_id') for item in RUNNER.REGISTRY}, {'warm', 'cold'})
                text = marker.read_text(encoding='utf-8')
                self.assertIn('exact arg', text)
                self.assertIn('other arg', text)
                for record in list(RUNNER.REGISTRY):
                    self.assertTrue(group_gone(record['pgid']))
                self.assertTrue(RUNNER.pid_alive(peer.pid))
            finally:
                for proc in (warm, cold, peer):
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=5)
                RUNNER.reap_owned(list(RUNNER.REGISTRY))
                RUNNER.REGISTRY.clear()

            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=4)
            clear_handshake()
            marker.unlink(missing_ok=True)
            resist = start('warm', '--resist')
            peer = subprocess.Popen(['sleep', '40'], start_new_session=True, stdout=subprocess.DEVNULL)
            child_path = Path(str(marker) + '.child')
            try:
                self.assertTrue(service_until(child_path.exists))
                child = int(child_path.read_text(encoding='utf-8'))
                record = next(item for item in RUNNER.REGISTRY if item.get('launch_id') == 'warm')
                self.assertEqual(resist.wait(timeout=15), 0)
                deadline = time.time() + 2
                while time.time() < deadline and RUNNER.pid_alive(child):
                    time.sleep(0.05)
                self.assertFalse(RUNNER.pid_alive(child))
                self.assertTrue(group_gone(record['pgid']))
                self.assertTrue(RUNNER.pid_alive(peer.pid))
                self.assertFalse(RUNNER.LAUNCHES['failures'])
            finally:
                if resist.poll() is None:
                    resist.kill()
                    resist.wait(timeout=5)
                if peer.poll() is None:
                    peer.kill()
                    peer.wait(timeout=5)
                RUNNER.reap_owned(list(RUNNER.REGISTRY))
                RUNNER.REGISTRY.clear()

            parent = subprocess.Popen(['sleep', '40'], stdout=subprocess.DEVNULL)
            child = None
            try:
                prepared = RUNNER.prepare_browser_launches(root, sys.executable, parent_pid=parent.pid, deadline=4)
                clear_handshake()
                marker.unlink(missing_ok=True)
                child = start('warm', 'after ack')
                self.assertTrue(service_until(marker.exists))
                record = next(item for item in RUNNER.REGISTRY if item.get('launch_id') == 'warm')
                parent.kill()
                parent.wait(timeout=5)
                child.wait(timeout=10)
                self.assertTrue(marker.exists())
                self.assertTrue(group_gone(record['pgid']))
            finally:
                if parent.poll() is None:
                    parent.kill()
                    parent.wait(timeout=5)
                if child is not None and child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                RUNNER.reap_owned(list(RUNNER.REGISTRY))
                RUNNER.REGISTRY.clear()

            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=4)
            clear_handshake()
            marker.unlink(missing_ok=True)
            pause = root / 'pause'
            held = start('warm', 'during spawn', extra={'CX83_LAUNCH_PAUSE': str(pause)})
            peer = subprocess.Popen(['sleep', '40'], start_new_session=True, stdout=subprocess.DEVNULL)
            try:
                self.assertTrue(service_until(pause.exists))
                self.assertTrue(any(item.get('launch_id') == 'warm' for item in RUNNER.REGISTRY))
                record = next(item for item in RUNNER.REGISTRY if item.get('launch_id') == 'warm')
                os.kill(held.pid, signal.SIGTERM)
                os.kill(held.pid, signal.SIGTERM)
                Path(str(pause) + '.go').write_text('go\n', encoding='utf-8')
                held.wait(timeout=10)
                self.assertTrue(group_gone(record['pgid']))
                self.assertTrue(RUNNER.pid_alive(peer.pid))
            finally:
                if held.poll() is None:
                    held.kill()
                    held.wait(timeout=5)
                if peer.poll() is None:
                    peer.kill()
                    peer.wait(timeout=5)
                RUNNER.reap_owned(list(RUNNER.REGISTRY))
                RUNNER.REGISTRY.clear()

            evidence = root / 'evidence'
            nonce = json.loads((evidence / 'launch-warm.json').read_text(encoding='utf-8'))['nonce']
            log = evidence / 'node.log'
            log.write_text(nonce + '\n', encoding='utf-8')
            RUNNER.release_launch_controls(evidence)
            self.assertFalse((evidence / 'launch-warm.json').exists())
            self.assertFalse(RUNNER.scrub_tree(evidence, ['owner-secret'], [nonce]))
            self.assertNotIn(nonce, log.read_text(encoding='utf-8'))
            log.write_text('owner-secret in the log\n', encoding='utf-8')
            self.assertTrue(RUNNER.scrub_tree(evidence, ['owner-secret'], [nonce]))
            self.assertNotIn('owner-secret', log.read_text(encoding='utf-8'))

    def test_launcher_signal_requires_the_current_child_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            root.mkdir()
            prepared = RUNNER.prepare_browser_launches(root, sys.executable, deadline=2)
            source = prepared['launcher'].read_text(encoding='utf-8')
            self.assertIn('WNOWAIT', source)
            self.assertNotIn('child.poll', source)
            spec = importlib.util.spec_from_file_location('cx83_launcher_signal_under_test', prepared['launcher'])
            launcher = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(launcher)
            sent = []
            real_kill = os.kill
            real_waitid = os.waitid
            previous = {signum: signal.getsignal(signum) for signum in launcher.CAUGHT}

            def record_kill(pid, signum):
                sent.append((pid, signum))

            launcher.os.kill = record_kill
            try:
                observed = {}

                def waitid(kind, pid, options):
                    observed['pid'] = pid
                    observed['options'] = options
                    return object()

                launcher.os.waitid = waitid
                self.assertTrue(launcher.direct_child_exited(123))
                self.assertEqual(observed['pid'], 123)
                self.assertTrue(observed['options'] & os.WNOWAIT)
                self.assertTrue(observed['options'] & os.WNOHANG)

                launcher.CHILD.update({'pid': 123, 'forward': True, 'reaped': False, 'pending': []})
                launcher.on_launcher_signal(signal.SIGTERM, None)
                self.assertEqual(sent, [(123, signal.SIGTERM)])

                class Child:
                    pid = 123

                    def wait(self, timeout=None):
                        launcher.on_launcher_signal(signal.SIGTERM, None)
                        return 0

                    def kill(self):
                        raise AssertionError('the unreaped child was killed after disarm')

                sent.clear()
                self.assertEqual(launcher.reap_direct_child(Child()), 0)
                self.assertFalse(launcher.CHILD['forward'])
                self.assertTrue(launcher.CHILD['reaped'])
                self.assertEqual(sent, [])
                launcher.on_launcher_signal(signal.SIGTERM, None)
                self.assertEqual(sent, [])

                launcher.CHILD.update({'pid': 123, 'forward': False, 'reaped': False, 'pending': []})
                launcher.on_launcher_signal(signal.SIGINT, None)
                self.assertEqual(sent, [])
                self.assertIn(signal.SIGINT, launcher.CHILD['pending'])

                launcher.group_members = lambda: [{'state': 'verified', 'pid': 456, 'pgid': 7, 'started': 'Birth A'}]
                launcher.inspect_member = lambda pid: {'state': 'verified', 'pid': pid, 'pgid': 9, 'started': 'Birth B'}
                self.assertEqual(launcher.next_drain_action(signal.SIGTERM), 'retry')
                self.assertEqual(sent, [])

                launcher.inspect_member = lambda pid: {'state': 'unknown'}
                self.assertEqual(launcher.next_drain_action(signal.SIGKILL), 'hold')
                self.assertEqual(sent, [])
            finally:
                os.kill = real_kill
                os.waitid = real_waitid
                for signum, handler in previous.items():
                    signal.signal(signum, handler)

    def test_phase_error_stops_before_the_marker_and_stays_sanitized(self):
        secret = 'hunter2password'
        dirty = {
            'phase': 'preview',
            'error': f'preview failed password={secret} cookie=sid token=abc123\n    at main ({secret})\n<html>{secret}</html>',
            'stack': secret,
            'env': {'SECRET': secret},
        }
        clean = RUNNER.sanitize_phase_error(dirty)
        self.assertEqual(clean, {'phase': 'preview', 'error': 'preview failed password=[redacted] cookie=[redacted] token=[redacted]'})
        self.assertNotIn(secret, json.dumps(clean))
        self.assertEqual(RUNNER.sanitize_phase_error({'phase': 'other', 'error': 5, 'stack': secret}), {'phase': 'runner', 'error': 'phase failed'})

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / 'failed'
            evidence.mkdir()
            (evidence / 'phase-error.json').write_text(json.dumps(dirty), encoding='utf-8')
            started = time.time()
            with self.assertRaises(RUNNER.PhaseFailure) as caught:
                RUNNER.wait_json(
                    evidence / 'preview-done.json', time.time() + 5,
                    lambda item: item.get('phase') == 'preview-done', evidence)
            self.assertLess(time.time() - started, 2)
            self.assertFalse((evidence / 'preview-done.json').exists())
            self.assertEqual(caught.exception.payload['phase'], 'preview')
            self.assertNotIn(secret, json.dumps(caught.exception.payload))
            stored = (evidence / 'phase-error.json').read_text(encoding='utf-8')
            self.assertNotIn(secret, stored)
            self.assertNotIn('stack', stored)

            outside = root / 'outside.txt'
            outside.write_text(secret, encoding='utf-8')
            linked = root / 'linked'
            linked.mkdir()
            (linked / 'phase-error.json').symlink_to(outside)
            self.assertEqual(RUNNER.owned_phase_error(linked), {'phase': 'runner', 'error': 'phase failed'})
            self.assertEqual(outside.read_text(encoding='utf-8'), secret)

            live = root / 'live'
            live.mkdir()

            def fail_later():
                time.sleep(0.3)
                (live / 'phase-error.json').write_text(
                    json.dumps({'phase': 'cache', 'error': 'cache stopped'}), encoding='utf-8')

            threading.Thread(target=fail_later, daemon=True).start()
            started = time.time()
            with self.assertRaises(RUNNER.PhaseFailure) as live_failure:
                RUNNER.wait_json(
                    live / 'cache-ready.json', time.time() + 5, lambda item: item.get('phase') == 'revalidated', live)
            self.assertLess(time.time() - started, 2)
            self.assertEqual(live_failure.exception.payload, {'phase': 'cache', 'error': 'cache stopped'})
            self.assertFalse((live / 'cache-ready.json').exists())

            healthy = root / 'healthy'
            healthy.mkdir()
            marker = healthy / 'preview-done.json'

            def write_marker():
                time.sleep(0.3)
                marker.write_text(json.dumps({'phase': 'preview-done'}), encoding='utf-8')

            threading.Thread(target=write_marker, daemon=True).start()
            started = time.time()
            payload = RUNNER.wait_json(
                marker, time.time() + 5, lambda item: item.get('phase') == 'preview-done', healthy)
            self.assertEqual(payload, {'phase': 'preview-done'})
            self.assertLess(time.time() - started, 2)
            self.assertIsNone(RUNNER.owned_phase_error(healthy))

            manifest = root / 'manifest.json'
            manifest.write_text('{"origin":"http://127.0.0.1:9"}', encoding='utf-8')
            js_dir = root / 'js'
            js_dir.mkdir()
            script = root / 'phase-check.cjs'
            script.write_text(
                "const fs=require('fs'); const path=require('path'); const checks=require(process.env.CHECKS);\n"
                "const secret=process.env.PHASE_SECRET; const dir=process.env.PHASE_DIR;\n"
                "const error=new Error('preview failed password='+secret+' cookie=sid token=abc123\\n    at main ('+secret+')\\n<html>'+secret+'</html>');\n"
                "error.stack='stack '+secret;\n"
                "const saved=checks.persistPhaseError('preview', error, dir);\n"
                "const raw=fs.readFileSync(path.join(dir,'phase-error.json'),'utf8');\n"
                "if (raw.includes(secret) || raw.includes('stack') || raw.includes('html')) process.exit(2);\n"
                "if (saved.phase!=='preview' || saved.error.includes(secret)) process.exit(3);\n"
                "const dirty=checks.sanitizePhaseError({phase:'nope', error:'x', stack:secret, env:{SECRET:secret}});\n"
                "if (JSON.stringify(dirty).includes(secret) || dirty.phase!=='runner') process.exit(4);\n"
                "process.stdout.write('PHASE_JS_OK\\n');\n",
                encoding='utf-8')
            node = '/opt/homebrew/bin/node'
            if not Path(node).is_file():
                node = 'node'
            env = os.environ.copy()
            env.pop('NODE_OPTIONS', None)
            env.pop('PLAYWRIGHT_MODULE', None)
            env['MANIFEST'] = str(manifest)
            env['EVIDENCE'] = str(js_dir)
            env['CHECKS'] = str(REPO / 'tests' / 'browser' / 'checks.cjs')
            env['PHASE_SECRET'] = secret
            env['PHASE_DIR'] = str(js_dir)
            completed = subprocess.run(
                [node, str(script)], cwd=temporary, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('PHASE_JS_OK', completed.stdout)
            js_saved = (js_dir / 'phase-error.json').read_text(encoding='utf-8')
            self.assertNotIn(secret, js_saved)
            self.assertEqual(stat.S_IMODE((js_dir / 'phase-error.json').stat().st_mode) & 0o077, 0)

    def test_visible_setup_fills_the_second_date_and_opens_headspace(self):
        text = (REPO / 'tests' / 'browser' / 'checks.cjs').read_text(encoding='utf-8')
        preview = text.split('async function journalPreviews', 1)[1].split('async function journalWrites', 1)[0]
        intention = preview.split("await page.goto(origin + '/journal/?synthetic=1'")[-1]
        date_at = intention.find('input[name="local_date"]')
        click_at = intention.find("name: 'Check proposal'")
        self.assertGreater(date_at, -1)
        self.assertLess(date_at, click_at)
        self.assertIn('manifest.anchor', intention[date_at:click_at])
        screens = text.split('async function screens', 1)[1].split('async function access', 1)[0]
        short = screens.split("day('short_sleep')", 1)[1].split("day('mixed')", 1)[0]
        open_at = short.find("summary', { hasText: 'Details' }")
        text_at = short.find('headroom.innerText()')
        self.assertGreater(open_at, -1)
        self.assertLess(open_at, text_at)
        self.assertIn('section[aria-label="Headspace"]', short)
        self.assertIn('element.open === true', short)
        self.assertIn('isVisible()', short)
        self.assertIn("wrap === 'anywhere'", short)
        self.assertIn("hidden !== 'hidden'", short)
        self.assertIn('manifest.long_headroom', short)
        self.assertNotIn('textContent', short)

    def test_cache_log_waits_for_the_appended_stylesheet_row(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / 'manifest.json'
            manifest.write_text('{"origin":"http://127.0.0.1:9"}', encoding='utf-8')
            script = root / 'cache-log.cjs'
            script.write_text(
                "const fs=require('fs'); const os=require('os'); const path=require('path');\n"
                "const checks=require(process.env.CHECKS);\n"
                "const dir=fs.mkdtempSync(path.join(os.tmpdir(),'cx83-cache-'));\n"
                "const file=path.join(dir,'proxy.log');\n"
                "const sheet='/static/tracking/app.css?v=shell-12';\n"
                "const line=(url,status,req,etag)=>'FORWARD GET '+url+' '+status+' req_inm='+req+' req_ims= etag='+etag+' cache=max-age%3D0\\n';\n"
                "function fail(code,detail){ process.stderr.write(detail+'\\n'); process.exit(code); }\n"
                "(async()=>{\n"
                "  fs.writeFileSync(file, line('/static/other.css',304,'old','old'));\n"
                "  const cursor=checks.logCursor(file);\n"
                "  const started=Date.now();\n"
                "  const pending=checks.waitForAppendedStylesheet(file, sheet, cursor, row=>row.status===304 && row.reqInm==='newtag' && row.etag==='newtag', 1000);\n"
                "  await new Promise(resolve=>setTimeout(resolve,150));\n"
                "  fs.appendFileSync(file, line(sheet,304,'newtag','newtag'));\n"
                "  const delayed=await pending;\n"
                "  if (!delayed.found || delayed.found.path!==sheet || delayed.found.reqInm!=='newtag' || delayed.found.etag!=='newtag') fail(2, JSON.stringify(delayed));\n"
                "  if (delayed.rows.some(row=>row.path!==sheet)) fail(3, JSON.stringify(delayed));\n"
                "  if (Date.now()-started<100) fail(4, 'matched before the append');\n"
                "  const emptyCursor=checks.logCursor(file);\n"
                "  const quiet=Date.now();\n"
                "  const none=await checks.waitForAppendedStylesheet(file, sheet, emptyCursor, row=>row.status===304, 200);\n"
                "  if (none.found || none.rows.length || Date.now()-quiet<150) fail(5, JSON.stringify(none));\n"
                "  const wrongCursor=checks.logCursor(file);\n"
                "  fs.appendFileSync(file, line('/static/tracking/other.css',304,'newtag','newtag'));\n"
                "  const wrongUrl=await checks.waitForAppendedStylesheet(file, sheet, wrongCursor, row=>row.status===304 && row.reqInm==='newtag', 200);\n"
                "  if (wrongUrl.found || wrongUrl.rows.length) fail(6, JSON.stringify(wrongUrl));\n"
                "  const badCursor=checks.logCursor(file);\n"
                "  fs.appendFileSync(file, line(sheet,304,'othertag','othertag'));\n"
                "  const wrongValidator=await checks.waitForAppendedStylesheet(file, sheet, badCursor, row=>row.status===304 && row.reqInm==='newtag' && row.etag==='newtag', 200);\n"
                "  if (wrongValidator.found || wrongValidator.rows.length!==1 || wrongValidator.rows[0].reqInm!=='othertag') fail(7, JSON.stringify(wrongValidator));\n"
                "  process.stdout.write('CACHE_LOG_OK\\n');\n"
                "})().catch(error=>{ process.stderr.write(String(error&&error.stack||error)); process.exit(1); });\n",
                encoding='utf-8')
            node = '/opt/homebrew/bin/node'
            if not Path(node).is_file():
                node = 'node'
            env = os.environ.copy()
            env.pop('NODE_OPTIONS', None)
            env.pop('PLAYWRIGHT_MODULE', None)
            env['MANIFEST'] = str(manifest)
            env['EVIDENCE'] = str(root)
            env['CHECKS'] = str(REPO / 'tests' / 'browser' / 'checks.cjs')
            completed = subprocess.run(
                [node, str(script)], cwd=temporary, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('CACHE_LOG_OK', completed.stdout)

    def test_csv_preview_accepts_only_the_two_verified_messages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / 'manifest.json'
            manifest.write_text('{"origin":"http://127.0.0.1:9"}', encoding='utf-8')
            script = root / 'csv-preview.cjs'
            script.write_text(
                "const checks=require(process.env.CHECKS);\n"
                "const base={calorie:'1',calorieHero:'1 cal',detailUrl:'http://127.0.0.1/summaries/nutrition/browser-csv-id/?synthetic=1',"
                "storedCsv:'source csv:browser-csv id browsercsv1 status CSV-ELIGIBLE',csvId:'browser-csv-id'};\n"
                "const local='Nothing is saved until you confirm.';\n"
                "const preserved='No records have been added yet.';\n"
                "function fail(code,detail){ process.stderr.write(detail+'\\n'); process.exit(code); }\n"
                "function withPage(page, patch){ return Object.assign({}, base, patch||{}, {page}); }\n"
                "if (!checks.csvPreviewOk(withPage('<p>'+local+'</p>'))) fail(2, checks.csvPreviewDetail(withPage(local)));\n"
                "if (checks.csvPreviewDetail(withPage(local))!=='preview='+local) fail(3, checks.csvPreviewDetail(withPage(local)));\n"
                "if (!checks.csvPreviewOk(withPage('<p>'+preserved+'</p>'))) fail(4, checks.csvPreviewDetail(withPage(preserved)));\n"
                "if (checks.csvPreviewDetail(withPage(preserved))!=='preview='+preserved) fail(5, checks.csvPreviewDetail(withPage(preserved)));\n"
                "const unrelated=checks.csvPreviewDetail(withPage('Records were saved.'));\n"
                "if (checks.csvPreviewOk(withPage('Records were saved.')) || unrelated!=='previewCopy') fail(6, unrelated);\n"
                "const fuzzy=checks.csvPreviewDetail(withPage('Nothing is saved until you confirm'));\n"
                "if (checks.csvPreviewOk(withPage('Nothing is saved until you confirm')) || fuzzy!=='previewCopy') fail(7, fuzzy);\n"
                "const partial=checks.csvPreviewDetail(withPage('No records have been added'));\n"
                "if (checks.csvPreviewOk(withPage('No records have been added')) || partial!=='previewCopy') fail(8, partial);\n"
                "const cases=[\n"
                "  ['calorie',{calorie:'2'},'calorie'],\n"
                "  ['caloriesUsed',{calorieHero:'Not used'},'caloriesUsed'],\n"
                "  ['detail',{detailUrl:'http://127.0.0.1/summaries/nutrition/other/'},'detail'],\n"
                "  ['source',{storedCsv:'id browsercsv1 status CSV-ELIGIBLE'},'source'],\n"
                "  ['sourceId',{storedCsv:'source csv:browser-csv status CSV-ELIGIBLE'},'sourceId'],\n"
                "  ['eligible',{storedCsv:'source csv:browser-csv id browsercsv1'},'eligible'],\n"
                "];\n"
                "for (const [name, patch, expected] of cases) {\n"
                "  const parts=withPage(local, patch);\n"
                "  const detail=checks.csvPreviewDetail(parts);\n"
                "  if (checks.csvPreviewOk(parts) || !detail.split(',').includes(expected)) fail(9, name+':'+detail);\n"
                "}\n"
                "process.stdout.write('CSV_PREVIEW_OK\\n');\n",
                encoding='utf-8')
            node = '/opt/homebrew/bin/node'
            if not Path(node).is_file():
                node = 'node'
            env = os.environ.copy()
            env.pop('NODE_OPTIONS', None)
            env.pop('PLAYWRIGHT_MODULE', None)
            env['MANIFEST'] = str(manifest)
            env['EVIDENCE'] = str(root)
            env['CHECKS'] = str(REPO / 'tests' / 'browser' / 'checks.cjs')
            completed = subprocess.run(
                [node, str(script)], cwd=temporary, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('CSV_PREVIEW_OK', completed.stdout)
