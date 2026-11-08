# MCP connection and verification

Status on November 6, 2026: local OAuth issuance, SDK authorization, persistence, refresh and revocation pass with real loopback HTTP and disposable synthetic data. Chrome consent also passes with a locally intercepted synthetic callback. No actual ChatGPT account consent or connection is verified. The existing MyFitnessPal ChatGPT connection does not establish dashboard ingestion. See [current verification](VERIFICATION.md) for exact results and limits.

## Architecture

`dashboard.mcp_server.build_application(django_app)` composes one ASGI application. With all MCP variables absent it returns the Django application with no MCP endpoint. Partial configuration stops startup. With complete configuration, the official MCP 2.3.0 SDK owns `/mcp`, its protected resource discovery route, transport authentication, and lifespan; Django is mounted last at `/`. The transport is stateless Streamable HTTP. Source persistence and idempotency belong to the database, not an MCP session.

The application supports two explicit authentication modes. The default external mode verifies an established issuer's JWTs. Optional built in mode uses Django OAuth Toolkit 3.4.1 for authorization, code/token exchange, discovery, client metadata validation, expiry, rotation and revocation within this same application. Application policy restricts owner, resource and scopes; there is no custom token cryptography or anonymous fallback. Browser login alone never grants MCP access. No existing identity provider, connection or business credential was changed.

## Optional built in personal issuer

Set `MCP_AUTH_MODE=builtin` and `MCP_PUBLIC_ORIGIN` to the approved origin without a path or trailing slash. The issuer is that origin and the protected resource is that origin plus `/mcp`. `OWNER_USERNAME` must name the existing active owner. Do not set the external mode variables at the same time. `MCP_WRITES_ENABLED=0` keeps access read only; `1` additionally permits explicit consent to `health:write`. No personal configuration was changed during implementation.

For a new, separately initialized synthetic local instance only:

```sh
export MCP_AUTH_MODE=builtin
export MCP_PUBLIC_ORIGIN=http://127.0.0.1:8000
export MCP_WRITES_ENABLED=0
# Use the existing secure Django configuration and explicit loopback local mode.
.venv/bin/python -m uvicorn dashboard.asgi:application --host 127.0.0.1 --port 8000 --no-access-log
```

Install the hash lock and apply migrations only to the deliberately selected instance before launching. The OAuth library adds its own tables. Implementation tests migrated only disposable databases; this is not permission to migrate existing personal or production storage. Production origins must use HTTPS with local mode disabled. Local mode rejects public origins and must never be tunneled. `scripts/prepare_env.py --hostname <approved-hostname> --builtin-oauth` can prepare a new private configuration file; it refuses to replace any existing file and leaves writes disabled.

The issuer publishes `/.well-known/oauth-authorization-server`; the SDK publishes protected resource discovery. Authorization uses `/oauth/authorize/`, tokens `/oauth/token/`, and protocol revocation `/oauth/revoke/`. Owner consent is mandatory even for a previously approved client. Only authorization code with S256 PKCE and refresh grants are accepted. Authorization codes expire in 60 seconds, access tokens in 15 minutes, and refresh tokens expire 30 days after their paired access token expiry. Refresh rotation and reuse detection are enabled. Access and refresh tokens are hashed at rest. Exact resource audience and active owner are checked at issuance and every MCP request. Owner revocation from **Dashboard access** removes that client's access tokens, refresh tokens and pending grants immediately.

ChatGPT's documented preferred client metadata URL is `https://chatgpt.com/oauth/client.json`. Toolkit validates CIMD documents and callback matching; the application allows only the `chatgpt.com` host and keeps open dynamic client registration disabled. Existing explicit client registrations are also supported. A client configured to bypass consent is rejected. Do not invent a callback URL or register another account's client. The CIMD test uses a synthetic document and a stubbed fetch; no actual ChatGPT metadata or account consent was verified. The separate real HTTP proof uses a predeclared synthetic public client.

Toolkit 3.4.1 omitted the RFC 9207 `iss` parameter from consent denial in local testing. The wrapper adds the pinned issuer to success/error callback responses only after Toolkit validates the client and redirect. Chrome also required the validated callback origin in the consent page's `form-action` policy; that exception applies only to the consent document, while normal pages remain restricted to this application. [OpenAI authentication requirements](https://developers.openai.com/plugins/build/auth), [Toolkit documentation](https://django-oauth-toolkit.readthedocs.io/en/latest/).

## Existing external JWT mode

| Variable | Required value |
| --- | --- |
| `OWNER_USERNAME` | The sole active Django owner account |
| `MCP_ISSUER_URL` | Exact trusted HTTPS issuer, including the provider's trailing slash convention |
| `MCP_JWKS_URL` | Pinned HTTPS JWKS endpoint controlled by that issuer |
| `MCP_RESOURCE_URL` | Exact HTTPS endpoint ending in `/mcp`; loopback HTTP permitted only for local testing |
| `MCP_SUBJECT` | Exact issuer subject for the owner; no email based inference |
| `MCP_WRITES_ENABLED` | `0` by default; `1` only after the owner explicitly enables scoped writes |

JWT verification uses PyJWT, RS256 only, with signature, issuer, audience, subject, expiry and issued at validation. The access token must contain `client_id` or `azp` and a space separated `scope` string. The token audience must equal `MCP_RESOURCE_URL`. Individual signing keys are not cached indefinitely; the JWKS set has a 60 second cache. The issuer's access token expiry and revocation design must be reviewed during account setup. No arbitrary JWT `jku` or `x5u` URL is used.

