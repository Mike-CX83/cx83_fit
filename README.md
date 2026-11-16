# CX83 Fit

## Project Description

CX83 Fit is a personal health and fitness dashboard that brings measurements, nutrition, activity, recovery, clinical notes, and journaling into one place. It is designed around one authenticated owner, with source information and correction history preserved alongside records.

The public repository contains application source and documentation. The hosted dashboard at [live.cx83labs.com](https://live.cx83labs.com) requires owner authentication; publishing this repository does not make its personal records public.

## Contents

* [Usage](#usage)
* [How It Works](#how-it-works)
* [Installation](#installation)
* [Integrations](#integrations)
* [Tech Stack](#tech-stack)
* [Verification and Limitations](#verification-and-limitations)
* [Author](#author)

## Usage

After signing in to a configured instance:

1. Use **Today** to review dated observations and available check-in information.
2. Open **Diary** to record meals and review nutrition entries.
3. Use **Plan** and **Progress** to review saved goals, measurements, and trends.
4. Add body measurements or upload progress photos, then compare views over time.
5. Use **Journal** to save entries and review proposed structured observations before saving them.
6. Open **Records** to maintain clinical context such as medication and diagnosis entries.
7. Use **Holding Space** to manage support contacts and, when separately configured, initiate a message.
8. Export stored history or import a supported CSV through a preview and confirmation flow.

These are features present in the source. Availability on any running instance depends on its deployed version, configuration, and stored data.

## How It Works

Django serves the authenticated pages and stores records in SQLite. Shared service functions support browser and MCP operations.

Records retain units, dates, source identifiers, and whether they are synthetic test data. Measurement corrections use versions to reject stale updates. Stable request IDs prevent duplicate writes, and imported source records remain separate from manual corrections.

Charts use recorded observations rather than filling missing dates with invented values. The journal distinguishes observed information from unknown, declined, conflicting, or intended actions. Journal continuity, Headspace, and sobriety pattern modules provide separate summaries; they are application rules, not clinical diagnoses.

Progress images are served through authenticated routes. Display copies are normalized, while originals are retained for export. The export is a ZIP, not an encrypted backup. The separate backup script uses restic.

## Installation

### Current checkout limitation

The reviewed `main` checkout is incomplete:

* `0007_journal.py` depends on the absent migration `tracking.0006_plan_window`.
* `tracking/plan_views.py` imports `tracking.plan`, but `tracking/plan.py` is absent. This blocks normal URL loading.
* The pasted diary import path references `tracking.diary_push`, which is also absent.

Restore these original files from the owning project history before attempting a fresh installation. Do not bypass or fake the migration.

Several verification scripts cited in older documentation are also absent. These repository gaps do not establish the state of an existing deployed installation.

### Prepare a separate development environment

Requirements: Git, Python 3.13, and the dependencies pinned in `requirements.lock`.

```bash
git clone https://github.com/Mike-CX83/cx83_fit.git
cd cx83_fit
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
```

Set the following in your local shell or private environment configuration:

* `DASHBOARD_LOCAL_ONLY=1`
* `DASHBOARD_ALLOWED_HOSTS=127.0.0.1,localhost`
* `OWNER_USERNAME=owner`
* `DJANGO_SECRET_KEY`: a dedicated random value of at least 50 characters.
* Optional `DASHBOARD_PRIVATE_ROOT`: a separate directory for the development database and private files.

Keep the secret stable across restarts and outside Git. Default storage is `private/dashboard.sqlite3`.

After restoring the missing source files and migration, initialize only the new development instance:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser --username owner
.venv/bin/python -m uvicorn dashboard.asgi:application --host 127.0.0.1 --port 8000 --no-access-log
```

Open `http://127.0.0.1:8000/login/`. Local mode is for loopback development only. Existing instances must retain their database, owner, and secret.

## Integrations

* **Oura:** the direct adapter implements authorization, bounded collection sync, and source record storage. It is disabled by default and requires separate account consent and configuration.
* **MCP:** authenticated tools support tracking, journal, and other dashboard operations. Access rules and write conditions are defined per tool; browser login is separate from MCP authorization.
* **Holding Space SMS:** code exists for manual outreach and delivery handling, but requires a separately configured messaging service and number.
* **Other health sources:** connecting an app elsewhere does not automatically populate this dashboard. The CSV importers expect the formats documented in this repository.

See [Oura setup](docs/OURA_SETUP.md), [MCP setup](docs/MCP_SETUP.md), and the [data contract](docs/DATA_CONTRACT.md).

## Tech Stack

* Python, Django, SQLite, and Uvicorn.
* Django templates, CSS, and locally served Chart.js.
* Pillow for image processing.
* Django OAuth Toolkit, PyJWT, and the MCP SDK.
* Oura OAuth and HTTP integration.
* restic for the separate encrypted backup workflow.

## Verification and Limitations

The checked-in test module is `tracking/tests.py`. After resolving the source and migration gaps, the corresponding command is:

```bash
.venv/bin/python manage.py test tracking
```

The older `scripts/verify_local.py`, `scripts/verify_oauth.py`, `scripts/verify_backup.py`, and broader `tests/` suite are not included in this checkout. Historical passing counts in [verification notes](docs/VERIFICATION.md) describe earlier environments, not a new run of this repository.

The verification notes include November 8 deployment checks, so the earlier root README's blanket statement that deployment was incomplete is no longer an adequate status summary. Live service status, actual provider connectivity, and physical phone behavior were not retested during this documentation review.

* [Operations and backup guidance](docs/OPERATIONS.md)
* [Deployment documentation](deploy/live.cx83labs.com/README.md)
* [Headspace development plan](Headspace/README.md)
* [Historical README checkpoint](docs/README_CHECKPOINT_2026_11_16.md)

## Author

**Mike Hankins**, founder of CX83 Labs, registered nurse, and software engineering student.

[GitHub](https://github.com/Mike-CX83) · [CX83 Labs](https://cx83labs.com)

The Oura collection registry includes adaptation of Oscar Pacheco's MIT licensed work, credited in [the included notice](tracking/oura/PROSCAR_LICENSE.txt).
