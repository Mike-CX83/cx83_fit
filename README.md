# Private Health Dashboard

Local first release implementation checkpoint, November 6, 2026. **Measurements, private photos, summaries, targets, charts, reviews, imports, exports and encrypted restore are implemented and tested locally. Actual ChatGPT access, physical iPhone checks and deployment remain incomplete.** No personal records, credentials, wearable files or photos are included.

The complete governing specification was read from `/Personal_Health_Fitness_Dashboard_Build_Prompt.txt` in ChatGPT on November 5, 2026, all 412 lines, 20,565 bytes. `rule_set.docx` was also read. The specification remains the finish line; this checkpoint does not replace it.

## Oura continuation

The Oura adapter, public privacy/terms pages and OAuth callback are implemented locally with synthetic tests. It reuses the reviewed MIT collection registry and established OAuth/crypto/HTTP libraries. Raw source records and revisions preserve original IDs, numeric values, units and missing values. Stored Oura records are available through the existing OAuth protected `read_oura` tool and export. Oura remains disabled and unconnected until actual registration and consent. See [exact URLs and setup](docs/OURA_SETUP.md). The latest full suite passes 237 tests; the dependency audit covers 42 locked packages. No personal database migration or deployment occurred.

## What exists

One Django application and SQLite database with owner restricted sessions, CSRF, login limiting, measurements, private photos, nutrition/recovery/activity/clinical summaries, editable targets, Chart.js trends, saved reviews, separate annotations, reviewed CSV imports, private exports, restic backups and scoped OAuth MCP. The history page shows previous and current values, source and escaped notes. Imported originals remain read only. MCP stays disabled until explicitly configured. An optional personal OAuth issuer now runs inside the same application using Django OAuth Toolkit; existing external JWT mode remains supported. Read and write authorization are separate from browser login.

The existing project `.venv` and original dependency pins were preserved while adding Pillow 13.0.0 and Django OAuth Toolkit 3.4.1 with required dependencies. The latest passing suite count and rendered checks are recorded in `docs/VERIFICATION.md`. External JWT persistence tests use real Django/SDK ASGI applications and replace only the JWKS fetch. The separate built in issuer proof performs real consent, token exchange, scoped MCP reads/writes, retry, restart, refresh and revocation over loopback with no issuer substitute. These synthetic checks do not establish actual ChatGPT access. See [verification evidence](docs/VERIFICATION.md).

## Decisions and status

Read `docs/PHASE_1.md`, `docs/INTEGRATIONS.md`, `docs/DATA_CONTRACT.md`, `docs/VERIFICATION.md` and `docs/OPERATIONS.md`.

MyFitnessPal was successfully read through the existing ChatGPT connection on November 5, 2026. That historical check does not connect the dashboard. No direct source adapter is enabled. Nutrition targets are editable and have no default recommendations. There are no paid AI calls, background AI tasks or business mailbox connections.

## Local setup

Use the existing `.venv` for this checkpoint. `requirements.lock` was generated with Python 3.13, and installed versions match it. This session verified workspace writes, loopback listeners and PyPI DNS resolution. The locked set of 42 dependencies passed a strict advisory audit with none skipped and no reported vulnerabilities. The earlier socket and DNS failures describe the prior session. No environment reset, existing connection change or deployment occurred. Pillow and Django OAuth Toolkit with its required dependencies were added without upgrading the original pins. Validate the lock on the intended deployment platform before release. Never weaken authentication to make a preview run.

```sh
# Only when creating a fresh development environment:
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
```

For first time initialization of a separate local instance, use the setup below. For an existing instance, preserve its database, owner and securely stored secret; do not regenerate credentials or repeat account creation.

```sh
export DASHBOARD_LOCAL_ONLY=1
export DASHBOARD_ALLOWED_HOSTS=127.0.0.1,localhost
export OWNER_USERNAME=owner
export DJANGO_SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))')"
umask 077
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser --username "$OWNER_USERNAME"
.venv/bin/python -m uvicorn dashboard.asgi:application --host 127.0.0.1 --port 8000 --no-access-log
```

