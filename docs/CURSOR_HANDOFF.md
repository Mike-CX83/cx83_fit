# Cursor continuation handoff

## Labs, meds, and diagnoses live, November 8, 2026, 3:21 AM CST

Published to `live.cx83labs.com`. Server commit `d4fd80f`. App container restarted in place (`ad48d4a2e237`, start `2026-11-08T09:21:00Z`). Shared proxy start remains `2026-10-10T17:40:21Z`. No migration. `OURA_ENABLED` stays 0.

`/records/` is the current list of labs, medications, and diagnoses. Today and More link to it. Plan links to it instead of holding the long form. Numeric results with a unit and a supplied reference range stay at `/summaries/health/`, titled Lab results. ChatGPT tools are `read_clinical_items`, `save_clinical_item`, and `stop_clinical_item` on the existing `health:read` connection. A repeated request replays. The receipt keeps the id and kind, not the name or detail. A new lab with the same name replaces the current result and keeps the older row.

Owner pages `/records/`, `/`, `/more/`, `/summaries/health/`, and `/plan/` returned the new copy. Anonymous `/records/` redirects to login. Focused tests passed: 19 tests across clinical, plan, and summaries. A disposable phone-width browser saved a synthetic medication and marked it not current, with no horizontal overflow. Laptop-width More stayed inside 1120. This was not a physical phone or a Dot voice check. ChatGPT needs a tool refresh before the new tools appear.

## Sobriety pattern live, November 8, 2026, 3:16 AM CST

Published to `live.cx83labs.com`. Server commit `1d89416`. Pre-migration backup snapshot `634478f2ca93166533f3864c0b088ed1470fa5e744e50aad940d810736ef9bc7`. Post-migration snapshot `bb56a59b66783f154f1a87c81a22896824d2e074a184fba929f101bdecfd30a0`. Migration `tracking.0009_sobrietyday` applied. App container restarted in place (`ad48d4a2e237`, start `2026-11-08T09:16:51Z`). Shared proxy start remains `2026-10-10T17:40:21Z`. Oura, MyFitnessPal, and the backup timer stayed active. `OURA_ENABLED` stays 0. Anonymous `/mcp` returned 401 and anonymous `/` returned 302. The module imports and the table is `tracking_sobrietyday`.

`read_sobriety_pattern` was already named in the live server file. The missing module is now mounted, so a ChatGPT session that already lists that tool can call it. A session that cached an older tool list still needs a refresh. One check-in a day is enough. Oura remains disconnected, so off-wrist stays idle until that connection is authorized.

## Quieter Today layout live, November 8, 2026, 3:11 AM CST

Published to `live.cx83labs.com`. Server commit `9a2214e`. App container restarted in place (`ad48d4a2e237`, start `2026-11-08T09:11:32Z`). Shared proxy start remains `2026-10-10T17:40:21Z`. No migration. `OURA_ENABLED` stays 0.

Live owner pages `/`, `/diary/`, `/plan/`, `/progress/`, and `/more/` returned 200. Today shows the check-in line and does not show the synthetic-test toggle or the synthetic 180.125 lb weight. ChatGPT can save a meal with `save_meal` and read one day's facts with `read_watch_signals` after a tool refresh. That read does not score relapse.

`read_sobriety_pattern` is registered in the same server file. The 3:16 AM note above is the publish that mounted the module and applied migration `0009`.

Local browser check on a disposable signed-in server, not a physical phone: 390 Today, Diary, Progress, and More had no horizontal overflow. 768 Today used the desktop tabs and stayed inside the window. 1440 Plan stayed inside 1120. 1920 Today used a 1360 column and two meal columns. Dot voice was not tested.

## Sobriety pattern, November 8, 2026

Local only. `read_sobriety_pattern` recomputes a 14 day tracker from journal, scores, ring and watch wear, recovery, training, nutrition, and measurements, with 3 and 7 day slices. No sobriety button. A blank day stays unknown. Off-wrist is a connected device that was not worn, separate from a stale sync. Domain 12 accepts craving, confidence, access, and use. Migration `tracking.0009_sobrietyday` is in the tree and was not applied on the live server. Morning and evening can both be saved. One check-in covers the day. A check-in reads the pattern after `read_journal_context` and before the follow-ups. The pattern is spoken only when the day is rising or high, a device is off-wrist, a use is in the window, or a run is open. It is not part of Daily State. Skills: `.cursor/skills/personal-health-dashboard/SKILL.md` and `.cursor/skills/sobriety-pattern/SKILL.md`. Note: `docs/BODY_SCAN_RESEARCH.md`. `.venv/bin/python scripts/verify_local.py` passed: 274 tests, 17 opt-in socket tests skipped. ChatGPT will not see `read_sobriety_pattern` until the tool list is refreshed. This was not published.

## CX83 Fit layout and chrome pass, November 8, 2026, 2:56 AM CST

Local only. Compact header, quiet Sign out, phone bottom tabs (Today / Diary / Progress / More), desktop top tabs, More as its own page, slim footer. Today is a calorie hero, compact chips, and meal sections with Add links into Diary prefills. Amber flare `#F59E0B` is limited to the active tab / date underline, calories remaining, and Add links. User-facing Synthetic labels and the export synthetic checkbox are gone; `?synthetic=1` still works for tests. Export always excludes synthetic rows. Also allowed the pre-existing `SobrietyDay` model through migration `0009` and the backup table list so local checks stay green. No live publish.

`.venv/bin/python scripts/verify_local.py` passed: 264 tests, 17 opt-in socket tests skipped.

## CX83 Fit daily UX, November 8, 2026, 2:30 AM CST

Local only. No deploy, migration, model change, or ChatGPT scope change. Primary nav is Today, Diary, Plan, Progress, More. Today shows calories, protein, fiber, steps, and weight against goals. Meal entry moved to `/diary/`. Plan keeps the 90 day window, goals, trends, and clinical items. Measurements and photos live under Progress. Synthetic toggles and operator essays left the normal screens; `?synthetic=1` still works for tests. Purple marks the active nav item. Protein uses the purple to pink goal bar. Yellow is only for close or flagged values. Electric Blue stays the button color.

`.venv/bin/python scripts/verify_local.py` passed: 264 tests, 17 opt-in socket tests skipped. Live hosting still serves the prior layout until a separate publish.

## Continuity, writes, and governing document, November 8, 2026, 2:26 AM CST

Pre-migration backup snapshot `f7e36b03659898b419c15c8b73f40ca7f85bb256ea5cf05ce57d87acaf2d9655`. Then published memory, morning and evening check-ins, optional scores, and the private governing document. Server commit `564b06b`. Migration `tracking.0008_journal_continuity` applied. The app container was recreated (`ad48d4a2e237`, start `2026-11-08T08:26:06Z`) so `MCP_WRITES_ENABLED=1`. Shared proxy start remains `2026-10-10T17:40:21Z`. Twenty containers stayed up. Oura, MyFitnessPal, and the backup timer stayed active. `OURA_ENABLED` stays 0 because the server has no Oura client secret or token key. Journal row count stayed 0.

