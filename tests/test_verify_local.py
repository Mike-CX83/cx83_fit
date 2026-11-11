"""Synthetic checks for disposable local verification. No provider and no checkout writes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from django.conf import settings
from django.test import SimpleTestCase

from tracking.sms import SmsError, send_text


REPO = Path(__file__).resolve().parents[1]


def load_runner():
    path = REPO / 'scripts' / 'verify_local.py'
    spec = importlib.util.spec_from_file_location('cx83_verify_local_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()


class VerificationEnvironmentTests(SimpleTestCase):
    def inherited(self, checkout):
        return {
            'PATH': '/usr/bin',
            'SMS_ENABLED': '1',
            'SMS_ACCOUNT_SID': 'ACsyntheticisolation',
            'SMS_FROM_NUMBER': '+15555550199',
            'SMS_AUTH_TOKEN_FILE': str(checkout / 'missing-synthetic-token'),
            'SITE_EDITS_ENABLED': '1',
            'OURA_ENABLED': '1',
            'OURA_CLIENT_SECRET_FILE': str(checkout / 'missing-oura-secret'),
            'DASHBOARD_PRIVATE_ROOT': str(checkout / 'private'),
            'DASHBOARD_STATIC_ROOT': str(checkout / 'staticfiles'),
            'DASHBOARD_TEST_LOOPBACK': '1',
            'MCP_WRITES_ENABLED': '1',
            'TMPDIR': str(checkout / 'tmp'),
            'TEMP': str(checkout / 'temp'),
            'TMP': str(checkout / 'var-tmp'),
        }

    def test_inherited_provider_and_site_edit_settings_are_neutralized(self):
        with tempfile.TemporaryDirectory(prefix='health-verify-env-') as folder:
            root = Path(folder)
            checkout = root / 'checkout'
            disposable = root / 'disposable'
            temp_dir = root / 'temp'
            env = RUNNER.verification_environment(
                self.inherited(checkout), disposable, loopback=False, temp_dir=temp_dir)
        self.assertEqual(env['PATH'], '/usr/bin')
        self.assertEqual(env['SMS_ENABLED'], '0')
        self.assertEqual(env['SITE_EDITS_ENABLED'], '0')
        self.assertEqual(env['DASHBOARD_PRIVATE_ROOT'], str(disposable.resolve()))
        self.assertEqual(env['DASHBOARD_STATIC_ROOT'], str(disposable.resolve() / 'staticfiles'))
        self.assertEqual(env['TMPDIR'], str(temp_dir.resolve()))
        self.assertEqual(env['TEMP'], str(temp_dir.resolve()))
        self.assertEqual(env['TMP'], str(temp_dir.resolve()))
        self.assertFalse(RUNNER._inside_checkout(temp_dir.resolve(), disposable.resolve()))
        self.assertNotIn('DASHBOARD_TEST_LOOPBACK', env)
        for key in (
            'SMS_ACCOUNT_SID', 'SMS_FROM_NUMBER', 'SMS_AUTH_TOKEN_FILE',
            'OURA_ENABLED', 'OURA_CLIENT_SECRET_FILE', 'MCP_WRITES_ENABLED',
        ):
            self.assertNotIn(key, env)
        self.assertFalse(env['DASHBOARD_STATIC_ROOT'].startswith(str(checkout)))
        self.assertFalse(env['DASHBOARD_PRIVATE_ROOT'].startswith(str(checkout)))

    def test_loopback_remains_opt_in(self):
        with tempfile.TemporaryDirectory(prefix='health-verify-loop-') as folder:
            root = Path(folder)
            plain = RUNNER.verification_environment(
                self.inherited(root / 'checkout'), root / 'plain', loopback=False, temp_dir=root / 'temp')
            opted = RUNNER.verification_environment(
                self.inherited(root / 'checkout'), root / 'opted', loopback=True, temp_dir=root / 'temp')
        self.assertNotIn('DASHBOARD_TEST_LOOPBACK', plain)
        self.assertEqual(opted['DASHBOARD_TEST_LOOPBACK'], '1')

    def test_running_suite_has_provider_and_site_edits_disabled(self):
        self.assertFalse(settings.SMS_ENABLED)
        self.assertFalse(settings.SITE_EDITS_ENABLED)
        self.assertEqual(settings.SMS_ACCOUNT_SID, '')
        self.assertEqual(settings.SMS_FROM_NUMBER, '')
        self.assertEqual(settings.SMS_AUTH_TOKEN_FILE, '')
        self.assertNotIn('site:write', settings.OAUTH2_PROVIDER['SCOPES'])
        with self.assertRaises(SmsError) as caught:
            send_text('+15555550100', 'synthetic')
        self.assertEqual(caught.exception.code, 'app_number_missing')


class DisposableStaticRootTests(unittest.TestCase):
    def base_env(self, private, static_root):
        return {
            'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
            'DJANGO_SETTINGS_MODULE': 'dashboard.settings',
            'DASHBOARD_LOCAL_ONLY': '1',
            'DASHBOARD_ALLOWED_HOSTS': '127.0.0.1,localhost,testserver',
            'DASHBOARD_PRIVATE_ROOT': str(private),
            'DASHBOARD_STATIC_ROOT': str(static_root),
            'OWNER_USERNAME': 'synthetic-owner',
            'DJANGO_SECRET_KEY': 'synthetic-verification-secret-key-not-used-outside-this-test-00',
            'PYTHONDONTWRITEBYTECODE': '1',
            'SMS_ENABLED': '0',
            'SITE_EDITS_ENABLED': '0',
        }

    def test_static_override_inside_the_checkout_is_refused(self):
        checkout_static = REPO / 'staticfiles'
        before = checkout_static.exists()
        with tempfile.TemporaryDirectory(prefix='health-verify-private-') as private:
            env = self.base_env(private, REPO / 'staticfiles')
            result = subprocess.run(
                [sys.executable, '-c', 'import dashboard.settings'],
                cwd=REPO, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DASHBOARD_STATIC_ROOT must stay outside the source checkout.', result.stderr)
        self.assertEqual(checkout_static.exists(), before)

    def test_collected_static_files_stay_outside_the_checkout(self):
        checkout_static = REPO / 'staticfiles'
        before = sorted(path.relative_to(checkout_static).as_posix()
                        for path in checkout_static.rglob('*') if path.is_file()) if checkout_static.exists() else []
        with tempfile.TemporaryDirectory(prefix='health-verify-static-') as folder:
            root = Path(folder)
            private = root / 'private'
            temp_dir = root / 'temp'
            private.mkdir()
            temp_dir.mkdir()
            env = RUNNER.verification_environment({
                'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
                'SMS_ENABLED': '1',
                'SMS_ACCOUNT_SID': 'ACsyntheticisolation',
                'SMS_FROM_NUMBER': '+15555550199',
                'SMS_AUTH_TOKEN_FILE': str(temp_dir / 'missing-synthetic-token'),
                'SITE_EDITS_ENABLED': '1',
                'TMPDIR': str(private / 'unsafe-temp'),
            }, private, loopback=False, temp_dir=temp_dir)
            env['DJANGO_SETTINGS_MODULE'] = 'dashboard.settings'
            probe = subprocess.run(
                [sys.executable, '-c',
                 'import django; django.setup(); from django.conf import settings; '
                 'print("SMS_ENABLED=" + str(settings.SMS_ENABLED)); '
                 'print("SMS_ACCOUNT_SID=" + settings.SMS_ACCOUNT_SID); '
                 'print("SITE_EDITS_ENABLED=" + str(settings.SITE_EDITS_ENABLED)); '
                 'print("STATIC_ROOT=" + str(settings.STATIC_ROOT)); '
                 'print("PRIVATE_ROOT=" + str(settings.PRIVATE_ROOT))'],
                cwd=REPO, env=env, capture_output=True, text=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            reported = dict(line.split('=', 1) for line in probe.stdout.splitlines() if '=' in line)
            self.assertEqual(reported['SMS_ENABLED'], 'False')
            self.assertEqual(reported['SMS_ACCOUNT_SID'], '')
            self.assertEqual(reported['SITE_EDITS_ENABLED'], 'False')
            self.assertEqual(Path(reported['STATIC_ROOT']).resolve(), (private / 'staticfiles').resolve())
            self.assertEqual(Path(reported['PRIVATE_ROOT']).resolve(), private.resolve())
            self.assertEqual(env['TMPDIR'], str(temp_dir.resolve()))
            collected = subprocess.run(
                [sys.executable, 'manage.py', 'collectstatic', '--noinput', '--verbosity', '0'],
                cwd=REPO, env=env, capture_output=True, text=True)
            self.assertEqual(collected.returncode, 0, collected.stderr)
            self.assertTrue((private / 'staticfiles' / 'tracking' / 'app.css').is_file())
            self.assertFalse(str(private / 'staticfiles').startswith(str(REPO)))
        after = sorted(path.relative_to(checkout_static).as_posix()
                       for path in checkout_static.rglob('*') if path.is_file()) if checkout_static.exists() else []
        self.assertEqual(after, before)


def tree_names(path):
    return sorted(item.relative_to(path).as_posix() for item in path.rglob('*'))


class TempRootTests(unittest.TestCase):
    def layout(self, folder):
        root = Path(folder)
        checkout = root / 'checkout'
        outside = root / 'outside'
        (checkout / 'tmp').mkdir(parents=True)
        outside.mkdir()
        (checkout / 'marker').write_text('synthetic')
        return checkout, outside

    def test_tmpdir_inside_the_checkout_creates_nothing(self):
        with tempfile.TemporaryDirectory(prefix='health-temp-root-') as folder:
            checkout, _outside = self.layout(folder)
            before = tree_names(checkout)
            with self.assertRaises(RUNNER.UnsafeTempRoot) as caught:
                RUNNER.validated_temp_parent({'TMPDIR': str(checkout / 'tmp')}, checkout)
            self.assertIn('TMPDIR', str(caught.exception))
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.validated_temp_parent({'TMPDIR': str(checkout)}, checkout)
            self.assertEqual(tree_names(checkout), before)

    def test_temp_or_tmp_inside_the_checkout_is_not_a_fallback(self):
        with tempfile.TemporaryDirectory(prefix='health-temp-root-') as folder:
            checkout, outside = self.layout(folder)
            before = tree_names(checkout)
            with self.assertRaises(RUNNER.UnsafeTempRoot) as caught:
                RUNNER.validated_temp_parent({
                    'TMPDIR': str(outside),
                    'TEMP': str(checkout / 'tmp'),
                }, checkout)
            self.assertIn('TEMP', str(caught.exception))
            with self.assertRaises(RUNNER.UnsafeTempRoot) as tmp_caught:
                RUNNER.validated_temp_parent({'TMP': str(checkout / 'tmp')}, checkout)
            self.assertIn('TMP', str(tmp_caught.exception))
            self.assertEqual(tree_names(checkout), before)

    def test_symlink_and_relative_path_into_the_checkout_create_nothing(self):
        with tempfile.TemporaryDirectory(prefix='health-temp-root-') as folder:
            root = Path(folder)
            checkout, outside = self.layout(folder)
            link = root / 'link-into-checkout'
            link.symlink_to(checkout / 'tmp', target_is_directory=True)
            before = tree_names(checkout)
            with self.assertRaises(RUNNER.UnsafeTempRoot):
                RUNNER.validated_temp_parent({'TMPDIR': str(link)}, checkout)
            previous = os.getcwd()
            try:
                os.chdir(outside)
                with self.assertRaises(RUNNER.UnsafeTempRoot):
                    RUNNER.validated_temp_parent({'TMPDIR': '../checkout/tmp'}, checkout)
            finally:
                os.chdir(previous)
            self.assertEqual(tree_names(checkout), before)
            self.assertEqual(link.resolve(), (checkout / 'tmp').resolve())

    def test_temp_dir_inside_the_data_root_creates_nothing(self):
        with tempfile.TemporaryDirectory(prefix='health-temp-root-') as folder:
            private = Path(folder) / 'private'
            private.mkdir()
            (private / 'marker').write_text('synthetic')
            before = tree_names(private)
            with self.assertRaises(RUNNER.UnsafeTempRoot) as caught:
                RUNNER.verification_environment({}, private, loopback=False, temp_dir=private / 'tmp')
            self.assertIn('disposable data root', str(caught.exception))
            self.assertEqual(tree_names(private), before)

    def test_external_directory_still_holds_the_disposable_root(self):
        with tempfile.TemporaryDirectory(prefix='health-temp-root-') as folder:
            root = Path(folder)
            checkout, outside = self.layout(folder)
            link = root / 'link-outside'
            link.symlink_to(outside, target_is_directory=True)
            before = tree_names(checkout)
            parent = RUNNER.validated_temp_parent({'TMPDIR': str(link)}, checkout)
            self.assertEqual(parent, outside.resolve())
            with tempfile.TemporaryDirectory(prefix='health-local-verification-', dir=parent) as created:
                created_path = Path(created).resolve()
                self.assertTrue(created_path.is_dir())
                self.assertFalse(created_path == checkout.resolve() or checkout.resolve() in created_path.parents)
                self.assertTrue(outside.resolve() in created_path.parents)
            self.assertEqual(tree_names(checkout), before)
            self.assertFalse(any(outside.glob('health-local-verification-*')))
