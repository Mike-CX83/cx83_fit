# Product roadmap

Canonical product plan, November 8, 2026, 11:30 PM CST (Tulsa, Oklahoma). Planning and research only. No application code, migration, purchase, credential, send, or deployment is authorized by this file.

This file is the current product direction. It keeps earlier decisions and points at the notes that still own them. Execution evidence stays in [VERIFICATION.md](VERIFICATION.md) and [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md). The original finish line remains [Personal_Health_Fitness_Dashboard_Build_Prompt.txt](Personal_Health_Fitness_Dashboard_Build_Prompt.txt). Where a later choice in this file widens that first release, it is a staged extension, and it still needs its own authorization before anyone builds it.

## How to read this

| Mark | Meaning |
| --- | --- |
| Confirmed | Already chosen, and either built or explicitly kept |
| Proposed | Design for a later build. Usable as the working plan until a decision replaces it |
| Open | Needs a decision or more evidence before a default is chosen |

## Product direction

CX83 Fit brings a person's health and fitness information together in one place: a private dashboard, journal, Headspace check-in system, trends, and Holding Space for accountability and owner-controlled sharing. Holding Space is both the owner's partner-management area and the dashboard partners use for what the owner has shared.

The idea came from sobriety. The owner wants to notice a change in routine or behavior early enough to check in or ask for help. The same shape should work for training with a coach, managing diabetes, or asking a trusted person to help with consistency. The owner's plan defines what matters. The app does not assume one condition.

Two product names stay as they are until a rename is chosen. The app is CX83 Fit. Steady is only the working name direction. Headspace is the check-in block on Today. Its number is still Daily State.

Pricing direction clarified November 10, 2026, as a product idea only:

* Free core: owner dashboard, core Headspace score, and Holding Space partner dashboards.
* Optional paid owner agent tier: owner dashboard chatbot, optional supported wearable connections, and agents that help update CX83 Fit and supported connected apps. This tier also includes chatbots for the owner's Holding Space partners.
* Without the owner's agent tier, a Holding Space partner can purchase just their own chatbot, limited to information the owner explicitly shares with them.
* A partner, family member, friend, or other supporter can gift the full owner agent tier. The recipient accepts and controls all enabled features and permissions; payment grants no access to their information or control of their account.
* Exact prices, billing provider, gift durations, and renewal mechanics remain open. SMS operating cost and any limit on owner plans also stay open. See Subscription and gifting direction below.

### Foundation first and gradual rollout

Clarified November 10, 2026. The first priority is a useful basic dashboard and the ability to connect ChatGPT and Claude for permitted analysis and updates. Built-in chatbots, broader agents, wearables, subscriptions, and gifting roll out gradually after that foundation. This is product direction, not a claim that all connections or workflows already work.

People can choose how to use the dashboard and combine these methods:

* **Manual:** Add and correct information themselves, keep a journal, use Headspace, review numbers and trends, and share selected information through Holding Space. A chatbot, external assistant, agent, or wearable is not required for the basic dashboard to be useful.
* **Files:** Upload supported files or exports, review the proposed records, and confirm what is saved. Existing reviewed CSV support is the starting point; broader document and image imports remain staged work.
* **Connected apps:** Import information from supported apps when a working connection and permission exist. Show the source, last update, missing information, and duplicates rather than implying that every app is connected or automatically synchronized.
* **Optional AI help:** Connect ChatGPT or Claude to help add records, update the dashboard, analyze numbers and trends, and update supported apps where authorized writes are available. People can work through the dashboard or directly in their chosen assistant. A direct assistant-to-app action requires that assistant's own supported app connection and permission; it does not automatically update CX83 Fit. A dashboard-mediated action requires a supported dashboard connection. Show what was saved to each destination, and reconcile imported copies without double counting.

The product should explain these choices in everyday language for people unfamiliar with chatbots or agents, and make the manual path obvious for people who do not want them. A chatbot lets someone ask questions or request help in a conversation. An agent can carry out specifically permitted tasks, such as adding a reviewed entry. Neither gets blanket access or permission to act. AI helps explain available evidence and trends; missing information stays unknown.

The connected ChatGPT/Claude workflow is separate from the later paid chatbot built into CX83 Fit. Connecting an external assistant must not depend on launching the built-in paid assistant first. This clarification does not set pricing for external services or promise that their subscriptions, connections, or app capabilities are included. The existing paid-tier and gifting direction remains a later product option, with exact commercial terms open.

Delivery order: establish and verify the dashboard, manual entry and supported file imports; verify optional ChatGPT access and add Claude support with scoped reads and explicitly authorized writes; then expand supported app workflows and later built-in agents and wearable options. Journal, Headspace, Holding Space, and accountability remain the core product throughout. Each capability is released only when its actual behavior and permissions have been verified. Existing milestones below describe feature slices, not a requirement to finish a paid chatbot before connecting external assistants.

## What already exists

Preserve these. Do not rebuild them to match a generic dashboard.

| Area | Current state | Where it lives |
| --- | --- | --- |
| One Django app, SQLite, owner session | Built. Login names on the live app are one owner, not separate people | [PHASE_1.md](PHASE_1.md), [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md) |
| Measurements, private photos, reviewed CSV, summaries, targets, charts, reviews, exports, encrypted backup | Local first release. Live history is a separate publish record | [DATA_CONTRACT.md](DATA_CONTRACT.md), [VERIFICATION.md](VERIFICATION.md) |
| 90 day plan window | Daily steps, sleep, workouts, device calories, and the meal diary are analyzed inside 90 days. Current labs, medications, and diagnoses stay available after that window. Missing days stay unknown. Sources are not added together | `tracking/plan.py` |
| Meals | One meal row is separate from a daily nutrition total | `DietEntry` and nutrition `SummaryRecord` |
| Photos | Original bytes can keep metadata, including location. The display JPEG is metadata free. Both are private | [DATA_CONTRACT.md](DATA_CONTRACT.md) |
| Journal, memory, questions, Daily State, Routine Alignment | Built and published as the check-in loop. Registry `registry-3`. Domains 12, 13, 14, 16, 17, 18, 19 | [DATA_CONTRACT.md](DATA_CONTRACT.md), [01-JOURNAL-AND-DOMAINS.md](journal-intelligence-handoff/01-JOURNAL-AND-DOMAINS.md) |
| Headspace display | Steady at 70 and above, Stretched from 40 through 69.99, Running low below 40. Fewer than two of mood, energy, and focus leaves the score blank. Sleep, food, and steps can explain the day. They do not change the number | [03-SCORING-AND-MISSING-DATA.md](journal-intelligence-handoff/03-SCORING-AND-MISSING-DATA.md), [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md) |
| Sobriety pattern | Separate 14 day read with 3 and 7 day slices. A blank day is unknown. Off wrist, a stale sync, and a device that was never connected stay distinct. It is not part of Daily State | [BODY_SCAN_RESEARCH.md](BODY_SCAN_RESEARCH.md), `.cursor/skills/sobriety-pattern/SKILL.md` |
| Clinical list | Current labs, medications, and diagnoses. Numeric lab results with a unit and a supplied range also live on the health summary | `tracking/clinical.py` |
| Oura | Adapter exists and is covered by synthetic tests. On the live dashboard `OURA_ENABLED` is 0. The intended path is standalone Oura, then ChatGPT, then this dashboard. That transfer is not implemented. Direct dashboard Oura is a disabled backup | [INTEGRATIONS.md](INTEGRATIONS.md), [OURA_SETUP.md](OURA_SETUP.md) |
| MyFitnessPal | A ChatGPT account read worked on November 5, 2026. This app does not ingest it. A later status call failed before returning a connection. Current availability is unverified | [INTEGRATIONS.md](INTEGRATIONS.md) |
| Apple Health | Documented export path only. No adapter and no native app | [INTEGRATIONS.md](INTEGRATIONS.md), [OSS_REUSE_AND_MOBILE.md](OSS_REUSE_AND_MOBILE.md) |
| ChatGPT connection | OAuth MCP. Journal and check-in tools are on `health:read` with an explicit save flag. Measurement and review writes need `health:write` and `MCP_WRITES_ENABLED`. `site:write` cannot change health records | [MCP_SETUP.md](MCP_SETUP.md), [DATA_CONTRACT.md](DATA_CONTRACT.md) |
| Holding Space tab | Up to five active partners. Name and phone required. Reach Out records a discreet manual text. Reply STOP opts that number out. The same request does not send twice. `SMS_ENABLED` is unset, so live sends stay "Not sent". No Twilio account, billing, or number is installed | `tracking/holding.py`, `tracking/sms.py` |
| Partner dashboard | Not built. The November 8 narrow page (shared name, Headspace word, age of that word, "I checked in") was a plan only | This file replaces that unbuilt page. The owner's tab stays |
| 3D body scan | Researched and not scheduled. Progress photos and tape measurements remain the body record | [BODY_SCAN_RESEARCH.md](BODY_SCAN_RESEARCH.md) |
| In-app assistant | Not built. ChatGPT remains a separate connection | [06-PHASES-AND-ACCEPTANCE.md](journal-intelligence-handoff/06-PHASES-AND-ACCEPTANCE.md) |

