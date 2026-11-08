# Established components and private iPhone delivery

Decision recorded November 5, 2026; implementation status updated November 6, 2026, America/Chicago. Quality means maintained dependencies, reproducible builds, verified access controls, reliable data and demonstrated recovery. It does not require enterprise platform complexity for one person.

## Oura client review

The requested evaluation of Proscar and Robcerda is complete in [OURA_REUSE_REVIEW.md](OURA_REUSE_REVIEW.md), including pinned source, both MIT licenses, executed tests and fresh audits. Neither client meets the ingestion requirements unchanged. Reuse verified small definitions and test scenarios, preserve the existing OAuth protected MCP endpoint, and use established OAuth/crypto libraries for the remaining integration. No upstream server was installed into the application. The subsequent implementation reuses only the attributed Proscar collection registry; oauthlib, cryptography and httpx2 come from the existing lock, with simplejson 4.2.0 added for decimal preservation. See `OURA_SETUP.md`.

## Reuse decisions and actual status

| Concern | Established component | Status and application-specific work |
|---|---|---|
| Database models, forms, login, sessions and CSRF | Django 5.2.19 LTS | Installed and exercised by local ORM, browser-view, disk concurrency and process restart tests. Domain schema, ownership and correction rules are custom. |
| Login attempt limiting | django-axes 8.3.1 | Installed. Real login tests verify lockout despite changing user agents, cookies and IPs, plus cooldown and reset. No homemade authentication or throttling. |
| Static assets | WhiteNoise 6.12.0 | Installed; asset collection passes. Serves application assets only; private photos must use authenticated views. CSS rendered successfully in Chrome at desktop and phone widths; physical iPhone checks remain pending. |
| MCP protocol, discovery and authentication middleware | Official Python MCP SDK 2.3.0 | Installed. Eleven internal ASGI authorization tests, eleven actual loopback HTTP tests and the integrated persistent flow pass; actual ChatGPT verification remains pending. |
| Reviewed measurement CSV import | Python CSV library plus Django forms, sessions and transactions | Implemented and tested with bounded uploads, private expiring previews, explicit confirmation, duplicate prevention and atomic conflict rejection. This accepts the application's measurement format, not provider exports or live adapters. |
| Token verification and structured tool validation | PyJWT 2.15.1 and Pydantic 2.14.3 | Installed and tested with synthetic signed tokens. Owner, audience and scope policy remains application-specific. No custom JWT cryptography. |
| Responsive interface | Tabler UI, MIT [1] | **Deferred.** Existing Django templates and restrained CSS already meet local layout needs; replacing working markup with another UI framework is not required for this release. |
| Trend charts | Chart.js, MIT [2] | **Implemented.** Chart.js 4.6.1 is vendored locally with integrity and license records; exact bundled @kurkle/color 0.3.2 is covered by the audit. Observation charts preserve missing dates, units and source/method distinctions. |
| Photo decoding and metadata handling | Pillow [3] | **Implemented.** Pillow 13.0.0 is hash locked and tested for format/size/dimension bounds, orientation and metadata removal. Capture and upload dates remain separate. |
| Encrypted backups | restic, BSD 2-Clause [4] | **Implemented and verified with synthetic data.** restic 0.19.1 encrypts consistent SQLite/photo snapshots; isolated restoration is exercised by a reproducible proof. No live backup destination or schedule is configured. |
| Optional OAuth issuer within this application | Django OAuth Toolkit 3.4.1 [5] | **Implemented and locally verified.** Owner consent, S256 PKCE, exact resource, hashed opaque tokens, refresh rotation and revocation use Toolkit. CIMD registration is restricted to the ChatGPT host. Actual ChatGPT consent remains unverified. |

Keep custom code limited to personal tracking schema, provenance, date/unit interpretation, correction history, idempotency, narrow source adapters and the views/tools connecting those pieces. Reuse stable upstream primitives for general authentication, encryption, charts and image parsing. Retain license notices. The Python 3.13 hash lock matches installed versions and `pip check` passes. On November 6, `pip-audit` 2.10.1 completed a strict audit of all 41 hash locked dependencies, finding no known vulnerabilities with none skipped; Pillow and Django OAuth Toolkit with its required dependencies were added without upgrading the original pins. Refresh the audit before release and validate installation on the intended platform. Documentation and package installation do not establish connected or deployed status.

