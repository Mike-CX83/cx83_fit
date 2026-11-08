# Operations and release gates

## Current environment

The November 6 local continuation preserved the existing repository, personal storage and connections. Workspace writes, loopback listeners and downloads work in this session. The independent first release modules, private export and encrypted restore proof are implemented. The full synthetic suite passes 204 tests including actual HTTP; see `VERIFICATION.md` for exact evidence. Pillow 13.0.0 and Django OAuth Toolkit 3.4.1 with required dependencies were added without upgrading the original pins; all 41 locked dependencies passed strict advisory checks. Chart.js 4.6.1 is hosted locally with its license. No production migration, SSH action or deployment occurred.

Current changes remain uncommitted from baseline `5573b02`. Existing production/personal configuration was not loaded or altered. Synthetic fixture servers and databases are separate from `private/`.

## Before activation

1. Preserve the existing hash locked dependency set, validate installation on the intended platform and refresh its advisory audit before release. The November 6 strict audit passed for all 41 dependencies.
2. Run Django tests and `makemigrations --check --dry-run`; validate migrations match the models.
3. Preserve the passing synthetic OAuth/HTTP MCP tests, separately from browser authentication. Select the built in personal issuer with the approved HTTPS origin, or independently configure an external issuer, audience, subject and JWKS. Follow `MCP_SETUP.md`; do not reuse CX83 business credentials. Toolkit migrations were exercised only in disposable databases and require deliberate authorization before applying to existing personal or production storage.
4. Verify the remote connection using the actual ChatGPT account. A local SDK client cannot satisfy this acceptance requirement.
5. Inspect an authorized DigitalOcean host read only. Confirm separate OS user, app path, SQLite volume, credential storage, private media path and available disk/memory. One application process is sufficient initially. Sharing a server is not physical isolation.
6. Obtain authorization for any existing reverse proxy changes, production migrations, domain changes or paid services. No deployment template should be applied blindly.
7. Use HTTPS, explicit hosts, secure cookies, an ASGI server and a controlled proxy that strips untrusted forwarding headers. Keep production local mode disabled. Run `manage.py check --deploy`. Supply static assets from the app's collected static directory only. Never map a private media directory into a web server.

## Restart and continuity proof

The existing local acceptance test proves the synthetic browser/MCP flow and persistence across an actual process restart using the composed ASGI application and a disposable disk database. The November 6 suite also passes actual loopback HTTP transport tests. `scripts/verify_oauth.py` separately proves real local consent, token issuance, scoped MCP, restart, refresh rotation and owner revocation. Actual ChatGPT account consent and deployment remain separate release checks.

Use a fresh synthetic database, create an authenticated browser entry, read and correct it via authenticated MCP, retry its request, then stop the process and restart with the same private volume. Reauthenticate and verify the same record ID, version, value, units, date and audit history. Repeat with outbound networking disabled to prove reads depend on stored data. Do not populate real health history until this test succeeds.

## Implemented encrypted backup and isolated restore

### Google Drive preparation, November 6

Mike selected Google Drive as the primary encrypted destination, explicitly using **CX83 Labs Google Workspace**, with an optional later Mac copy. Use the Workspace user's My Drive with a dedicated backup folder; no Shared Drive has been selected. The connected ChatGPT Drive app uses Gmail and is independent of this authorization. **On November 7, the dedicated Workspace authorization and one real synthetic encrypted upload/restore passed from the Mac.** The verified account is `mike@cx83labs.com`. No server schedule or dashboard deployment has run, and no real health records were uploaded. Official restic 0.19.1 and rclone 1.76.0 Mac ARM64/Linux AMD64 release archives were downloaded into ignored `output/deploy/tools/` and matched upstream SHA256SUMS. See `docs/evidence/backup-tools.json` and `drive-backup-verification.json`. No global install or project dependency change occurred.

The existing `scripts/backup.py` now additionally accepts only a dedicated Google Drive remote under `rclone:health_dashboard_backup:cx83-personal-health-dashboard/<repository>`. Remote mode requires explicit rclone/config paths, a private config containing only that remote, a dedicated client, `drive.file` scope and offline authorization. It removes inherited RESTIC/RCLONE overrides and refuses nonempty initialization targets. The established snapshot/encryption/restore logic is reused. Local compatibility passed the existing synthetic SQLite/photo/encrypted-token backup, restore and restored application checks. Focused configuration checks rejected full Drive scope and verified inherited credential isolation; no full application suite was rerun.

