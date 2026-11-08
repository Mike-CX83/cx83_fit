# Verification checkpoint

## Oura server setup ready, November 8, 3:47 AM CST

App container `a10f91a0cf70` started `2026-11-08T09:47:13Z`. Shared proxy start remains `2026-10-10T17:40:21Z`. `OURA_ENABLED` is 1 and the redirect matches `https://live.cx83labs.com/integrations/oura/callback/`. Inside the app, both secret files are mode 400, UID 10001, and readable. The requested scope list is the nine official scopes and does not include `stress`. Anonymous `/integrations/oura/` redirects to login. After owner sign-in the page contains "Oura setup is enabled.", "Connect Oura", and "No Oura account has been authorized." No authorization was completed in this step and no ingestion was run. This is not a connected Oura account.

## Your Headroom live, November 8, 3:40 AM CST

Server commit `0808ae8`. App container `ad48d4a2e237` restarted at `2026-11-08T09:39:59Z`. Shared proxy start remains `2026-10-10T17:40:21Z`. No migration and no Oura change.

`tests.test_headroom`, `tests.test_journal_continuity`, and `tests.test_today_signals` passed: 13 tests. Covered cases: no score without two ratings, 6 and 8 staying 70.00 and Steady, one low rating staying blank, short sleep leaving an 80.00 score unchanged, a 14 day drop, a move under 5 points staying about the same, food under half a saved goal, missing sleep not called short, and synthetic rows hidden from the personal page. A disposable browser at 390px showed the synthetic card at 25.00 Running low, no horizontal overflow, and the eat link opened `/diary/` with the same date. At 1440px the card was two columns, the main column was 1120px, and overflow was false. The personal preview without `synthetic=1` said Not enough to score. Live owner `/` returned 200 and contained Your Headroom, the 0 to 100 scale, and Start here. Personal values were not recorded. No AI check-in and no text alert were added.

## Labs, meds, and diagnoses live, November 8, 3:21 AM CST

Server commit `d4fd80f`. App container `ad48d4a2e237` restarted at `2026-11-08T09:21:00Z`. Shared proxy start remains `2026-10-10T17:40:21Z`. No migration and no Oura change.

Anonymous `/records/` redirects to login. After owner sign-in, `/records/` contains the three empty current lists, `/` and `/more/` link to that page, `/plan/` links to it, and `/summaries/health/` is titled Lab results. Focused local tests passed: 19 tests in `tests.test_clinical`, `tests.test_plan`, and `tests.test_summaries`. A disposable browser at 390px saved a synthetic medication and marked it not current with no horizontal overflow. At 1440px, More used the desktop tabs and a 1120px column. No personal clinical text was entered. ChatGPT tool refresh and a physical phone check were not done.

## Sobriety pattern live, November 8, 3:16 AM CST

Server commit `1d89416`. Pre-migration snapshot `634478f2ca93166533f3864c0b088ed1470fa5e744e50aad940d810736ef9bc7`. Post-migration snapshot `bb56a59b66783f154f1a87c81a22896824d2e074a184fba929f101bdecfd30a0`. Migration `0009_sobrietyday` applied. Container `ad48d4a2e237` restarted at `2026-11-08T09:16:51Z`. Shared proxy start remains `2026-10-10T17:40:21Z`. Oura, MyFitnessPal, and the backup timer stayed active. Anonymous `/mcp` returned 401 and anonymous `/` returned 302. The pattern module imports. No personal check-in was entered. A ChatGPT session that already lists `read_sobriety_pattern` can call it. A session with an older tool list still needs a refresh.

## Quieter Today layout live, November 8, 3:11 AM CST

Server commit `9a2214e`. App container `ad48d4a2e237` restarted at `2026-11-08T09:11:32Z`. Proxy start unchanged at `2026-10-10T17:40:21Z`. No migration and no Oura change.

Owner sign-in reached `/`, `/diary/`, `/plan/`, `/progress/`, and `/more/` with status 200. The live Today page contains "No check-in yet" and does not contain "Include synthetic" or "180.125". A disposable local browser, not a physical iPhone, showed no horizontal overflow at 390 on Today, Diary, Progress, and More; at 768 on Today; at 1440 on Plan; and at 1920 on Today. Large-monitor Today measured a 1360px column. `save_meal` and `read_watch_signals` are in the published tool file. At this checkpoint `read_sobriety_pattern` was named in the server file but its module was not mounted yet. The 3:16 AM checkpoint above is the one where that call became live.

## Check-in and sobriety pattern alignment, November 8, 3:02 AM CST

Documentation and the two project skills now use one check-in order. `read_journal_context` stays the opener, follow-ups, memory, and scores. `read_sobriety_pattern` stays the separate 14 day read. Daily State still excludes sobriety fields. No new test run was started for the wording pass. The tracker run remains the 274 passed tests, 17 skipped socket tests, recorded in `docs/CURSOR_HANDOFF.md`. Live hosting was not updated. ChatGPT still needs a tool refresh before it can call `read_sobriety_pattern`.