`health:read` is mandatory for every MCP request. Writes are absent from the tool listing unless enabled on the server; they additionally require `health:write` and an affirmative authorization intent argument. Tool annotations and intent flags are descriptive controls, not substitutes for token authorization. The client must request confirmation for writes and act only on measurements actually supplied or confirmed by the owner.

The tool surface includes `read_measurements`, `read_tracking`, `read_overview`, explicit `read_photo`, and optionally `write_measurement` and `save_review`. Measurement reads are bounded to 366 inclusive days with at most 100 records per page. Writes accept approved fields, UUID request IDs and optimistic correction versions where applicable. Provenance is server controlled and provider records remain immutable. New domain tools must preserve these restrictions.

## Local verification

Run from the repository root:

```sh
.venv/bin/python scripts/verify_local.py
# Additional Uvicorn socket tests only when the environment permits local ports:
.venv/bin/python scripts/verify_local.py --loopback
.venv/bin/python scripts/verify_oauth.py
```

The full application suite passes 204 tests including internal ASGI and actual loopback HTTP. The external JWT tests use ephemeral signed fixtures and substitute the JWKS retrieval only. The built in issuer tests exercise real Toolkit issuance, S256, exact resource, owner/CSRF, invalid redirects/scopes, hashed tokens, expiry, refresh reuse and revocation. A CIMD fixture checks the allowed host and metadata validation without contacting ChatGPT. These checks do not establish an account connection.

The separate integrated process test uses the real composed Django/SDK application and real measurement services with disk SQLite. Only JWKS fetching is replaced. It verifies synthetic browser password login and CSRF entry, MCP read/correction/retry, browser readback, and persistence of records, versions, session and retry results after an actual process exit and restart. Issuer failure denies MCP while stored browser history remains accessible.

The separate `verify_oauth.py` process proof performs owner login and consent, real token exchange, read only write rejection, approved synthetic write, idempotent retry, process restart, refresh rotation and immediate owner revocation. It uses the actual composed Django/SDK server and a disposable disk database over loopback; no issuer/JWKS substitute is used. Its synthetic callback is captured without contacting an external host. Browser consent was also checked at a phone viewport with a locally intercepted callback. Actual ChatGPT and physical iPhone acceptance remain separate checks.

## Actual ChatGPT verification gate

November 6 account setup research: the current OpenAI help page describes **Plugins → plus → Add custom MCP server**, without first enabling Developer Mode. It accepts a reachable HTTPS endpoint or an available Secure MCP Tunnel. It currently describes personal Pro custom MCP access as read/fetch and full MCP actions for Business/Enterprise/Edu, so inspect this specific personal account's actual permissions before promising writes. Do not move private health data into a business workspace to work around an account limit. A tunnel is a separate transport setup requiring authorization and compatible authentication configuration; it is not permission to expose the current local HTTP preview. The selected durable hosting plan remains the existing DigitalOcean target. [Current OpenAI connection guidance](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).

1. Confirm this account can add a custom authenticated MCP server in the intended ChatGPT client. Existing connected apps do not prove custom server creation rights. Current documentation describes Streamable HTTP and OAuth support, but account eligibility and the exact management UI still require inspection.
2. Establish the isolated authenticated endpoint through a supported authorized deployment. Local development continues independently; do not expose the loopback HTTP development mode through a public tunnel. No server, domain or proxy change is authorized by this document.
3. Select the implemented personal issuer or an independently configured external issuer. Use the actual ChatGPT CIMD document or exact client/callback metadata supplied by the client. Do not invent redirect URLs or reuse business app credentials. Complete owner consent interactively.
4. Read one explicitly synthetic dated measurement through the real ChatGPT tool.
5. Obtain explicit authorization to enable the scoped write and correct that synthetic record with its current version and stable request UUID. Read it back through ChatGPT and the authenticated page.
6. Retry the same request and verify no duplicate, restart the process, then read it again. Record date, build revision and result without tokens or personal data.

Present blockers: no authorized reachable dashboard HTTPS endpoint or actual dashboard consent in ChatGPT; custom MCP setup eligibility in this exact account/client remains unverified. A separate identity service is no longer required. All 41 locked dependencies passed the November 6 strict advisory audit. Existing ChatGPT connections remain unchanged, and no public tunnel or hosted endpoint was created. Local fixture tests do not establish provider or ChatGPT access.

## Security and source references

SDK responses set `Cache-Control: no-store, private`. Host and Origin are restricted to the configured resource origin; no wildcard CORS is added. Requests are capped at 64 KiB. SDK logging propagation is disabled because validation errors may include inputs. Retain only coarse operational event counts outside this module, never raw request bodies or tokens. TLS termination, HTTPS redirection and response hardening for the public endpoint remain deployment verification requirements.

Official sources inspected on November 5, 2026:

* [MCP Python SDK 2.3.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)
* [SDK authorization example](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs_src/authorization/tutorial001.py)
* [SDK auth configuration](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/src/mcp/server/auth/settings.py)
* [SDK HTTP application API](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/src/mcp/server/mcpserver/server.py)
* [SDK protected resource discovery](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/src/mcp/server/auth/routes.py)
* [ChatGPT plugin authentication](https://developers.openai.com/plugins/build/auth)
* [ChatGPT MCP client documentation](https://learn.chatgpt.com/docs/extend/mcp)


## Stored Oura reads

`read_oura(collection, connection_id?, include_synthetic=false, limit=20, offset=0)` uses the existing health:read scope. It does not call Oura, initiate consent, change tokens or trigger sync. Its raw_json field intentionally carries original JSON as text to preserve exact source numbers across MCP encoding. Follow next_offset and keep account and source provenance. A connection status with an old successful page does not prove all categories are complete or current. Real ChatGPT access remains untested until authorized HTTPS hosting and owner consent.