Live checks: anonymous `/login/` returned 200, anonymous `/mcp` returned 401, and owner `/journal/` shows Check proposal. OAuth metadata advertises `health:read`, `health:write`, and `site:write`. The governing document is mounted for authorized reads and its status call does not include the text. `.venv/bin/python scripts/verify_local.py` passed before the migration: 264 tests, 17 opt-in socket tests skipped.

ChatGPT still has to refresh tools. The current token can use the journal, memory, question, score, and governing tools on `health:read`. Measurement and review writes need a reconnect that grants `health:write`. A Dot voice session can write only when that session can call tools. That voice call has not been tested.

The project skill is `.cursor/skills/personal-health-dashboard/SKILL.md`. The private arsenal catalog had no health or journal skill to reuse.

## Journal tools published, November 8, 2026, 2:14 AM CST

Published the proposal check and the ChatGPT journal tools to `live.cx83labs.com`. Server commit `abeb443`. App container restarted in place (`51b14e3eef62`, start `2026-11-08T08:13:38Z`). Shared proxy start remains `2026-10-10T17:40:21Z`. Twenty containers stayed up. Oura, MyFitnessPal, and the backup timer stayed active. `MCP_WRITES_ENABLED` stays 0. No new migration. `tracking.0007_journal` was already applied. Journal row count stayed 0.

Verified: anonymous `/journal/` returns 302 to login. Anonymous `/mcp` returns 401. Owner sign-in reaches `/journal/` with Check proposal, Save journal entry, and the Journal nav. A synthetic proposal check returned "Nothing was saved" and "explicit_choice, observed, no". The saved list stayed empty and the row count stayed 0. The running app contains `save_journal_entry`.

The agreed journal work is on the live site: entry save and correction, explicit false versus intention versus silence, qualitative notes, owner-only rejection of someone else's proposal, export and backup coverage for the diary, clinical items, and journal, and the same read, check, save, and delete actions on the existing `health:read` connection. The private governing document is still not mounted. Its pointer code is present and returns unavailable.

Not done, and not part of this publish: morning and evening question routing, durable memory, Daily State and Routine Alignment scores, and a tested Dot voice session. ChatGPT will not show the new tools until that connector is refreshed. A voice session can use them only if it can call tools.

## Journal tools for the ChatGPT connection, November 8, 2026, 2:09 AM CST

Mike requires ChatGPT and Dot to perform the same journal actions as the owner. Local MCP tools now do that on the existing `health:read` connection: `read_journal`, `preview_journal`, `save_journal_entry`, and `delete_journal_entry`. A save or delete still requires an explicit authorization flag. Measurement writes stay behind `MCP_WRITES_ENABLED=0`. `site:write` still cannot change health records. Proposal checks still write nothing. `.venv/bin/python scripts/verify_local.py` passed: 261 tests, 17 opt-in socket tests skipped. These tools are not on the live server yet. After publish, the personal ChatGPT connector must refresh tools. A voice session can use them only if that session can call tools. That voice behavior has not been tested.

## Journal proposal check, November 8, 2026, 2:04 AM CST

Local only. A client can propose observations and the server checks them before anything is saved. `POST /journal/preview/` and the journal page button "Check proposal" both use that check. The response says nothing was saved. Explicit false, an intention, and silence stay distinct. A qualitative note does not gain a severity. A proposal about someone else is rejected for the owner. Disagreeing proposals are returned unresolved. The check does not infer a fact from the wording. No score, memory, question router, Dot tool, or MCP journal tool was added. `MCP_WRITES_ENABLED` stays 0.

`.venv/bin/python scripts/verify_local.py` passed: 258 tests, 16 opt-in socket tests skipped. A disposable browser at `127.0.0.1:8768` checked "I did not meditate" as an explicit no and left the saved list empty. That server was stopped. This was not deployed. The dark chrome publish below is separate and does not include this check.

## Dark CX83 Fit chrome, November 8, 2026, 2:01 AM CST

Switched the live dashboard to the CX83 Labs Midnight dark treatment. Page `#080E22`, surfaces `#101A33`, silver type, Electric Blue actions, luminous `#B6EAFF` links. Header uses `symbol-showcase.svg`; footer uses `logo-dark.svg`. Server commit `470f306`. App restarted in place (`51b14e3eef62`, start `2026-11-08T08:00:58Z`). Shared proxy start remains `2026-10-10T17:40:21Z`. Connectors and backup timer stayed active. `MCP_WRITES_ENABLED` stays 0. Chart colors were not retuned in this pass.

## Journal published live, November 8, 2026, 1:56 AM CST

Published the owner journal loop to `live.cx83labs.com`. Server commit `ac2a940`. Pre-migration Drive backup snapshot `e2bbac4c50f38bb1e4c5aaf82b9491adb30a76c1aca47aa4fa46fe079d27eed1`. Migration `tracking.0007_journal` applied on the live volume. App container restarted in place (`51b14e3eef62`, start `2026-11-08T07:56:39Z`). Shared proxy start remains `2026-10-10T17:40:21Z`. All 20 container IDs unchanged. Oura, MyFitnessPal, and the backup timer stayed active. `MCP_WRITES_ENABLED` stays 0. No ChatGPT or Dot journal tools were added.

Verified: anonymous `/journal/` redirects to login. Owner sign-in reaches `/journal/` with Sign out, CX83 Fit chrome, and Journal nav. Backup script on the host now counts journal tables when that group is complete. Next local build remains client extraction proposals. Journal MCP/Dot access still needs a new consent before any tool.

## CX83 Fit branding live, November 8, 2026, 1:48 AM CST

Published CX83 Fit branding to `live.cx83labs.com`. Server checkout commit `dd7d951`. Only branding source under `dashboard`, `tracking`, and `docs/BRANDING.md` was written. The Journal nav link was not published. App container `personal-health-dashboard` restarted in place (`51b14e3eef62`, start `2026-11-08T07:47:59Z`). Shared proxy `896e154e5916` start remains `2026-10-10T17:40:21Z`. All 20 container IDs unchanged. Oura, MyFitnessPal, and the backup timer stayed active. Public anonymous `/login/` shows CX83 Fit, the Labs mark, and the light palette. Manifest, favicon mark, and Geist font return 200. No migration, proxy, DNS, connector, backup, or health-record change.

## Local journal loop, November 8, 2026, 1:51 AM CST

Built and tested locally. This pass did not deploy, migrate production, enable live journal writes, or change connectors. The branding publish above did not include this journal code. The live Journal link remains unpublished.

The local dashboard saves a journal entry and one explicit observation in the existing database. `/journal/` is owner only. A date only entry does not invent a clock time. Explicit false stays false, unknown stays empty, and a qualitative note is not turned into a number. The same request id replays. A different payload or a stale version is rejected. A text correction does not rewrite the observation version. Deletion clears the active text, observation value, and receipt body. A tombstone remains. Synthetic entries stay out of the personal list.

`ReviewNote` and `DietEntry` stay what they are. Journal text is not a review annotation and not a meal row. Receipts store the entry id, versions, and operation. They do not store the journal text. Domains 12, 13, 14, 16, 17, 18, and 19 are a database constraint. The code registry currently accepts two unscored slots, `note` and `explicit_choice`. `lineage_id`, `processing_state`, and reserved `mcp` and `voice` channel values leave room for later memory, questions, scores, and Dot. Those systems are not implemented. The service accepts dashboard saves only, and it does not parse a story into facts.

