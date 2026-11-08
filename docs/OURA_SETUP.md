# Oura setup and local proof

Implemented locally November 6, 2026. **Not deployed, authorized against Mike's account or tested with real ingestion.** The portal application draft remains unsubmitted. Existing provider connections and the DigitalOcean server are unchanged.

## Exact registration addresses

Mike selected `live.cx83labs.com`. These local routes now exist and have synthetic HTTP tests. Public DNS/TLS and deployment are still pending, so the addresses are not yet reachable registration prerequisites.

| Oura form field | Exact URL |
| --- | --- |
| Website | `https://live.cx83labs.com/` |
| Privacy policy | `https://live.cx83labs.com/privacy/` |
| Terms | `https://live.cx83labs.com/terms/` |
| Redirect URI | `https://live.cx83labs.com/integrations/oura/callback/` |

Keep the trailing callback slash. Select all available categories and leave every separate Require checkbox unchecked. The current official [OpenAPI 1.43](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json) advertises `email`, `personal`, `daily`, `heartrate`, `workout`, `tag`, `session`, `spo2`, `heart_health`. The prose [authentication page](https://cloud.ouraring.com/docs/authentication) lists only eight but documents S256 PKCE and single use refresh tokens. The [reuse review](OURA_REUSE_REVIEW.md) lists the 19 verified collection endpoints. Do not add the third party `stress` scope without official support. All scopes are requested, but denied scopes remain optional and may yield unavailable categories.

## Local implementation

`tracking/oura/` reuses the small MIT Proscar collection registry at the reviewed revision, with the original license retained. It does not install or run either reviewed MCP server. The existing oauthlib 4.0.1, cryptography 50.0.2 and httpx2 2.16.0 handle protocol, encryption and HTTP. New hash locked simplejson 4.2.0 preserves decimal numeric values. Existing dependency versions are unchanged.

The owner starts Oura authorization with a CSRF protected POST. oauthlib prepares the code flow and S256 challenge. A ten minute state record binds the active owner to a random HttpOnly, Secure, SameSite Lax cookie restricted to the callback path. The main login cookie remains SameSite Strict. A committed one time state claim precedes token exchange. Duplicate callback parameters, wrong cookies, expiry, cancellation and replay cannot exchange a code. Callback scope parameters are ignored; token response scope is stored if supplied, otherwise unknown.

Access/refresh tokens and pending PKCE secrets use Fernet encryption. Only ciphertext is stored in SQLite. The encryption key and application secret are private regular files outside the database/photo root. No plaintext fallback exists. Export serializers omit credentials. A persistent refresh lease serializes processes before spending a rotating refresh token. A crashed or ambiguous refresh requires reauthorization rather than replay. New tokens are persisted before use; disconnect or a new grant generation prevents an old worker from restoring credentials.

The optional personal profile lookup binds a grant to a provider account ID. A later authorization with the same verified ID reuses that account's history. If personal access is declined, an explicitly unidentified grant gets separate storage; it is never guessed to be an earlier account. Different accounts and wearable systems remain separate. Reauthorizing an unidentified account may leave separate copies of overlapping history; the UI discloses this limitation. Provider identity verification is necessary before merging those histories.

## Ingestion and history

The Oura page at `/integrations/oura/` shows authorization, last successful fetched page and per collection sync receipts. It can fetch or resume one page per explicit POST. The `sync_oura` management command supports all 19 categories. No background schedule or webhook subscription is installed.

Each page and its cursor commit together. A persistent connection lease prevents overlapping sync workers; a new grant generation or disconnect prevents an in flight old worker from writing data. Pagination detects cycles and has explicit per invocation and total run bounds. Partial/failed results never become complete receipts. GET retries cover transient network errors, 429 and selected 5xx responses, with bounded backoff. Longer Retry-After delays are stored as retry times instead of shortened; extreme delays require review. Token POSTs are never automatically retried. A rejected access token can trigger one serialized renewal and GET retry; scope related 401 errors are classified separately. Provider redirects are not followed, ambient HTTP proxy settings are not used, successful responses are bounded, and error bodies are not reflected in messages.

Request up to 31 dates per window. Daily endpoints include a disclosed two day margin on each side because of API date boundary differences; every returned record is retained. Heart rate and battery windows use UTC midnight boundaries. Original offset timestamps, date only fields, nulls and absent fields remain unchanged. Singleton profile values are not turned into dated measurements. No daily totals are invented or combined with manual or other wearable data.

Exact UTF-8 source response pages are stored once per account/collection/content hash. Each provider ID identifies a source record; changes append an immutable revision with a page/index reference. Identical reimports create no extra records or revisions. Heart rate and battery schemas lack a provider ID, so their local keys use a labelled full content hash. Identical samples deduplicate; changed values remain distinct observations because the API provides no trustworthy correction identity. The original source ID remains null rather than an invented provider ID.

Stored source records are available in the owner interface, the scoped `read_oura` MCP tool and the private export. `raw_json` is intentionally a JSON string so MCP encoders cannot round source numbers. Follow `next_offset`; source text is untrusted data, never instructions. Whole response pages and record revisions are exported under `oura/`. Export remains unencrypted and sensitive. No Oura data is sent to a client merely by authorizing Oura; the client must separately have dashboard OAuth read access and request it.

Disconnection clears local tokens and pending authorizations while preserving imported history. Revoke the grant separately in the Oura account. The first implementation does not automatically process provider deletion webhooks or delete absent records, and does not provide an Oura history deletion UI. Privacy and terms pages describe these actual limits.

## Configuration after hosting and registration

Keep `OURA_ENABLED=0` until the registered credentials and private key files exist. The first hosted stage can serve the public policy pages without an Oura client secret. After registration, use the optional `deploy/live.cx83labs.com/compose.oura.yaml` overlay in addition to the base and hostname override. It mounts two dedicated secret files, enables only Oura and fixes the callback URL. The existing `.env` holds the nonsecret `OURA_CLIENT_ID`; do not paste the secret or encryption key into chat, Git or ordinary logs.

The proposed files on the established host are `/opt/personal-health-dashboard/secrets/oura-client-secret` and `/opt/personal-health-dashboard/secrets/oura-token-key`. Create with restrictive permissions and ownership readable only by application UID 10001 and the authorized administrator. Local file backed Compose secrets retain host file ownership; do not assume Compose's uid/mode settings fix it. Keep the containing directory restricted, confirm the runtime can read them, and separately protect an off device copy of the token encryption key. Generate a fresh key with `cryptography.fernet.Fernet.generate_key()`; never regenerate over an existing key. Losing the key prevents credential decryption and requires reauthorization, while stored health history remains intact.

Run migration `0005_oura_integration` only in an explicitly authorized instance after backup. This session applied it only to disposable synthetic databases, not the existing personal database or prior preview database. Backup tooling remains compatible with established pre Oura v1 snapshots and now includes Oura tables; source records, revisions and encrypted tokens were exercised in the isolated restoration proof. Encryption key custody is separate from that database backup.

Operator ingestion syntax, after real authorization:

```sh
.venv/bin/python manage.py sync_oura \
  --connection ACTUAL_ACCOUNT_UUID --start YYYY-MM-DD --end YYYY-MM-DD --pages 5
```

Use the actual account UUID from connection status. Omit `--collection` for all 19 collections or supply one catalog name. A partial receipt includes its run UUID; resume it with `--resume RUN_UUID` and the same connection argument. Break longer history into windows and revisit previous windows for delayed updates. Never interpret a partial receipt or missing permission as no observations.

## Executable evidence

```sh
.venv/bin/python scripts/verify_local.py --loopback
.venv/bin/python scripts/verify_oura.py
.venv/bin/python scripts/verify_oauth.py
.venv/bin/python scripts/verify_backup.py --restic /absolute/path/to/verified/restic
```

See `VERIFICATION.md` for the latest executed results. Tests substitute only synthetic outbound provider responses, use disposable storage and never use personal credentials. Actual Oura consent, real account grants and ingestion, publicly reachable policy/callback pages, browser SameSite behavior, target container/runtime capacity and actual ChatGPT access remain separate acceptance steps. The preflight and prepared deployment files are not permission to deploy.
