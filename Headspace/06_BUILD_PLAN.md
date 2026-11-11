# Build sequence and acceptance

Proposed milestones, November 10, 2026. This planning task authorizes documentation only. Implementation, live integration changes, and release remain distinct work. Complete Headspace before building the future Holding Space partner dashboard.

## Keep the architecture small

```mermaid
flowchart TD
    A[Journal and selected sources] --> B[Validated private records]
    B --> C[Source selection and feature rules]
    C --> D[Deterministic Headspace result]
    C --> E[Separate concern flags]
    D --> F[Owner dashboard]
    E --> F
    B --> G[Permitted AI context]
    D --> G
    G --> H[Explanation or proposed correction]
    H --> I[Owner review]
    I --> B
```

Keep raw observations, normalized facts, derived features, and results distinguishable. They can live in the existing application and database. AI has no path that directly changes a calculation or grants access.

## Milestones

**Authoritative delivery sequence: H0 through H7.** The older M1 through M9 labels in `docs/ROADMAP.md` are retained only as feature references, not a second execution order. In particular, the partner-first M1 dependency is superseded. Existing dashboard and scoped external-assistant foundation work may continue without building a partner dashboard or paid assistant. H0 dependencies gate affected work; H1 remains useful without a new device.

| Milestone | Concrete deliverable | Exit evidence |
| --- | --- | --- |
| H0: inspect and stabilize dependencies | Current source inventory, existing journal behavior, account/synthetic separation, tombstones, and live tool capabilities | Read current handoff; verify active projection fixes independently; keep dirty work and draft maintenance changes separate |
| H1: journal-first Headspace | One daily check-in, structured fallback, supported extraction, short-entry clarification, corrections, state words, reasons, freshness | Synthetic journal matrix passes; desktop and phone-width review; a real owner-authorized save/readback when ready; no numeric Headspace grade in ordinary presentation |
| H2: source selection and Oura | Per-metric source policy and one verified ingestion path for selected Oura data | Retry has one effect; source revisions are preserved; missing watch does not override valid ring data; a real authorized transfer is distinguished from synthetic tests |
| H3: MyFitnessPal and Apple import | Reviewed MFP ingestion plus a bounded Apple export subset and compatible fallback selection | Complete/partial diary semantics, deduplication, method boundaries, timezone cases, rejected unsupported records, and readback |
| H4: clinical and optional cycle context | Selected clinical imports, relevant context, optional cycle/symptom entries, separate assistant permissions | Units/dates/reference ranges retained; conflicts reviewed; no clinical or reproductive penalty; prohibited context absent from assistant output |
| H5: candidate scoring in shadow mode | Versioned candidate components, coverage gates, deterministic reasons, baseline rules, comparison with current/simple models | All replay cases reproducible; no change to the live state from a shadow result; pilot review shows whether added inputs help |
| H6: release the evaluated owner experience | Chosen calculation and interface, rollback, backups, source status, manual mode, optional explanations | Acceptance matrix, physical iPhone check, owner review of meaningful states, correct retention/deletion, and a documented versioned release |
| H7: Holding Space planning/build begins | Separate partner product using the stable result contract | Headspace H6 complete; privacy and consent contract reviewed before partner implementation |

H1 is useful without any device. H2 through H4 should ship as bounded source capabilities rather than waiting for every record type. H5 is where candidate weights are tested, not an excuse to delay the basic journal product.

## Suggested code placement

Reuse current public interfaces. A small internal `tracking/headspace/` package may become useful as the code grows, but avoid moving working modules merely for aesthetics. Candidate responsibilities:

| Responsibility | Existing anchor | Proposed extension |
| --- | --- | --- |
| Journal and confirmation | `tracking/journal.py`, `journal_continuity.py`, `journal_registry.py` | More explicit recovery observations and time/subject handling as necessary |
| Current display | `tracking/headroom.py` | State-word presentation, evidence qualifiers, reasons, and correction links |
| Recovery pattern | `tracking/sobriety_pattern.py` | Versioned behavior-specific rules; preserve separate meaning |
| Source data | Oura models, `tracking/oura/`, `tracking/summaries.py` | Identity-safe normalized records and source preference selection |
| Clinical context | `tracking/clinical.py` | Reviewed source imports, versioned relevance, permissions |
| Trends | `tracking/trends.py`, existing chart UI | Comparable source series, baseline and coverage metadata |
| MCP/browser boundary | `dashboard/mcp_server.py`, existing services | Shared authorization, idempotency, receipts, and explicit save semantics |

