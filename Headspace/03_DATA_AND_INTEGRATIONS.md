# Data sources and integrations

Proposed contracts, November 10, 2026. A connected ChatGPT tool and a functioning dashboard ingestion path are separate capabilities.

## Four sources, one evidence ledger

| Source | What is established in this review | Next delivery requirement |
| --- | --- | --- |
| Oura | Standalone connector responds using OAuth; its collection catalog includes native sleep/readiness scores and raw sleep, activity, stress, and other collections. Existing dashboard adapter code is present. Recorded project direction keeps the direct adapter as a disabled backup | Preserve the selected standalone path. Add or verify an authorized, idempotent transfer into dashboard storage and prove one source record survives retrieval and retry |
| MyFitnessPal | Status tool reports configured credentials and America/Chicago diary timezone, but explicitly reports no live account verification; this check does not contact MyFitnessPal. The public developer portal describes a private API for approved developers | Verify a bounded read, preserve provider IDs and diary completeness, and test dashboard ingestion separately. Do not claim the existing sign-in is a general commercial integration |
| Apple Health | HealthKit is a native Apple framework. Existing project notes describe exports, with no verified dashboard adapter or native companion | Start with an explicitly supported, reviewed export subset; evaluate a native companion only when ongoing synchronization is needed |
| Medical records / MyChart | A Health tool surface exists in this ChatGPT session; no medical records were retrieved or exported for this planning task. Existing dashboard clinical records and reviewed imports are available foundations | Choose a supported patient-authorized export or FHIR route. Prove field completeness, provenance, review, and dashboard write capability. Do not assume a connection inside ChatGPT grants the server access |

This is a capability inventory, not a fresh count of imported records. Personal connection details and identifiers belong in private configuration, never in this repository.

## Selecting a source per metric

On connection, show the available metric families, the proposed primary source, an optional fallback, and a short reason. Suggested owner configuration:

| Metric | Primary | Fallback or addition | Rule |
| --- | --- | --- | --- |
| Native sleep score | Oura | Another verified native score selected later | Never substitute a derived duration value under the same name |
| Sleep duration and timing | Oura main sleep session | Apple Health with original writer identified | Select one coherent session source; handle naps separately |
| Resting or overnight heart rate | Oura for the chosen nightly definition | Apple Watch under its own definition | Do not splice nightly mean and daytime resting estimates into one raw trend |
| HRV | Oura RMSSD series | Apple SDNN as a separate series | Different methods never become interchangeable fallback values |
| Steps | Oura, as requested | Apple Health if selected source is unavailable | Choose a supported aggregate; do not sum ring, phone, and watch totals |
| Workouts | Owner chooses source by workout type | Other source can add a distinct workout | Overlapping sessions require deduplication |
| Food and nutrition | MyFitnessPal | Reviewed manual entry | A copied Apple Health nutrient is not another meal |
| Clinical labs and medication list | Original clinical record | Reviewed owner correction overlay | Preserve the original record, date, units, and status |
| Cycle dates and symptoms | Owner-selected manual or Apple source | Other authorized source adds context | Optional, private by default; do not infer from profile sex |
| Mood or State of Mind | Dashboard check-in | Apple State of Mind if opted in | Keep constructs distinct; Apple valence is not a numeric mood conversion without an explicit mapping |

Store primary and allowed fallbacks for each metric, with effective dates. A fallback only applies to genuinely compatible measurements. Preserve the selected source and why it won. Do not choose whichever source makes the result look best. Show a source switch on the trend and start a comparable baseline when methods differ.

## Normalized observation contract

Preserve the original provider payload privately and maintain a separate normalized record. Suggested fields, reusing existing models when possible:

| Field group | Required information |
| --- | --- |
| Ownership | Owner ID, connection/account ID, personal versus synthetic namespace |
| Identity | Provider, original writer/device, original record ID, provider revision, stable event identity |
| Time | Occurred start/end, source local date and timezone, imported time, last provider update, precision |
| Measurement | Metric, value, unit, method, statistic, measurement window, reference range where supplied |
| Quality | Complete, partial, unknown, invalid, stale, not applicable, or unavailable; quality reason |
| Lineage | Original source, transport path, parent observation IDs, content hash for audit, extraction/version links |
| Consent | Permitted use categories, assistant access, sharing eligibility, effective consent version |
| Lifecycle | Active revision, correction overlay, deletion/tombstone state, superseding record |

