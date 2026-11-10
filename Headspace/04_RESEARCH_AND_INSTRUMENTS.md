# Research and measurement choices

Research checked November 10, 2026. This is a focused evidence review for a product plan, not a registered systematic review or a clinical validation study. Primary studies, instrument owners, official platform documentation, and original repositories were prioritized. Search coverage included alcohol, other substance recovery, gambling, compulsive behaviors, EMA, physiological monitoring, questionnaires, and reusable software.

## Findings that shape the design

| Finding | Evidence and limit | Product consequence |
| --- | --- | --- |
| Current behavior, craving, and affect can inform near-term recurrence | A study of 43 adults used repeated EMA and found useful associations, but its sample and horizon are narrow [R03](07_SOURCES.md#r03) | Collect brief explicit observations with timestamps; do not import its probabilities into Headspace |
| Prediction horizon matters | A 2024 study used 151 people in early alcohol recovery and 4 daily reports to study hour, day, and week horizons [R04](07_SOURCES.md#r04) | Once-daily check-ins cannot be assumed to reproduce a model trained on four reports a day |
| Longer warning windows are being studied | A 2026 study using the same sized early-recovery cohort reported useful discrimination across future windows and weaker performance for some groups [R05](07_SOURCES.md#r05) | Test fairness and transportability; do not describe this as independent confirmation in a different broad population |
| Wearables plus EMA are feasible, with adherence challenges | A 2026 Oura and peer-support feasibility trial enrolled 229, but only 63 provided at least 30% of the required data across phases [R08](07_SOURCES.md#r08) | Missingness and engagement are central engineering requirements; feasibility is not universal predictive validation |
| More passive data is not automatically better | A study of cellular communication features in 144 people did not show clear incremental discrimination over baseline features [R19](07_SOURCES.md#r19) | Keep location and phone sensing deferred; require measurable added value before collecting more |
| Gambling has related but distinct patterns | In a 97-person EMA study, cravings and self-efficacy related to gambling episodes and expenditure [R09](07_SOURCES.md#r09) | Reuse the observation structure, then validate a gambling module separately |
| Physiology needs context | Oura explains that physiological stress can reflect activity, illness, hormones, stimulants, and other factors [P02](07_SOURCES.md#p02) | A wearable cannot determine whether the owner is lying or drinking |
| A model's target can differ from its marketing label | Several public relapse-oriented repositories train on stress datasets [O11](07_SOURCES.md#o11), [O12](07_SOURCES.md#o12) | Read datasets and labels before adopting an algorithm |

## Instruments to reuse or evaluate

Keep published wording, response options, recall period, scoring, and version together. Extracting a few topics into a daily check-in creates a custom check-in; it does not remain the original validated instrument. Keep questionnaires separate from the daily Headspace composite.

| Instrument | Appropriate purpose | Recommendation and limits |
| --- | --- | --- |
| Brief Addiction Monitor, BAM | Monitoring substance use, risk factors, and protective factors across treatment [R01](07_SOURCES.md#r01) | Best initial conceptual structure for the recovery module. The VA cautions that it is not a refined overall total score, with limitations on composite interpretation. Use item-level change and the original version's recall window |
| AWARE | Warning signs studied in alcohol treatment and later young-adult substance treatment [R02](07_SOURCES.md#r02) | Candidate periodic review if the burden is acceptable. It has 28 items in the revised form; do not turn its sample-based probabilities into a personal relapse forecast. CASAA describes its library as free to use and for professional use |
| Penn Alcohol Craving Scale, PACS | Five items about the preceding week of alcohol craving [R06](07_SOURCES.md#r06) | Candidate optional weekly craving measure. Verify the exact instrument's distribution terms before embedding. Do not rename a one-question daily urge rating PACS |
| BARC-10 | Recovery resources and strengths [R07](07_SOURCES.md#r07) | Good candidate for a periodic view of support and resources. The original validation concerns recovery capital and sustained remission, not today's momentary relapse probability |
| WHO-5 | Five items about wellbeing over two weeks [R13](07_SOURCES.md#r13) | Useful periodic wellbeing candidate. The reviewed WHO publication has a noncommercial share-alike license; a future commercial product must resolve that specific reuse permission rather than assuming public access means unrestricted use |
| PHQ-9 and GAD-7 | Symptom screening and change over their specified recall windows [R14](07_SOURCES.md#r14) | Optional later measures when the product can handle the result appropriately. Do not fill answers from journal inference. Verify the actual version, translation, scoring, and response workflow; any safety item requires a deliberate response design |
| PROMIS short forms | Standardized domains such as fatigue, sleep disturbance, and affect [R15](07_SOURCES.md#r15) | Strong measurement ecosystem, but digital administration can require HealthMeasures permission and review. Defer until the specific value justifies integration work |
| Gambling-specific measures | Severity, harms, urges, and perceived control | Research the exact instrument and permissions during the gambling milestone. Alcohol thresholds do not transfer. No gambling questionnaire is selected for the first build |
| CSBD-19 or CSBD-DI | Screening constructs related to compulsive sexual behavior [R10](07_SOURCES.md#r10) | Later, optional, with behavior-specific review. Screening evidence is not daily relapse prediction. Do not diagnose from sexual frequency, sexual orientation, high desire, or moral disapproval |

Suggested first package: a custom brief daily check-in inspired by EMA constructs, a transparent recovery observation profile, and an optional periodic BAM-informed review. Add a formal instrument only with its original instructions and appropriate use reviewed. This keeps the main interaction small while preserving a path to stronger measurement.

## Journal research versus journal grading

No selected study establishes that an unrestricted personal journal can be converted into a calibrated cross-addiction Headspace score. Clinical language models often study different text, outcomes, and populations. For example, a psychosis relapse study using clinical notes had much lower performance on external validation than internal validation. That is a reminder to test transfer, not a reason to apply its model here. [R17](07_SOURCES.md#r17).

Use language processing to identify what the person actually said and request clarification. Keep clinical labels, numeric ratings, event timing, and negation explicit. The scoring service then evaluates the supported fields. Short writing, anger, loneliness, swearing, and distress do not establish dishonest participation.

The design hypothesis is that private reflection, transparent extraction, no disclosure penalty, and low-burden questions will support honest engagement. That hypothesis must be tested with users; it is not an efficacy claim established by the sources in this review.

## Biology and clinical context

Sleep, HRV, heart rate, respiratory rate, and temperature can reflect multiple overlapping processes. A recent wearable study of future high-risk drinking identified physiological and behavioral correlates, while explicitly acknowledging work schedules, illness, activity, and wear time as potential explanations. [R18](07_SOURCES.md#r18).

Cycle studies using Oura observed changes in some physiological signals across phases, without establishing a universal daily mood penalty. Keep observed symptoms and individually relevant context. Do not infer a hormone concentration or causal explanation from a ring. [R16](07_SOURCES.md#r16).

Relevant labs and medication changes may help interpret an observation, but this review does not establish any equation that converts thyroid results, testosterone, blood counts, diagnoses, or medication lists into Headspace points. Start with source-aware context and selective review. Expand only with a specific hypothesis and evaluation.

## What requires additional evidence

| Question | Evidence needed | Build consequence |
| --- | --- | --- |
| How much should the journal weigh? | Comparison of simple candidates, user-rated usefulness, and later outcome validation | Candidate weights remain in shadow mode |
| When does a participation change become meaningful? | Personal expected cadence, known technical availability, confirmed reasons, and prospective evaluation | Prompt and qualify evidence before making a behavioral inference |
| Does nutrition improve recovery monitoring? | Complete diaries, appropriate targets, confounder control, incremental value over the journal | Keep optional and lightly weighted in experiments |
| Can one architecture support different addictions? | Common schema plus separate cohorts, event definitions, and validation | Shared infrastructure, separate behavior modules |
| What is a useful alert burden? | Owner preferences, true event frequency, missed episodes, and false alerts per person-week | No automatic partner alert threshold chosen now |
| Can a model transfer between devices? | Matched methods, comparable windows, calibration and external evaluation | No pooled raw HRV baseline across RMSSD and SDNN |
| Can Headspace be marketed as a medical predictor? | Specific intended-use, clinical, privacy, and regulatory assessment [R12](07_SOURCES.md#r12) | No clinical prediction claim from this planning work |

## Research follow-through

Maintain a study register with population, sample, device, input cadence, outcome, horizon, missing-data handling, validation split, performance, licensing, and limitations. Record negative findings too. A paper's open access license, its dataset license, its code license, and the questionnaire's license are separate facts.

No study dataset, pretrained model, or research repository was installed or executed during this review. The next software selection step is a small isolated benchmark on fabricated or separately authorized data, followed by a documented accept or reject decision.