A private governing document can later be identified by `governing/current.json` in private storage, with an id, version, and sha256. The app does not read or return the document text. Nothing is mounted, and the journal page says so. `rule_set` stays outside Git.

Owner export now includes diet entries, clinical items, journal entries, observations, and correction field names. Deleted journal text is omitted. `scripts/backup.py` counts those tables when the whole group is present and still verifies older snapshots that lack plan or journal tables. A partial group is rejected.

`.venv/bin/python scripts/verify_local.py` passed after the final version fix: 256 tests, 16 opt-in socket tests skipped. Migration check passed. A disposable browser session saved, corrected, and deleted a synthetic entry at desktop and 390 pixel width. The plan page still opened. That server used a temporary database and was stopped. Production `MCP_WRITES_ENABLED` stays 0. Migration `0007_journal` is local only. The live backup timer still runs the previously deployed script until a separate release.

Next: keep using the local journal page. The following build step is a client extraction proposal that the server validates, still without scores, Dot, or a production write. ChatGPT or Dot journal access needs a new consent before any tool is added.

## CX83 Fit branding, November 8, 2026, 1:40 AM CST

Product identity is now **CX83 Fit**, built by CX83 Labs. Local chrome uses the Labs geometric frame, light CX83 palette, and Geist. Brand rules are in `docs/BRANDING.md`. Assets are under `tracking/static/tracking/brand/`. Local browser verification covered sign in, overview, and plan. Live hosting was not updated. Next UX work can continue on the current layout; publish the branding with the next authorized app update when ready.

## Journal repository assessment, November 8, 2026, 1:31 AM CST

Inspection and planning only. No application code, migration, test run, commit, push, deployment, permission, backup, connector, or health-record change was made. The uncommitted tree on `main` at `5573b02` was left as found.

### What already exists

The app is one Django project with SQLite, owner login, and login names `kayla` and `mike` mapped to that single owner. Those names are not separate privacy boundaries. Live ChatGPT access is `health:read` plus `site:write`. `health:write` is not advertised and `MCP_WRITES_ENABLED` stays 0. Site edit tools can change source files. They cannot write health records.

Durable records already cover body measurements, corrections, photos, nutrition/recovery/activity/clinical summaries, editable targets, saved reviews, Oura source pages and revisions, a 90 day meal diary (`DietEntry`), and current clinical items. `WriteRequest` gives owner scoped idempotent receipts: the same request id and payload replay, and a different payload is rejected. Reviews, summaries, and measurements already use that pattern. Exports, encrypted restic backups, and OAuth request limits exist. The live plan page, daily Drive backup, and standalone Oura and MyFitnessPal connectors stay in place and were not retested in this pass.

`ReviewNote` is a dated annotation, optionally linked to a measurement or summary. It does not carry a domain, a typed value, an evidence state, or a correction of its own text. `DietEntry` is a meal row with optional calories, protein, and fiber. Neither is a journal. No model, tool, page, or test implements domains 12, 13, 14, 16, 17, 18, or 19, morning or evening check-ins, observations, memories, question state, or optional state and alignment scores.

The local `../sources/rule_set.docx` is readable and remains outside this repository. It has seven governing sections: date and time, whole person context, nutrition and training, mental and nervous system, spiritual framework, identity and continuity, and communication. It contains personal numeric targets. The deployed app does not mount that file. It must not be copied into Git, fixtures, or the business mailbox.

### What needs extending

Journal text, supported observations, corrections, and later memories and questions need their own records. Reads, writes, exports, deletion, and backup coverage have to include them. Current ZIP export and `scripts/backup.py` table lists omit `DietEntry` and `ClinicalItem` from migration `0006`. New journal tables must not repeat that gap. Existing review receipts also store saved text inside `WriteRequest.response`. A deleted review cannot be restored by retry, but that stored response can still hold the text. Journal receipts should not copy that behavior.

Scoring, question routing, Dot voice, and a private runtime copy of `rule_set` are later work. Dot tool access during voice is unverified. A local MCP test would not prove it.

### Recommended architecture

Keep one application and the existing database. Add a journal entry for authorized source text and a separate observation for each supported fact. Reuse `WriteRequest` for the commit and correction receipt. Keep the seven domain IDs in a versioned code registry. Let the conversational client propose structured observations and let the server validate types, states, ownership, and versions. Calculate any later score on the server from stored inputs. Do not put narrative entries in the meal diary or in review notes.

Unknown, declined, not applicable, pending, and conflicting stay distinct from false and from numeric zero. A saved entry remains readable if extraction fails. Corrections supersede observations and invalidate dependent output. Synthetic rows stay out of personal reads by default.

Do not attach journal writes to `site:write` or to the current live `health:read` grant. When a client write is later authorized, use a new journal scope that existing tokens do not already have. Until then, the dashboard owner session is the only writer, and only in an isolated local database. Production `MCP_WRITES_ENABLED` stays 0.

Leave Daily State and Routine Alignment unimplemented until the metric definitions are chosen. The formulas in the planning package are illustrations, not approved defaults. No new recovery score, model API, vector store, worker, or scheduled interpretation job.

### Departures from the planning package

The package is the right shape. These choices fit the code better:

* Separate journal and observation records, instead of extending `ReviewNote`. A review remains an annotation and must not become the narrative store.
* Receipts store the request id, payload hash, owner, operation, and result ids. Replay rereads the current row. The receipt does not keep a second copy of the journal text.
* The first loop is dashboard only. MCP journal tools wait for the new scope and a separate enablement. Voice is a later client proof, with the dashboard as the fallback if voice cannot call tools.
* `rule_set` stays a private local document for this slice. Generic protocol text can live in code. A deployed private copy needs its own protected store and is not required to save the first entry.
* Backup and export coverage is part of the first slice, including the existing omission of diary and clinical plan rows if that fix stays inside the same local change. That fix is local compatibility work. It is not a production migration or a live restore.

### Smallest useful slice

One local synthetic loop, still not started:

1. Save an authorized journal entry with capture time, occurred date, timezone, channel, and synthetic flag.
2. Attach one validated observation with domain id, value state, and source link.
3. Read it back after a process restart in a disposable database.
4. Correct it with an expected version. A stale version and a reused request id with a different payload must fail closed.
5. Delete it so active text and derived rows are gone, with a minimal tombstone and no text left in the receipt.
6. Include the new rows in the owner export and the backup table manifest. Run focused synthetic tests only.

No production migration, health-record write, deploy, or publish belongs to that slice.

### Open decision

One product choice is still open: whether a future ChatGPT or Dot connection may read journal text with the existing `health:read` grant, or only after a new consent. The recommendation is a new consent. Implementation of the local dashboard loop does not need that answer. It does need a separate go ahead before code changes.

### Not done

Dot voice, fresh session retrieval, physical iPhone journal use, production schema changes, and live health writes remain unverified and unauthorized. The planning files under `docs/journal-intelligence-handoff/` are unchanged.

## Suggested journal architecture handoff, November 8, 2026, 1:24 AM CST