A transport is not the origin: Oura to Apple Health to an export is still one Oura observation. Likewise, MyChart through Apple Health and the same MyChart FHIR resource obtained directly are potential duplicates.

Do not deduplicate only by value and date. Distinct legitimate observations can share both. Use provider/account/original ID and revision first, then source-aware matching for copied records with an explicit review state. Identical retries return the original receipt. Provider corrections supersede the projection. Deletion suppression must survive reimport.

## Known foundation dependency

The current project handoff records synthetic reproductions of an Oura projection deletion failure and account/synthetic identity collisions in `tracking/device_log.py`. These are software findings, not evidence of a real-data incident. Another project owner is handling that work. Headspace ingestion must wait for verified identity isolation and tombstone handling; do not build scores over a projection that can mix owners, accounts, or synthetic status. Do not alter that active fix while adding this planning package.

## Initial metric registry

| Family | Collect when available and authorized | First scoring role |
| --- | --- | --- |
| Journal state | Mood, energy, focus, chosen stress or affect descriptors | Core state from confirmed ratings |
| Recovery behavior | Urges, coping confidence, perceived control, trigger access, explicit behavior events, completed coping and support | Separate behavior-specific concern rules |
| Participation | Expected cadence, completed check-in, declined fields, pause reason, source freshness | Evidence and routine clarification |
| Sleep | Native score, duration, onset/wake timing, regularity, wake intervals | One selected recovery contribution; other fields explain it |
| Autonomic and physiological | Resting/overnight HR, HRV with method, temperature deviation, respiratory rate, overnight SpO2 | Context and personal trends, initially no independent composite weights |
| Activity | Steps, workout type/duration/load where provided, recovery or rest mode | Context or selected routines, never an automatic demand to exercise |
| Nutrition | Complete diary flag, calories and selected nutrients, meal timing if actually present, agreed targets | Optional plan alignment; not inferred from an empty diary |
| Symptoms | Pain, fatigue, illness, GI symptoms, sleep problems, relevant severity/duration | Context; explicit urgent concerns stay separate |
| Medical context | Active diagnoses, medications and changes, selected labs, clinician-authored restrictions or plans | Interpretation context; no fixed diagnostic penalty |
| Reproductive context | Optional period dates, symptoms, contraception changes, user-supplied phase information | Confounder context; no automatic score deduction |

Cardiovascular age, estimated VO2 max, every sleep stage, and every imported lab do not need to become daily scoring inputs. Retain relevant data for detail and future research without increasing first-release complexity.

## Oura implementation scope

Reuse the existing collection catalog, OAuth handling, pagination, immutable originals, revisions, and encrypted token practices. The dashboard's existing review of Oura OSS is [OURA_REUSE_REVIEW.md](../docs/OURA_REUSE_REVIEW.md).

Begin with `daily_sleep`, `sleep`, `daily_readiness`, and `daily_activity`. `daily_stress` and `daily_resilience` can be contextual extensions when actual values exist. Presence in the catalog does not prove every account has records. Preserve nulls and follow pagination. A successful account check does not prove complete ingestion.