Journal phase history, acceptance tests, and the coding prompt stay in [journal-intelligence-handoff/](journal-intelligence-handoff/00-MASTER-BUILD-BRIEF.md). Do not start a second morning or evening check-in from this roadmap. The live check-in order is `.cursor/skills/personal-health-dashboard/SKILL.md`.

## Decisions this pass keeps

* One application and one database. Scores and permission checks run on the server.
* Unknown stays unknown. A missing entry is never stored or shown as zero. Explicit zero and explicit false stay what they are.
* Synthetic rows stay out of personal trends, scores, and partner views.
* One active source of truth for an overlapping metric. Meal rows and daily totals stay distinct. Watch, phone, and ring totals are never summed. A Health copy of an Oura observation is not a second observation. See [DATA_CONTRACT.md](DATA_CONTRACT.md).
* Provider originals stay read only. A local correction is an overlay.
* ChatGPT is not the database. The server is.
* The private `rule_set` stays outside Git. Personal targets stay editable.
* No health information goes through a business mailbox. No secrets go in Git.
* Manual Reach Out stays a fixed discreet note. It does not include a score, a diagnosis, or a record. Automatic alerts stay a separate feature and are not built.
* Twilio is the selected app sender. Mike chose it on November 8, 2026. Nothing has been purchased.
* Partner acknowledgment is separate from sent and delivered. A text does not mean the person checked in.
* Urgent safety signals stay off the composite score. The sobriety pattern stays off Daily State.
* Body scanning stays unscheduled.
* Local development continues without making SSH or deployment a prerequisite.

The unbuilt partner page from the 4:42 AM note showed only a name, a Headspace word, whether that word was current, and an "I checked in" action. This pass replaces that unbuilt page with a permissioned partner dashboard. The owner's Holding Space tab, the five person limit, and the discreet Reach Out path stay.

## Confirmed requirements

These come from the November 8 product direction and from behavior already chosen.

1. Up to five partners. Name and phone are required. Email is optional.
2. A partner can verify a phone, accept an invitation, and open a browser dashboard.
3. Consent to receive texts is separate from dashboard access.
4. Every partner dashboard has a Trends section. It contains only the metrics and the level of detail granted to that partner.
5. The owner can share a summary without sharing the underlying entries, and can preview the partner view before saving.
6. The owner has separate controls for photos, 3D scans, journals, labs, cycle data, glucose, location, and alert details. Access can be revoked immediately. The server enforces that revocation for pages, files, and any assistant query.
7. The owner dashboard, core Headspace score, and Holding Space partner dashboards are free. Optional owner and partner chatbot access follows the November 10 subscription and gifting direction below. Payment never widens sharing permissions.
8. Setup can hold one or more plans. A plan can start from sobriety, bodybuilding or fitness, health monitoring, or custom. The owner can edit it as goals change.
9. A missed log never becomes a zero. A change in usual logging can be a signal only when that metric was expected, the source was enabled, and the sync was current. A disabled tracker, a broken sync, and a metric the plan never included stay labeled as those conditions.
10. Thin evidence is shown as thin. Observations remain available for questions even when they do not feed the current score.
11. Urgent concerns, including suicidal language and potentially serious symptoms, use a path that can act without waiting on the overall score. Automated emergency routing and automated urgent detection stay behind clinical, privacy, regulatory, and operational review.
12. Location is optional and belongs to a plan. The preferred record is arrival and departure, not a continuous trail. Unavailable location is a data gap, not a missed routine.
13. An assistant may propose plan metrics and extracted fields. It may not silently overwrite a record, a plan, a permission, or an alert rule.
14. Imports show the original source, dates, units, uncertain fields, and possible duplicates before anything is saved. The owner can correct an extraction.
15. External assistants start read only. Writes or scheduled pushes are designed only after a specific tool is shown to support them.

## Proposed design

### Partner identity and permissions

A partner is a new person, with a session that cannot open the owner dashboard. Today's owner login is not that boundary.

Proposed fields: name, verified phone, optional email, invitation state, text-consent state, dashboard-access state, and a per-category grant. Grants are explicit. The default for a new partner is no shared data.

Proposed categories, each with its own on or off, and where it matters a choice between summary and individual entries:

| Category | Summary example | Entry example | Default |
| --- | --- | --- | --- |
| Headspace | The word, and whether it is current | Permitted factor explanations and coverage; internal score number stays hidden | Off until the owner shares at least the word |
| Fitness trends | A trend the owner names | Workouts, meals, measurements | Off |
| Photos | A shared still image | The photo library | Off. Share the metadata-free display image unless the owner deliberately includes the original |
| 3D scans | Not available. The feature is unscheduled | Same | Off, and empty |
| Journals | A one-line status such as "a journal exists" | Journal text | Off |
| Labs | "A result was recorded on a date" | Value, unit, range, name | Off |
| Cycle | A phase label the owner chooses | Symptoms and dates | Off |
| Glucose | A range summary the owner chooses | Readings and meal context | Off |
| Location | "Usual arrival shifted" | The events themselves | Off |
| Alert details | "Mike asked for a check-in" | Why the alert fired | Off. The discreet Reach Out text stays the default |

