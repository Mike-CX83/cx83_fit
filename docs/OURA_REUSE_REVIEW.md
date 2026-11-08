# Oura reuse review

Reviewed November 6, 2026. Completed before adding Oura integration code. Both repositories were cloned into temporary directories and tested in separate temporary environments. The dashboard environment, MCP endpoint, credentials and DigitalOcean services were not changed by this evaluation. All tests used upstream synthetic fixtures. No live Oura authorization or ingestion was attempted.

## Decision

Neither repository is a suitable unmodified ingestion client for this dashboard. Prefer small, attributed reuse of Proscar's collection registry after checking it against Oura's current schema, plus its date boundary and pagination regression scenarios. Keep the existing Django and official MCP endpoint. Use the already installed oauthlib for OAuth protocol handling and cryptography for token encryption. Do not install either complete MCP server or introduce a Node sidecar or Cloudflare deployment.

This is a fit decision, not a claim that the projects are unusable. Their interactive query tools and this application's durable, source faithful ingestion have different requirements. Passing their tests does not establish the additional guarantees below.

## Versions, maintenance and licenses

| Project | Inspected revision | Maintenance evidence | License |
| --- | --- | --- | --- |
| [proscar87/oura-mcp](https://github.com/proscar87/oura-mcp) | `30b20cb5a5cd93ee34635af640db2f6ff62a4ee6`, October 27, package 0.4.1 | 132 commits at inspection; October 28 CI and November 2 schema drift workflow succeeded | MIT, copyright 2026 Oscar Pacheco |
| [robcerda/oura-mcp-server](https://github.com/robcerda/oura-mcp-server) | `29902f81541a55dcc34e8507531a7d5b47eef500`, September 26, package 0.1.0 | Four commits at inspection; automation is active, but November 2 and October 26 supply chain runs failed | MIT, copyright 2025 Rob Cerda |

Both licenses permit modification and reuse with the copyright and permission notice retained. Neither has a maintenance SLA. Proscar has the stronger observed recent implementation activity. These are dated observations, not promises of future maintenance. CI status came from GitHub's public Actions API; it is separate from the local runs below.

## Executed tests and audits

| Check | Observed result |
| --- | --- |
| Proscar Python, Python 3.13, fresh editable development install | 362 passed, zero skipped after building TypeScript parity fixtures. Initial 336 passed plus 26 skipped was superseded by this complete run |
| Proscar TypeScript | `npm ci --ignore-scripts`, TypeScript build and all 143 tests passed |
| Proscar Worker unit tests | All 13 passed. No Worker deployment, workerd end to end test, container or desktop bundle test was run |
| Robcerda Python | Hash verified runtime requirements installed; 79 tests passed, zero skips. pytest and pytest-asyncio installed separately in the disposable environment. Starlette test transport and pytest fixture scope deprecation warnings observed |
| Proscar Python resolved third party set | 33 installed third party packages, including test dependencies, audited with strict pip-audit; zero findings and zero skips. This is a fresh resolution, not an upstream Python lock. The first party editable package was reviewed as source and excluded from advisory lookup because that release was not found on PyPI |
| Robcerda runtime requirements lock | 41 applicable installed packages on macOS/Python 3.13. pip-audit returned two entries for the **same** unique `PYSEC-2026-4320` / `GHSA-6q48-6c7w-9gw2` advisory in certifi 2026.7.22. Do not report these as two different vulnerabilities. Advisory recommends certifi 2026.10.19 or later |
| Proscar TypeScript lock | npm audit: 22 affected packages including dev dependencies: 7 moderate, 11 high, 4 critical. Production only: 9 affected packages, 4 moderate, 4 high, 1 critical |
| Proscar Worker lock | npm audit: 19 affected packages including dev dependencies: 8 moderate, 9 high, 2 critical. Production only: 8 affected packages, 5 moderate, 3 high |

npm totals include inherited dependency findings, not a count of independent exploitable paths. They do not prove the specific client code reaches every vulnerable function. They do rule out describing either JavaScript dependency tree as clean. No `npm audit fix`, dependency upgrade or source patch was applied to upstream. The initial npm install could not write the default cache; retrying with a temporary cache succeeded without changing global permissions.

Reproduction commands, run from each temporary checkout:

```sh
# Proscar: isolated Python environment, then TypeScript parity fixtures
python -m pip install -e '.[dev]'
cd ts
npm ci --ignore-scripts --cache /tmp/health-reuse-npm-cache
npm run build
npm test
npm audit --json
npm audit --omit=dev --json
# From the repository root after the TypeScript build:
python -m pytest -q -rs
# Worker unit tests and advisory audit, without deploy or dev server:
cd ts/worker
npm ci --ignore-scripts --cache /tmp/health-reuse-npm-cache
npm test
npm audit --json
npm audit --omit=dev --json
# Robcerda, in its own environment:
python -m pip install --require-hashes -r requirements-lock.txt
python -m pip install pytest pytest-asyncio
PYTHONPATH=src python -m pytest -q
```

The dashboard's existing pip-audit installation audited the exact resolved Proscar third party versions with `--no-deps --disable-pip --strict`, and Robcerda's lock with `--require-hashes --disable-pip --strict`. Audit JSON is retained in `docs/evidence/oura-reuse-2026-11-06/`. Full test and installation logs remain temporary files `/tmp/health-reuse-*-tests.log` and `*-install.log`; the durable results and scope are recorded here. Advisory results are time and platform specific.

## Implementation findings

### Proscar

The Python `src/oura_mcp/client.py` and `collections.py` cover all 19 current collections, detect repeated pagination tokens, disclose truncation and preserve returned IDs in JSON mode. The date margin and missing versus empty test scenarios are useful. The separate TypeScript client exposes an injected `Auth` interface with an account identity. Python `fetch()` instead reads process global credentials and offers no per request token or transport injection.

Python's cache key does not contain an account identity. A synthetic probe replaced `_token` from credential A to credential B for the same closed date range. `_request` was called once and the second fetch returned A's record. Both Python and TypeScript hold past nonempty ranges for the process lifetime, assuming past records cannot change. That conflicts with delayed wearable synchronization and revised records. Clearing a global cache around requests is not a safe concurrent integration design.

`authorize.py` builds authorization URLs manually, with state but no Oura PKCE challenge. The Worker uses an established provider library for its own MCP OAuth layer, but its separate Oura authorization builder likewise does not send an Oura PKCE challenge. Those are different authorization boundaries. Python refresh uses a thread lock and atomic credential file replacement, but not a persistent cross process lease before consuming a rotating refresh token. Keyring is optional with a private plaintext file fallback.

Python retries only HTTP 429 and caps the requested wait at eight seconds, including a longer server `Retry-After`. It does not retry transient 5xx or transport errors. Pagination may return partial results that a durable importer must not mistake for a complete sync. Its advice to resume on the following day can omit remaining samples on the last partial day, so it is unsuitable as a durable cursor.

Raw JSON is decoded with ordinary Python floats, and TypeScript uses JavaScript numbers. Neither keeps exact original response bytes. CSV projections and analysis tools deliberately omit or derive fields. Do not use those outputs as source originals. Its scope mapping assigns cardiovascular age and VO2 max to daily; current Oura schema also advertises `heart_health`, so do not reuse that permission map without verification.

### Robcerda

`client.py` provides readable httpx transport and token refresh, bounded pagination, explicit rate limit errors and useful mock transport fixtures. Its structured tool outputs are useful UI references. `get_collection()` returns raw rows and a continuation token before presentation helpers strip time series. That raw layer is the only plausible ingestion surface.

However it is coupled to global clients, sessions, dotenv and keyring/file storage. Refresh locking is per process, with recovery after a conflicting refresh rather than durable serialization before spending the token. Its session object contains unredacted secret fields. OAuth is manually implemented without PKCE, uses an assumed expiry if missing or malformed, and reuses an old refresh token when the response omits one. These do not meet our fail closed token requirements.

Pagination has a page cap but no repeated cursor detection or durable duplicate prevention. It retries 429 but not transient 5xx/transport errors. Presentation options can remove time series and summary tools calculate rounded derived values. Its default scopes also include `stress`, which is absent from the current official OpenAPI scope list. Do not copy that scope on assumption.

The complete package requires `mcp[cli]>=1.30,<2`, incompatible with this dashboard's locked MCP 2.3.0. Installing it would change the established endpoint dependency contract. Extracting and substantially rewriting its global client would create a local fork with little retained benefit.

## What can be reused, and what belongs here

* Reuse Proscar's small MIT collection definitions after schema comparison, with its license and pinned revision recorded. Correct descriptions from official schema where needed. Do not copy unsupported permission assumptions.
* Reuse pagination cycle, partial result, local date boundary, zero/null and refresh race scenarios as regression requirements. If copying test code, retain the corresponding MIT notice. Test ideas alone do not require importing a server package.
* Continue using existing mature OAuth, crypto, Django and MCP libraries. There is no reason to build a second MCP endpoint, OAuth issuer, generic JSON RPC server or credential manager.
* Application specific code is still required for owner bound Oura consent, browser state and PKCE, encrypted token persistence with cross process refresh coordination, account separated raw records and immutable revisions, lossless source values, safe bounded retries, durable pagination and duplicate prevention, sync receipts, exports and connection status.
* Keep original provider IDs separate from any derived key needed by collections that have no ID. Preserve original units, offsets, date only values, nulls and field absence. Do not round, sum overlapping devices, infer missing measurements or overwrite old revisions.

## Primary documentation checked

[Oura authentication](https://cloud.ouraring.com/docs/authentication), [errors](https://cloud.ouraring.com/docs/error-handling), [API reference](https://cloud.ouraring.com/v2/docs), and the reference page's [OpenAPI 1.43 schema](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json).

The authentication page lists eight scopes; OpenAPI adds `heart_health`, for nine: `email personal daily heartrate workout tag session spo2 heart_health`. Its 19 collection names match Proscar's registry. Oura recommends an OAuth library and supports S256 PKCE. Refresh tokens are single use. API support does not establish that this user's device, membership and grant return every category.

The developer portal remains unmodified and unsubmitted because the Computer Use session was stopped. Mike requested every available category checked and every separate Require box unchecked. No live authorization, provider ingestion, DNS change or deployment is claimed. `live.cx83labs.com` remains the selected hostname for preparation on the established DigitalOcean server.

## Verified collection support

Each row below is a documented GET collection in the official OpenAPI 1.43 schema, under `/v2/usercollection/`. None has been read from Mike's account. Date bounds and numeric values must stay in their source representation. Request all fields by omitting `fields`; never use a summary or CSV projection as an original.

| Collection | Query shape | Record identity handling required |
| --- | --- | --- |
| `daily_activity` | Date range and next_token | Original id |
| `daily_cardiovascular_age` | Date range and next_token | Original id |
| `daily_readiness` | Date range and next_token | Original id |
| `daily_resilience` | Date range and next_token | Original id |
| `daily_sleep` | Date range and next_token | Original id |
| `daily_spo2` | Date range and next_token | Original id |
| `daily_stress` | Date range and next_token | Original id |
| `enhanced_tag` | Date range and next_token | Original id |
| `heartrate` | Datetime range and next_token; optional latest | No provider id in schema; preserve timestamp, timestamp_unix and source separately from a derived local key |
| `personal_info` | Singleton, no query parameters | Original id; do not infer measurement date |
| `rest_mode_period` | Date range and next_token | Original id |
| `ring_battery_level` | Datetime range and next_token; optional latest | No provider id in schema; preserve raw timestamps and values, label any derived local key |
| `ring_configuration` | next_token without date range | Original id |
| `session` | Date range and next_token | Original id |
| `sleep` | Date range and next_token | Original id |
| `sleep_time` | Date range and next_token | Original id |
| `tag` | Date range and next_token | Original id; older format remains documented |
| `vO2_max` | Date range and next_token | Original id; preserve this endpoint's exact case |
| `workout` | Date range and next_token | Original id |

A listed collection is API support, not proof of this device's coverage or account permissions. The schema's route security declarations do not supply a reliable per collection scope mapping. Record actual permission failures separately from empty results. Do not add presumed measurements, timezone or units to fields without a documented basis. The portal's scope selection and its separate Require flags remain an independent, uncompleted UI step.
