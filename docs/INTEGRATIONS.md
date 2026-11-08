## November 6 Oura continuation

Mike confirmed personal ChatGPT custom MCP OAuth availability and selected `live.cx83labs.com` for preparation only. The Oura application draft is unsubmitted. Select all available data categories with all separate Require boxes unchecked. Current official OpenAPI 1.43 advertises nine scopes: `email personal daily heartrate workout tag session spo2 heart_health`; the prose authentication page lists the first eight. See [reuse review](OURA_REUSE_REVIEW.md) for inspected upstream implementations, licenses, tests, dependency audits and remaining custom requirements. Do not copy the third party `stress` scope without official support.

The later local continuation implemented and synthetically tested Oura ingestion, callback and privacy/terms pages. Real authorization and ingestion remain pending. See [Oura setup](OURA_SETUP.md) and the current verification checkpoint. The stopped Computer Use session prevented editing the portal draft; no submission or credential creation is claimed. The existing DigitalOcean preflight succeeded read only, and exact unexecuted hosting preparation is in `../deploy/live.cx83labs.com/`. Existing connectors remain intact. This current direction supersedes earlier minimum scope recommendations below.

# Integration decisions

Research and inspection date: November 5, 2026, America/Chicago.

This document records access evidence and decisions. A connector exposed inside ChatGPT does not give this application's server credentials or ingestion access. No provider adapter is considered working until an authorized sample has passed validation and a successful account request is recorded.

## Selection matrix

| Source | Selected approach | Evidence | Gap and current state |
| --- | --- | --- | --- |
| MyFitnessPal | Preserve the existing ChatGPT connector. Reuse its supported implementation only if an isolated application access path is established. Otherwise use reviewed official CSV exports. | The parent build session successfully read the authorized live diary for November 5, 2026 through ChatGPT. Connector metadata exposes nutrition, weight, notes, stable request IDs and bounded diary ranges. Official export covers meal nutrition, progress and exercise. | ChatGPT account read: **verified with an authorized account**. All returned fiber values were unknown in the inspected sample. Credential presence was true and the connector's `remote_auth` field false; neither establishes app access. Targeted accessible paths and repository searches did not locate the underlying implementation. Application ingestion: **blocked or unavailable**. |
| Oura | Direct API v2 using an established OAuth client, with authorization code and PKCE. Support a reviewed Membership Hub export when API access is unavailable. | Official OAuth, scope, membership, export and error documentation. | **Documented but untested**. Ring generation, membership, application registration, consent, actual response schema and history remain unverified. |
| Apple Health / Watch | Import the native Health XML export for release one. Consider an existing bridge only if scheduled collection is a demonstrated requirement. | Apple documents Export All Health Data. HealthKit access requires device capability and per data type authorization. | **Documented but untested**. No server access or export sample verified. No new native iPhone app. |
| Clinical | Reviewed manual entries or structured imports with original values, units, provider and reference ranges. | This is an accepted first release path in the build specification. ChatGPT Health documentation describes connected access within ChatGPT. | **Documented but untested**. No external provider API or app credential verified. Provider originals remain read only. |
| Photos and body measurements | First class manual entry and private upload; no external account required. | Build specification. | Local implementation and acceptance status belong in the verification report, not a provider connectivity claim. |

## MyFitnessPal

The existing connector offers separate nutrition, weight and exercise capabilities. Its exposed weight tool uses the account's display unit; a future adapter must obtain that unit explicitly. No general body measurement write tool was identified. Do not infer fiber availability from a tool description or convert missing fiber to zero. Do not replace the functioning food logging workflow.

The official Premium/Premium+ export is a ZIP containing nutrition, progress and exercise CSVs. Nutrition is summarized by meal, and progress may include weight, neck, waist and hip. Inspect actual headers, units, fiber coverage and diary completeness before implementing a format-specific parser. A public developer portal exists, but reusable API entitlement was not established; do not label the existing connector an official API without inspecting its implementation.

## Oura

Request `daily` for sleep, activity and readiness. Add `workout` only if used. Do not request email, personal information, tags, sessions, SpO2 or dense heart rate data without a requirement. Confirm summary field coverage before deciding whether `heartrate` is necessary.

Use OAuth authorization code with PKCE S256 and an established client library. Send the required nonempty `User-Agent`. Refresh tokens are single use: serialize refresh, atomically replace tokens, and keep secrets out of logs. The documentation marks personal access tokens deprecated.