The owner can preview the exact partner page, then save. Revoke clears that partner's grants in the same server check that serves HTML, files, exports, and assistant context. A removed partner, a STOP reply, and a turned-off share all close access. STOP applies to texts. It is recorded separately from dashboard access so the owner can stop texts and still leave a dashboard, or the reverse, on purpose.

Phone verification proves control of the number. Invitation acceptance proves the person wants the dashboard. Text consent is an unchecked choice with the message purpose, a frequency description, "message and data rates may apply", HELP, and STOP. Those three states are stored with the time and the disclosure version. Adding a partner does not check the consent box.

The Trends section is always on the partner page. With no grants it says that nothing has been shared.

### Personal plans

During setup the owner can create one or more plans and write:

* the goal
* why they want support
* which signals matter
* who should see what
* what should happen when a pattern changes

Starting templates are sobriety, bodybuilding or fitness, health monitoring, and custom. A template proposes metrics. The owner approves them. Approved choices become structured rules the app can apply the same way every time. Editing a plan does not rewrite history. Older days keep the rules that were active then.

Optional tracking, each off until a plan turns it on:

* mood, stress, cravings
* sleep, activity, nutrition
* spiritual practices
* menstrual cycle and related symptoms
* glucose, with meal context when the person or a source supplies it
* illness
* pain and muscle tension
* nausea, vomiting, diarrhea, constipation, shortness of breath

Entries can be structured, journal text, or both. When the person supplies them, keep timing, severity, duration, source, and units. A journal or import extraction stays pending until the owner confirms or corrects it. The existing proposal check is the pattern: the server validates, and a proposal writes nothing by itself.

Candidate sources that are not designed yet: dental records, massage notes, chiropractic notes, and other clinic documents. Each needs its own storage decision before a build. Until then they stay in the import parking lot below.

### Headspace score

Keep the current Daily State formula as `daily-state-1` until a versioned replacement is accepted. Headspace displays that result. It does not store a second hidden score.

The newer [Headspace scoring and validation proposal](../Headspace/02_SCORING_AND_VALIDATION.md) owns candidate formulas and coverage gates. The earlier candidate table below remains research history, not a second formula specification or current default. Proposed model, still without new live numeric defaults:

* A versioned rule set with a common signal list and plan-specific metrics.
* Emotional, mental, and spiritual journal entries can sit beside physical measures the plan selected: sleep, activity, food logging, symptoms, and routine changes.
* Each published score stores the formula version, the input ids and revisions, coverage, the result, and the time it was computed.
* The owner can open a day and see which inputs moved the result and how much information was present.
* A correction supersedes the result. A formula change starts a new series or a clearly labeled recalculation. Historical results stay attached to the formula that produced them.
* Population cutoffs from a study are research context. They are not this owner's threshold.

The current bands (70, 40) and the two-of-three mood, energy, and focus gate are the live display. They are not retired by this document. A later version has to show why a new gate is better on this owner's data, or on a synthetic evaluation, before it replaces them.

Candidate rules to evaluate before any default is chosen:

| Candidate | Evidence in hand | Why it is not a default yet |
| --- | --- | --- |
| Keep a composite blank unless at least two planned dimensions and about 60 percent of planned weight are present | Already the suggested Daily State gate, and the live score uses two of three ratings | The 60 percent figure is a product suggestion. It has not been checked against false "running low" days |
| Treat a within-person move as more meaningful than a population cutoff | EMA relapse work looks at a person's own rise in craving or negative affect. The sobriety read already uses a mood drop of at least 2 points from the prior median | The 2 point rule is a local heuristic. It is not a validated instrument |
| Require several days of a shift before calling a routine changed | Single prompts predict the next prompt better than they predict one or two weeks ahead. Accuracy drops as the lag grows | The right window is still open: 1, 3, 7, or 14 days are already used for different reads |
| Keep craving, confidence, access, and use on the sobriety pattern | Moore and colleagues, 2014: a craving increase was associated with about 14 times the chance of relapse at the next prompt, in a treatment sample. A 100 day study linked craving, negative affect, availability, and permission to drink with a lapse about three hours later. Coping confidence was protective | Those samples are not this owner. The pattern labels `lower`, `rising`, `high`, and `incomplete` stay as built until a review changes them |
| Offer a validated questionnaire as an optional check, separate from the daily score | AWARE predicted later substance use in treatment samples. Published probabilities are from those samples. PHQ-9 and GAD-7 are validated distress screeners. PROMIS short forms cover mood, sleep, and pain with published norms | Using a screener as a daily score would blur a personal capacity number with a clinical instrument. Any use needs the instrument's own wording, cadence, and a clear "this is not a diagnosis" line |
| Let sleep and food explain a day without changing the number | Already true for Headspace. Sleep under 360 minutes and food under half a saved goal are explanations | A plan that wants sleep inside the number needs an explicit new formula version |
| Score logging consistency only for metrics the plan marked as expected, and only when the source is connected and fresh | The sobriety read already separates off wrist, `source_stale`, and `not_connected` | Extending that to every tracker needs the plan's expected cadence first |

Research to use when choosing windows, direction, thresholds, false alarms, and missed events:

* Establish a personal baseline from the owner's own days. Prefer a median and a typical range over a population norm. Wait until the plan has enough expected observations to describe "usual". The minimum count is an open decision. Do not backfill missing days to manufacture a baseline.
* Compare windows the app already understands: the day, 3 days, 7 days, 14 days, and the 90 day plan window. Report direction and coverage for each window that has data.
* Call a routine change only when the shift repeats across the chosen window. A single odd day stays visible as a day.
* Evaluate an alert rule on past days before it can text anyone. Count false alarms (the rule fired and the owner says the day was ordinary) and missed events (the owner marked a meaningful change and the rule stayed quiet). Keep that review on synthetic data first, then on the owner's own labels if he chooses to mark days. Do not copy a published odds ratio into a threshold.
* Leave the underlying observations queryable when they are excluded from the score.

Urgent path, separate from the score:

* Suicidal language and potentially serious symptoms do not wait for a low Headspace number.
* The first version of this path is a person reporting a concern, plus a clear on-screen response. Automated detection that contacts someone is gated. See alerts below.
* The sobriety pattern can still be read on a check-in. It does not become the urgent path and it does not become the Headspace number.

### Proposed data integrity and consent based Holding Space notifications

Proposal only, recorded November 10, 2026. Mailbox message `msg-e86810f3` and the owner's follow-up are one request. The [existing Headspace build plan](../Headspace/06_BUILD_PLAN.md#proposal-data-integrity-and-consent-based-notifications) owns the detailed requirements and acceptance cases; do not create a second plan here.

Before intentional disconnection of selected sources or deletion of selected important evidence, preview each named authorized partner and the exact disclosure. Distinguish relevant labs or sustained sleep/heart-rate evidence from routine corrections, duplicate cleanup, and food-entry deletion. Explain categories, recipients, details, timing, scope, review and withdrawal during setup, with separate owner authorization and recipient consent. Changes in provenance, availability, and coverage must not silently imply improved health; missing data remains unknown. Technical gaps, non-wear, disability, routine changes and privacy choices are not evidence of dishonesty or substance use.