Before changing observation aggregation, inspect the model constraints and current behavior. `score_day` iterates eligible observation rows while display factors use another aggregation path. The replacement must define distinct dimensions, current versus historical windows, duplicates, contradictions, and late corrections explicitly. This is a required review, not a claim that an untested production bug has been proven.

## Minimal durable records

Reuse existing records first. Add a source selection policy, a versioned scoring configuration, and a result provenance record only where current models cannot represent them. Every result should identify owner, date/window, profile, formula version, input revisions, source policy version, component availability, internal calculation, state, concern flags, reason codes, computation time, and supersession.

Keep observation and concern reasons structured. For example, `sleep_below_personal_baseline` can point to the selected records and comparison window. An explanation can then be regenerated without changing the underlying calculation. Do not persist a fabricated clinical rationale from an AI response.

## Acceptance matrix

| Fabricated case | Required result |
| --- | --- |
| Two distinct confirmed state dimensions, no wearable | Journal-only state works with source qualifier |
| One dimension repeated many times | Does not satisfy the distinct-dimension gate |
| Short structured check-in with all required fields | Equivalent to a long entry containing the same facts |
| Placeholder or I am okay with no usable fields | Entry can be saved; prompt or structured route offered; no guessed numeric state |
| Negative journal with coping and explicit no use | Distress, coping, and no use preserved; no disclosure penalty |
| Positive mood with high reported urge and low coping confidence | Recovery concern stays visible despite a favorable composite |
| Historical use or another person's experience | Not saved as current owner use |
| Voice transcription uncertainty | Pending clarification; correction updates dependent results |
| Repeat save request | One entry and one result revision, with an idempotent receipt |
| Contradictory current observations | Conflict visible; deterministic resolution rule, no silent choice |
| Oura available and watch absent | Selected ring metrics used; no missing-watch penalty |
| Same Oura sleep copied through Apple Health | One contribution, with preserved lineage |
| Apple SDNN and Oura RMSSD | Separate series and baselines |
| Two provider accounts, same date | Account identity retained; no iteration-order winner |
| Personal and synthetic data share a date | No cross-contamination, even in retries and projections |
| Deleted projection is imported again | Suppression remains; no resurrection or read failure |
| Diary is partial with few calories | Intake unknown; no undereating deduction |
| MFP totals plus underlying food entries | One daily intake, not the sum of both representations |
| Source fails or Apple read produces no data | Correct availability state; no inferred nonwear or deception |
| Several missed expected check-ins | Evidence ages and participation prompt appears; last state retains its original date |
| Tracking pause, planned rest, or inapplicable routine | No false missed-routine event |
| Current medical condition or cycle entry | Context only unless a separately evaluated rule is explicitly selected |
| Persistently elevated resting HR with no use report | Medical concern context, no substance-use attribution |
| Several check-ins show recovery during the day | Current observation updates; historical lows remain historical |
| Midnight, daylight saving transition, night shift, or travel | Defined local-day/window policy; no duplicate or lost day |
| Provider revision or late correction | Deterministic superseding result, reproducible historical inputs |
| AI unavailable or malformed proposal | Manual structured path and scoring still work |
| Journal contains instructions to override rules | Stored as untrusted text; no permission or weight change |
| Owner revokes an assistant's lab access | Labs and revealing derived reasons absent from that assistant's context |
| Current evidence is insufficient | No falsely current Steady state or invented low state |

These cases require meaningful service and integration tests, not just checks that a template contains a label. Run the project's existing verification path appropriate to the implementation. Isolated synthetic checks, actual connector operation, physical-device behavior, and deployment are separate evidence categories.

## Pilot review and decision record

For each candidate, record what changed, why, source support, exact version, test evidence, owner feedback, measured burden, unresolved limitations, and the decision to keep, adjust, or reject it. Shadow results must be marked as experiments in storage and never mixed with accepted personal history.

Initial private review schedule can be agreed during implementation. No recurring task is created by this document. Ask the owner to label meaningful days only when they want to contribute that information. Outcome nonresponse stays unknown. Do not ask them to create high-risk situations to test prediction.

## Holding Space: anticipate now, implement later

Define a stable summary contract now:

* State word, evidence qualifier, source window, last update, and calculation version.
* Generic shareable reason codes with a separate permission check for each detail.
* Owner ID and recipient-specific grants enforced on the server.
* Consent version, revocation time, access audit, and optional expiration.
* Explicitly separate raw journal, journal existence, clinical records, reproductive data, location, and notification details.