Google setup requires Mike's CX83 Labs Workspace account. Rclone's shared Google client is being retired; do not use it. Create/select a dedicated Google Cloud project **owned by the CX83 Labs organization**, enable **Google Drive API**, configure Google Auth Platform branding with **Internal** audience and add only `https://www.googleapis.com/auth/drive.file` under Data Access. Use a **Desktop app** OAuth client named `CX83 Personal Health Backups`. Download its client JSON locally; do not paste it in chat or commit it. `drive.file` limits this client to files it creates, including a new visible `cx83-personal-health-dashboard` folder. A root-folder setting alone is not an authorization boundary. [Rclone scope documentation](https://rclone.org/drive/#scopes), [Google Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app).

Internal audience restricts this client to the Workspace organization and does not use the External Testing/publishing workflow. Workspace admin policies can still block or limit it. If Internal is unavailable, check project organization ownership rather than silently switching to External or changing organization-wide controls. External Testing refresh tokens expire after seven days and are unsuitable for unattended backups. If Google requests homepage/privacy URLs, use only accurate reachable pages, never claim the reserved dashboard URLs are live. No OAuth app publishing, administrator policy change or consent has been performed. [Google OAuth app states](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview), [refresh token policy](https://developers.google.com/identity/protocols/oauth2#expiration).

After the JSON is downloaded, run the helper below with its actual local path. It imports credentials into mode 0600 `secrets/backup/rclone/rclone.conf`, opens Google's browser flow through rclone and suppresses provider/config output. It never changes the default rclone config. On successful offline authorization it creates `secrets/backup/restic-password` once with mode 0600. Reauthorization uses `--authorize --reauthorize` without replacing the backup password. Rclone handles token refresh and atomic config updates; its credential directory must remain writable. OAuth `client_secret` must be stored verbatim: rclone marks this field Sensitive rather than IsPassword, and `oauthutil.OverrideCredentials` passes it directly to the OAuth client. It must not be run through `rclone obscure`. Filesystem protections are required. [Pinned rclone implementation](https://github.com/rclone/rclone/blob/v1.76.0/lib/oauthutil/oauthutil.go).

November 7 correction: the initial helper incorrectly obscured the Desktop OAuth secret. No token was present. Its protected config was retained in a mode 0600 `rclone.conf.before-secret-fix-*` file and the matching client's unauthenticated configuration was corrected atomically. Existing authorized configurations refuse this implicit repair. Three focused synthetic credential-import regression tests passed; no application suite was repeated. Failed OAuth runs now expose only an allowlisted error name, never the raw provider response or config. Earlier prepared backup supplements contain the incorrect importer and must be superseded before deployment; the application image itself is unaffected.

```sh
.venv/bin/python scripts/setup_drive_backup.py \
  --rclone output/deploy/tools/rclone-1.76.0/osx-arm64/rclone \
  --client-json /actual/local/downloaded-client.json --authorize
```

Save the generated backup password separately in Mike's password manager before real records or scheduling. Keep the dedicated Google client/config recoverable too. No password manager item has been created or recovery password displayed. Never put these files in Git, Drive backup contents or chat. The existing standalone Oura/MyFitnessPal credentials and callbacks are unrelated and remain untouched.

After fresh authorization and before uploading, verify the selected Workspace identity using Google's documented `GET https://www.googleapis.com/drive/v3/about?fields=user(emailAddress)` with the access token in the Authorization header, not the URL. Read the protected token in process memory, disable redirects and compare the returned address to `mike@cx83labs.com` without logging it or the token. This metadata-only read supports `drive.file`. Rclone Drive does **not** implement `rclone config userinfo`; do not treat its unsupported-method error as an OAuth failure. This account/API check passed on November 7 before the upload. The connected ChatGPT Drive profile is not evidence of the backup connection's account. Browser automation remains unavailable; future reauthorization uses the helper and owner browser consent, not a connector reset. Do not change or reuse Gmail connector authorization. [Google Drive metadata API](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get).

To reproduce the real Drive verification using the existing synthetic fixture, replace `UNIQUE` with a fresh suffix. This creates a new encrypted test repository and performs one full data check and isolated restore, including application reads, exact Oura synthetic originals/revisions, photos and token decryption. It never reads the existing personal database. The test repository is retained; it does not prune or delete other backups.

That proof has now passed for `synthetic-check-20261107-44e79a13`; the commands below are reproduction instructions, not a request to rerun it. Preserve the verified repository and use the separate `restic` directory for production only after deployment approval. The recovery password exists in protected local storage; its separate password-manager copy is still an owner action. The remote repository contains only encrypted data and encrypted key material, never the recovery password or rclone config.

```sh
.venv/bin/python scripts/verify_backup.py \
  --restic output/deploy/tools/restic-0.19.1/darwin_arm64/restic \
  --rclone output/deploy/tools/rclone-1.76.0/osx-arm64/rclone \
  --rclone-config secrets/backup/rclone/rclone.conf \
  --password-file secrets/backup/restic-password \
  --repository rclone:health_dashboard_backup:cx83-personal-health-dashboard/synthetic-check-UNIQUE \
  --output docs/evidence/drive-backup-verification.json
```

After dashboard deployment approval, `deploy/live.cx83labs.com/compose.backup.yaml` provides a separate one-shot backup container with no public ports, app dependency or shared business network. It mounts only this dashboard volume, explicit script/tools, the writable dedicated rclone credential directory and read-only recovery password. Tools must be installed as `tools/restic` and `tools/rclone` (0555), script readable, credential directory/config/password owned by UID/GID 10001 at 0700/0600. The prepared service/timer proposes daily backups at 03:15 America/Chicago plus up to 15 minutes jitter, with a missed-run catchup after reboot. Nothing is installed/enabled. Verify `/usr/bin/docker` and current credentials before activation. Use the same explicit project and all four Compose files; initialization is a deliberate first command with all normal backup arguments plus `--initialize`, not a container startup migration. The timer's normal command omits initialization. No retention deletion is implemented or authorized by this preparation. To stop scheduled backups later, disable only `personal-health-backup.timer`; retain repository, credentials and data. Dashboard and personal connectors keep running.

`scripts/backup.py` is an operator command, not a browser endpoint or scheduled job. It obtains an IMMEDIATE SQLite reserved write lock, uses SQLite's online backup API through a separate read connection, then copies only active referenced immutable photo originals and display files while retaining that lock. The snapshot manifest records hashes and table counts. A private temporary directory under the selected private root holds the plaintext staging snapshot until restic completes; normal success and error exits remove it. A killed process can leave this private staging directory, so inspect it intentionally before removing anything. Use encrypted local disk storage for temporary plaintext snapshots/restores.

Use an installed, verified restic binary and a random password stored in a mode 600 file separately from the encrypted repository. Preserve that password through a trusted secret store; losing it makes the repository unusable. The following paths are placeholders for a separately authorized local instance and backup destination:

```sh
.venv/bin/python scripts/backup.py backup \
  --restic /absolute/path/to/restic \
  --private-root /private/application/storage \
  --repository /separate/encrypted/repository \
  --password-file /separate/protected/password-file \
  --initialize
```

Use `--initialize` only for the first backup into a new path; the command refuses an existing destination. Subsequent backups omit it. This example uses local storage outside application data. Google Drive requires the explicit remote/configuration options above; no backend or credential is inferred. Capture the returned snapshot ID, then verify that exact snapshot:

```sh
.venv/bin/python scripts/backup.py restore-check \
  --restic /absolute/path/to/restic \
  --repository /separate/encrypted/repository \
  --password-file /separate/protected/password-file \
  --snapshot SNAPSHOT_ID \
  --restore-parent /existing/private/test-directory
```

This runs restic `check --read-data` and `restore --verify` into a new disposable subdirectory. It validates file hashes, SQLite integrity/foreign keys and tracked table counts, then removes the disposable restore. It never replaces live storage. `scripts/verify_backup.py --restic /absolute/path/to/restic` separately creates a complete synthetic application fixture, verifies restored Django queries and owner authentication, rejects a wrong password and detects tampering. This proof passed on November 6 with restic 0.19.1. [Restic restore documentation](https://restic.readthedocs.io/en/stable/050_restore.html), [repository checks](https://restic.readthedocs.io/en/stable/045_working_with_repos.html).

For an actual disaster recovery, stop writes and source collection, select the intended snapshot, restore to a separate empty private directory with restic, and run integrity checks before any cutover. Use the matching repository source/schema and separately protected application configuration. Do not copy an old `.env` from an untrusted archive. Reapply deletions made after the selected snapshot, clear restored browser sessions and pending previews, and remove restored OAuth access tokens, refresh tokens and pending grants before activation. An older snapshot can otherwise revive a later revoked authorization; require fresh owner consent. Keep client application registrations unless deliberately changing them. Rotate credentials if compromise is suspected, and validate representative reads with MCP/source writes disabled. Switching the application's private root to restored storage requires explicit authorization and a reversible rollback plan. This local task performed no such cutover.

Backups include the database (including authentication hashes, sessions, review state, OAuth client registrations, hashed tokens and pending grants) and active referenced photos. The manifest includes the four core OAuth table counts, and the synthetic restoration proof was rerun after adding Toolkit. Backups deliberately exclude environment secret files, source code, temporary uploads and orphan files. Keep source code and separately protected configuration available for recovery. No actual destination, off-device copy, automatic schedule or retention deletion was configured. Proposed retention remains seven daily and four weekly encrypted snapshots, pending an explicit operational decision. Old snapshots and exported ZIP files retain their original data until intentionally expired or removed.

Measurement/summary deletion hides records and retains corrections and source tombstones. Photo deletion clears notes and removes both files. Saved review deletion clears current text/receipt and retains a retry tombstone. A permanent erasure workflow across old exports/backups is separate; do not silently prune history.

## Export and request bounds

The authenticated CSRF protected export assembles usable exact JSON, spreadsheet safe CSV, audit/source/tombstone history, targets, saved reviews and original/display photos into a ZIP. It excludes synthetic history by default, caps output at 512 MiB and bounds record/audit categories. Private ASGI photo/export downloads stream in 64 KiB chunks. The exported ZIP is plaintext and must be stored privately.

Upload handlers enforce actual file bytes: 64 KiB for measurements, 256 KiB for summaries, 12 MiB for photos. `dashboard/request_limits.py` additionally bounds incoming Django request bodies before its ASGI handler spools them. Normal routes allow 64 KiB; the three upload routes allow their file bound plus 16 KiB for multipart fields. Oversized declared lengths are rejected without receiving a body, and actual chunk bytes are counted even without a length or with a falsely small length. Invalid or duplicate length headers return 400, oversized bodies 413, and uploads idle for 15 seconds or exceeding 120 seconds total return 408. These errors contain no request data and use private no-store headers. A rejected partial upload closes Django's spool before any view runs. The timeout ends when the body is complete, so it does not cancel a long export or response. MCP retains the SDK's independent 64 KiB limit.

These bounds passed real Django ASGI tests and actual Uvicorn HTTP tests; the OAuth process proof also passed through the new wrapper. Before hosted release, configure matching reverse proxy bounds and test request handling, free disk, export memory, concurrent load and backup duration against the authorized server capacity. Application bounds do not protect a proxy that buffers requests upstream. No reverse proxy configuration was changed here.

## Import preview retention

Reviews become unusable after 15 minutes. Confirmation removes their row payload; cancellation, replacement and logout also discard it. Expired reviews are removed when accessed. An abandoned payload can remain in the database session row until session cleanup, so expiry is not immediate physical erasure. Use Django’s `clearsessions` maintenance command for expired sessions in an authorized operational schedule; no schedule was enabled by this local continuation.

## Data and logs

Current application logs discard request details rather than send sensitive values to crash reporting or analytics. Before production, add a minimal operational log containing event types and opaque request IDs only, with no bodies, measurements, notes, credentials or signed URLs. Measure resource use using synthetic data. No regulatory compliance claim is made.

## Oura credentials and backup compatibility

See `OURA_SETUP.md` for the separate outbound Oura configuration and local proof. Credential and pending PKCE ciphertext are stored in SQLite; the Fernet key and Oura client secret are private files outside the data/backup root. Exports omit tokens. A database backup alone does not recover encrypted tokens without the separately protected key. Keep key custody distinct and never overwrite an existing key during setup.

Backup counts now include the six Oura tables when the complete migration is present. Older v1 snapshots without those tables remain verifiable; restore only their declared, allowlisted table counts. A partially created Oura schema is rejected. The synthetic restic proof includes source originals/revisions and decryption of restored token ciphertext using a separately held key. Perform schema upgrades only after a verified backup in the explicitly authorized instance. No recurring job or retention cleanup has been enabled.