This is resistance to manipulation, not a foolproof guarantee. Review deletion rights, minimal audit retention, coercion, safe exit, false alarms, failed notifications and minimum disclosure before implementation. Revoking access must not covertly or unavoidably notify an unsafe partner. Urgent-health workflows require separate qualified review and cannot rely solely on Headspace. H0 through H6 may define and evaluate owner evidence integrity; the partner dashboard and live notifications remain deferred to H7 after H6. No live change or partner message is authorized here.

### Alerts

Two workflows:

1. Opt-in alerts for a sustained Headspace change. The owner chooses the partners, the condition, and how much the message reveals. Both the owner and the recipient have to opt in. The condition uses a published score version and a sustained window, so one thin day does not send. AI may explain a pattern later. It may not change the threshold, add a recipient, or add detail the owner did not allow.
2. A possible urgent concern. This is not the low-score text. It has its own copy, its own recipients, and its own disclosure limit. Sensitive detail stays in the authenticated dashboard. The text can ask someone to open that dashboard.

Shared message rules, extending the manual Reach Out path:

* Recipient consent, STOP, and HELP are required before an automatic send.
* Duplicate prevention already exists for one manual request id. Automatic sends also need a cooldown and a rule that a repeated condition does not send again until the cooldown ends or the owner resets it.
* Provider acceptance, handset delivery, and a human acknowledgment stay separate. The partner dashboard "I checked in" action is the acknowledgment. An SMS reply can also count once that inbound path is verified.
* A failed send is visible to the owner, with a safe error code. The current manual path already stores that.
* If nobody acknowledges, the owner sees who was contacted, who has not responded, and how long it has been. A second contact is another explicit choice. The app does not place a 911 call because a partner is quiet.

What the app should show the moment the owner reports an urgent concern, as a proposal for review:

* A plain statement that this screen is not emergency dispatch.
* Actions the owner can take immediately: call 911 from the phone, call or text a chosen partner, and open 988 if the concern is a suicide or mental-health crisis.
* A short record that the owner marked the concern, stored for the owner, shared only with partners who already have alert-detail access.
* No automatic text until the urgent workflow itself is opted in and the review gate below is passed.

### SMS, compared