## CX83 Fit layout and chrome pass, November 8, 2:56 AM CST

Local application checks only. `.venv/bin/python scripts/verify_local.py` passed: 264 tests, 17 opt-in socket tests skipped. Covers the new shell (`/`, `/diary/`, `/progress/`, `/more/`), synthetic UI removal, and export always excluding synthetic rows. Migration `0009_sobrietyday` is present for the already-defined model and is allowlisted in backup counts. No production publish or personal-record check. Live hosting was not updated.

## CX83 Fit daily UX, November 8, 2:30 AM CST

Local application checks only. `.venv/bin/python scripts/verify_local.py` passed: 264 tests, 17 opt-in socket tests skipped. Covered routes include `/`, `/diary/`, `/plan/`, `/progress/`, journal, summaries, reviews, trends, and import receipt pages after the daily UX strip. No production publish, migration, or personal-record check. Live `live.cx83labs.com` was not updated in this pass.

## Continuity, writes, and governing document, November 8, 2:26 AM CST

Backup snapshot `f7e36b03659898b419c15c8b73f40ca7f85bb256ea5cf05ce57d87acaf2d9655` completed before the migration. Server commit `564b06b`. Migration `0008_journal_continuity` applied. New app container `ad48d4a2e237` started `2026-11-08T08:26:06Z`. Shared proxy `896e154e5916` still started `2026-10-10T17:40:21Z`. Twenty containers remained. Oura, MyFitnessPal, and the backup timer stayed active. `MCP_WRITES_ENABLED` is 1. `OURA_ENABLED` is 0. `tracking_journalentry` count stayed 0.

Public login returned 200. Anonymous `/mcp` returned 401. Owner `/journal/` returned 200 and contained Check proposal. Metadata scopes are `health:read`, `health:write`, and `site:write`. The mounted governing document reports available with version `2026.11.08`, and the status call does not include its text. Local `verify_local.py` passed with 264 tests and 17 skipped socket tests before this release. No ChatGPT reconnect and no Dot voice tool call were performed.

## Journal tools published, November 8, 2:14 AM CST

Server commit `abeb443`. App container `51b14e3eef62` restarted at `2026-11-08T08:13:38Z`. Shared proxy `896e154e5916` still started `2026-10-10T17:40:21Z`. Twenty containers remained. `oura-personal.service`, `myfitnesspal-personal.service`, and `personal-health-backup.timer` stayed active. `MCP_WRITES_ENABLED` stayed 0. Live migrations are `0001` through `0007_journal`. No new migration ran. `tracking_journalentry` count stayed 0.

Anonymous `/journal/` returned 302 to login. Anonymous `/mcp` returned 401. Owner sign-in loaded `/journal/` with Check proposal and Save journal entry. The synthetic check "I did not meditate" displayed "Nothing was saved" and "explicit_choice, observed, no". The page list stayed empty. The running container contains `save_journal_entry`. This was not a ChatGPT tool-refresh test and not a Dot voice test.

## Journal tools for the ChatGPT connection, November 8, 2:09 AM CST

`.venv/bin/python scripts/verify_local.py` passed: 261 tests, 17 opt-in socket tests skipped. A `health:read` token can list and call `read_journal`, `preview_journal`, `save_journal_entry`, and `delete_journal_entry`. Save without explicit authorization is rejected and does not call the service. Preview does not write. Measurement writes still require `health:write`. No production publish and no live ChatGPT or Dot voice session was tested.

## Journal proposal check, November 8, 2:04 AM CST

`.venv/bin/python scripts/verify_local.py` passed: 258 tests, 16 opt-in socket tests skipped. No production migration. The check writes nothing. Tests cover explicit false, intention, silence, a qualitative note with no invented severity, another person's symptom, disagreeing proposals, and a prompt-injection sentence stored only as proposal text. Anonymous `/journal/preview/` redirects to login. A disposable browser on `127.0.0.1:8768` showed "Nothing was saved" and "Ready to save: domain 18, explicit_choice, observed, no" while the saved list stayed empty. The temporary server was removed. ChatGPT and Dot were not given a journal tool.

## Dark CX83 Fit chrome, November 8, 2:01 AM CST

`https://live.cx83labs.com/login/` serves the dark CX83 palette: `color-scheme:dark`, Midnight page, `#101A33` panels, showcase mark, and dark Labs wordmark. Manifest background and theme are `#080E22`. Server commit `470f306`. App ID still starts `51b14e3eef62`. Shared proxy start remains `2026-10-10T17:40:21Z`. Oura, MyFitnessPal, and backup timer stayed active.

## Journal published live, November 8, 1:56 AM CST

