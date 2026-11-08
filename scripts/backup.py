"""Consistent SQLite/photo snapshots encrypted by restic, with isolated restore checks.

No scheduler, retention deletion or live restore is enabled here.
The caller supplies an installed restic binary and a separately protected password file.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
from uuid import UUID


TABLES = ('tracking_measurement', 'tracking_correction', 'tracking_summaryrecord',
          'tracking_summarycorrection', 'tracking_progressphoto', 'tracking_nutritiontargets',
          'tracking_writerequest', 'tracking_reviewnote', 'django_migrations',
          'oauth2_provider_application', 'oauth2_provider_accesstoken',
          'oauth2_provider_refreshtoken', 'oauth2_provider_grant',
          'tracking_dietentry', 'tracking_clinicalitem',
          'tracking_journalentry', 'tracking_journalobservation', 'tracking_journalcorrection',
          'tracking_journalmemory', 'tracking_journalquestion', 'tracking_journalscore',
          'tracking_sobrietyday',
          'tracking_ouraauthorization', 'tracking_ouraconnection', 'tracking_ourasync',
          'tracking_ourapage', 'tracking_ourarecord', 'tracking_ourarevision')
# Older snapshots omit later groups. A group is counted only when every table in it exists.
OPTIONAL_GROUPS = (
    ('Oura', ('tracking_ouraauthorization', 'tracking_ouraconnection', 'tracking_ourasync',
              'tracking_ourapage', 'tracking_ourarecord', 'tracking_ourarevision')),
    ('Plan', ('tracking_dietentry', 'tracking_clinicalitem')),
    ('Journal', ('tracking_journalentry', 'tracking_journalobservation', 'tracking_journalcorrection')),
    ('JournalContinuity', ('tracking_journalmemory', 'tracking_journalquestion', 'tracking_journalscore')),
    ('Sobriety', ('tracking_sobrietyday',)),
)


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def counted_tables(present):
    """Choose allowlisted tables that this snapshot actually has."""
    present = set(present)
    optional = {name for _, group in OPTIONAL_GROUPS for name in group}
    chosen = [name for name in TABLES if name not in optional]
    for label, group in OPTIONAL_GROUPS:
        found = [name for name in group if name in present]
        if not found:
            continue
        if len(found) != len(group):
            raise ValueError(f'{label} schema is incomplete; do not back up a partial migration.')
        chosen.extend(group)
    return chosen


def counts(db, tables=None):
    # Preserve restoration of snapshots made before later optional groups.
    # Names from a restored manifest must never become arbitrary SQL.
    if tables is None:
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        tables = counted_tables(present)
    if not tables or not set(tables) <= set(TABLES):
        raise ValueError('Unknown backup manifest table.')
    return {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in tables}


def snapshot(private_root, target):
    """SQLite backup API plus immutable referenced photo files under a reserved write lock."""
    private_root = Path(private_root).resolve(strict=True)
    db_path = private_root/'dashboard.sqlite3'
    if db_path.is_symlink() or not db_path.is_file():
        raise ValueError('A regular dashboard database is required.')
    target = Path(target)
    with sqlite3.connect(db_path, timeout=20) as lock:
        lock.execute('BEGIN IMMEDIATE')
        with sqlite3.connect(db_path.as_uri()+'?mode=ro', uri=True) as source, sqlite3.connect(target/'dashboard.sqlite3') as destination:
            source.backup(destination)
        os.chmod(target/'dashboard.sqlite3', 0o600)
        manifest = {'format': 'private-health-backup-v1', 'counts': counts(lock), 'files': {}}
        for photo_id, original_format, original_hash in lock.execute(
                'SELECT id, original_format, original_sha256 FROM tracking_progressphoto WHERE deleted_at IS NULL'):
            photo_id = str(UUID(photo_id))
            extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[original_format]
            for index, name in enumerate([f'photos/{photo_id}/original.{extension}', f'photos/{photo_id}/display.jpg']):
                source_file = private_root/name
                if source_file.is_symlink() or not source_file.resolve(strict=True).is_relative_to(private_root/'photos'):
                    raise ValueError('Photo paths must remain inside private storage.')
                destination = target/name
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                shutil.copyfile(source_file, destination)
                destination.chmod(0o600)
                file_hash = digest(destination)
                if index == 0 and file_hash != original_hash:
                    raise ValueError('An original photo failed its integrity check.')
                manifest['files'][name] = file_hash
        manifest['files']['dashboard.sqlite3'] = digest(target/'dashboard.sqlite3')
        (target/'manifest.json').write_text(json.dumps(manifest, indent=2))
        (target/'manifest.json').chmod(0o600)
    return manifest


def verify_restore(root):
    root = Path(root)
    manifest = json.loads((root/'manifest.json').read_text())
    if manifest.get('format') != 'private-health-backup-v1':
        raise ValueError('Unknown backup format.')
    for name, expected in manifest['files'].items():
        path = root/name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root.resolve()):
            raise ValueError('Unexpected restored path.')
        if digest(path) != expected:
            raise ValueError('A restored file failed its integrity check.')
    with sqlite3.connect((root/'dashboard.sqlite3').resolve().as_uri()+'?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Restored database integrity failed.')
        if counts(db, manifest['counts']) != manifest['counts']:
            raise ValueError('Restored record counts differ.')
    return {'verified_files': len(manifest['files']), 'counts_match': True, 'integrity': 'ok'}


class Restic:
    def __init__(self, binary, repository, password_file, *, rclone=None, rclone_config=None):
        self.binary = str(Path(binary).resolve(strict=True))
        self.remote = str(repository).startswith('rclone:')
        self.rclone = self.rclone_config = None
        if self.remote:
            match = re.fullmatch(r'rclone:(health_dashboard_backup):(cx83-personal-health-dashboard/[A-Za-z0-9_-]+)', str(repository))
            if not match or not rclone or not rclone_config:
                raise ValueError('Use the dedicated backup remote, repository directory and explicit rclone files.')
            self.repository = str(repository)
            self.rclone = str(Path(rclone).resolve(strict=True))
            config_path = Path(rclone_config)
            if config_path.is_symlink() or not config_path.is_file() or config_path.stat().st_mode & 0o077:
                raise ValueError('The rclone configuration must be a private regular file.')
            self.rclone_config = str(config_path.resolve())
            config = configparser.ConfigParser(interpolation=None)
            config.read(self.rclone_config)
            if set(config.sections()) != {'health_dashboard_backup'}:
                raise ValueError('Use a separate configuration containing only the backup connection.')
            remote = config['health_dashboard_backup']
            if remote.get('type') != 'drive' or remote.get('scope') != 'drive.file' or not remote.get('client_id'):
                raise ValueError('Use a dedicated Google client and the limited drive.file scope.')
            if remote.get('service_account_file') or remote.get('team_drive'):
                raise ValueError('This connection uses user OAuth and My Drive, not a service account or Shared Drive.')
            token = json.loads(remote.get('token', '{}'))
            if not token.get('refresh_token'):
                raise ValueError('Authorize offline backup access before using the repository.')
        else:
            if rclone or rclone_config or ':' in str(repository):
                raise ValueError('Do not mix local storage with remote credential options.')
            self.repository = Path(repository).resolve()
        password = Path(password_file)
        if password.is_symlink() or not password.is_file() or password.stat().st_mode & 0o077:
            raise ValueError('The password file must be a private regular file (mode 600).')
        self.password = password.resolve()
        if not self.remote and self.password.is_relative_to(self.repository):
            raise ValueError('Keep the password outside the encrypted repository.')

    def run(self, *args, cwd=None):
        # Ignore inherited restic overrides, including password commands and remote destinations.
        env = {key: value for key, value in os.environ.items() if not key.startswith(('RESTIC_', 'RCLONE_'))}
        options = []
        if self.remote:
            env['RCLONE_CONFIG'] = self.rclone_config
            options = ['-o', 'rclone.program=' + self.rclone]
        result = subprocess.run([self.binary, *options, '--repo', str(self.repository), '--password-file', str(self.password),
            '--no-cache', '--json', *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=1800)
        if result.returncode:
            raise ValueError(f'Restic {args[0]} failed (exit {result.returncode}); check the binary, repository and password locally.')
        return result.stdout

    def backup(self, private_root, initialize=False):
        private_root = Path(private_root).resolve(strict=True)
        if not self.remote and (self.repository.is_relative_to(private_root) or private_root.is_relative_to(self.repository)):
            raise ValueError('Use a separate repository outside private application storage.')
        if initialize:
            if self.remote:
                env = {key: value for key, value in os.environ.items() if not key.startswith(('RESTIC_', 'RCLONE_'))}
                # Inspect this dedicated directory only; never list the user's Drive.
                target = self.repository.removeprefix('rclone:')
                check = subprocess.run([self.rclone, '--config', self.rclone_config, 'lsf', target,
                    '--max-depth', '1'], env=env, capture_output=True, text=True, timeout=60)
                if check.returncode not in (0, 3) or check.stdout.strip():
                    raise ValueError('Remote initialization requires a new empty directory.')
            elif self.repository.exists():
                raise ValueError('Initialization requires a new repository path.')
            self.run('init')
        with tempfile.TemporaryDirectory(prefix='health-backup-', dir=private_root) as staging:
            snapshot(private_root, Path(staging))
            output = self.run('backup', '.', '--host', 'private-health-dashboard', '--tag', 'health-v1', cwd=staging)
        summary = next(json.loads(line) for line in output.splitlines() if json.loads(line).get('message_type')=='summary')
        snapshot_id = summary['snapshot_id']
        if not re.fullmatch('[0-9a-f]{64}', snapshot_id):
            raise ValueError('Unexpected snapshot identifier.')
        return snapshot_id

    def restore_check(self, snapshot_id, parent):
        if not re.fullmatch('[0-9a-f]{8,64}', snapshot_id):
            raise ValueError('Use an explicit snapshot ID, not latest.')
        self.run('check', '--read-data')
        with tempfile.TemporaryDirectory(prefix='health-restore-check-', dir=parent) as target:
            self.run('restore', snapshot_id, '--target', target, '--verify')
            return verify_restore(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore-check'])
    parser.add_argument('--restic', required=True, help='Absolute installed restic binary path')
    parser.add_argument('--repository', required=True, help='Local repository or dedicated rclone backup repository')
    parser.add_argument('--rclone', help='Absolute verified rclone binary path for Google Drive')
    parser.add_argument('--rclone-config', help='Dedicated mode 600 Google Drive backup configuration')
    parser.add_argument('--password-file', required=True)
    parser.add_argument('--private-root')
    parser.add_argument('--initialize', action='store_true', help='Initialize a new repository only')
    parser.add_argument('--snapshot')
    parser.add_argument('--restore-parent', help='Existing private directory for disposable plaintext restore')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        restic = Restic(args.restic, args.repository, args.password_file,
                        rclone=args.rclone, rclone_config=args.rclone_config)
        if args.action == 'backup':
            if not args.private_root:
                parser.error('backup requires --private-root')
            result = {'snapshot_id': restic.backup(args.private_root, args.initialize)}
        else:
            if not args.snapshot or not args.restore_parent:
                parser.error('restore-check requires --snapshot and --restore-parent')
            result = restic.restore_check(args.snapshot, args.restore_parent)
        print(json.dumps(result))
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError, StopIteration, KeyError, configparser.Error):
        # Tool output can include private paths. Do not echo it or raw exception inputs.
        print('Backup operation failed. Check local paths, permissions, repository credentials and file integrity. No live restore was performed.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