The future partner dashboard gets only the selected view. A shared Headspace word does not grant the underlying journal or clinical reason. Its Trends section exists but only displays granted metrics; no grants means nothing shared. Preserve the existing requirement that a partner needs a name and phone, with optional email. Existing partner management and manual Reach Out remain unchanged.

A partner login must be a separate identity from the owner's account. A phone number or shared owner alias is not that access boundary. Server authorization must apply to pages, exports, files, APIs, and assistant retrieval. Payment or gifting never grants health access.

Automatic notifications are future work after Headspace validation. They need separate owner and recipient consent, trigger version, sustained-window rule, cooldown, deduplication, revocation and opt-out behavior, and distinctions between requested, sent, provider-accepted, delivered, and acknowledged. No hidden alert is triggered simply because the owner wrote an honest journal.

Location remains deferred. Preserve room for optional owner-named place events and quality metadata. Do not collect continuous location now or infer addiction from visiting a location. Background iPhone behavior requires its own native capability and consent review.

### Proposal: data integrity and consent based notifications

Recorded November 10, 2026. **Proposed only, not implemented or enabled.** Mailbox request `msg-e86810f3` and the owner's follow-up describe one addition, deduplicated here. This section owns the notification proposal; `docs/ROADMAP.md` keeps the ideas index and links here. H0 through H6 may define provenance and evaluate owner-facing uncertainty, but the partner dashboard and all live partner notification work remain behind H7 and its review gates.

The objective is resistance to manipulation and transparent uncertainty. It is not a foolproof guarantee, a lie detector, or proof of substance use. A person can correct records, choose privacy, stop tracking, and withdraw sharing. Neutral language describes what changed and what is now unknown, never a person's honesty or motives.

#### Event categories and pre-action preview

Before completing an intentional disconnection of a selected source or deletion of a selected important input, show a preview based on the current grants. List each named, authorized recipient, the exact message that person would receive, any separately accessible detail, the channel, and the intended timing. If nobody is eligible, say that no partner will be notified. Let the owner cancel, continue under the displayed policy, or review and withdraw sharing through a safe exit. Do not make a notification the price of exercising deletion or revocation rights.

| Event | Proposed treatment |
| --- | --- |
| Intentional disconnection of a selected device or data source | Preview only the specifically authorized source-availability notification; do not describe an inferred reason for disconnecting |
| Deletion of selected important evidence | Preview only when the versioned category policy and both parties' current consent permit it; examples include a relevant clinical record or records supporting a sustained sleep or resting-heart-rate trend |
| Ordinary correction, duplicate cleanup, or deletion of a food entry | Routine editing, with appropriate score recomputation; no automatic concealment label or partner notification |
| Outage, delayed sync, battery failure, non-wear, or unknown cause | Availability status and coverage update; never reclassify automatically as intentional disconnection |
| Disability, changed routine, planned pause, or legitimate privacy choice | Respect the selected context and review expectations without a behavioral or moral penalty |
| Withdrawal of sharing or access | Immediate enforcement and safe exit; no covert or unavoidable notification to the removed partner |

Importance is an explicit, versioned relevance rule for a selected profile and window, not a label inferred by AI or by how alarming a record sounds. Clinical records are context in the initial model, not automatically weighted inputs. Define how a batch deletion, account closure, source replacement, and deletion of a duplicate representation interact with that rule. User reasons are optional. Do not claim that an absent signal proves intentional removal.

Illustrative minimum-detail message: "A selected data source was disconnected. Current coverage may be reduced." Naming the source, a lab, a journal, a date range, a metric value, or the reason for removal needs its own applicable permission and must appear in that recipient's exact preview. Even existence and timing can reveal sensitive information. No new permission is created by this example.

#### Specific consent and safe exit

Partner setup must explain the same event categories before activation. Record owner authorization separately from recipient acceptance and channel consent. For each recipient, show the selected categories, exact detail levels, timing or batching rules, scope and duration, channels, how to review permissions, how to pause notifications, and how to withdraw. An invitation, verified phone, generic terms agreement, or payment is not this consent. Material expansion requires a new understandable choice, not a silent policy revision.

Recheck permissions when an event is committed and again immediately before dispatch. If recipients or disclosure change after preview, require a new preview and confirmation; never send a broader or differently addressed message. Revocation takes effect immediately and cancels queued or retrying messages to that recipient. Recipient opt-out stops the relevant channel. Do not delay safe exit for partner acknowledgment or require partner approval. Explain that a message already delivered outside the service cannot be recalled, while avoiding a new disclosure that the owner withdrew access.