Pre-migration encrypted backup snapshot `e2bbac4c50f38bb1e4c5aaf82b9491adb30a76c1aca47aa4fa46fe079d27eed1` completed. Server commit `ac2a940`. Migration `0007_journal` is applied. App restarted only; ID still starts `51b14e3eef62`. Shared proxy ID still starts `896e154e5916` with start `2026-10-10T17:40:21Z`. Twenty container IDs unchanged. Oura, MyFitnessPal, and backup timer stayed active. `MCP_WRITES_ENABLED` is 0.

Anonymous `https://live.cx83labs.com/journal/` returns 302 to login. Owner browser login reached `/journal/` with Sign out, Journal nav, and CX83 Fit chrome. No personal journal text was entered in this check. ChatGPT journal tools were not added.

## CX83 Fit branding live, November 8, 1:48 AM CST

`https://live.cx83labs.com/login/` returns title and chrome **CX83 Fit**, theme `#080E22`, brand mark, and Labs footer line. Manifest name/short_name are `CX83 Fit`. Static mark and Geist font return HTTP 200. Server commit `dd7d951`. App container restarted only; ID still starts `51b14e3eef62`. Shared proxy ID still starts `896e154e5916` with start `2026-10-10T17:40:21Z`. Twenty container IDs unchanged. Oura, MyFitnessPal, and backup timer stayed active. No personal records were opened or changed.

## Local journal loop, November 8, 1:51 AM CST

`.venv/bin/python scripts/verify_local.py` passed after the final journal version fix. Django check, migration consistency, static collection, and 256 tests passed. Sixteen opt-in loopback socket tests were skipped. No production database was migrated. This journal code was not part of the branding publish above.

The new tests cover explicit false versus unknown, a qualitative note with no invented number, replay, conflicting request ids, stale versions, a text correction that leaves the observation version unchanged, deletion that clears active text and receipt content, owner isolation, diet and clinical export rows, journal CSV formula protection, synthetic exclusion, the governing-document pointer refusing embedded text, process restart on a disposable database, and backup snapshots that omit later table groups. A partial journal or Oura schema is rejected. Every current tracking model is on the backup allowlist.

A disposable local server at `127.0.0.1:8767` used a temporary database. Browser sign-in reached the overview. `/journal/` saved a synthetic entry, showed date only capture, domain 19, an observed note, and no score. A correction persisted. At 390 by 844 pixels the page had no horizontal overflow. Deletion removed the text from the list, left an empty body and empty observation value, and stored a receipt with only the id and deleted flag. `/plan/` still opened. The temporary server and database were removed. This is not physical iPhone, ChatGPT, or Dot verification. Live health writes stayed disabled.

## CX83 Fit branding, November 8, 1:40 AM CST

Local disposable instance on `127.0.0.1:8766` showed product name **CX83 Fit**, the Labs frame mark, Electric Blue actions on a light `#F5F7FF` ground, and the Labs wordmark in the footer. Browser checks covered sign in, overview, and plan at desktop width and a 390×844 phone viewport. Manifest returns name and short_name `CX83 Fit` with theme `#080E22`. Favicon and vendored Geist font served from `/static/`. Focused login and plan tests passed, 11 tests. No live deploy, no personal records, and the shared proxy were unchanged. Live `live.cx83labs.com` still serves the prior green chrome until this checkout is published there.

## Plan page, November 8, 12:31 AM CST

Signed-in browser load of `https://live.cx83labs.com/plan/` showed the 90 day window from 2026-08-11 through 2026-11-08, empty goals, common meals, device burn, and diary, plus chart links for weight, measurements, sleep, and recovery. The weight chart opened on that same window and reported 0 observations. `/nutrition/targets/` shows steps and sleep hours alongside the food goals. Anonymous `/plan/` returns 302. Focused plan tests passed, 4 tests, plus the existing nutrition target test. Migration `0006` applied. The shared proxy was not restarted. No personal diary, goal, or measurement was entered.

## Commit and publish, November 8, 12:02 AM CST

`commit_and_publish` is available to the existing `health:read site:write` token. A local publish-script check committed one synthetic file and refused `secrets/note.txt`. On the server, the same secret request returned "A requested path cannot be committed." and did not restart the app. The server source commit `c9e9bd4` tracks 0 secret, private, runtime, or `.env` paths. Anonymous `/` returns 302 and anonymous `/mcp` returns 401. The app container ID starts `51b14e3eef62`. The shared proxy was not restarted. No phone edit has been published yet.

## ChatGPT site edits, November 7, 11:44 PM CST