The superuser command creates the initial account only; no admin or registration URL is exposed. Save the generated secret securely outside source control before restarting, or sessions will be invalidated. The database remains persistent in `private/dashboard.sqlite3`. Local HTTP is for loopback only. Never bind this development mode to a public interface or tunnel it.

The initial screen is intentionally simple. Use synthetic entries for acceptance checks. Synthetic entries never become real entries through correction. Loopback listeners work in the current session; the default verification still works without a listening socket.

For personal OAuth in this application, explicitly select `MCP_AUTH_MODE=builtin` and set `MCP_PUBLIC_ORIGIN` to the selected origin. Local synthetic development can use `http://127.0.0.1:8000` with local mode enabled; a hosted release requires HTTPS and local mode disabled. Leave writes disabled unless deliberately enabling the separate consent scope. Existing external issuer variables must not be mixed with built in mode. See [MCP setup](docs/MCP_SETUP.md) for all settings, migration boundaries and actual ChatGPT acceptance. No existing personal configuration or database was modified to activate this mode.

## Reviewed measurement CSV import

From the authenticated overview, choose **Import CSV**, enter a stable source name, upload the file, review the rows and confirm. Upload and preview create no measurements. Reviews are stored in the database session, belong to that owner and browser session, and expire after 15 minutes. A new upload replaces the previous review. Confirmation uses the stored rows rather than browser supplied replacements. Confirmation and cancellation require CSRF protection.

The format is UTF-8 CSV with an optional BOM, at most 64 KiB and 200 data rows. Required columns are `source_record_id,metric,value,unit,local_date,source_timezone,synthetic`. Optional columns are `side,location,notes,observed_at`. Headers must be exact; column order may vary. The following example is entirely synthetic:

```csv
source_record_id,metric,value,unit,local_date,source_timezone,synthetic,side,location,notes,observed_at
synthetic-001,weight,100.125,kg,2026-11-05,America/Chicago,true,,,Synthetic verification,2026-11-05T08:30:00-06:00
```

Use lowercase `true` or `false` explicitly for `synthetic`. Weight accepts `kg` or `lb`; circumferences accept `cm` or `in` and require a location. Arm, thigh and calf require `left` or `right`. Dates use `YYYY-MM-DD`, source timezones use IANA names, and optional observed times include a UTC offset consistent with the local date. Date only measurements stay date only.

The source name accepts 1 to 32 lowercase letters, digits, underscores or hyphens and starts with a letter or digit. It becomes `csv:<name>`. Row IDs accept 1 to 120 ASCII letters, digits, periods, underscores, colons or hyphens and start with a letter or digit. Reuse the same source name and stable row IDs for later files from that source. Identical stored rows are visibly skipped; changed values under an existing ID or deleted rows block the entire batch. Confirmation rechecks IDs inside one transaction. Each added row has a distinct audit request, with a separate batch receipt for retries. Original units, dates, source timezone, source ID and initial values remain attributed. Synthetic rows stay excluded from personal history.

This imports the dashboard's own measurement format. It does not parse MyFitnessPal, Oura or Apple Health exports, or establish a provider connection.

## Tests

```sh
.venv/bin/python scripts/verify_local.py
# Additional real HTTP transport tests, only where local ports are permitted:
.venv/bin/python scripts/verify_local.py --loopback
# Separate real OAuth issuance, scoped MCP and restart proof with disposable data:
.venv/bin/python scripts/verify_oauth.py
```

SQLite transactions use IMMEDIATE mode and optimistic version checks. A correction must supply the last observed version. Retrying the same request identifier with a different payload is rejected. Retrying an identical request returns the original result.

The runner checks installed lock versions, dependency compatibility, Django configuration, migration consistency, static collection and synthetic test suites. Tests use disposable databases and do not contact existing connectors. Concurrent disk SQLite tests verify duplicate creates and competing corrections. An issuer failure denies MCP access while authenticated stored browser history remains readable.