Gen3 and later require active membership for API access. All users can request their files through Membership Hub, although preparation may take up to ten days. Export durations are seconds. Oura on the Web was discontinued October 5, 2026; use Membership Hub instructions. The documented error page states 5,000 requests per five minutes, but implement conservative requests and bounded handling of HTTP 429 and `Retry-After` rather than relying on a limit as capacity.

The current API/MCP agreement, effective June 8, 2026, distinguishes their storage conditions. Section 3(m) prohibits caching Oura MCP data without separate permission and limits API retention to what is necessary. Do not use the Oura MCP server as an archival bridge. Before enabling direct API ingestion, document the personal history purpose, retention and deletion behavior against the applicable terms. A user-provided export is a practical alternative, not proof that any API retention condition has been satisfied.

## Apple Health and clinical records

Apple's native export path is Health, Summary, profile, Export All Health Data. A future import must use a streaming XML parser with external entities disabled, bounded input sizes and no unrestricted archive extraction. Retain source/device identity and original timestamps. Watch, phone and Oura copies can overlap; never sum them by default.

ChatGPT Health permissions do not transfer to this application. Provider API ingestion requires its own verified authorization. Reviewed clinical imports must preserve source values separately from annotations. Do not call provider APIs to modify original records.

## Synchronization and evidence

Once authorized ingestion works, use daily summaries and explicit refresh. Begin with a bounded 30 day backfill and extend only after sample verification. Provider failure must preserve stored history. Report latest available measurement date, last successful sync, connection state and a safe actionable error separately.

Every source uses one of: **Not investigated**, **Documented but untested**, **Implemented with synthetic tests**, **Verified with an authorized account**, **Blocked or unavailable**. Synthetic tests cannot promote an integration to an authorized account state. No adapter is implemented merely because documentation exists.

## Official sources

1. [MyFitnessPal export](https://support.myfitnesspal.com/hc/en-us/articles/360032273352-Export-your-nutrition-progress-and-exercise-data)
2. [MyFitnessPal developer portal](https://www.myfitnesspal.com/apps/api/version): direct retrieval was blocked; no entitlement assumed.
3. [Oura API membership requirements](https://support.ouraring.com/hc/en-us/articles/4415266939155-The-Oura-API)
4. [Oura authentication](https://cloud.ouraring.com/docs/authentication)
5. [Oura error handling](https://cloud.ouraring.com/docs/error-handling)
6. [Oura export](https://support.ouraring.com/hc/en-us/articles/360025441594-Export-Share-Your-Oura-Data)
7. [Oura membership](https://support.ouraring.com/hc/en-us/articles/4409086524819-Oura-Membership)
8. [Oura API and MCP agreement](https://cloud.ouraring.com/legal/api-agreement)
9. [Apple Health export](https://support.apple.com/guide/iphone/share-your-health-data-iph5ede58c3d/ios)
10. [HealthKit authorization](https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data)
11. [Health in ChatGPT](https://help.openai.com/en/articles/20001036-health-in-chatgpt)


## November 6 local implementation update

A later November 6 call to the existing MyFitnessPal `fitness_connection_status` tool failed at the ChatGPT MCP transport before returning connection status. No diary data was retrieved and no settings were changed. This does not establish expired provider credentials or revoke the earlier successful read; current availability remains unverified. Oura's official authentication documentation was rechecked and still describes application registration, authorization code/PKCE and the `daily` scope for sleep, activity and readiness. No Oura account access or client registration was performed.

The dashboard now has validated manual source summaries and an explicitly documented reviewed CSV format for nutrition, recovery, activity and clinical records. Their state is **Implemented with synthetic tests**. They preserve stable IDs, units, source/device identity, completeness, synthetic status and deletion tombstones. They do not convert a MyFitnessPal, Oura or Apple Health native export automatically and do not establish any provider connection. The previous source access matrix still applies to live ingestion.

The UI reports latest stored observation dates and elapsed days separately from live synchronization, which remains disconnected with no successful sync timestamp. Stored history is available without contacting providers. There is no sync scheduler or refresh button that pretends to call an unconnected source. A real adapter and its refresh/retry behavior require authorized application access or a verified export sample first.

Personal MCP reads cover all local modules, source coverage, targets, review history and explicitly requested private normalized photos. Narrow writes cover measurements and explicitly saved reviews/annotations. The optional personal issuer now uses Django OAuth Toolkit in this same application, with a passing real loopback consent/token/MCP/restart/refresh/revocation proof. Existing external JWT mode remains supported. Actual ChatGPT consent and account verification still need an authorized reachable HTTPS endpoint and account setup. Local evidence does not connect any provider; existing ChatGPT connections remain untouched.