The health plugin permission is Allow all, matching CX83 Website. Reconnect consent listed read access and one exact repository replacement. A new access token has scope `health:read site:write`. Metadata at `https://live.cx83labs.com/.well-known/oauth-authorization-server` advertises those scopes and does not advertise `health:write`. Inside the app container, `/repo` contains only `dashboard`, `docs`, and `tracking`. `secrets` and `.env` are absent there, and resolving `secrets/note.txt` is refused. A source file under `/repo/dashboard` can be read. Anonymous `/` returns 302 and anonymous `/mcp` returns 401. The app container ID starts `469a6614e49c`. The shared proxy was not restarted. Focused repository tests passed, 2 tests, plus the metadata test. No ChatGPT chat has performed an edit yet. A source edit does not reload the running process.

## Login names, November 7, 10:57 PM CST

`kayla` and `mike` sign in to the existing single owner account on `https://live.cx83labs.com`. Browser sign-in for each name reached the overview. A wrong password did not. Anonymous `/` still redirects to login. The password is private in `secrets/deploy/dashboard-owner-password` and is not recorded here. The app container was recreated for the login-name mounts. Its ID starts `8b9209696c6e`. The other 19 containers, including the shared proxy, kept their IDs. No migration, backup, full suite or connector change ran. Focused login tests passed: 7 tests.

Personal ChatGPT connected to `https://live.cx83labs.com/mcp` on November 7, 2026 after 11:06 PM CST. Consent granted `health:read` only. A valid access token was issued to the ChatGPT application. The connected chat reported 0 measurements for 2026-01-01 through 2026-11-07. No measurement values were recorded here. Focused OAuth tests passed, including a synthetic signed client assertion, rejection of a reused assertion, and rejection of the wrong key. The physical iPhone check remains unverified.

## Native server deployment, November 7 evening

The approved image/source/backup artifacts were hash verified on `vaultstorage-pilot` and installed in the new dedicated app directory/volume. Native server password/CSRF login, secure cookies, a synthetic browser measurement, synthetic exclusion, and session/data persistence after an app-only restart passed. Loopback binding, read only root, 384 MiB limit, public policy handlers and canonical OAuth issuer metadata matched the plan. The first server-to-Google-Drive encrypted backup passed, with actual expired-access-token refresh observed. Its daily timer is enabled/active. All 19 original containers retained their running IDs, and both standalone connector units retained their state/PIDs. Evidence: `docs/evidence/deployment-native-20261107.json`. No full suite, repeat build, shared proxy restart or real-health upload occurred.

Public HTTPS for `live.cx83labs.com` passed on November 7, 2026 at 10:49 PM CST. The certificate is Let's Encrypt YR2 for that exact name, valid through February 6, 2027. HTTP redirects to HTTPS. Anonymous `/` redirects to login and anonymous `/mcp` returns 401. Browser owner login reached the overview. The shared proxy was not restarted. The same 20 container IDs remained running, and the standalone Oura and MyFitnessPal units stayed active. Physical iPhone and actual dashboard ChatGPT reads remain unverified. This hosted check is not those remaining gates.

Updated November 6, 2026, America/Chicago. **237 application tests passed with no skips**, including actual loopback HTTP. The separate encrypted backup/restore proof passed. Rendered Chrome checks cover desktop and phone widths with disposable synthetic data. Actual ChatGPT authorization, real provider ingestion, physical iPhone/Safari and deployment remain unverified. No existing connection was changed.

## Current Oura continuation

### Verified Google Drive backup, November 7

The corrected Desktop OAuth flow saved an access token and offline refresh token, and Google Drive `about.get?fields=user(emailAddress)` verified `mike@cx83labs.com` with the limited `drive.file` grant. Rclone Drive's generic UserInfo command is unsupported; the documented read-only metadata API was used instead. Credential directories are 0700, config/recovery password files 0600 and both are ignored by Git. No secret was printed or packaged.

`scripts/verify_backup.py` passed one real encrypted upload and one isolated restore from a new synthetic-only Google Drive repository. The three database/photo files matched their hashes; SQLite integrity/foreign keys and tracked table counts matched. Restored Django application reads verified synthetic source IDs, exact Oura original/revision values, restored token decryption with the separately held fixture key, photo bytes, correction/deletion history, partial/zero/null summaries, review and targets. Wrong-password rejection and intentional restored-file tampering checks passed. Live/local source storage stayed intact. The remote synthetic repository is retained. Evidence: `docs/evidence/drive-backup-verification.json`, `drive-backup-run.json` and `drive-backup-preparation.json`.

Only the three credential-import regression tests and this backup proof ran for the latest correction; no full application suite, Linux rebuild, production migration, server service/timer, billing setting or existing connector was changed. The test ran from the Mac. A live access-token expiry/refresh cycle was not forced. Server recurring backups and hosted dashboard acceptance remain pending deployment approval. Mike subsequently confirmed saving the recovery password in his password manager on November 7; this is owner-reported and was not independently inspected. Earlier pending/blocked backup statements below describe historical preparation stages.

### Google Drive backup preparation

