# Scoring and validation

Design proposal, not a validated clinical algorithm. November 10, 2026.

## One state, several explicit kinds of evidence

Headspace describes current reported capacity and the context around it. Keep a separate, nonnumeric recovery concern result and an independent urgent concern pathway. Evidence sufficiency describes what the system knows; it is not a fourth mental health grade. Do not call the composite a probability of relapse, a diagnosis, or proof of abstinence.

The established calculation remains `daily-state-1` until a replacement is implemented, evaluated, and deliberately released. Historical scores retain their original version. The following candidate is for shadow evaluation, meaning it is calculated without changing the displayed state or contacting anyone.

## Candidate components

| Component | Candidate full-profile weight | Eligible input | Exclusions |
| --- | --- | --- | --- |
| J: journal state | 60% | Explicitly rated mood, energy, and focus, with at least two distinct dimensions | Sentiment guesses, text length, diagnoses, disclosures as penalties |
| S: sleep or recovery | 20% | One selected provider sleep score, initially Oura, for the completed main sleep period | Adding sleep score, readiness, HRV, and stress as four independent votes |
| N: nutrition plan alignment | 10% | Confirmed complete diary and a current, appropriate owner-approved plan | Missing meals treated as zero, generic calorie targets, exercise calories treated as exact |
| R: selected routines | 10% | Outcomes for a small set of agreed applicable practices | Unknown outcomes, rewarding device ownership, re-counting journal completion |

These weights encode the proposed priority of the journal. They are not estimated effect sizes and have not been proven to predict an outcome. Also evaluate a journal-only baseline and a simple journal plus sleep model. Prefer the smallest model that is useful.

### J calculation

Keep the initial 0 to 10 positive-direction anchors for mood, energy, and focus. For the latest confirmed eligible rating in each distinct dimension, calculate `J = 10 * mean(ratings)`. Require at least two distinct dimensions. A qualitative journal can generate a score after the owner confirms anchored responses. Repeating one dimension does not satisfy this gate.

If future dimensions use opposite directions, their registry entries must define the transform. Distress is not assumed to be the inverse of energy. Craving and coping confidence stay in the recovery rules rather than being silently inferred from mood.

### S calculation

For the first Oura profile, use the native daily sleep score as supplied, with its date and source version. Reuse its meaning; do not recalculate it from stages. Missing sleep score remains unknown. Readiness and physiological measures explain context but do not add extra full weights to the same signal family.

If another provider is selected later, use a provider-specific adapter and baseline. Similar numeric scales do not make two proprietary scores interchangeable. Raw sleep duration and regularity can support a separately named future component after evaluation; they must not be labeled Apple's Sleep Score. A manual sleep rating belongs to a manual profile, with its own provenance.

### N calculation

First present complete-day trends and meal regularity. Add an actual N component only when the user has chosen an appropriate nutrition plan and explicitly enabled it. A journal-only or recovery-only user does not need calorie tracking.

For a future configurable target-band implementation, every selected nutrient needs an approved lower bound L, upper bound U, direction, and an outside-band tolerance D. For measured value x, distance is zero inside the band and the distance to its closest boundary otherwise. A candidate alignment value is `100 * max(0, 1 - distance / D)`. Average only according to the plan's declared weights, with all required fields known. Require `D > 0`, compatible units, and a confirmed complete day. No default caloric prescription, universal tolerance, or medical recommendation is supplied here.

Use a three-complete-day view for the pilot, with at least two complete days and coverage shown. This cadence is also a hypothesis. A single large meal should not dominate. A partial diary can show what is recorded, but cannot prove undereating. A plan change creates a new target version. For an eating disorder history or calorie tracking that increases distress, leave this component off and offer an owner-chosen meal routine instead.

### R calculation

For selected nonoverlapping practices with known outcomes, use `100 * completed_weight / applicable_weight`, initially equal weights. Require all applicable outcomes to be known for a finalized R. Planned rest or an agreed exception is not failure. No applicable practices means the component is inactive, not 100.

The same meal, sleep period, coping action, or journal fact must not be counted in several components. Maintain an evidence family tag and an allocation policy. Journal participation governs freshness and coverage; do not count it again as a routine penalty.

## Profiles and missing components

Define the profile before observing the result. A missing source is not silently removed from an active profile to improve its score. A person can intentionally change profiles; preserve when and why.

| Profile | Components | Meaning |
| --- | --- | --- |
| Journal only | J | Fully supported mode; no wearable requirement |
| Journal and recovery | J, S | Native sleep score or a separately configured manual recovery component |
| Full personal pilot | J, S, N, R when explicitly enabled | The owner's selected sources and plan |

For available eligible components P, `H = sum(w_i * value_i for i in P) / sum(w_i for i in P)`. Also calculate `coverage = observed_active_weight / planned_active_weight`. This renormalization must be visible in the provenance and qualification, never disguised as a complete full-profile result.

Candidate gates to test: J must be valid and current. Coverage of at least 80% permits a current result; 60% through less than 80% permits a visibly limited provisional result; below 60% produces no current composite. Journal-only mode has complete coverage when J is valid, but its explanation says it is based on self-report. These are operating hypotheses, not validated cutoffs. Do not compare a full-profile day with a journal-only day as if the evidence were identical.

The existing 70 and 40 boundaries can be retained only as initial evaluation bins: Steady at or above 70, Stretched from 40 to below 70, Running low below 40. New weighting changes their interpretation, so evaluate and calibrate the boundaries before adoption. No numeric result is presented as the main user-facing grade.