Planning only: [journal intelligence build brief](journal-intelligence-handoff/00-MASTER-BUILD-BRIEF.md) links eight Markdown files covering original domains 12, 13, 14, 16, 17, 18 and 19, adaptive check-ins, optional scoring, missing data, provenance/privacy, integration, phased acceptance and a coding-agent prompt. The package distinguishes required outcomes from adaptable recommendations and requires repository inspection first. Existing source changes and private synced documents were preserved. All eight files and their relative links were checked. Application tests were not rerun for this documentation-only change. No health records, live services, permissions, integrations, deployment, commit or push were changed. Dot voice behavior remains unverified. Next: the coding agent reads the master brief and current code, records its reuse/extend decisions here, and implements only within separately authorized scope.

Updated November 8, 2026, 12:31 AM CST. **The live plan page at `https://live.cx83labs.com/plan/` holds the 90 day window, goals, diary, common meals, and trends.** Health record writes from ChatGPT stay off. Device burn is logged only from records the dashboard already holds. Preserve standalone connections, business workloads, credentials and local history. Do not reset or touch parent `sources/` files. Read the newest checkpoint before making changes.

## Plan page, November 8, 12:31 AM CST

`/plan/` shows goals, meals that repeat at least twice, a diary, a MyFitnessPal paste that updates the same meal, calories burned separate from food, and trends for weight, waist, chest, hip, arm, thigh, calf, sleep, HRV, resting heart rate, and readiness. Each trend opens the existing chart for 2026-08-11 through 2026-11-08. Goals are edited at `/nutrition/targets/` and now include steps and sleep hours. Migration `tracking.0006_plan_window` is applied. The app restarted at `2026-11-08T06:30:46Z`. The shared proxy still started `2026-10-10T17:40:21Z`. The page is empty of real history. ChatGPT can read it with `read_fitness_plan` after a tool refresh. No personal meals, labs, or goals were entered.

## Commit and publish, November 8, 12:02 AM CST

ChatGPT now has `commit_and_publish` on the existing `site:write` scope. After a source edit, that tool commits the named `dashboard`, `tracking`, or `docs` files in the server checkout and restarts only `personal-health-dashboard`. It does not push, and a secret path is refused. The host unit is `personal-health-publish.path`. The server baseline commit is `c9e9bd4`. The app container ID starts `51b14e3eef62` and it started `2026-11-08T06:02:09Z`. The shared proxy still started `2026-10-10T17:40:21Z`. Tools were refreshed in the personal ChatGPT plugin. No phone edit has been committed yet.

Next action: from the phone, ask ChatGPT to change one visible line and publish it. Then reload `https://live.cx83labs.com`.

## ChatGPT site edits, November 7, 11:44 PM CST

CX83 Website is set to Allow all. The health plugin now uses that same permission. Its description is "Read and edit the private health dashboard site. One exact source replacement. Health records stay read only." Tools were refreshed and the account was reconnected. The new access token scope is `health:read site:write`. Public metadata advertises those two scopes. `health:write` is not advertised and `MCP_WRITES_ENABLED` stays 0.

The live tools are `read_repository_file`, `search_repository`, and `apply_repository_edit`. An edit must match one exact span, must be explicitly authorized, and refuses credential, secret, private, and database paths. The container sees only `dashboard`, `tracking`, and `docs` under `/repo`. Secrets and `.env` are not mounted. `dashboard` and `tracking` are also mounted over the running app code. Docs are read only. The app container was recreated. Its ID starts `469a6614e49c` and it started `2026-11-08T05:39:03Z`. The shared proxy ID still starts `896e154e5916` and it still started `2026-10-10T17:40:21Z`.

Focused repository tests passed: one unique replacement, a duplicate span refused, and secret paths refused. Anonymous `/` still redirects to login and anonymous `/mcp` still returns 401. This is not a ChatGPT chat edit yet. Mike can ask the personal ChatGPT window to change a source file. The running pages keep their loaded code until the app container is restarted. There is no commit, push, or deploy tool.

Next action: from the personal ChatGPT window, ask for a specific one line source change and confirm the file on the server changed. Restart only `personal-health-dashboard` when that change should appear on the live site.

## Login names, November 7, 10:57 PM CST

The app still has one owner account. `DASHBOARD_LOGIN_NAMES=kayla,mike` maps those sign-in names to it. The pinned image was not rebuilt. The running app container was recreated with read-only mounts from `deploy/live.cx83labs.com/compose.login-names.yaml` for `dashboard/auth.py`, `dashboard/settings.py` and the login template. New app container ID starts `8b9209696c6e`. The other 19 container IDs were unchanged, including `coolify-proxy` `896e154e5916`. No shared proxy restart, migration, backup or connector change was made.

Verified: anonymous `/` still lands on login. Browser sign-in as `kayla` and as `mike` reached the overview and Sign out. A wrong password stayed on the login page. Focused `LoginSecurityTests` passed, 7 tests. The full suite was not rerun.

## Routing inspection, November 7, 10:24 PM CST

Cursor browser tools loaded `https://example.com/`. The title is `Example Domain`. The live page has no heading element. Its first text is the English documentation sentence.

The private SSH forward is still running as pid 17601: Mac `127.0.0.1:18440` to server Coolify `127.0.0.1:8000`. Cursor browser opened `http://127.0.0.1:18440/login`. Title `Coolify`, first heading `Coolify`. The login form is waiting. No password was entered.

Cloudflare opened at `https://dash.cloudflare.com/login` and is also waiting on sign-in. No DNS write was made.

Read-only checks before any change: `live.cx83labs.com` has no A answer at 1.1.1.1. Nameservers are Cloudflare. On `vaultstorage-pilot` the dashboard container is running, 20 containers are up, `personal-health-ingress` exists with only `personal-health-dashboard` attached, `coolify-proxy` remains on `coolify` and `vaultstorage-pilot_default`, and `/data/coolify/proxy/dynamic/personal-health-dashboard.yaml` is absent. No proxy save, network attach, route install, restart, migration, or backup action was performed. Oura ingestion and MCP writes stay disabled. The stopped Mac connector runtimes were not started.

Coolify login succeeded with the copied pilot password for `mike.hankins.rn@gmail.com`. The only Coolify server is named `localhost` (`eyey2xr4p6d3crz40fe6nej4`); that is the Coolify host on `vaultstorage-pilot`. There is no server record named `vaultstorage-pilot`.

The proxy editor first showed a shorter configuration than `secrets/deploy/proxy-original.yaml`: it omitted `vaultstorage-pilot_default` and the certificate email, while `/data/coolify/proxy/docker-compose.yml` still matched the original hash. The first save wrote that shorter text. A second save restored those existing lines and added only `personal-health-ingress` in both network locations. The saved configuration and the compose file now both match `secrets/deploy/proxy-with-dashboard-network.yaml`, SHA256 `e33e7759bc98d342086f05557648aefa7a5f336a5c97847f10885f3ba6ea8b71`. The proxy container was not restarted. Its id still starts `896e154e5916` and it started `2026-10-10T17:40:21Z`. It remains attached to `coolify` and `vaultstorage-pilot_default`. Coolify reports that the saved change is not applied until a restart. That restart was not performed.

DNS A `live` was absent. It was created as `157.245.247.90`, DNS only, TTL Auto. Authoritative Cloudflare DNS and 1.1.1.1 both answer that address. Existing records were left in place.