Mike selected Google Drive through **CX83 Labs Google Workspace** and authorized preparing the dedicated backup connection plus one synthetic cloud backup/restore. Actual organization-owned Google project/Internal Desktop client setup and owner consent remain pending. The connected ChatGPT Drive app was checked and belongs to Gmail; it was not changed or used for backup writes. Browser automation's access host was unavailable; Chrome was opened through the installed application for Mike's account/project step. No real Drive credentials, backup, OAuth app publication, server service/timer or dashboard deployment were created by this preparation.

The established snapshot/restore helper was extended with an explicit limited `drive.file` rclone backend; encryption and SQLite/photo snapshot logic were reused. Official restic 0.19.1 and rclone 1.76.0 Mac/Linux archives matched upstream SHA256SUMS. The existing local encrypted backup/restore proof passed after the backend change, including restored application reads and exact synthetic Oura/photo/token state, wrong password rejection and tamper detection. Focused checks verified credential environment isolation, full-Drive scope rejection and private Desktop-client import without displaying its synthetic secret. The proposed backup Compose overlay parsed with an isolated network, resource limits, no ports and no app restart dependency. No VM start or full application suite was needed. Evidence: `docs/evidence/drive-backup-preparation.json` and `backup-tools.json`.

The cloud proof is prepared through the existing `scripts/verify_backup.py` using a unique synthetic-only remote repository and one isolated restore. It has not run against Drive. See `OPERATIONS.md` for exact owner setup, secure credential import, recovery password custody and Google's seven-day Testing-token rule. A later server installation needs a client suitable for unattended use, private UID 10001 credentials and explicit approval. The immutable application image is unchanged; the backup helper is mounted separately by the optional backup service. Original release archives remain intact; backup additions are packaged separately.

### Focused Linux release preparation, November 6 at 14:14 CST onward

At Mike's request, the full application suite was not repeated. The pinned Python 3.12 Linux amd64 image built successfully with the existing hash locked dependencies. `scripts/verify_container.py` passed using the real deployment Compose files in the existing isolated `mcp-migration-test` VM. It exercised real password/CSRF login over fixture HTTPS through Traefik 3.6, secure cookies, anonymous browser/MCP rejection, public policy/static responses, malicious forwarded-header replacement, a synthetic browser write and identical retry, then a container restart with the same browser session and data. One record and one write receipt remained. Twelve reads at concurrency two passed. Observed memory was 99.07 MiB under the 384 MiB limit; this is a small personal workload proof, not sustained capacity benchmarking.

The container's read only root, dropped capabilities, CPU/PID/memory limits, absent published test ports and restart policy were verified. `/data` was 0700 and SQLite 0600. The entrypoint now sets umask 077, and the base image is pinned by digest. Linux `pip check` passed. Django deployment checks had only the deliberate single-host HSTS warnings W005/W021; preload and includeSubDomains remain disabled. An initial smoke assertion was corrected to accept equivalent Cache-Control directive ordering. No application behavior changed to satisfy that assertion. Evidence: `docs/evidence/container-release.json`.

The existing read only server preflight passed again at 2026-11-06T20:14:46Z with zero unknown/review items: 1.7 GiB available RAM, 60 GiB free disk, 19 existing containers and unused dashboard path/account/port. Oura and MyFitnessPal systemd units were active/enabled with no automatic restarts. Their independent migration is documented in their owning repositories, not proof of dashboard ingestion. No dashboard deployment, DNS, proxy or production data change occurred. The default Docker context stayed `default`; coursework was untouched. The synthetic smoke containers/volumes/network were removed and the dedicated VM was stopped after packaging.

The tested image is preserved locally under ignored `output/deploy/`. The exact first-hosting proposal and rollback are in `deploy/live.cx83labs.com/README.md`. Backup destination/key custody remain undecided. Mike asked about GitHub; source code can be versioned there, while database/photo backups need a separate encrypted destination. Until that is chosen, the proposed initial hosting uses synthetic health records only, with provider ingestion and MCP writes disabled. Actual public TLS, ChatGPT owner consent/reads and physical iPhone acceptance remain post-approval checks. Earlier local 237-test and encrypted restore results below remain historical evidence and were not rerun.

`verify_local.py --loopback` passed all 237 tests with zero skips, locked dependency matching, pip compatibility, Django checks, migration consistency and static collection. Two additional backup compatibility tests verify restoration of pre Oura v1 snapshots and reject unknown manifest table names or a partial schema. The 31 additional Oura tests cover the actual oauthlib protocol helpers, S256 challenge/verifier, owner/browser state, callback replay/expiry/cancellation, encrypted storage and private key files, refresh rotation and ambiguous failure, disconnect races, account binding, all collection query shapes, exact decimals/timestamps/null/absent fields, pagination/resume/cycles/rollback, duplicate prevention, source separation, retry delays, restricted reads, exports and public policy pages. Outbound HTTP uses synthetic transport responses. The existing MCP HTTP suite additionally exercises scoped `read_oura` dispatch.