Treat native scores as vendor outputs. Oura describes Daytime Stress as physiological and relative to the person, with multiple possible causes. It does not directly measure emotional distress or identify a substance. Distinguish what the Oura app displays from what the authorized API actually returns. [P01](07_SOURCES.md#p01), [P02](07_SOURCES.md#p02).

The preferred initial workflow remains an explicitly invoked transfer through the existing authorized connector and dashboard service. Prove a durable receipt and readback. A ChatGPT conversation is not an unattended scheduler. A later server pull needs its own supported access and user authorization; do not turn on the disabled direct adapter just because the code exists.

## Apple Health implementation scope

The web dashboard cannot read HealthKit directly. For the first slice, implement a bounded export parser for the precise supported types, with preview and confirmation. Use streaming parsing, file size limits, safe archive extraction, and XML entity protection. Reject unsupported structures clearly. Large full exports must not be loaded unbounded into memory.

For eventual ongoing updates, evaluate an iOS companion using SpeziHealthKit. It must respect native background delivery, device locking, permissions, offline queues, and retries. Prove behavior on a physical iPhone before promising regular ingestion. No native app is required to finish journal-only Headspace.

Apple now displays a Sleep Score, but the reviewed official developer answer says no API access was available when posted. Current documentation reviewed did not establish a usable sleep-score endpoint. Recheck the actual target SDK at implementation; until then, expose the score as unavailable rather than recreating it. Sleep samples are available through documented HealthKit types. [P03](07_SOURCES.md#p03), [P04](07_SOURCES.md#p04).

HealthKit intentionally does not reveal denied read permission in the same way as a normal connection failure. An empty response can look like no data. Therefore the application must not confidently label an empty Apple result as device nonwear or deliberate permission withdrawal. [P11](07_SOURCES.md#p11).

## MyFitnessPal implementation scope

Reuse the existing personal connector after a live read test. Import food entries and daily totals as different record types, preserving meal IDs, portions, source date, and units. Do not add totals to the entries that generated them. Record whether a day is complete, partial, user-confirmed complete, or unknown. A diary with no entries is not proof of fasting.

Prefer the source's supported structured export or approved API. The official API is private and approval-based, so a working personal connector does not establish product-wide API rights. Do not design a commercial signup flow around sharing the owner's credentials. [P08](07_SOURCES.md#p08).

Undereating and overeating must be interpreted against the person's current plan and enough complete data. Distinguish planned dieting, illness, incomplete logging, and actual intake. Do not automatically add device calorie burn to an intake target or prescribe restriction as a response to a bad day.

## Medical records and MyChart

Keep imported clinical records available in the private dashboard, but curate a smaller relevant context for Headspace. Candidate resources include Condition, Observation, MedicationRequest/MedicationStatement, AllergyIntolerance, DiagnosticReport, and clinician-authored plans or documents when supported. Preserve original status, dates, provider identity, laboratory reference ranges, and FHIR version.

Choose one initial path in this order: supported reviewed export into the existing clinical service; patient-authorized Epic FHIR if registration and the provider endpoint are available; or a future native Apple Health clinical-record bridge. MyChart login occurs at the provider's authorization page, not in a new password collection form. Apple clinical records are themselves permissioned FHIR resources. [P05](07_SOURCES.md#p05), [P09](07_SOURCES.md#p09).

Existing ChatGPT access does not promise bulk export, every historical note, continuous synchronization, or a write into CX83 Fit. Prove those steps individually. If only a summary is available, label it as a summary and do not manufacture underlying records. The eventual import should show what was included, omitted, failed, duplicated, or awaiting review.

Labs such as CBC, thyroid results, glucose, and hormone measurements can be relevant context when present, but relevance and timing must be reviewed. A diagnosis or old abnormal result is not a permanent daily deduction. A medication list does not establish that a dose was taken. Wearables cannot infer hormone concentrations. Avoid causal claims such as a laboratory value caused a mood change, or treatment recommendations based on the composite.

## Period and hormone context

Offer cycle tracking to anyone for whom it is relevant. It is optional and private by default. Capture user-provided dates and symptoms, irregular cycles, and relevant treatment changes without assuming a standard 28-day cycle. Do not infer pregnancy, ovulation, or adherence from missing entries. A physiological shift may have multiple explanations.

Evidence shows cycle-associated changes in some wearable measurements; it does not justify treating menstruation as worse mental health. In the first version, annotate comparable trends. Phase-specific personal baselines require enough confirmed cycles and their own evaluation. Do not automatically correct every person's HRV or temperature by a population average. [R16](07_SOURCES.md#r16), [P06](07_SOURCES.md#p06), [P07](07_SOURCES.md#p07).

## Freshness and scheduling

Store each source's expected cadence and last success separately from the latest observation time. Recompute after accepted new data, a correction, a source preference change, or an explicit refresh. Start with existing jobs or a Django management command when a scheduled path is authorized; do not add a new queue service just for a daily calculation.

Initial freshness hypotheses: a current check-in belongs to the present local day; sleep belongs to the completed sleep period; nutrition finalization waits for the user's day completion; medical context keeps its clinical date and review state rather than being treated as a daily observation. Test travel, daylight saving changes, night shifts, late sync, revised sleep sessions, and future timestamps.

## Access boundaries

Raw journals, reproductive information, medical notes, medications, and lab values each need separate access categories. The owner can allow Headspace computation while restricting an assistant's access to raw records. Derived reasons can leak sensitive facts, so their sharing policy must follow the underlying evidence. No raw health information belongs in project mail, ordinary request logs, analytics, or Git. Future partner access is designed in [06_BUILD_PLAN.md](06_BUILD_PLAN.md).