A rendered Chrome login check exposed an existing CSRF failure: `Referrer-Policy: no-referrer` made the form POST send `Origin: null`, which Django correctly rejected. The policy now uses `same-origin`; the browser login succeeds, same origin requests pass, and null or foreign origins still fail even with a valid CSRF token. Referrer details remain withheld from other origins. See [MDN's policy definitions](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy). The rendered CSV upload, review, confirmation, reimport, synthetic exclusion and logout flow passed at 1440 × 1000 and 390 × 844 viewport sizes using a disposable synthetic database. Imported records and the browser session survived a server restart. These Chrome checks do not establish physical iPhone or Safari installation behavior.

The latest advisory check used the already installed `pip-audit==2.10.1`, leaving the project environment unchanged. To reproduce it with authorized advisory service access:

```sh
audit_dir="$(mktemp -d "${TMPDIR:-/tmp}/health-audit.XXXXXX")"
.venv/bin/python -m pip_audit --require-hashes --disable-pip --strict \
  -r requirements.lock --progress-spinner off --timeout 20 \
  --cache-dir "$audit_dir/cache" --format json --output "$audit_dir/audit.json"
```

Check the exit status and JSON: all 42 locked dependencies must be present, with no skipped entries or vulnerabilities. Advisory results are a dated checkpoint and should be refreshed before release.

## DigitalOcean package

See docs/DEPLOYMENT.md and docs/DEPLOYMENT_PREFLIGHT.md. A separate Docker Compose application, network and data volume are prepared with a loopback-only port. No proxy labels, automatic migrations, existing service changes or remote execution are included. DigitalOcean deployment is deferred; SSH is not a prerequisite for continued local development. Container execution, target-platform installation and authorized deployment checks remain pending.

## iPhone installation

The selected mobile delivery is a private installable web app hosted on the same DigitalOcean application. Installation metadata is included; actual iPhone installation is unverified. Once HTTPS deployment is ready, use Safari, Share, Add to Home Screen, and Open as Web App. No App Store submission is needed. The first release will not cache private records or photos offline. Apple Health still requires a supported export or bridge. Use maintained OSS components for the finished interface, charts, media handling and backups as documented in docs/OSS_REUSE_AND_MOBILE.md.

## Remaining release work

Independent local features, including the personal OAuth issuer, are implemented and tested. The release still requires an authorized reachable HTTPS endpoint and actual ChatGPT consent, read and approved write; a separate identity service is optional. No source adapter is connected: the working fallback is reviewed manual entry or the documented dashboard CSV format. Native provider exports require verified headers, units and coverage before adapters are added. Physical iPhone Safari, Home Screen installation, target platform checks, real encrypted backup destination/key custody and deployment remain separate gates. No deployment or recurring schedule was enabled.

This directory is the owning local source repository. Preserve decisions and test evidence here. The delivered source archive is a checkpoint, not a deployed service. It contains no database or authentication state.

## Cursor continuation

Read `docs/CURSOR_HANDOFF.md` when continuing in the IDE. The complete original specification is copied in `docs/Personal_Health_Fitness_Dashboard_Build_Prompt.txt` for local access. The current continuation began from clean HEAD `5573b02` and continued through the independent local first release features. The earlier parser checkpoint at `edb871f` and its access failures are historical context, not current limitations. Rendered Chrome results are recorded separately from the integration tests in `docs/VERIFICATION.md`.

## Photos, summaries and saved reviews

Private photos accept JPEG, PNG and WebP still images up to 12 MiB, 25 million pixels and 10000 pixels per edge. Pillow applies orientation and creates a display JPEG with no embedded metadata. Untouched originals remain private for export and can retain GPS or other metadata. HEIC is explicitly rejected. Capture date is separate from upload time. Compare two selected dates and the same view. Photo deletion removes both files and leaves a minimal retry tombstone.

Nutrition, recovery, activity and health pages accept reviewed source records. A source name is provenance, not an account connection. Mark incomplete diaries and incomplete wearable coverage as partial or unknown. All unspecified values remain null. Daily totals are unique per source and kind; use a stable source name for each actual source, and do not aggregate overlapping wearable records. HRV requires a device and method (`RMSSD`, `SDNN`, or `source_unspecified`). Weekly averages use only explicitly complete records with known values and show observation counts. Sources, devices, HRV methods and synthetic history remain separate. No nutrition target is supplied automatically.

The summary CSV format is UTF-8, maximum 256 KiB and 200 rows. Required headers: `source_record_id,kind,local_date,source_timezone,completeness,synthetic,values`. Optional: `device,notes`. `kind` is `nutrition`, `recovery`, `activity` or `health`. `completeness` is `unknown`, `partial` or `complete`. `values` contains a quoted JSON object with these fixed keys and units:

| Kind | Numeric fields and units | Additional fields |
| --- | --- | --- |
| nutrition | `calories` kcal; `protein`, `total_carbohydrates`, `fat`, `fiber` g | Net carbohydrates calculated only from consistent known carbohydrate/fiber values |
| recovery | `sleep_minutes` min; `hrv_ms` ms; `resting_hr_bpm` bpm; `readiness` 0 to 100 | `hrv_method`; CSV `device` required with HRV |
| activity | `steps` integer count; `workout_minutes` min | `workout_summary` text |
| health | `value` in supplied units, up to six decimal places | Required `name`, `unit`; optional `reference_range` copied from source |

Numeric summary values allow up to three decimal places except clinical values. At least one known numeric value is required. Missing keys, empty numeric fields and JSON null remain unknown. Explicit zero is preserved. The source namespace, stable IDs, immutable originals, 15 minute server preview and confirmation rules match measurement imports. Example containing only synthetic data:

```csv
source_record_id,kind,local_date,source_timezone,completeness,synthetic,values,device,notes
synthetic-nutrition-001,nutrition,2026-11-05,America/Chicago,partial,true,"{""calories"":""0"",""protein"":""25"",""fiber"":null}",,Synthetic verification
```

These formats are documented dashboard imports. They do not automatically parse native MyFitnessPal, Oura or Apple Health files. Do not label arbitrary export files as supported before their actual columns, units and completeness have been verified.

Reviews can be saved explicitly through the browser or scoped MCP write. Separate annotations can reference an owned measurement or summary without changing its original values. Notes are displayed as escaped data. Deleting a review clears its saved text and receipt and leaves a retry tombstone; earlier backups retain their snapshots. Measurement/summary deletion intentionally retains correction history and tombstones and is not permanent erasure.

## Charts and MCP reads

`/trends/` plots recorded observations over at most 366 inclusive local dates, up to 2000 records with a visible truncation message. Sources, units, side/location, device, HRV method, completeness and synthetic status stay separate. No missing date is interpolated or zero filled. Exact values remain readable below the chart. Chart.js 4.6.1 and its license are served locally; CSP allows same origin scripts only, without inline executable scripts.

Authenticated tools are `read_measurements`, `read_tracking`, `read_overview` and `read_photo`. Reads require `health:read`, bounded date ranges and pagination. `read_tracking` supports measurements, nutrition, recovery, activity, health, photos (metadata) and saved reviews. Photo content additionally requires an explicit image request and returns a normalized image through the authenticated MCP response, never a permanent public URL. Sources and coverage are explicit; no source is shown as live connected. Optional `write_measurement` and `save_review` require configured write mode, `health:write`, explicit authorization and a stable request ID. Imported provider copies remain immutable.

## Export and encrypted backups

The authenticated **Export history** action downloads a ZIP with exact JSON, spreadsheet safe CSV, corrections, provenance, deletion tombstones, saved reviews, targets and original/display photos. It excludes synthetic records by default and excludes deleted photo bytes. CSV formula prefixes are escaped; JSON retains exact text. The ZIP is not encrypted. Keep it private. Maximum assembled size is 512 MiB and 100000 records/audit events per bounded category; larger archives require an operator backup.

`scripts/backup.py` uses SQLite's backup API under a reserved write lock plus immutable referenced photo files, then restic encryption. It restores only into a disposable isolated directory for verification; it has no live restore or retention deletion action. It does not back up application secrets or OAuth configuration. Keep those separately protected. See `docs/OPERATIONS.md` for exact commands and recovery handling.

The reproducible synthetic proof is:

```sh
.venv/bin/python scripts/verify_backup.py --restic /absolute/path/to/restic
```

It checks an encrypted snapshot, full repository data, restored file hashes, database integrity/foreign keys, counts, owner password verification and representative restored application reads, including corrections, tombstones, summaries, photos, targets and reviews. Wrong passwords and tampering are rejected. All fixtures and decrypted restore files are disposable. No recurring backup, retention cleanup, paid task or real destination was enabled.