`.venv/bin/python scripts/verify_oura.py` passed separately against a disposable disk database. Two independent processes competed for an expired token: exactly one reached the synthetic token exchange; the other received refresh_busy. A fresh process read the persisted rotated token and exact numeric source records, and local disconnection retained history. This is not live Oura authorization.

`.venv/bin/python scripts/verify_oauth.py` passed real local owner login, OAuth consent/code/PKCE, MCP scoped writes, restart, refresh and revocation. It now also reads an Oura original through the actual composed Django/MCP endpoint after restart, confirms exact source IDs and decimal JSON, excludes synthetic records by default and denies Oura reads after revocation. No external issuer or ChatGPT account was used.

`.venv/bin/python scripts/verify_backup.py --restic /tmp/health-dashboard-restic` passed again with Oura source records, immutable revisions and encrypted tokens in the restored database. A separately held synthetic key decrypted the restored token. Database/file integrity, application reads, wrong password rejection and tamper detection passed. No personal storage or backup destination changed.

All 42 hash locked packages passed strict pip-audit with zero findings and zero skips; evidence is `docs/evidence/oura-integration-audit-2026-11-06.json`. Only simplejson 4.2.0 was added to the installed dependency set; previous versions stayed unchanged. Its decimal support avoids coercing source numeric values through binary floating point. OAuth, HTTP and crypto reuse existing locked libraries. The Proscar registry is attributed with its MIT license; neither upstream MCP server is installed in this app.

Public policy and callback routes were verified with Django HTTP tests. New browser rendering and cross site cookie behavior have not been verified in an actual browser; the browser access host was unavailable. The Oura portal draft is untouched and unsubmitted. All Oura migrations ran only in disposable databases. The existing personal/preview databases and credentials remain unchanged.

The optional Oura Compose overlay was parsed with temporary synthetic secret files. The resolved callback URL, secret mounts, private networks and disabled MCP writes matched the proposal. No Docker daemon, remote file, DNS record, proxy, service or connection was changed. The default local Docker socket remains absent. Target runtime and capacity validation still need an authorized isolated environment. No deployment occurred.

## Permissions and preservation

Work began from clean `main` at `5573b02`; changes remain uncommitted. Project writes, loopback sockets and package downloads were verified. The existing environment was preserved; Pillow 13.0.0 and Django OAuth Toolkit 3.4.1 with its required dependencies were added to the Python lock without upgrading the original pins. No parent sources, personal database, credentials, remote services or existing connections were changed. Migrations ran only in disposable synthetic databases. The isolated Playwright daemon received scoped automatic approval for its normal macOS cache; protections were not changed.

## Executed application checks

```sh
.venv/bin/python scripts/verify_local.py --loopback
```

The command passed locked version matching, dependency compatibility, Django configuration, migration consistency, static collection and all 237 tests. Default execution without `--loopback` skips the optional real socket classes; those skips are not passes.

Coverage includes original domain/DST/unit rules, owner auth and CSRF, lockout, persistent browser/MCP write/read/correction/retry, process restart, disk SQLite concurrency, correction history, measurement CSV parser/import/browser boundaries, private photo formats/metadata/files/owner access, summaries/targets/deletion, summary CSV confirmation, bounded reads and exports, review scope/idempotency/annotations/deletion, charts and bounded asynchronous downloads. All fixtures are synthetic.

The composed Django/official SDK process proof uses a disposable disk database and signed fixture JWTs; only external JWKS retrieval is replaced. The process restarts with the same storage and reads the same measurements, versions, audit and session. Both internal ASGI and actual HTTP suites reject missing/invalid tokens, wrong issuer/audience/subject, missing read/write scopes, foreign Origin and unauthorized writes. New photo content requires explicit intent; saved reviews require separate write scope and explicit authorization. These local proofs do not establish ChatGPT account consent.

Both Django and the MCP wrapper now use `Referrer-Policy: same-origin`; the former `no-referrer` policy caused Chrome form POSTs to send `Origin: null`. The regression suite accepts correct same origin requests and rejects null/foreign origins even with valid CSRF tokens. CSP allows only local scripts for the vendored chart library, with no inline executable scripts or external CDN.

## Built in OAuth issuer proof

`scripts/verify_oauth.py` passed against a real Uvicorn Django/SDK application and disposable migrated disk database. It performs owner password login, CSRF protected consent, S256 PKCE, exact resource binding, real code exchange, denial of writes with a read token, an approved synthetic measurement write, duplicate retry, process restart with persisted records/session/tokens, refresh rotation and owner revocation. Both previously issued read/write access tokens then return 401, and refreshing the revoked grant fails. No live issuer, JWKS mock, ChatGPT account or public endpoint is used by this proof.