Fabricated full-profile calculation: J=60, S=50, N=80, R=75 gives H=61.5, provisionally Stretched. If S is temporarily missing, observed coverage is 80% and the internal result is 64.375, explicitly missing sleep. If J is missing, no fresh Headspace is issued even if all device values look favorable. A journal-only J=70 is Steady based on the check-in, not a claim that every health domain is covered.

## Recovery concerns cannot be averaged away

Use separate explicit observations for each chosen behavior: urge intensity, coping confidence or perceived control, access to personally defined triggers, recent behavior, support actions, and meaningful routine changes. Candidate rules should consider combinations and time, not a single universal factor.

Examples for evaluation include a marked personal rise in urges together with reduced coping confidence, or confirmed disengagement from selected recovery support together with another independently supported concern. Keep the underlying observations and show the reason. Strong current concerns should remain prominent even when Headspace is Steady. Do not invent an undisclosed band override in the first release.

Recent use is a reported event with a time window and behavior type. It is not an inference from heart rate, calories, typing, a location, or missing wearables. Future alcohol, other substance, gambling, and compulsive behavior modules share record structures but need separate evidence, thresholds, and outcome definitions. [R03](07_SOURCES.md#r03), [R04](07_SOURCES.md#r04), [R09](07_SOURCES.md#r09).

## Participation and device absence

Track three separate things: a technical observation gap, a user-reported interruption of an agreed behavior, and a change in usual participation. The first reduces available evidence. The second can affect the selected routine. The third prompts clarification and changes the evidence qualification. Never convert all three into use or deception.

Only look for a participation shift if a routine was opted in, expected on those dates, and previously established. Do not penalize a person who has never owned a wearable. No watch data while Oura provides the selected metric is not a gap. A device producing no samples does not by itself establish that it was intentionally removed.

## Baselines and trends

Use a preceding personal baseline for the same metric, device, method, and context. Initial candidate: the preceding 28 days, excluding the current window, with at least 14 valid comparable observations. This is a testable engineering default. Before that, show raw observations and a learning-baseline state. Never replace missing days with zero.

Use medians and robust spread. A candidate robust deviation is `(x - median) / (1.4826 * MAD)`. If spread is zero or too small, use a documented measurement-resolution floor or decline to classify; never divide by zero. A deviation alone identifies change, not its cause. Check three-day and seven-day windows before interpreting persistent shifts. Do not let a rolling baseline immediately absorb a sustained deterioration; keep a versioned reference period and make resets explicit.

Account for shift work, training blocks, illness, surgery recovery, medication changes, timezones, and optional cycle context. A provider or algorithm change is a break in comparability. Separate RMSSD from SDNN HRV. Hold selected methods constant within a trend.

A backend recomputation can be immediate after an accepted event; source data may still arrive hours later. Display both event time and last import time. Journal corrections and late source revisions recompute affected results with a supersession record, not silent historical replacement.

## Urgent concerns

Potentially serious symptoms and explicit immediate safety concerns do not wait for a composite score. A confirmed sustained resting heart rate around 130 requires a medical concern pathway and contextual review; it is not evidence of drinking. Resting tachycardia has many possible causes. [R11](07_SOURCES.md#r11).

The first implementation offers an owner-facing help action and existing contact options when the owner reports a concern. It does not build autonomous emergency detection or partner dispatch. A normal composite must never suppress a directly reported urgent concern. Later automated routing requires its own validated trigger, consent, response ownership, and release review.

## Validation plan

1. Define the construct and outcome first. Capacity, need for support, craving, lapse, heavy drinking, and compulsive behavior episodes are different labels. Use the user's stated recovery goal and preserve explicit no-event reports separately from unknown days.
2. Test deterministic rules on fabricated boundary cases before private data. Include the acceptance matrix in [06_BUILD_PLAN.md](06_BUILD_PLAN.md).
3. Evaluate extraction on an independently labeled set of short, long, colloquial, negated, historical, quoted, and conflicting examples. Report precision and recall by field, unsupported assertions, correction rate, and failures involving another person.
4. Run the candidate beside current behavior in a consented private pilot, initially four to six weeks. This duration tests usability and data flow; it does not establish clinical predictive validity.
5. Compare simple baselines with each added component. Record whether nutrition or wearables add usefulness beyond the journal. Use an ablation comparison that removes one family at a time.
6. If prediction research proceeds, define a fixed horizon and episode rule before evaluation. Split by person and time; fit normalization only on the training portion; exclude future records and revisions not available at prediction time. Adjacent overlapping windows must not leak across training and test sets.
7. Report precision, recall, false alerts per person-week, missed labeled episodes, lead time, calibration if probabilities are produced, and uncertainty. Accuracy or AUROC alone is insufficient for uncommon events.
8. Evaluate separately for journal-only users, shift workers, different devices, neurodivergent communication styles, and relevant demographic groups. Report missing outcome labels rather than calling them negative events.
9. Measure trust and burden: willingness to disclose, feeling punished, abandoned check-ins, usefulness, and time spent. Any observed punitive effect requires a redesign.
10. Before external prediction claims, obtain independent clinical and statistical review, prospective evaluation in the target population, and a review of intended use. Wellness wording alone does not settle regulatory status. [R12](07_SOURCES.md#r12).

Numeric clinical performance gates remain unset until the intended outcome, event prevalence, and response burden are defined. Do not invent a success percentage to make an unvalidated model appear accepted. Hard software gates are immediate: no cross-owner disclosure, no synthetic data in personal results, no unsupported extracted facts, no duplicate weighting, and reproducible outputs for identical versioned inputs.