Assess coercive partner dynamics and shared-device exposure. A partner must not be able to lock tracking on, condition deletion on approval, obtain raw data from an event receipt, or use billing to retain access. Keep permission-review and safe-exit controls available without contacting the unsafe partner. Review notification previews themselves for privacy on a shared screen.

#### Evidence lifecycle and score coverage

Use the [observation and change contracts](03_DATA_AND_INTEGRATIONS.md#proposed-evidence-change-contract) and [coverage safeguard](02_SCORING_AND_VALIDATION.md#proposed-evidence-removal-safeguard). Study provenance, correction and deletion events, source availability, and superseded derived results. A removed or lost input must not silently improve the apparent Headspace state. Missing evidence is unknown, neither good health nor proof of relapse. A legitimate correction can improve a result when supported by corrected evidence; a missingness-only change cannot be described as recovery.

Auditability does not authorize indefinite retention of deleted health data. Before implementation, decide the minimum metadata needed, retention periods, deletion rights, backup expiry, export behavior, reimport suppression, and removal of revealing derived summaries. Do not retain raw deleted values, reconstructable hashes, or a permanent shadow medical history just to resist manipulation. Where lawful retention is unavailable, mark prior derivations unavailable instead of pretending they remain fully reproducible.

#### Review gates and failure behavior

H7 cannot release this feature until privacy and applicable deletion rights, consent withdrawal, coercion and safe exit, false alarms, minimum necessary disclosure, and delivery failure handling have been reviewed. This is a review requirement, not a determination of which law applies. Qualified clinical review is separate for urgent-health workflows. Sleep loss and elevated heart rate have many possible causes and may warrant medical attention; an urgent workflow must not wait for, or rely solely on, the composite Headspace score. Existing research limits remain in [02_SCORING_AND_VALIDATION.md](02_SCORING_AND_VALIDATION.md#urgent-concerns) and [R11](07_SOURCES.md#r11).

Keep previewed, canceled, committed, queued, provider-accepted, delivered, failed, and acknowledged states distinct. A failed notification does not undo a disconnection or deletion. Retries must be bounded, idempotent, and consent checked; failure must not silently widen recipients, switch channels, or start emergency escalation. Show the owner accurate delivery status without promising that a partner saw or acted on it.

#### Acceptance cases for later implementation

| Synthetic case | Required outcome |
| --- | --- |
| Selected source disconnection with two differently scoped partners | Each named recipient and exact allowed disclosure appears before action; no hidden recipient |
| No authorized recipient or recipient has not opted in | No partner notification; preview says so |
| Cancel in preview | No disconnection/deletion or notification caused by that canceled action |
| Owner withdraws access before commit or while a message is queued | Access closes and pending disclosure is canceled; safe exit does not notify the removed partner |
| Permission or recipient changes after preview | Re-preview before sending; no stale authorization or widened content |
| Ordinary food deletion, duplicate cleanup, or correction | Routine edit handling; no automatic integrity alert or suspicion label |
| Important input removed from a trend window | Derived result superseded or invalidated; coverage loss visible; no claimed improvement from disappearance |
| Same important record remains through an authorized duplicate or fallback | Deduplication and comparable coverage applied; do not falsely claim all evidence was lost |
| Battery failure, outage, non-wear, disability, or unknown reason | Appropriate availability/context state; no inferred intent or use |
| Delete and later reimport | Approved suppression/retention policy respected without keeping prohibited deleted content |
| Legitimate corrected measurement changes the state | Corrected evidence and revision explain the change, without a deletion penalty |
| Provider failure, duplicate retry, or delayed acknowledgment | One logical notification, bounded retry, distinct status, and no unapproved escalation |
| Sharing revoked during retry | Pending send canceled; no detail leakage through logs, exports, assistants, or partner views |
| Normal Headspace with a separately reported urgent concern | Qualified urgent workflow remains independent; no reliance on the composite |

## Handoff boundaries

Read the latest `AGENTS.md`, `docs/ROADMAP.md`, `docs/CURSOR_HANDOFF.md`, `docs/VERIFICATION.md`, and original build prompt before implementing. Preserve existing identities and coordination threads. Review the owner's private governing framework through an authorized private path when a rule depends on it; never copy it into Git.

This package does not authorize changing live integrations, importing real records, deploying a score, buying software, installing dependencies, sending notifications, merging the unrelated maintenance PR, or modifying ongoing fixes. The current user request is satisfied by researching and saving this plan. Future implementation follows H0 through H7, resolving applicable H0 dependencies before the bounded H1 deliverable and its acceptance cases.