The 237 application tests include 12 OAuth tests covering the real Toolkit code/token flow, owner and CSRF, wrong PKCE/resource/redirect/scope, expiry, inactive owner, hashed access token storage, refresh replay protection, disabled endpoints, consent cancellation, rejection of consent bypass and a host restricted CIMD fixture. CIMD retrieval is stubbed with a synthetic document; actual ChatGPT metadata retrieval and account authorization remain unverified. New configuration preparation is tested for private permissions, read only defaults and refusal to overwrite an existing file.

Rendered Chrome at 390 × 844 showed the consent screen without horizontal overflow and completed authorization to a locally intercepted synthetic HTTPS callback. Issuer and code were present. No external callback host was contacted. Screenshot: `output/playwright/phone-oauth-consent.png`. Chrome initially blocked the redirect under `form-action 'self'`; the consent document now additionally permits only the callback origin already validated by Toolkit. Regression checks keep ordinary pages restricted to this application. Toolkit's consent denial omitted `iss`; the wrapper adds the pinned issuer only after client/redirect validation, with a cancellation regression test. No anonymous preview or authentication bypass was added.

## Dependency and artifact checks

The earlier request transport continuation added ten checks, bringing the full suite to 204 passing tests with no skips. Real Django ASGI tests verify declared and chunked overflow, falsely small length, invalid/duplicate headers, idle and total deadlines, spool closure, client disconnection, normal login/CSRF and uninterrupted response work after upload. Actual Uvicorn socket tests return 413 for oversized declared/chunked requests and 408 for a stalled body. `scripts/verify_oauth.py` was rerun successfully through the new wrapper. Timeout tests use shorter injected durations; application defaults remain 15 seconds idle and 120 seconds total. The tests remain synthetic and do not migrate personal storage.

The Docker CLI is installed, but the explicitly selected local default Unix socket `/var/run/docker.sock` is absent. A separately named `colima-wd2200` context belongs to coursework and was neither started nor used. No Docker context or global setting was changed. Container build/runtime and server capacity verification remain pending. Browser output and Playwright artifacts are now excluded from Docker build context in addition to existing private storage and secret exclusions.

The earlier 41 package checkpoint, including Pillow 13.0.0, Django OAuth Toolkit 3.4.1, oauthlib 4.0.1 and jwcrypto 1.6.1, passed strict `pip-audit==2.10.1` with zero reported vulnerabilities and no skipped dependencies. The original 33 dependency versions were preserved. Audit JSON was checked separately. Chart.js 4.6.1 was fetched from its official npm distribution with SHA512 integrity validation, is served locally with license notices, and passed npm audit with zero vulnerabilities. Hash/provenance details are in `tracking/static/tracking/vendor/README.md`. These are dated advisory checks, not guarantees about future advisories or another deployment platform.