`coolify-proxy` was attached to `personal-health-ingress` without a restart. The prepared route is installed at `/data/coolify/proxy/dynamic/personal-health-dashboard.yaml`, mode 644, SHA256 `203cf15d6fd4770281e5c59ab487e0eab9c5f2814b6da3381f95bfb989ab1f1f`, matching the local route file. The proxy container id still starts `896e154e5916` and it started `2026-10-10T17:40:21Z`. It is attached to `coolify`, `vaultstorage-pilot_default`, and `personal-health-ingress`.

Focused checks passed. The public certificate is Let's Encrypt YR2 for `live.cx83labs.com`, valid through February 6, 2027. HTTP redirects to HTTPS. Anonymous `/` redirects to `/login/`. Anonymous `/mcp` returns 401. Owner login in the browser reached the overview and showed Sign out. The same 20 container IDs were running before and after. `oura-personal.service`, `myfitnesspal-personal.service`, and `personal-health-backup.timer` stayed active. `coolify.cx83labs.com` returned 302. `sign.cx83labs.com`, `n8n.cx83labs.com`, and `lead.cx83labs.com` returned 200. Oura ingestion and MCP writes stayed disabled. The stopped Mac connector runtimes were not started.

ChatGPT `private_key_jwt` client metadata is now accepted. The signing key is checked when ChatGPT sends a client assertion. ChatGPT also advertises public PKCE, and that path remains available. The change is mounted read-only from `dashboard/private_key_jwt.py` and `dashboard/oauth.py` through `deploy/live.cx83labs.com/compose.private-key-jwt.yaml`. Only the dashboard app container was restarted. The shared proxy start time is still `2026-10-10T17:40:21Z`.

Personal ChatGPT connected to `https://live.cx83labs.com/mcp`. Owner consent granted `health:read` only. A valid ChatGPT access token exists for the ChatGPT application. A connected chat asked for the measurement count from 2026-01-01 through 2026-11-07 and the reply was 0. No measurement values were shown. The physical iPhone check has not started.

Mike later confirmed the iPhone login. The current next action is the site edit check at the top of this file.

## Current deployed backend checkpoint

The approved artifacts were uploaded, hash verified and installed only under `/opt/personal-health-dashboard`. The pinned Linux image is running as `personal-health-dashboard`, restricted to `127.0.0.1:18170` and its new private networks. Only the new dedicated volume was migrated. Owner username is `owner`; its generated password is stored privately on the Mac at `secrets/deploy/dashboard-owner-password`. The dedicated server configuration was copied privately to `secrets/deploy/dashboard-server.env` for recovery; never print either file. Real password/CSRF login, secure session cookies, one clearly synthetic measurement, exclusion from personal history and session/data persistence after an app-only restart passed on native server loopback. Public policy handlers and pinned OAuth metadata responded. This is not public TLS, browser visual or actual ChatGPT verification.

The first native server backup to `rclone:health_dashboard_backup:cx83-personal-health-dashboard/restic` passed. The expired Google access token refreshed successfully; the server's protected rclone config now contains newer access state than the original Mac config. Preserve it before recovery/reauthorization; do not overwrite it with stale state. `personal-health-backup.timer` is enabled/active for daily 03:15 America/Chicago with up to 15 minutes jitter. First snapshot ID is `090c95e20c19502776f31dd5c692d3097e9d81a0b1dd61bc9e88156c29069755`. No real health records were added. The existing Mac cloud restore proof remains valid and was not rerun. Native evidence is `docs/evidence/deployment-native-20261107.json`; private execution evidence is `/root/health-dashboard-stage-20261106` on the target and `secrets/deploy/deployment-state.json` locally.

Preservation verification passed: all 19 original container IDs remain running; the additional dashboard makes 20. Oura and MyFitnessPal systemd state/PIDs match the original baseline. No shared proxy restart, route, DNS, business database or standalone connector credential change has been made.

Remaining public routing requires two owner-side changes or supported browser/API access: (1) Cloudflare A `live` → `157.245.247.90`, DNS only, TTL Auto; (2) save the two reviewed network additions in Coolify's supported saved Proxy Configuration before attaching the running proxy. The complete unchanged-plus-two-additions file is privately prepared/opened in Cursor at `secrets/deploy/proxy-with-dashboard-network.yaml`; original is `proxy-original.yaml`. A private SSH forward is active in exec session `84175`, binding Mac `127.0.0.1:18440` to existing server Coolify `127.0.0.1:8000`. Its login page returned HTTP 200. Mike requested Coolify help and was asked to open that URL, sign in normally and show the page. Do not create API credentials, reset passwords or edit Coolify's database as a shortcut. A new Chrome retry after Mike changed settings still reported `The browser access host is unavailable`; no native Chrome window control or alternative browser stack was used.

Once saved configuration and DNS are verified, attach only `coolify-proxy` to the existing new `personal-health-ingress` network, install only the prepared route file, verify certificate/HTTPS, perform hosted owner login and actual ChatGPT read, then help Mike with physical phone access. Oura ingestion and MCP writes remain disabled. Do not repeat installation, schema creation, production backup initialization, full test suites or deployment approval. Preserve existing resources and resume from their verified state. Earlier preparation states below are historical.

## ChatGPT Chrome browser-control repair, November 7 evening

Diagnosed the original ChatGPT desktop Chrome integration. Did not treat Cursor browser tools as proof. Installed app is `/Applications/ChatGPT.app` (`com.openai.codex`). Before repair it had been the same process since November 2 (`26.1027.51404`). Chrome `156.0.8078.81` stayed running. Official plugin checks: Chrome running; ChatGPT extension `hehggadaopoacecdllhhajmbjkdcmajg` installed and enabled in Profile 21 (CX83 Labs Work) and Profile 10; native-host manifest `com.openai.codexextension` correct.

Cause: `~/.codex/chrome-native-hosts-v2.json` still had presence `lastSeenAt` `2026-11-02T20:42:24Z` for that long-lived ChatGPT process. Chrome’s native helper was up, but the desktop runtime registry was stale, matching `cua.getState()` `browsers: []` / `The browser access host is unavailable` and Computer Use stopping `com.google.Chrome` for the turn. Extension/native-host install was not the missing piece.

Repair: hid the open secret editor tab; quit ChatGPT only (AppleScript quit was ignored, then SIGTERM to the ChatGPT process); relaunched ChatGPT; left Chrome profiles/tabs/sign-ins in place; SIGTERM of the two `ChatGPT for Chrome` native-host helpers so Chrome respawned them against the current helper. ChatGPT itself updated on relaunch to `26.1027.61615`. Registry now matches live ChatGPT pid `88822` with `lastSeenAt` `2026-11-08T03:34:21Z`. Native host still correct. Two new helper processes started. Chrome was not quit.

Retry in the original thread then failed with both `Sky Computer Use native pipe startup failed` and `The browser access host is unavailable`. Desktop logs for that resumed thread `01a1b935-…` show no in-app browser route (`No ChatGPT browser route is available for browser session …`) while other chats opened after relaunch did get a route. Computer Use helper and Chrome native host are running on the Mac; the old thread did not rebind to them. Do not repeat the ChatGPT SIGTERM. Next owner action: in ChatGPT desktop, open a **new** local Work/Codex chat in this project, press ⌘⇧B once, then run the Chrome list/read prompt there. If macOS prompts for Accessibility or Screen Recording for ChatGPT or ChatGPT Computer Use, allow those. If Settings → Computer Use → Chrome still shows disconnected, click Connect. Do not reset profiles or change approval modes. Deployment, DNS, Coolify, and existing services were not changed.

