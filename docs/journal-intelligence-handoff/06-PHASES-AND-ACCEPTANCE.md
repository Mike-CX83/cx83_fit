# Implementation phases and acceptance tests

Suggested sequencing for later authorized implementation. The morning and evening check-in, the registry, and the sobriety pattern are already in the skills and `docs/DATA_CONTRACT.md`. Do not start a second check-in from this list. This planning delivery does not initiate these phases.

## Phase 0: inspect and choose

Read owning instructions, governing documents, latest checkpoint, code and current diff. Map existing data/auth/receipt/export/backup facilities. Record a concise reuse/extend/build decision in the existing handoff, with proposed departures from this package and reasons. Verify that the private rule_set can be read in the intended runtime without committing it. Resolve the shared-owner privacy boundary and actual client capabilities before exposing sensitive journals.

Exit: bounded implementation scope, selected architecture, open product decisions and explicit verification boundaries. No deployment or credential change.

## Phase 1: smallest persistent journal loop

Implement only when implementation is authorized. Start with a synthetic entry, source-linked observation, authorized read, correction, duplicate-safe receipt and restart persistence in an isolated local database. Reuse existing authentication. Add export/deletion coverage with the schema so sensitive data does not become trapped.

Exit: one reliable local loop; current health-record write settings remain unchanged outside the isolated test environment.

## Phase 2: registry and extraction

Add the seven original domains, typed validation, uncertainty and source spans. Test client-proposed extraction and dashboard entries awaiting extraction. Add confirmed memory lifecycle and safe reprocessing. No semantic understanding is claimed for an unimplemented parser.

Exit: meaningful synthetic examples produce supported observations, ambiguities and durable retrieval without invented metrics.

## Phase 3: routing and optional scoring

Add morning/evening protocol, bounded questions, skips/cooldowns and selected practices. Introduce scores only after definitions and user preferences are settled. Start with individual metrics and coverage if composites are not useful.

Exit: repeatable formulas and reproducible question selection, with clear reasons and no unknown-to-zero conversion.

## Phase 4: restrained dashboard and actual client proof

Add journal entry/history/correction and small optional status indicators. Preserve existing objective trends and plan page. Test phone-width and desktop rendering. Once separately authorized, verify the real ChatGPT text loop and then Dot voice, fresh-session retrieval, interrupted calls and denied permissions. If voice tools are unavailable, document the precise limitation and demonstrate the manual/text fallback.

Exit: each interface has its own evidence; a local pass never substitutes for actual client proof.

## Phase 5: authorized release and operations

Prepare a narrow release, migration/rollback procedure, encrypted restore proof, retention documentation and preserved-service checks. Deploy only with separate authorization. Record implemented, tested, connected, deployed and independently verified states distinctly in `docs/CURSOR_HANDOFF.md` and `docs/VERIFICATION.md`.

## Acceptance matrix, all test content synthetic

| Test | Expected result |
| --- | --- |
| “I did not meditate”; “I may meditate later”; no mention | False, intention and unknown remain distinct |
| “I feel drained” without a number | Qualitative observation; no invented severity |
| User discusses another person's symptoms | Subject retained; no personal symptom assigned to the owner |
| Morning report describes yesterday; ambiguous midnight wording | Occurred date differs from capture time; ambiguity flagged |
| DST repeated hour and date-only input | Offset/precision retained; no invented timestamp or duplicate day |
| Same request retried after timeout | One entry and stable receipt; different payload with same ID rejected |
| Correction from two sessions | Stale expected version refused; current data preserved |
| Entry persists but extraction fails | Entry readable with pending/failed processing; safe retry, no lost text |
| Reprocess same source with revised extraction | Controlled revision; no duplicated observations or events |
| Contradictory statements | Conflict surfaced or explicit correction recorded; no silent truth overwrite |
| Two selected state dimensions 6 and 8, third unknown | Suggested score 70 with 2/3 coverage; one dimension alone yields no score |
| One complete, one missed, one unknown practice | Counts and missingness; no full daily alignment percentage |
| No applicable practices or no observations | No score; never 0 or 100 by default |
| Formula change or corrected source | Versioned superseding calculation; historical lineage remains visible |
| Sobriety day missing between confirmed days | Gap shown as unknown; uninterrupted streak not fabricated |
| Question answered in narrative, skipped, or recently asked | No redundant question; budget/cooldown respected |
| Stale memory or resolved concern | Current context marked stale or resolved; no perpetual prompting |
| Prompt-injection text inside entry | Stored/rendered as data; cannot invoke privileged operations |
| Read-only token or site-edit token attempts journal write | Rejected; no record or partial change |
| Wrong owner attempts record, receipt or export read | Rejected without leaking existence/content |
| Restart and source outage | Stored authorized journal history remains retrievable |
| Delete and retry/re-import | No active text or derived memory resurrection; minimal tombstone only |
| Export and encrypted isolated restore | All new record types/provenance usable; deletion and auth recovery policy tested |
| Synthetic data mixed with personal query | Excluded by default from personal history and scores |
| Voice mishears negation or rating | Material uncertainty clarified before committing |
| Actual text/voice save and fresh-session retrieval | Receipt and server read agree; state each client result separately |
| Voice tool failure | No false saved claim; practical authenticated fallback |
| Existing measurement/import/photo/provider workflows | Relevant regression checks still pass; source priorities unchanged |

## Later, not started

Steady is the working name direction for the app. The current product name stays CX83 Fit until a rename is chosen. Your Headroom is the dashboard display of Daily State and is already separate from the items below. Do not start these phases from this note.

### AI check-ins inside the web app

A later phase can put AI in the web app to review stored metrics and Headroom trends more than once a day. It can notice a meaningful change, explain the factors already on file, and suggest a practical next step. Frequency and data permissions have to be chosen by the user. A source that is not connected and authorized stays out, including private messages. There is no AI inside the app in the current phase. ChatGPT remains a separate connection.

### Accountability partners and text alerts

A later phase can let the user invite a trusted person. Both people have to opt in before any text is sent. The user chooses the Headroom threshold, the recipients, and what the text is allowed to say. A score under that threshold can ask the partner to reach out. The trigger stays on the defined Daily State bands. AI may help explain a pattern later, and it must not change the threshold, add a recipient, or add detail the user did not allow.

Repeated alerts, brief moves around the threshold, and missing or stale data need a pause or a cooldown so one thin day does not spam anyone. The user can pause alerts, remove a partner, and revoke sharing. The partner can unsubscribe. The default text stays discreet: no addiction history, no private conversation, and no detailed health record. A low score is a request to connect. It is not proof of a relapse and it is not an emergency alert. No text is sent in the current phase.

Run focused tests as changes warrant and the repository's required checks before declaring implementation complete. Documentation-only delivery needs link/content validation, not production calls or a repeat of the application suite. Keep fixtures disposable and output free of private text.
