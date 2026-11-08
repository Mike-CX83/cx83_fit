# Data contract

This is the release acceptance contract. It does not claim that every item below is already implemented. The verification report owns implementation evidence and remaining gaps.

## Common record

Store a stable internal ID, metric, value, original unit, event timestamp or applicable local date, source timezone, source system, source record ID when supplied, entry/import time, provenance class, method/device, completeness and quality flags, and revision history. Preserve original values alongside any documented conversion. A source timestamp must not be replaced with import time.

Use `America/Chicago` for local manual dates and display. Store offset-aware event timestamps and the original source date/time representation. A date-only record stays date-only; do not invent noon or midnight as a measurement time. Handle overnight sleep by retaining start, end and the provider's assigned day. Show the assigned day consistently and document any local waking-date derivation. Daylight saving days can contain 23 or 25 hours. Reject ambiguous manual clock times unless an offset is provided.

## Field ownership and permitted direction

| Record | Authoritative source and precedence | Permitted direction |
| --- | --- | --- |
| Manual weight or circumference | User entry with consistent location and optional left/right side. An intentional local correction supersedes that entry's earlier revision. | UI or explicitly authorized MCP writes into tracking storage. No automatic provider writeback. |
| Imported body measurement | Provider record remains separately attributed. A user correction is a local overlay, preserving the imported original. | Provider/import to tracking only. |
| Nutrition | MyFitnessPal or a reviewed source export; retain meal/day completeness. Do not merge another copy of the same diary. | Read/import into tracking. Existing ChatGPT food logging remains its separate workflow. |
| Sleep and recovery | Oura when verified; retain method and device. A Health copy of the same Oura observation is not a second observation. | Read/import into tracking. |
| Steps and workout totals | Explicitly selected Watch source when available; otherwise show the chosen source. Preserve alternative sources separately. | Read/import into tracking. Never sum Watch, phone and ring totals. |
| Clinical result | Original laboratory/provider and specimen or observation date. User notes are separate. | Read/import only for the original; annotations may be locally corrected. |
| Photo | User-specified capture date and view, separate upload timestamp. | Private upload and intentional delete. No public permanent link. |

Missing source priorities must produce separate labeled series or a visible unresolved selection, not an invented combined total. Do not silently overwrite a user's correction during synchronization.

## Missing, partial, stale and zero

* `null` means unknown or unavailable. Numeric zero is valid only when reported or explicitly entered.
* A missing diary is not fasting. A partial diary is not total daily intake. Summaries carry completeness and observed day counts.
* Missing wearable coverage is not inactivity. Show available observation counts or coverage; do not infer full wear time from one sample.
* Staleness is relative to each source's documented expected update interval, not a universal threshold. Latest measurement and last successful sync are different fields.
* Calculate net carbohydrates only when total carbohydrates and fiber are both present and comparable. Preserve both source values. If either is missing or fiber exceeds total carbs, net carbs is unavailable with a quality flag; never silently clamp or substitute.
* Keep HRV methods distinct, including RMSSD versus SDNN and sleep summary versus spot reading. Do not average different methods or devices into one baseline. Clinical and device estimates also remain distinct.
* Averages identify unit, method, source, date range, observed count and any partial coverage. Do not include missing days as zero or include synthetic records in real trends.

## Validation, deduplication and corrections

Validate explicit metric/unit pairs, finite values, dates, bounded text and allowed measurement locations before writing. Record left/right side where relevant. Do not accept arbitrary database field names.

Enforce uniqueness on source plus source record ID where reliable. Where a provider supplies no ID, document a deterministic fingerprint from the source record's immutable identifying fields; do not deduplicate solely by value. Different legitimate observations can have equal values.

Every intended write has a stable request ID. Retrying the same ID and identical payload returns the original result without another record. Reusing the ID with different content is a conflict. Apply record changes, revision history and idempotency state in one transaction. Use expected revision checks for corrections so concurrent updates cannot silently erase changes.

Deletion must preserve a minimal source tombstone sufficient to prevent automatic reimport. A subsequent sync must not resurrect the record. A user may explicitly undo deletion or approve a fresh import. Keep deletion and correction actions auditable without retaining unnecessary deleted content.

## Photos, exports and retention

Validate image type from decoded content and enforce upload and pixel limits. Remove unnecessary location metadata from the stored working image while preserving explicitly entered capture date and view. If the release keeps an original upload for the required original-photo export, store it privately with the same authorization and deletion rules; make clear that an original can contain metadata removed from the displayed copy. Do not transmit images elsewhere for analysis.

Export usable measurements and source metadata, corrections, tombstones where needed for continuity, and original photos when retained. Include a format version and export time. Protect the export as health data. Do not include secrets, sessions or authentication tokens.