## Read first

Read `AGENTS.md`, `README.md`, `docs/VERIFICATION.md`, the complete original `docs/Personal_Health_Fitness_Dashboard_Build_Prompt.txt`, and the read only `../sources/rule_set.docx`. Architecture, source contracts and operating details live in `PHASE_1.md`, `DATA_CONTRACT.md`, `INTEGRATIONS.md`, `OSS_REUSE_AND_MOBILE.md` and `OPERATIONS.md`.

## Authorization and working state

Mike initially requested local development and synthetic verification. He subsequently approved initial deployment at `live.cx83labs.com`, its new schema/route and daily encrypted Google Drive backups on November 7. That approval remains in effect; see the current deployed backend checkpoint. Environment resets, unrelated service/credential changes and paid subscriptions remain outside scope. Do not ask for the deployment approval again.

Work began from clean `main` at `5573b02`. The current implementation is uncommitted; preserve it. No commit, push or deployment was performed. The original private database and credentials were not changed. Migrations were exercised only against disposable synthetic databases.

This session verified workspace writes, loopback listeners and package downloads. Its filesystem permissions allow this project and temporary directories; Git metadata and several configuration directories are read only. An isolated Playwright Chrome daemon needed a scoped, automatically approved escalation for its standard macOS cache. No security setting was changed. Historical socket/DNS/SSH failures do not describe the current local execution environment.

## Current Oura and hosting continuation

### Approved deployment checkpoint, November 7 evening

Mike explicitly approved initial dashboard deployment at `live.cx83labs.com` with daily encrypted Google Drive backups. A fresh read only preflight at `2026-11-08T03:23:09Z` passed with zero review/unknown items: 1.5 GiB available memory, 60 GiB free disk, 19 existing containers; both standalone connector units active/enabled with no automatic restarts. Approved image/source/current backup supplement checksums matched. Only `/root/health-dashboard-stage-20261106` was created on the server, mode 0700, with a private baseline. No app image/config/credentials have been uploaded, application started, backup timer installed or DNS/proxy change made by the agent yet. The proxy config hash still matches the prepared baseline. The new hostname has no DNS A answer at inspection.

Cloudflare DNS API credentials were not available in exposed tools/local configured references; the scoped 1Password helper reported uninitialized access even outside the sandbox. Mike was asked to create only the approved DNS record, then instead requested a Cursor-agent prompt to restore this ChatGPT session's Chrome control. Diagnose the browser integration before continuing manual browser-dependent DNS/Coolify configuration. Exact browser errors are `The browser access host is unavailable` and the application session reported stopped for the turn; opening Chrome does not restore the tool connection. Do not reset profiles, alter approval policies, expose secrets or substitute another automation stack as proof this session works. Preserve this deployment checkpoint and existing services. Deployment remains authorized; do not request that same approval again. The saved Coolify proxy-network delta must still be persisted through its supported configuration path before public routing.

### Current Google Drive result, November 7

The corrected Google OAuth flow completed with both access and refresh tokens saved. The dedicated account was verified as `mike@cx83labs.com` using Google Drive `about.get` with only `fields=user(emailAddress)`; rclone Drive does not implement its generic UserInfo command. No additional scope was requested. The config and recovery password are mode 0600 inside mode 0700 directories and ignored by Git. No credential value was displayed. No payment method or organization-wide policy was changed by the agent.

**One actual Google Drive encrypted synthetic backup and isolated restore passed.** The test repository is `rclone:health_dashboard_backup:cx83-personal-health-dashboard/synthetic-check-20261107-44e79a13`. Three files matched, database integrity/foreign keys and manifest counts matched, and restored application queries passed, including synthetic Oura exact values/revisions/token decryption, photos and deletion history. Wrong password and tampering were rejected. Evidence: `docs/evidence/drive-backup-verification.json`. The synthetic repository is retained. No real health records were uploaded. No full application suite or repeat Linux build was run. A complete live token-expiry/refresh cycle was not forced or claimed.

The Drive connection and Mac cloud proof are complete; server installation, recurring backup activation, real hosted HTTPS/ChatGPT/iPhone acceptance and dashboard deployment are not. The production repository `.../restic` is not initialized. The current backup deployment supplement is `dashboard-drive-backup-verified-20261107.tar.gz`; earlier archives remain preserved and superseded. Mike confirmed on November 7 that he saved the recovery password in his password manager. This is owner-reported custody; the agent did not inspect or write the password-manager item. Next owner step: review/approve the exact deployment and backup schedule in `deploy/live.cx83labs.com/README.md`. No production approval has been given yet. Existing standalone Oura/MyFitnessPal services and registrations are untouched. Earlier preparation/blocked states below are historical and superseded by this verified result.

November 7 importer correction: after Mike reported authorization complete, no token was saved. Source inspection of pinned rclone 1.76.0 showed the helper's `rclone obscure` step was incorrect for OAuth `client_secret`; the library uses that field verbatim. `scripts/setup_drive_backup.py` was corrected, and the unauthenticated dedicated config was repaired from the same downloaded Desktop client, preserving its previous private file. Client identity and scope were unchanged. Matching secret/ID booleans were verified without printing values. Three focused tests in `tests/test_drive_setup.py` passed, including refusing changes to an authorized connection. The helper now captures provider responses only in memory and reports allowlisted OAuth error names. A fresh corrected authorization flow was started; verify saved token state before claiming success. Earlier prepared backup supplements must be replaced with the corrected importer before deployment. No full application suite, server action or real health upload occurred.

November 7 authorization checkpoint: Mike confirmed saving the limited Drive scope and the setup helper launched the dedicated rclone browser flow. Owner screenshot then showed Workspace services unavailable and requiring owner reactivation. The dedicated callback process was stopped by exact command match; helper exited cleanly with its generic incomplete message. Configuration is preserved at mode 0600. No refresh token or recovery password is present, and no Drive backup/upload/restore succeeded. Keep account recovery details out of Git and business mailboxes. Next: Mike restores access to his Workspace Drive service, then rerun authorization with the existing client/config, privately verify `mike@cx83labs.com` and perform one synthetic cloud backup/restore. Do not recreate the project/client, switch accounts, change billing, deploy or enable the timer from this blocked authorization attempt.

Google backup update: Mike completed Workspace 2-step verification and screenshots verified the new organization-owned project `cx83-personal-health-backups` (number `922720354557`) and Internal audience. He created/downloaded its Desktop OAuth client. The matching downloaded JSON was read locally and imported into ignored `secrets/backup/rclone/rclone.conf` with mode 0600 and only `drive.file`; no credential values were displayed and the original download was retained. Offline authorization is still absent. Mike is completing Data Access with only `https://www.googleapis.com/auth/drive.file`. Next: after he confirms that setting is saved, run the existing setup helper with `--authorize`, have him approve the Workspace browser flow, privately verify the authorized identity is `mike@cx83labs.com`, then run the single prepared synthetic Drive backup/restore. Drive API enablement will be confirmed by the actual provider read. No password has been generated yet, cloud backup tested, or server change/deployment made. Browser control remains unavailable; do not repeat the Chrome reopen loop or print credentials.