| Path | What it does | Setup and cost notes, checked November 8, 2026 | Fit |
| --- | --- | --- | --- |
| App sender, Twilio | The server sends from a dedicated number. The manual Reach Out code already calls Twilio's message API. Mike's phone is never the sender | US long-code SMS is listed at $0.0083 per segment plus carrier fees (about $0.0035 to $0.005 per outbound segment depending on the carrier). A local number is about $1.15 per month. A failed message can add $0.001. US A2P 10DLC registration is required for application traffic. Sole-proprietor brand registration is listed at $4.50 once, with a low-volume campaign around $1.50 per month, plus campaign review fees. Toll-free traffic uses a separate verification and is blocked until verified. Unregistered traffic can be filtered. Consent has to be express, optional, and specific to texts. Marketing and transactional consent are separate. Sources: [Twilio US SMS pricing](https://www.twilio.com/en-us/sms/pricing/us), [A2P 10DLC](https://www.twilio.com/docs/messaging/compliance/a2p-10dlc) | Confirmed choice for automatic and manual app texts. Still not purchased |
| App sender, other CPaaS | Telnyx, Bandwidth, Plivo, and Vonage also sit on the same US 10DLC rules. Telnyx lists a lower per-segment platform price in November 2026 comparisons | Registration, consent, STOP, and campaign review remain. Switching vendors does not remove the carrier program. A comparison that is not Twilio's own price page should be rechecked before any purchase | Open. Twilio stays the selected vendor unless cost or registration failure forces a review |
| Phone verification codes | Proves the partner controls the number | Twilio Verify lists $0.05 per successful verification plus the SMS segment price. OTP-only traffic may have a narrower registration path than a general campaign. Confirm that before sending codes as ordinary messages | Proposed for partner verify. Live send still waits on an account |
| User-sent message | An `sms:` link opens the Messages app. The owner or the partner presses send. Apple's documented scheme is the number only. A prefilled body is widely used and is not a stable contract, and iOS and Android use different separators | No Twilio bill and no A2P campaign for that one message, because the handset sends it. Delivery depends on the person actually sending. In-app browsers often block the handoff. This cannot be an unattended alert | Proposed fallback while the app number is unregistered, and a permanent option when the owner wants the text to come from their own phone |

Do not mark SMS live because the code path exists. `SMS_ENABLED` stays unset until a personal Twilio account, billing, one number, and server-only credentials are installed, and until US sender registration is far enough along that a test message to an owned phone is accepted.

### Emergency options, compared

These are research notes. None of them is a build.

| Option | What it actually is | What a partnership or shortcut requires | Decision |
| --- | --- | --- | --- |
| User-initiated 911 call | A control that opens the phone dialer with 911. The person places the voice call | NENA tells app developers to dial 911 directly, keep the native voice call working, and say plainly when a call goes to a third party instead. An app cannot attach the health record, photos, or a reliable extra location payload to a legacy 911 call. Text-to-911 exists only where that call center accepts it, and a voice call is still the preferred path. Automated dialing is restricted in some places. Sources: [NENA smartphone apps](https://www.nena.org/page/smartphoneapps), [FCC text-to-911](https://www.fcc.gov/consumers/guides/what-you-need-know-about-text-911) | Proposed as a visible shortcut on the urgent screen after the review gate. It places no call by itself |
| Life Alert style service | A private monitoring center with its own equipment and operators. The button reaches that company, which then decides whether to notify 911, family, or a neighbor. It is a paid subscription and a different company | State programs for personal emergency response systems expect listed equipment, 24 hour operators, backup power, and a defined response. New York's PERS rules are one example, not a national license this app holds. UL 1637 is the home health care signaling standard those rules cite | Open. A monitoring subscription is a personal purchase, not a feature of this app, unless a later review says otherwise |
| Formal dispatch partnership | A path that delivers extra data to public-safety answering points. RapidSOS is one NG911-oriented clearinghouse. PSAPs still receive their normal location. Extra data is supplemental and depends on equipment, a secure connection, and a commercial integration | This app would need a partner agreement, a reliable trigger, audited uptime, and a way to avoid delaying the voice call. Most centers still cannot take an app's medical history as part of the call. Family notification is not a substitute for 911 | Gated. No design work beyond this note until clinical, privacy, regulatory, and operational review |

The review gate, before any automated urgent detection or any automated emergency routing, has to answer: who is the operator, what the person consented to, what leaves the dashboard, how a false alarm is stopped, how a missed acknowledgment is shown, and which laws apply if the app starts to look like a medical device or a monitoring service. Until that review, the urgent screen offers human actions only.

### Location

Proposed record: optional plan rule such as "usually at the gym by 5:00 AM" or "usually home by 6:00 PM", stored as arrival and departure events with a place label the owner named. Keep the event, the local time, the source, and whether the fix was good enough. Do not keep a continuous trail as the product record.

iPhone web app, from 2026 platform notes rather than a test on Mike's phone:

* Foreground geolocation can work while the site is open, including a Home Screen web app.
* Background geolocation, geofencing, and periodic background sync are not available to an iPhone web app. A closed or locked app will not notice a gym arrival.
* HealthKit, Bluetooth, and quiet background upload are native capabilities. The current release is a web app on purpose.

So a web-only check can record a location when the owner opens the app or taps "I'm here". A reliable "did I reach the gym before 5" watch, while the phone is in a pocket, needs a native app or a companion. That test is a milestone of its own, on a physical iPhone, before any location rule can mark a routine as missed. If the phone has no fix, the day says location unavailable.

### Assistants

Four permission layers, stored separately:

1. What the owner can see.
2. What each partner can see.
3. What the in-app assistant for that person can see.
4. What each external assistant can see.

Example the owner asked for: labs stay on the private dashboard, and every assistant is blocked from them. A block is enforced when the context is built, on the server. A prompt cannot widen it.

Owner assistant, proposed: help draft and revise a plan, explain a trend, and answer across permitted metrics. It can compare dates that exist, such as hormone lab dates beside sleep, and it has to say what the data can support. It can propose which metrics a plan should track, why, and which ones run every time. The owner approves. The approval is saved as rules.

Partner assistant, proposed and optional: included with the owner's paid agent tier, or available as a standalone purchase for that partner when the owner does not have the tier. It answers only using information the owner explicitly shares with that partner, further restricted by assistant grants. The partner dashboard itself stays free and useful with the assistant off. A purchase or gift does not widen these grants.

Imports, proposed: CSV and the health exports already documented, plus documents and images such as a lab PDF. The assistant suggests a destination. The review screen shows the file, the dates, the units, the uncertain fields, and possible duplicates. Saving is a separate action. This matches the current CSV review: upload does not write the record.

External assistants, with ChatGPT and Claude prioritized for the foundation. The table records current support separately from that intended direction:

| Assistant | Write or schedule support seen from this repo | Starting rule |
| --- | --- | --- |
| ChatGPT, including the existing MCP connection | Reads are live on `health:read`. Journal saves need an explicit flag. Measurement and review writes need `health:write` and the server write switch. A scheduled push into this app is not implemented. Voice tools work only when that voice session can call tools, which is unverified | Read only for any new external scope. Existing write tools stay as they are and do not gain new record types until a pass says so |
| Claude | No connector in this app. No evidence here of a write or a schedule | Read only, and only after a connection exists |
| Gemini | No connector in this app. No evidence here of a write or a schedule | Same |

Do not design external writes, or a nightly push, until the specific tool's current documentation and a synthetic call show that the operation exists.

### Integrations and source of truth

Connection words stay the ones in [INTEGRATIONS.md](INTEGRATIONS.md): not investigated, documented but untested, implemented with synthetic tests, verified with an authorized account, blocked or unavailable. A ChatGPT connector is not an application connection.

| Source | Data that matters here | Practical path | Permission and approval | Sync reliability | Current label |
| --- | --- | --- | --- | --- | --- |
| Manual entry and this app's CSV | Measurements, meals, summaries, journal, clinical items, photos | Already the source of truth when no device is connected | Owner session | The person files it | Implemented with synthetic tests |
| MyFitnessPal | Meals, daily nutrition, weight, exercise. Fiber was unknown in the November 5 sample | Keep the ChatGPT workflow. App ingestion needs a located implementation or a reviewed Premium export. Official public API entitlement was not established | Account stays in ChatGPT until an app grant exists | Unverified as of the November 6 failed status call | ChatGPT read verified once. App ingestion blocked or unavailable |
| Oura | Sleep, readiness, activity, workouts, non-wear | Disabled direct API backup. Preferred path is the existing standalone service, then ChatGPT, then this dashboard. Membership Hub export is the fallback. Personal tokens are deprecated | OAuth app, membership, scopes. API retention has to be documented before archival use | Not connected. Standalone service can be up while this app stores nothing | Implemented with synthetic tests. Live direct path disabled |
| Apple Health and Watch | Steps, workouts, sleep, cycle, symptoms, some records | On-device HealthKit, or the person exports XML. A web server cannot read HealthKit. Background delivery is a native feature | Per data type, on the phone | Export is manual. A native bridge would be a new app | Documented but untested |
| Android Health Connect | Steps and fitness stored on the phone. Medical records exist as a separate FHIR-style feature | Needs an Android app. No server feed by default | Per type, on the device | Phone must be present | Not investigated for this iPhone-first app |
| Google Fit and Fitbit cloud | Historical Google Fit APIs are supported only through the end of 2026. Google points cloud clients at the Google Health API | Do not start a new Fit REST integration | OAuth and a Google review | Deprecating | Not investigated. Avoid new work |
| Withings and similar smart scales | Weight and some body composition | Public OAuth partner API | Developer credentials and user consent | Depends on the scale reaching Withings | Not investigated. Strong candidate when weight needs a device |
| Garmin, WHOOP, Eight Sleep | Recovery, activity, sleep | Partner APIs. Several require a commercial agreement for production | Vendor approval. Sandbox is not production | Varies. Confirm at the time of a real integration | Not investigated |
| Dexcom and other CGM | Glucose readings. Developer docs exist. US sharing through Dexcom's API has historically been delayed rather than real time. Reconfirm the delay before promising meal-time coaching | Official developer app, then a production review | Health-data agreement. Likely a commercial or regulatory step for anything that looks like treatment advice | Not a replacement for the reader's own alarms | Not investigated |
| Labs (Quest, Labcorp, portals) | Dated results | PDF or portal export first. SMART on FHIR patient access where a portal offers it. No public consumer API was confirmed for Quest or Labcorp | Patient login. Each health system enables different FHIR resources | Manual until a portal works | Manual clinical items exist. File import does not |
| Dental, massage, chiropractic | Notes and dates | Likely PDF or a typed note. No vendor API was reviewed | The owner uploads | Manual | Open storage decision |
| ChatGPT as a bridge | Whatever the owner already connected inside ChatGPT | Can move a reviewed summary into this app. It is not a sync engine and it is not Oura archival | Existing OAuth scopes | Depends on a person or a session running the tool | Reads exist. A standing transfer does not |
| 3D scan apps | A mesh or a derived circumference | Not scheduled. Phone scans miss tape by centimeters in the research already filed | A scan vendor would be a new agreement | Would be a second body series beside tape and photos | Researched, not scheduled |

Comparison for a new metric:

* Direct vendor connection when the API is available to a personal app, the owner can consent, and the retention terms fit a private archive.
* Phone health hub when the data already lives on the iPhone and a native or share-sheet step is acceptable. It will not run as a background web sync.
* Manual import when the vendor only offers a file. This is the current working path.
* External assistant bridge when the owner already has the account connected in ChatGPT and the transfer is reviewed. It is a convenience, not the system of record.

When two sources can supply the same daily number, the app suggests one primary from the plan and the owner confirms it. The other source stays stored and labeled. Changing the primary is an event on the timeline. Original rows stay. Daily totals and meal entries are never merged into one row.

### History window

| Category | Proposed dashboard life | After 90 days | Delete, or only hide |
| --- | --- | --- | --- |
| Setup, plan rules, partners, grants, targets | Kept. This is the configuration | Still shown | Open only for account deletion |
| Meals, day activity, journals, photos, scans | Rolling 90 day working view. Meals grouped by day | Hidden from the day-to-day dashboard. Still in export and backup until a deletion decision | Open. Hiding is the proposal. Deleting is not |
| Labs | Dated results the owner can compare across years. Already kept past 90 days as current clinical items | Stay available | Open for a longer archive versus the same retention as everything else |
| Scores and saved summaries | Kept with the formula version so a later question can explain an old day | Readable from history. The Today page stays on the window | Open |
| Assistant access | Follows the same grants and the same hidden-versus-deleted rule | An assistant must not describe a hidden day as if it were gone, and must not read a deleted day | Depends on the deletion decision |
| Backups | Encrypted snapshots already exist | An old snapshot can still hold a row the dashboard no longer shows, until that snapshot ages out | Documented today: a live delete does not erase every backup |

The open decision is whether aging off the 90 day view removes the row from the database or only from the daily screens. That choice also decides export contents, assistant access, and whether a saved summary computed from those days remains.

## Subscription and gifting direction

Proposed clarification, November 10, 2026. Product idea and pricing direction only, not implemented or scheduled. This supersedes earlier wording that treated the partner assistant as the sole paid feature; it does not authorize billing, agents, integrations, or account changes.

| Access option | Included features | Permission boundary |
| --- | --- | --- |
| Free core | Owner dashboard, core Headspace score, and Holding Space partner dashboards | Existing owner controls and explicit per-partner sharing apply |
| Paid owner agent tier | Owner dashboard chatbot, optional supported wearable connections, agents that help update CX83 Fit and supported connected apps, and chatbots for the owner's Holding Space partners | Each feature and connection needs the owner's choice and appropriate permissions. Each partner chatbot sees only information explicitly shared with that partner and allowed for that assistant |
| Standalone partner chatbot | A Holding Space partner can purchase just their own chatbot when the owner does not purchase the agent tier | No owner agent tier or access for other partners is included. Only information the owner explicitly shares with the purchasing partner may be used, subject to assistant grants |
| Gifted owner tier | A Holding Space partner, family member, friend, or other supporter can purchase the full owner agent tier for the recipient | The recipient must accept the gift and controls which features, devices, apps, and sharing permissions to enable |

Gifting pays for access to features, never access to the recipient's information or control of their account. Payment must never grant additional visibility, monitoring rights, or authority over permissions. A giver who is also a partner keeps only the grants the owner explicitly chooses; gifting neither adds a partner nor expands existing grants. The recipient can decline the gift or leave individual features and connections disabled.

Gift duration, renewal, cancellation, and responsibility for future payments must be clearly disclosed before purchase and acceptance. No automatic charges to the recipient without explicit consent. Exact prices, billing provider, gift durations, and renewal mechanics remain open product decisions. When paid access ends, retain the free core and existing records under the app's retention policy; expiration must not itself delete records or widen sharing. The existing open retention decisions remain open.

Wearable support is optional and depends on verified capabilities of each device. Purchasing or accepting the tier does not connect a device or enable capture. Connected-app writes require appropriate user permissions and supported official interfaces. MyFitnessPal direct writes remain conditional on official approved API access and write entitlement; the existing ChatGPT connection does not establish either. Existing review, confirmation, provenance, and revocation requirements still apply. The modular wearable idea below remains a separate, unscheduled proposal.

Documentation checkpoint: reconciled the pricing summary, confirmed requirement 7, partner-assistant description, later billing scope, and open pricing decisions with this direction. The November 10 wearable idea and unrelated roadmap content are preserved. Validation is review of the diff against a pre-edit copy, not an application test. Next for this pricing proposal: decide prices and gift terms before separately authorizing billing implementation. These decisions do not block the basic dashboard or separately authorized external-assistant foundation.

Documentation checkpoint, November 10, 2026: clarified the foundation, manual/file/connected entry paths, optional AI analysis and updates, and gradual rollout; reconciled Claude priority and the external-assistant dependency. Reviewed against a pre-edit copy. No code, connection, billing, or account change is included. Next: verify the foundation workflows before expanding capabilities.

## Milestones

Sequence reconciliation, November 10, 2026: [Headspace H0 through H7](../Headspace/06_BUILD_PLAN.md#milestones) is the sole authoritative delivery sequence for this work. Complete the evaluated Headspace owner dashboard and scoring release at H6 before beginning the Holding Space partner dashboard or live notifications at H7. The older M labels below preserve feature ideas and acceptance details only; they are not a competing execution order. Existing dashboard and scoped external-assistant foundation work remains valid and does not depend on a partner dashboard or paid assistant.

| Retained feature reference | Placement under the authoritative sequence |
| --- | --- |
| M1 partner slice and M2 partner grants | Deferred to H7 after H6; owner plan configuration can support H1 through H4 without a partner implementation |
| M3 score version and coverage | H1 and H5 through H6; no dependency on M1 or M2 |
| M4 selected trackers | Bounded H1 through H4 context and selected routines; additional trackers remain later ideas |
| M5 imports and primary source | H2 through H4, with verified source identity and existing import review |
| M6 built-in owner assistant | Optional later work; not required for H1 or the external-assistant foundation |
| M7 external assistant grants | Existing foundation and applicable H0 through H4 boundaries; no partner dashboard prerequisite |
| M8 live alerts | H7 only, after partner permissions, separate consent and release review |
| M9 location trial | Deferred and unscheduled; separate authorization and physical-device evidence required |

The following feature slices retain their original acceptance intent subject to this mapping and the newer Headspace contracts. Tests stay synthetic until an explicitly authorized real-path check. A local pass is not a ChatGPT session, a physical iPhone, or a sent text.

### M1. Plan, one partner, one shared trend

Retained partner feature slice, deferred to H7 after H6. It proves a privacy boundary the app does not have yet; it is no longer the first buildable slice.

Dependencies: owner authentication as it exists. No Twilio purchase. No score change. No new device.

Acceptance:

* The owner creates one plan from a template or from custom, with a goal and one shared signal.
* The owner adds one partner with a name and a phone number. A sixth active partner is refused.
* The owner shares one progress photo with partner A and leaves partner B without that grant.
* The owner can open a preview that matches what A will see, including the Trends section.
* Partner A, in a partner session, can open the photo. Partner B receives a denial that does not reveal the photo. After revoke, A is denied on the page and on the file URL.
* An assistant-context function for A excludes the photo after revoke, even though the assistant itself is not built in this milestone.
* Synthetic fixtures only. The owner session still cannot be used as the partner session.
* Existing measurement, journal, Holding Space, and photo tests still pass.

Phone verification and live SMS can be stubbed in this milestone with an explicit test double. The states for verified, accepted, and text consent exist in the model so they are not invented later. A real text remains blocked while `SMS_ENABLED` is unset.

### M2. Grant matrix and preview

Within H7, depends on the retained M1 partner identity slice. This is not a prerequisite for Headspace H1 through H6.

Acceptance: separate controls exist for photos, scans, journals, labs, cycle, glucose, location, and alert details. Summary and entry can be granted independently where both exist. Empty categories explain that the data type is not collected yet. Revoke is immediate for every category that has a file or a query. Email stays optional.

### M3. Score version and coverage

Maps to H1 and H5 through H6. Keep current Daily State intact until an evaluated replacement is accepted. No dependency on the deferred M1 or M2 partner slices. Candidate scoring details and coverage gates are owned by [the Headspace scoring proposal](../Headspace/02_SCORING_AND_VALIDATION.md).

Acceptance: a new formula is versioned and does not silently replace `daily-state-1`. A missing expected log stays missing. A disabled tracker, a stale source, and a never-planned metric are labeled differently. Thin coverage is visible. Observations that are out of the score can still be read by the owner. Urgent language uses the separate screen and does not change the number by itself. Candidate thresholds from the table above are still proposals until the false-alarm review exists.

### M4. Plan-selected trackers

Maps to selected H1 through H4 capabilities with a versioned rule record. Do not expand the initial four-source scope to implement every retained tracker idea.

Acceptance: the owner turns on mood, stress, craving, sleep, activity, nutrition, spiritual practice, cycle, glucose, illness, pain, and the listed gut and breathing symptoms only where the plan includes them. Structured fields keep time, severity, duration, source, and units when supplied. Glucose can store meal context. A correction updates an extracted field without deleting the source text.

### M5. Imports and one primary source

Maps to H2 through H4 and depends on existing reviewed imports and verified source identity.

Acceptance: a synthetic lab PDF or CSV is proposed into a destination, shown with uncertain fields and a duplicate, and saved only after confirm. Two synthetic calorie totals suggest one primary. The owner can switch it. Meal rows and daily totals stay separate. The declined source remains stored and unlabeled as the total.

### M6. Owner assistant, read only

Optional later built-in assistant, not a Headspace release prerequisite. Reuse applicable owner permission checks and versioned coverage language; any partner assistant still waits for H7 grants.

Acceptance: the assistant can draft a plan and explain a trend using only permitted metrics. A blocked category such as labs is absent from the prompt and from the answer. It cannot save a plan, a grant, or an alert rule without a separate owner confirmation. No background job.

### M7. External read-only grants

Part of the optional external-assistant foundation. Reuse the server permission checker and applicable owner grants; deferred M2 partner grants are not a prerequisite; it does not depend on building M6's in-app assistant or launching billing. Verify the existing ChatGPT connection first and add Claude support next. Claude is planned, not connected. Gemini remains an open later choice. New scopes start read only; expand to explicitly authorized writes only after the specific interface and operation are verified.

Acceptance: an external token's grant is narrower than the owner's page when the owner says so. A write attempt on a new record type is rejected. No scheduled push.

### M8. Live alerts

Deferred to H7 after H6, partner identity, specific owner authorization, separate recipient consent, a verified authorized sender, and the cooldown design. Apply the [data integrity notification proposal and review gates](../Headspace/06_BUILD_PLAN.md#proposal-data-integrity-and-consent-based-notifications) before any such feature is implemented. Urgent automation still waits on its separate qualified review gate.

Acceptance: a synthetic sustained-change rule texts only opted-in partners, once per cooldown, with the allowed wording. STOP, a failed send, a missing delivery, and "I checked in" are distinct. Nobody acknowledging leaves a visible waiting state and does not call 911.

### M9. Location trial

Deferred and unscheduled. Requires separate authorization and physical iPhone evidence; it does not gate Headspace H0 through H6.

Acceptance: a written result says what the Home Screen web app recorded in the foreground and what it failed to record with the phone locked. The product keeps arrival and departure only if that trial supports the rule. A pocket rule that the web app cannot see is marked as needing a native companion, and it is not built inside the web app under another name.

### Explicitly later

Dental, massage, and chiropractic storage. 3D scans. Native HealthKit. Dexcom or other CGM. A monitoring-center contract. Automated emergency routing. Owner agent tier, standalone partner chatbot, and gift billing. Any change to the live Oura disablement or the MyFitnessPal ChatGPT account.

## Open decisions

1. SMS operating price and whether owner plans have a numeric limit. Owner dashboard, partner dashboards, and core score stay free either way.
2. Whether data older than 90 days is hidden or deleted, including labs, assistant access, exports, and saved summaries.
3. Storage and use for dental records, massage notes, and chiropractic notes.
4. Numeric defaults for the next score: baseline length, which window counts as a routine change, alert threshold, cooldown length, and what "thin evidence" displays.
5. Whether AWARE, PHQ-9, GAD-7, or a PROMIS short form is offered as an optional separate check.
6. Which partners are eligible for an urgent text, what the message may say, and how long "nobody answered" waits before the owner is prompted again.
7. Whether the urgent screen's 911 control is only a dialer link.
8. Whether a Life Alert style subscription is in scope at all.
9. Phone verification vendor details, and whether OTP uses Verify or the same A2P campaign as Reach Out.
10. Whether a user-sent `sms:` link is shipped before the Twilio number exists.
11. Adult partners only, until someone decides otherwise. This pass assumes adults.
12. Which file types count as a "supported health export" beyond the CSV formats already documented.
13. How to implement and verify the planned Claude connection and supported read/write operations. Whether Gemini will be connected remains open.
14. Whether the native companion for location is ever worth a separate app.
15. Exact prices and terms for the owner agent tier and standalone partner chatbot, billing provider, gift durations, renewal mechanics, cancellation terms, and responsibility for future payments. No payment processor is selected. The consent and free-core protections in Subscription and gifting direction apply regardless of those choices.

## Gaps that would change privacy, reliability, or usability

* A partner session has to be a different principal from the owner. Two login names on one owner account will leak a shared photo if they are reused as "my wife" and "my sponsor".
* Original photo files can contain GPS and the picture itself can show a place. A photo grant should default to the stripped display image, and the preview should say so.
* Phone numbers and consent records are personal data. They belong in the same export, backup, and deletion story as health rows. STOP must keep working if the dashboard account is removed.
* Carrier registration can block every text, including a verification code, after the code is written. The UI has to keep saying "not sent" until a real delivery is observed.
* An assistant that sees the owner prompt and the partner prompt in one process will leak unless the server builds a fresh context per principal.
* Cycle, glucose, journals, location, and labs are high-harm categories. They default off. A template must not opt them in silently.
* Symptom tracking plus an automatic alert can look like a medical device or a monitoring service. That is why urgent automation is gated. The urgent screen has to avoid sounding like dispatch.
* The 90 day view will confuse people if old labs vanish or if old photos disappear from backup language. The hide-versus-delete decision should land before M4 stores new sensitive categories.
* iPhone background limits will make a location rule look broken if the app treats a locked phone as a missed gym visit.
* Overlapping plans can double count one walk or one meal. The primary-source rule has to exist before a second plan turns on the same metric.
* Shared phones: a partner who uses the owner's unlocked browser is the owner's session. Sign-out and a partner-specific login need to be obvious.
* Crisis text stored in a journal becomes visible to anyone later granted journals. The urgent record needs its own grant, which is the alert-detail control.
* Time zone is America/Chicago for this owner. A "5 AM gym" rule has to use the plan's zone, including daylight saving days.
* This planning pass did not rerun the test suite and did not inspect the live server.

## Source notes for the research in this file

Relapse and baseline: [Moore and colleagues, 2014](https://doi.org/10.1037/a0034127), [Scott and colleagues, EMA after treatment](https://pmc.ncbi.nlm.nih.gov/articles/PMC8237687/), [AWARE validation](https://pmc.ncbi.nlm.nih.gov/articles/PMC3135308/), [sleep and craving EMA](https://pmc.ncbi.nlm.nih.gov/articles/PMC7080296/), and the sources already cited in [BODY_SCAN_RESEARCH.md](BODY_SCAN_RESEARCH.md). Those papers describe treatment samples. They are not a personal risk score.

SMS and emergency: Twilio pricing and A2P docs linked above, [NENA](https://www.nena.org/page/smartphoneapps), [FCC text-to-911](https://www.fcc.gov/consumers/guides/what-you-need-know-about-text-911), [RapidSOS platform FAQ](https://pages.rapidsos.com/our-latest/clearinghouse-faqs/). Life Alert is a private monitoring company with its own centers. It is not an API reviewed for this app.

Devices: [Oura and Apple notes](INTEGRATIONS.md), [Google Fit migration](https://developer.android.com/health-and-fitness/health-connect/migration/fit), [Withings partner hub](https://developer.withings.com/), [Dexcom getting started](https://developer.dexcom.com/docs/dexcom/getting-started). Vendor approval and delay claims should be rechecked on the vendor's own page before an integration milestone starts. iPhone background limits should be confirmed on a device in M9, not taken from a 2026 web article alone.


## Future idea: modular wearable AI observation and activity logging agent

Proposed, November 10, 2026. Idea entry only, unscheduled and not implemented. Any research trial or build needs separate authorization; existing milestones, integrations, and permissions remain as recorded above.

A modular agent could turn user-approved wearable observations into reviewed meal, workout, and activity records for CX83 Fit and supported health/fitness apps. Separate device adapters, AI skills, and app connectors would let users choose compatible inputs and destinations without tying the product to one wearable or provider.

* **Opt-in inputs:** Cameras, smart glasses, and other compatible wearables could supply event-triggered image/video snippets and sensor readings. Users choose capture triggers and can pause or stop collection; continuous recording is not the default. Device access, battery impact, and background limits need evaluation.
* **AI skills:** Identify candidate foods and meals, estimate portions and nutrition quantities, and show uncertainty for user confirmation or correction before logging. Seeing food does not prove it was consumed. Recognize candidate workouts, exercises, repetitions, and other activities using available visual and sensor evidence; uncertain results stay pending review.
* **Structured event timeline:** Keep event time and time zone, source device, observation versus AI estimate, confidence, confirmation/correction state, and destination sync status. Preserve provenance and prevent duplicate meals or activities across devices and apps, following the existing primary-source rule. Raw snippets need not be retained with the structured event.
* **User-controlled integrations:** Separate permission for each app, data type, read/write action, and any future automatic logging rule. Grants are optional, narrowly scoped, revocable, and enforced by the server. Start with reviewed records in CX83 Fit; connect other supported health/fitness apps only after verifying their official interfaces and user authorization. MyFitnessPal direct writes are conditional on official approved API access and write entitlement; the existing ChatGPT connection does not establish either. If unavailable, keep a reviewed local record or supported manual export without scraping or bypassing access controls.
* **Privacy and consent:** Process on-device where possible; obtain explicit consent before cloud processing or sharing. Minimize capture and retention, encrypt retained data, and provide deletion controls and visible capture status. Include bystander safeguards such as avoiding private spaces, obtaining consent where appropriate, and discarding or redacting unrelated people and sensitive content. No identification of bystanders or silent partner sharing.
* **Research candidates only:** Evaluate Meta Wearables Device Access Toolkit, Omi, and open-source exercise recognition for device compatibility, actual image/video/sensor access, accuracy, licensing, privacy, and operating cost. These are possible evaluations, not selected dependencies or verified capabilities.

Next decision: whether to authorize a bounded feasibility study for one capture source, one meal or workout skill, and reviewed CX83 Fit logging. This entry authorizes no installation, connection changes, data capture, API writes, or implementation.


## Proposed page and navigation refinements

Recorded November 10, 2026, from Mike's six screenshots and requested review. Planning only; no interface implementation or live verification occurred in this documentation pass.

Preserve the current structure and visual foundation: Today presents the daily essentials and direct actions, the main navigation opens frequently used pages, and More provides deeper information and tools. Keep Headspace prominent, its explanation available under Details, and the consistent colors, cards, and navigation. These are focused refinements, not a homepage redesign or a reason to expose every future feature at once.

* **Clarify Journal versus Diary:** Rename the food-logging navigation label and page title to Food Diary so people can distinguish meals from personal journal entries immediately. Keep naming consistent wherever the destination appears.
* **Organize More:** Group links into understandable sections such as Health information, Goals and reviews, and Connections and data tools. Clarify the difference between Labs, meds, diagnoses and Lab results so users know which destination they need. Preserve access to existing tools.
* **Make empty states actionable and accurate:** Use wording such as No sleep recorded instead of No sleep, so missing records do not imply no activity occurred. Where supported, offer the relevant next action, such as Add sleep, Import a file, or Connect a source. Do not offer an unavailable connection as if it works. Keep unknown distinct from a recorded zero.
* **Default the journal date sensibly:** Start a new entry on the day the user selected, or today in their configured time zone when no day was selected. Leave the date editable for backdated entries.
* **Use everyday language in journal lists:** Prioritize the entry date and preview. Remove internal presentation such as date, Etc/UTC, and No structured observation from the ordinary list, or translate genuinely useful status into plain language. Preserve source timestamps and metadata in the underlying record and appropriate detail views.
* **Match Headspace's empty visual state to its label:** When the screen says Not enough to score, the bar should look neutral rather than fully filled. Unknown and legitimate zero must remain distinct and understandable. The screenshot showed a full white bar; this is screenshot evidence, not a new claim about the current source or deployment. Existing overview/Plan bar corrections and independent re-review are already recorded in CURSOR_HANDOFF.md. Continue that workstream and verify its final result rather than starting a duplicate fix or weakening CSP.
* **Later, adapt Today to the person's plan:** Preserve the layout while letting the displayed daily measures reflect the person's selected goals. The current nutrition and body-tracking emphasis fits Mike's use; other plans may prioritize different measures. Keep Headspace and navigation consistent and avoid adding every tracker to every homepage.

Review criteria for a future implementation: a new user can distinguish food logging from journaling, find deeper information in More, understand missing data, and identify an available next action. Check the affected pages at desktop and phone sizes, including empty and populated states. Record implementation, local verification, and deployment separately.

Documentation checkpoint: preserved a pre-edit copy and reviewed the isolated diff. Earlier subscription, gifting, foundation, and wearable ideas remain unchanged. Next: prioritize these refinements within the existing UI workstream; this entry does not authorize code changes or deployment.