Retention must be documented separately for live records, deleted data and encrypted backups. A deletion affects the live system immediately; older backups may retain data until expiration. Restore procedures must reapply current deletion tombstones before resumed synchronization. Do not claim a deletion also erased every historical backup. External API retention requirements apply independently.

## MCP boundary

Use an established MCP SDK and authenticated supported transport. Default to read access. Require a distinct authorized write scope for approved body measurements and notes; possessing a read token does not authorize writes. Tool annotations describe intent but never replace server authorization.

Read requests require bounded dates, validated metric choices and pagination. Responses include explicit units, source, observation coverage and freshness. Writes require stable request IDs, explicit units, validation and a readable result that can be independently retrieved. Provider records are read only; only local tracking overlays may be corrected. A review is saved only when explicitly requested.

No arbitrary SQL, shell execution, unrestricted paths or general database administration. Private photo delivery must authenticate each request or use an appropriately short-lived mechanism. Imported notes and source text are untrusted data, never tool instructions. Local MCP client tests do not establish actual ChatGPT connectivity.

## November 6 implemented extensions

`ProgressPhoto` separates capture date from upload timestamp. Owner access gates every display and original download. Original bytes and SHA256 are retained privately; the display JPEG is reoriented and metadata free. Deletion clears notes and removes both files while preserving the minimal request tombstone. Files have mode 600 and directories mode 700. A crash between filesystem and database operations may leave an unreferenced private file; it is never publicly served and snapshots include only referenced active files. Do not run speculative orphan deletion on personal storage.

`SummaryRecord` stores one dated nutrition/recovery/activity summary per owner, source and date. Clinical records allow multiple named results per date. Source record IDs are unique per owner, source and kind. `values` uses the fixed schemas documented in README.md and `tracking/summaries.py`; unspecified numeric values are null, reported zero remains zero. Clinical units and reference ranges are copied from source. Completeness is explicit. HRV device and method are retained. Different sources and devices are not summed, and no provider priority is invented. The overview selects the latest dated record, shows its source and age, and does not claim it is a merged total.

Weekly averages use only complete records with known values. They group by source, device, HRV method and synthetic status and report denominators. Net carbohydrates require known consistent total carbohydrate and fiber values; negative/inconsistent results are flagged rather than clamped. Clinical/device measurements are not combined into a single series. Charts additionally separate units, measurement side/location and completeness. Nutrition targets are independent editable settings with optimistic version checks and no hardcoded recommendations.

Manual summary corrections use complete replacement validation and optimistic versions. Reviewed CSV imports use immutable originals, stable row IDs, an atomic whole batch and separate row/batch receipts. Duplicate, conflicting and deleted IDs cannot silently overwrite or revive history. The measurement and summary formats are the app's explicit formats, not assumed native vendor formats.

`ReviewNote` stores explicitly saved reviews and separately linked annotations. Linked records must belong to the same owner and have matching synthetic status. Original measurements and summaries are unchanged by annotations. Review text is untrusted data. Browser/MCP review saves are idempotent. Deletion clears text from the current record and receipt; the tombstone prevents replay from restoring it. Earlier exports/backups are separate copies.

MCP reads carry dates, provenance, explicit units, bounded ranges and pagination. Source coverage remains separate from connection status. Authenticated photo retrieval requires an explicit request and returns normalized content, not a public link. Writes remain optional and require the independent write scope and explicit intent. No tool accepts arbitrary file paths, shell, SQL or provider record writes.

Exports preserve exact JSON, original photos, corrections, targets, reviews and tombstones. Spreadsheet formula prefixes receive a protective apostrophe only in CSV; JSON retains original text. Backups preserve the SQLite schema and all database history plus active referenced photo files. After restoring an old snapshot, apply later intentional deletions before any source synchronization is resumed. No retention schedule is enabled by this local build.

## Oura source originals and revisions

OuraConnection separates provider accounts from other wearable sources. Verified provider IDs bind repeated authorizations; unidentified grants remain separate. OuraRecord preserves the exact provider ID when present, current lossless JSON and version. OuraRevision retains each changed original with a page/index reference. OuraPage retains exact UTF-8 API responses, deduplicated per account/collection/hash. Original units, offset timestamps, date only fields, nulls and absent fields are not normalized. Provider records do not automatically create body measurements or combine with manual summary totals.

Heart rate and battery schemas have no source record ID. Their explicit content_hash_no_id keys deduplicate identical observations without presenting a local key as a provider ID. Changed content remains a separate observation because there is no documented correction identity. Existing history is not removed when records are absent from a later fetch or a scope is declined. No provider deletion webhook handler exists in this version.

OuraSync records collection, actual query bounds, committed page cursor and partial/complete/error status. A cursor commits with its page records. Each invocation is bounded and can resume. Provider errors are categorized without storing error bodies. Export includes raw pages, records and revisions, but never authorization state or token ciphertext. The encrypted database backup includes credential ciphertext and requires separate key custody for recovery.