Latest backup continuation: Mike selected Google Drive and explicitly chose **CX83 Labs Google Workspace**, authorizing connection preparation and one synthetic upload/restore check. Use an organization-owned Google Cloud project, **Internal** audience and a dedicated Desktop OAuth client with `drive.file`. No Shared Drive or organization-wide policy change is authorized. The connected ChatGPT Drive app is Gmail and must not be used as the backup account. No local gcloud config or dedicated rclone connection was found. Browser automation returned “The browser access host is unavailable”; Google Cloud credentials was opened in Chrome through the installed app. Mike is being asked to select his Workspace account, create/select a CX83 Labs organization project and report its name/ID. Official pinned rclone/restic Mac/Linux tools are downloaded and checksum verified, without global installation. `scripts/setup_drive_backup.py` imports a downloaded Desktop client privately and delegates OAuth to rclone; no real credentials have been imported yet. The existing backup helper supports a separate limited `drive.file` remote and rejects broader scope/inherited credential overrides. Local synthetic backup/restore compatibility passed. Real Drive upload/restore remains blocked on Google project/client setup and owner consent. A one-shot backup Compose overlay and proposed timer are prepared only. See `OPERATIONS.md` for exact commands, key custody and Internal audience requirements. Next: Mike selects the organization project and downloads its Desktop OAuth client JSON locally; import it without printing secrets, complete Workspace browser consent, verify the authorized account, then run one cloud synthetic backup/restore. Dashboard deployment remains pending separate approval.

Latest checkpoint: Mike authorized dashboard release preparation with focused testing only. Production deployment still needs his separate approval. The Linux amd64 image built and the focused container/Traefik HTTPS/login/retry/restart/persistence smoke passed; see `VERIFICATION.md` and `docs/evidence/container-release.json`. No full suite was rerun. Fresh read only preflight at 2026-11-06T20:14:46Z passed, with 1.7 GiB available memory, 60 GiB free disk and 19 existing containers. The Docker base and exported application image are pinned; private data permissions are enforced by the container entrypoint. Reviewed artifacts live under ignored `output/deploy/` with a SHA256SUMS file.

Standalone Oura and MyFitnessPal are now separately hosted on this same server, verified through their personal ChatGPT connections and service restarts in the preceding workstream. Both Mac runtimes are stopped. Those connections are independent of this dashboard and do not automatically ingest data into it. Do not start Mac recovery runtimes or reuse their rotating tokens. Dashboard provider ingestion remains unconnected.

The existing deployment README now contains the concrete initial hosting and rollback proposal. Persist the new ingress network in Coolify's saved Proxy Configuration, preserving all existing fields, then attach that network live without restarting the shared proxy. Disk-only edits are overwritten by Coolify. The backup destination is still undecided; Mike asked about GitHub. Keep actual database/photos/secrets outside Git. Initial hosting can use synthetic records only until encrypted backup/key custody is decided. Next action: Mike reviews and explicitly approves the exact initial hosting changes. Do not deploy from preparation authorization alone.

Mike confirmed that his personal ChatGPT account has Add custom MCP server with OAuth. Actual ChatGPT consent and data access still require reachable HTTPS and remain untested. He selected `live.cx83labs.com` for preparation only. No DNS, proxy, service or deployment change is authorized or executed.

The existing `scripts/server_preflight.sh` completed on `vaultstorage-pilot` at 2026-11-06T12:54:54Z with exit 0. The private raw report is `/tmp/health-preflight-20261106.txt`. Available memory was 1.8 GiB, available disk 61 GiB, and 19 containers were running. Intended path/account and port 18170 were unused at inspection. This snapshot is not a workload capacity proof. Exact prepared routing and isolation changes are in `deploy/live.cx83labs.com/README.md`; merged Compose configuration was validated locally with a disposable synthetic `.env`, without a daemon action. Proxy network attachment persistence remains a predeployment detail to resolve.

Mike specifically requested evaluating `proscar87/oura-mcp` and `robcerda/oura-mcp-server` before adding Oura code. That evaluation is complete in `docs/OURA_REUSE_REVIEW.md`. Proscar passed 362 Python, 143 TypeScript and 13 Worker unit tests; Robcerda passed 79 Python tests. Proscar's resolved Python third party dependencies audited clean, but its JavaScript locks have findings. Robcerda's lock has one unique certifi advisory, reported twice by the audit. A synthetic probe reproduced Proscar Python cache reuse across changed credentials. Neither complete client meets this dashboard's requirements unchanged. Reuse verified collection definitions and regression scenarios where useful; retain established OAuth/crypto libraries and the current MCP endpoint. No upstream package was installed in the dashboard and no new Oura integration code was written before this review.

The Oura portal draft remains unsubmitted and untouched, with only Daily selected according to the last observed state. Mike wants every available category selected and every separate Require box unchecked. Computer Use reported its session stopped, so no further browser edit was attempted. Current official OpenAPI 1.43 lists 19 collections and nine scopes, including `heart_health`; the prose authentication page lists eight. Do not infer an unsupported `stress` scope from a third party project. No live Oura authorization, token or ingestion has been tested.

The local Oura integration is now implemented in `tracking/oura/`, with oauthlib S256 PKCE, browser bound one time state, separate encrypted token files, persistent refresh and sync leases, bounded retries, resumable page cursors, raw source pages and immutable revisions. The small Proscar collection registry is reused with its MIT license. `simplejson==4.2.0` was hash locked and installed to preserve decimal values; all prior dependency pins stayed unchanged. All 42 locked dependencies passed a fresh strict audit with no findings or skips.

The full local suite now passes **237 tests without skips**, including loopback HTTP. `verify_oura.py` additionally proved two separate processes share a refresh lease and only one token exchange occurs, plus disk restart, exact numeric values and disconnect history retention. The real local OAuth/MCP process proof now reads Oura originals after restart, preserves synthetic exclusion and rejects reads after owner revocation. The encrypted restic restore proof now includes Oura source records, revisions and encrypted tokens with the separately held key. None of these used actual provider credentials.

Public `/privacy/` and `/terms/`, owner `/integrations/oura/`, and `/integrations/oura/callback/` routes exist locally. Exact registration URLs and operator configuration are in `docs/OURA_SETUP.md`. `read_oura` uses the existing scoped MCP endpoint and only reads stored records. Exports include exact source responses and revision provenance without tokens. Oura is disabled by default. No live credentials, personal database or prior preview database were changed; migration 0005 ran only in disposable tests. No automatic sync schedule or webhook subscription exists. IDless heart rate/battery samples use explicitly labelled content keys, preserving changed observations separately. Declining personal scope leaves account identity unverified and grants separate rather than guessing a merge.

Next user action: review the prepared isolated deployment and explicitly authorize hosting when ready. Initial hosting must leave Oura disabled while the public policy pages become reachable. Then create the Oura registration with the documented URLs and optional scopes, install credentials privately, and complete real owner consent and ingestion. Do not ask for secrets in chat. Target container build/capacity checks and persistent proxy network attachment remain deployment gates. Browser access host was unavailable in this continuation; the portal draft remains untouched and unsubmitted. Actual ChatGPT, provider consent/ingestion, new UI rendering and physical iPhone verification remain pending. Local coding/testing authorization remains in force; deployment does not.