restic 0.19.1 for macOS arm64 was downloaded to a temporary path and checked against its official release SHA256SUMS. Archive hash: `7be0a144ccc377880f294204aa271d76e4b79554b42a751151d425ce6ebac143`. It was not installed globally or configured against personal data. [Official release](https://github.com/restic/restic/releases/tag/v0.19.1).

## Encrypted backup and restore proof

```sh
.venv/bin/python scripts/verify_backup.py --restic /absolute/path/to/restic
```

This independently passed using a migrated synthetic disk database and synthetic photo. A consistent SQLite backup and both photo files were encrypted into a new local restic repository. Full repository data checking and restoration with verification passed. Three restored files matched their hashes; SQLite integrity and foreign keys passed; all tracked table counts matched. A separate Django process authenticated the restored synthetic owner and read the expected deletion tombstone/corrections, nutrition zero/null values, photo, saved review and editable targets. A wrong encryption password was rejected and intentional damage to a disposable restored file was detected. Source storage stayed intact and temporary plaintext snapshots/restores were removed.

The proof is separate from the 237 application test count. No actual backup repository, recurring job or retention cleanup was enabled. Secret/configuration custody, a durable off-device destination and an approved retention schedule remain operational setup requirements. Restore testing is not permission to replace a live database.

## Rendered browser evidence

An isolated Chrome session used the real local Uvicorn application and a disposable synthetic database. Desktop viewport: 1440 × 1000. Phone viewport: 390 × 844. No physical iPhone or Safari is claimed.

The earlier measurement flow checked login, CSV upload/preview with no writes, confirmation, synthetic exclusion, safe reimport, discard, logout and persistence of record IDs and session after server restart. Current browser checks additionally exercised photo upload and same-view comparison by capture dates; actual Chart.js initialization and plot rendering; partial nutrition entry with explicit zero and unknown values; target save; explicitly saved review; reviewed clinical CSV preview/confirmation with no pre-confirmation writes and preserved six decimal precision; and authenticated ZIP download. The downloaded ZIP was independently opened: two measurements, four summaries, two intact original photos, correction history and targets matched the fixture. Phone chart and overview widths equal the viewport without horizontal overflow. Screenshots were visually inspected. The isolated browser and temporary synthetic server were stopped after verification.

Ignored screenshots are under `output/playwright/`: earlier `desktop-upload.png`, `phone-review.png`, `phone-history.png`, `desktop-reimport.png`; current `desktop-photo-comparison.png`, `desktop-trends.png`, `phone-trends.png`, `phone-overview.png`, `phone-nutrition.png`, `phone-summary-review.png`. Lazy images load when scrolled into view. A local SVG favicon was added after the earlier missing-favicon 404. Django may still warn about synchronous static-file iteration under ASGI; private photo/export responses now use bounded asynchronous chunks and have a regression check.

## Acceptance status and remaining gates

| Requirement | Evidence or remaining requirement |
| --- | --- |
| Browser measurement to MCP and authorized correction back | Passed locally, with retry and process restart |
| Owner access and independent read/write scopes | Passed locally, including private photos and saved reviews |
| Missing/partial/zero/synthetic distinctions | Summary, import, chart, average and browser checks passed |
| Overlapping sources | Source records remain distinct and are never summed; native provider adapters are not connected |
| Private photos and usable export | Synthetic tests and rendered upload/comparison/download passed |
| Encrypted backup restoration | Separate restic proof passed, including restored application reads |
| Stored history during provider failure | Local reads require no provider calls; issuer outage behavior tested; no source sync job exists |
| Personal OAuth issuer | Implemented with Toolkit; local consent/token/refresh/revocation and real SDK process proof passed |
| Actual ChatGPT read and approved write | Still needs an authorized reachable HTTPS endpoint, account setup and real owner consent; separate issuer/JWKS is optional |
| Connected sources | None connected to this dashboard; existing ChatGPT MyFitnessPal access was historically verified November 5 and preserved |
| Native vendor files | Not automatically supported; reviewed dashboard CSV formats are implemented and tested |
| Physical iPhone/Safari installation | Requires authorized HTTPS hosting and device verification |
| Production deployment and migrations | Not performed; explicitly outside this task |

The local implementation is ready for review, not a completed connected release. Next, when hosting is authorized, configure the approved HTTPS origin and complete actual ChatGPT consent using `MCP_SETUP.md`, then source access, device acceptance and operational setup. No deployment, paid service or scheduled job should be inferred from these local results.

## Historical checkpoints

Parser checkpoint `edb871f` passed 76 tests with 11 socket skips in a restricted session. This continuation began clean at `5573b02`; the measurement import checkpoint passed 126 tests, followed by the expanded local build above. A separate synthetic disk SQLite measurement import probe passed identical, overlapping and conflicting batches; it was not part of the 126 count. Historical socket/DNS failures do not describe this session's verified local access.

## Existing DigitalOcean target

Current read only evidence supersedes the historical SSH failure. Mike authorized the existing preflight, which completed at 2026-11-06T12:54:54Z on `vaultstorage-pilot`, `157.245.247.90`, with exit 0, no unknown checks and no flagged items. Available RAM: 1.8 GiB; swap used: 1 GiB; available disk: 61 GiB; inode use: 5%; 19 running containers. The application path/account and listener 18170 were absent. No service, file, credential or network was changed. This is a point snapshot, not a sustained workload test.

Read only inspection verified Traefik 3.6, watched file provider, `http`/`https` entry points and `letsencrypt` resolver. Mike selected `live.cx83labs.com` for preparation; DNS currently has no address. `deploy/live.cx83labs.com/` contains an unexecuted route and isolated Compose override. Docker Compose configuration was parsed and checked using a temporary synthetic environment, without starting a daemon or container. Private binding, project networks, read only filesystem, resource limits and read only MCP configuration matched the proposal. Runtime, TLS and persistent proxy network attachment remain unverified.

## Oura reuse evaluation

See `OURA_REUSE_REVIEW.md` for pinned commits, licenses, commands, source findings and audit boundaries. Independently executed upstream suites: Proscar 362 Python, 143 TypeScript and 13 Worker unit tests; Robcerda 79 Python tests. No skips in final Python runs. Proscar Python third party audit: 33 packages, zero findings or skips. Robcerda runtime lock: one unique certifi advisory duplicated in the output. Proscar npm audits contain production and development findings detailed in the review. These are separate from the dashboard's 204 tests and its dependency lock, which were not changed by the review.

A synthetic probe reproduced cached records from a previous credential in Proscar's Python client. Both clients require additional work for our ingestion guarantees; the review does not approve installing either server. No new Oura adapter or policy routes were implemented during that assessment; they were implemented and verified in the later continuation recorded above. No real provider request or authorization occurred. The portal draft remains unchanged because Computer Use reported its session stopped.