restic's official repository lists encrypted, integrity-protected storage, remote backends and restoration; its release page reports 0.19.1. The implemented backup uses a consistent SQLite snapshot plus private photos, keeps keys separate and verifies an isolated restore. The synthetic restoration proof passed; selecting durable storage, key custody and retention remains an operational step. [4]

Django OAuth Toolkit 3.4.1 keeps optional OAuth issuance inside the same application. Discovery, S256 PKCE, exact resource binding, SDK opaque token verification, expiry, refresh rotation and owner revocation have local evidence. The separate real HTTP process proof verifies consent, issuance, scoped MCP, retry and restart. CIMD validation uses a synthetic document and stubbed fetch; actual ChatGPT metadata/account authorization remains unverified. No existing identity provider, connector or business credential was changed. See `MCP_SETUP.md` for the tested compatibility details, configuration and release gate. [5]

## iPhone and web use

The selected delivery is one private web application, hosted on the authorized DigitalOcean target, with a Home Screen web app on iPhone. Both interfaces read and write the same server application and SQLite database. There is no separate mobile database or synchronization product.

After authenticated HTTPS deployment is verified, open the site in iPhone Safari, use Share, choose **Add to Home Screen**, enable **Open as Web App** when offered, and add it. Apple documents this supported installation path. It provides a launch icon and an app-style window without App Store distribution or a native application build. [6]

A web app manifest and installation metadata are authored; a local SVG favicon is included, while actual Safari installation and standalone rendering are **unverified**. Owner login/logout, access controls and reviewed CSV import behavior pass local tests. This November 6 session permits loopback listeners; the full suite passes 204 tests including actual HTTP transport. Chrome login, CSV import, history and reimport passed at desktop and phone widths; exact scope is recorded in VERIFICATION.md. Responsive rendering, session expiry and upload behavior still require physical iPhone checks, separately from desktop browser verification.

The first release requires an online connection; it is not deployed yet. Do not cache sensitive records, API responses or photos in a service worker, browser database or other offline store. Private responses must remain authenticated and use appropriate no-store headers. Future offline support would require a separate explicit design and deletion/security review.

A Home Screen web app does not grant direct HealthKit access. Apple Health ingestion still needs a supported authorized export or existing bridge; a web manifest cannot supply native HealthKit entitlements. [7] Scheduled collection belongs on the server. Do not depend on iPhone background execution or introduce scheduled mobile tasks.

## Release checks before claiming the installed experience works

1. Preserve the passing local persistent browser/MCP flow and complete actual ChatGPT verification separately.
2. Refresh the passing dependency advisory audit before release and complete target-platform installation; retain passing negative authorization and session tests.
3. Verify private HTTPS deployment on the intended DigitalOcean application without disturbing existing services.
4. Install from Safari and test standalone layout, navigation, login/logout, data correction and session expiry on iPhone; repeat the core workflow on desktop.
5. Confirm sensitive responses and photos are not cached offline, and confirm stored history survives app/server restart.
6. Preserve the passing private export and isolated encrypted backup restore checks; repeat them on the authorized deployment platform.

Private photos, charts and encrypted restoration are implemented and locally verified. No live dashboard deployment or actual iPhone installation is claimed. See `VERIFICATION.md` for executed checks and current environment blockers.

## Official sources

Sources accessed November 5, 2026, America/Chicago.

1. Tabler introduction, component reuse and MIT license: https://docs.tabler.io/ui/getting-started
2. Chart.js official documentation and MIT license: https://www.chartjs.org/docs/latest/ and https://github.com/chartjs/Chart.js/blob/master/LICENSE.md
3. Pillow image formats and metadata options: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
4. restic capabilities/license, current releases and restoration: https://github.com/restic/restic , https://github.com/restic/restic/releases and https://restic.readthedocs.io/en/stable/050_restore.html
5. Django OAuth Toolkit 3.4.1 documentation: https://django-oauth-toolkit.readthedocs.io/en/latest/
6. Apple Home Screen web app installation: https://support.apple.com/guide/iphone/turn-a-website-into-an-app-iphea86e5236/ios
7. Apple HealthKit framework documentation: https://developer.apple.com/documentation/healthkit