## Implemented local application

* Owner login, CSRF and lockout; persistent measurements, corrections, provenance, stable requests and deletion tombstones.
* Reviewed measurement CSV upload, preview, atomic confirmation and reimport protection: 64 KiB, 200 rows, 15 minute owner/session preview.
* Private JPEG/PNG/WebP photos, capture dates, front/side/back views, comparison, private originals, normalized metadata free display copies and intentional deletion. Maximum 12 MiB, 25 million pixels, 10000 pixels per edge. HEIC is explicitly unsupported.
* Nutrition, recovery, activity and clinical summaries with explicit source, date, timezone, completeness, device and HRV method. Unknown values remain null; reported zero remains zero. Daily values and complete record weekly averages are shown without combining sources. Net carbohydrate calculations preserve and flag inconsistent inputs.
* Reviewed summary CSV import: 256 KiB, 200 rows, fixed JSON value schema, preview, confirmation, immutable originals and safe reimports. This is the dashboard format, not a native provider export adapter.
* Editable nutrition targets with no invented defaults. Saved reviews and separate annotations do not modify imported originals.
* Overview, dated history, source freshness and explicit disconnected status. Chart.js observation charts keep source, unit, side/location, device, HRV method, completeness and synthetic status distinct. Missing dates are not interpolated or zero filled.
* Owner protected ZIP export with exact JSON, spreadsheet safe CSV, source/correction/tombstone history, saved reviews, targets and original/display photos. Download limit 512 MiB. Private ASGI downloads use bounded asynchronous reads.
* Consistent SQLite/photo snapshots encrypted by restic, plus an executable isolated restore proof. No actual backup destination, retention schedule or recurring job has been enabled.
* MCP `read_measurements`, `read_tracking`, `read_overview` and explicit `read_photo`. Optional write mode exposes only `write_measurement` and explicitly requested `save_review`. Read and write scopes remain separate. MCP stays disabled unless an authentication mode is explicitly configured.
* Optional personal OAuth issuer inside the same application using Django OAuth Toolkit 3.4.1. Owner consent, S256 PKCE, exact resource audience, hashed opaque tokens, refresh rotation/replay protection, expiry and owner revocation are tested. ChatGPT CIMD registration is restricted to `chatgpt.com`; open dynamic registration is disabled. Existing external JWT mode remains the default. See `MCP_SETUP.md` for configuration and proof boundaries.
* Incoming Django request body limits before disk spooling, including actual chunk counting and stalled upload deadlines. Normal requests allow 64 KiB; file routes add 16 KiB multipart allowance to their existing file bounds. Defaults are 15 seconds idle and 120 seconds total upload time. Real ASGI and HTTP tests pass; completed uploads do not impose a response timeout. See `OPERATIONS.md` for hosted proxy requirements.

## Dependencies and checks

Use the existing `.venv`. Pillow 13.0.0 and Django OAuth Toolkit 3.4.1 plus required dependencies were added to the hash lock without upgrading the original 33 pins. All 42 Python dependencies passed strict `pip-audit` with no reported vulnerabilities or skipped packages. Chart.js 4.6.1 is vendored locally with its MIT license and verified npm integrity; its npm dependency audit reported zero vulnerabilities. No browser CDN is used. restic 0.19.1 was downloaded to a temporary path for the synthetic proof and checked against its published SHA256; it was not installed globally.

Run:

```sh
.venv/bin/python scripts/verify_local.py --loopback
.venv/bin/python scripts/verify_oauth.py
.venv/bin/python scripts/verify_backup.py --restic /absolute/path/to/restic
```

The final full application suite passed all 237 tests with no skips; details are recorded in `VERIFICATION.md`. The backup proof checks decryption, all referenced file hashes, SQLite integrity and foreign keys, table counts, owner login, restored application reads, corrections, deletion tombstones, summaries, photos, targets and reviews. Wrong passwords and tampered restore files are rejected. It never restores into live storage.

Rendered Chrome verification uses an isolated synthetic database at desktop 1440 × 1000 and phone 390 × 844 widths. Login, measurement imports, photo upload/comparison, charts, partial nutrition entry, targets and ZIP export have been exercised. This is not physical iPhone or Safari verification. See `VERIFICATION.md` for precise scope and remaining checks.

Both Django and the composed MCP wrapper use `Referrer-Policy: same-origin`. The former `no-referrer` policy caused Chrome form POSTs to send `Origin: null`; null and foreign origins remain rejected. CSP permits scripts only from this application for the locally hosted chart library, with no inline script permission.

## Remaining release gates and next action

Mike has viewed the local preview and accepted the interface for now. His priority is connecting this dashboard to ChatGPT MCP and available provider APIs. The earlier no deployment instruction has not yet been explicitly lifted. Current OpenAI setup and personal account read/write caveats are recorded in `MCP_SETUP.md`; Mike has confirmed the custom MCP OAuth option; verify actual consent and write capabilities during hosted acceptance. The latest MyFitnessPal connection status attempt failed at the tool transport, so current provider availability is unverified; see `INTEGRATIONS.md`. Do not treat the preview or synthetic OAuth proof as a live connection.

The independent local first release features, including the built in personal issuer, are implemented. **Do not call the whole release finished or connected.** Actual ChatGPT consent/read/write still needs an authorized reachable HTTPS endpoint and account setup. It no longer requires a separate identity service: built in mode uses the configured Django owner, pinned resource and Toolkit opaque tokens. The separate `verify_oauth.py` proof passes real consent, token exchange, scoped MCP writes, retry, restart, refresh and revocation over loopback. Chrome also exercised consent with a locally intercepted synthetic callback. Neither proof is an actual ChatGPT connection; current no deployment authorization prevents establishing a hosted endpoint here.

The Oura adapter is implemented but has no real authorization or ingestion. No MyFitnessPal, Oura, Apple Health or clinical provider is connected to the dashboard. Existing ChatGPT connections were preserved. Reviewed entries and the documented dashboard CSV formats are the working first release fallback. Native provider adapters need supported application access or an authorized representative export with verified fields, units and coverage. Do not infer app access from a ChatGPT connector.

Next: once Mike authorizes a hosted release, configure the existing deployment package for the approved HTTPS origin and complete actual ChatGPT owner consent/read/write using `MCP_SETUP.md`. Source access remains a separate gate. Recheck physical iPhone Safari upload, login, expiry and Home Screen installation. Select the actual encrypted backup destination and key custody before scheduling backups or retention. Deployment capacity, target platform installation, operational body limits and production migrations remain separate authorized release checks. Do not migrate the existing personal database during local verification.

The Docker CLI is present, but the default local Docker socket is absent. The separate coursework context `colima-wd2200` was left untouched. Container runtime and capacity verification need a suitable isolated local runtime or the later authorized target. No Docker settings, daemon, container, connection or deployment was changed. `.dockerignore` now also excludes browser output and Playwright artifacts.

Historical checkpoints: parser only at `edb871f`; baseline 76 passes with 11 optional socket skips; reviewed measurement import 126 passing tests. Preserve these as history, not the current feature inventory.
