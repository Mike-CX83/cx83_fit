# Open source reuse decisions

Checked November 10, 2026. Repository metadata and documentation were inspected. No dependency was installed, benchmarked, security audited, or approved for production in this task.

## Smallest useful stack

Keep Django, the existing database, journal service, source records, OAuth, Chart.js, and existing validation patterns. Implement the first scoring formulas in ordinary Python. Reuse the current Oura catalog and ingestion work once its provenance defects are resolved. Add a library only for a demonstrated gap.

The most promising additions are medspaCy for a focused extraction evaluation, a FHIR model library for a verified clinical import, and SpeziHealthKit if a native bridge becomes necessary. Simple rolling medians and coverage rules do not need a machine learning platform. All adoption decisions still need compatibility and license checks at a pinned version.

## Library and platform comparison

Push dates below are observed repository activity, not proof of a stable release or maintenance quality. All listed repositories were unarchived when checked.

| Project | License observed | Last push, UTC date | Reusable capability | Decision |
| --- | --- | --- | --- | --- |
| [medspaCy](https://github.com/medspacy/medspacy) [O01](07_SOURCES.md#o01) | MIT | 2026-06-04 | Clinical text segmentation, context, negation, uncertainty, modular extraction | Evaluate selected components on journal language. Clinical-note rules need adaptation; no mental health scoring model is supplied |
| [ruptures](https://github.com/deepcharles/ruptures) [O02](07_SOURCES.md#o02) | BSD 2 clause | 2026-10-06 | Retrospective change point detection | Later trend analysis if simple windows fail. It detects statistical change, not relapse |
| [River](https://github.com/online-ml/river) [O03](07_SOURCES.md#o03) | BSD 3 clause | 2026-11-10 | Streaming statistics, anomaly detection, and learning | Later research candidate. Do not let an online model silently change production weights |
| [fhir.resources](https://github.com/nazrulworld/fhir.resources) [O04](07_SOURCES.md#o04) | BSD, three conditions verified in LICENSE; metadata says NOASSERTION | 2026-09-14 | Typed FHIR resource parsing and validation | Evaluate for clinical imports. Its current default is R5 with R4B/STU3 support; verify the real source's R4 compatibility rather than assuming it |
| [SpeziHealthKit](https://github.com/StanfordSpezi/SpeziHealthKit) [O05](07_SOURCES.md#o05) | MIT | 2026-10-08 | Native Swift HealthKit collection and background workflows | Preferred candidate for a later small iPhone companion. It does not make HealthKit available inside the current web app |
| [NeuroKit2](https://github.com/neuropsychology/NeuroKit) [O06](07_SOURCES.md#o06) | MIT | 2026-11-08 | Raw physiological signal processing and HRV methods | Defer. Daily provider HRV summaries are not raw beat intervals, and reprocessing them cannot recover missing signal data |
| [RADAR Questionnaire](https://github.com/RADAR-base/RADAR-Questionnaire) [O07](07_SOURCES.md#o07) | Apache 2.0 | 2026-09-09 | Scheduled questionnaires and active remote monitoring | Learn from the interaction and protocol design. Deploying the full research platform is unnecessary for this Django pilot |
| [LAMP Cortex](https://github.com/BIDMCDigitalPsychiatry/LAMP-cortex) [O08](07_SOURCES.md#o08) | BSD 3 clause | 2026-05-18 | Features derived from digital phenotyping data | Reference for feature definitions and later evaluation; LAMP data assumptions require adapters |
| [mindLAMP dashboard](https://github.com/BIDMCDigitalPsychiatry/LAMP-dashboard) [O08](07_SOURCES.md#o08) | AGPL 3.0 only, verified in LICENSE.md | 2026-11-10 | Broader mental health dashboard and platform | Do not replace CX83 Fit. Review network copyleft obligations before any code reuse; component licenses differ |
| [RAPIDS](https://github.com/carissalow/rapids) [O09](07_SOURCES.md#o09) | AGPL 3.0 | 2026-03-26 | Reproducible features from mobile and wearable streams | Research reference, not first runtime. Broad sensing pipeline and license obligations exceed the initial scope |
| [VADER](https://github.com/cjhutto/vaderSentiment) [O10](07_SOURCES.md#o10) | MIT | 2026-03-02 | Lexicon-based sentiment | Exclude from score calculation. May be a research baseline only; positive tone is not recovery and negative tone is not relapse |

## Relapse-oriented code that was actually found

| Candidate | What it contains | Why it is not a deployable Headspace predictor |
| --- | --- | --- |
| [TS4H 4Hz, 4 Pages](https://github.com/AbhishekSinghDhadwal/TS4H_4Hz_4Pages), Apache 2.0; last push 2025-12-17 [O11](07_SOURCES.md#o11) | CPU-oriented feature/model pipeline, subject-separated evaluation, streaming inference | The README uses WESAD, exam stress, and CAN-STRESS datasets with high-frequency sensor channels. This does not establish longitudinal relapse prediction from Oura daily summaries |
| [HRV AUD calibration](https://github.com/Om-C2026/hrv-aud-calibration), MIT; last push 2026-10-11 [O12](07_SOURCES.md#o12) | HRV stress-state analysis and cross-device comparisons | The repository identifies stress as a proxy and an ambulatory comparison of one person. It says longitudinal AUD validation is still needed. Do not reuse a stress AUROC as relapse accuracy |
| [NLML](https://github.com/nicolasleenaerts/NLML), no license established; last push 2026-02-01 [O13](07_SOURCES.md#o13) | R scripts originally developed for person-specific and pooled EMA prediction | Methodology reference only until reuse rights and compatibility are resolved; public source does not itself grant an OSS license |
| [Wyant and colleagues' study materials](https://osf.io/xta67/) [R05](07_SOURCES.md#r05) | The 2026 paper says questionnaires, data, preregistration, and scripts are available | The repository returned an access error in this session. Code, licenses, and pretrained artifacts were not inspected. Treat this as a targeted follow-up, not verified reusable software |

Research code can help reproduce feature engineering and evaluation. It cannot supply missing clinical validation or device compatibility. No ready-made package was accepted here as a general predictor for alcohol, other drugs, gambling, and compulsive behavior.

## Existing validators and bounded evaluation candidates

Dependency check, November 10, 2026: the actual working checkout's `requirements.lock` already includes `pydantic==2.14.3` through `mcp` and `mcp-types`, and `jsonschema==4.26.0` through `mcp`. Neither is a direct entry in `requirements.in`. Reuse existing validation patterns rather than proposing a new installation. If application code later relies on either directly, review whether it should become an explicitly declared direct dependency through the normal lock workflow. This manifest read is not proof of an installed runtime version or a new compatibility test. [O16](07_SOURCES.md#o16).

| Candidate | Verified scope | Decision |
| --- | --- | --- |
| Hypothesis [O14](07_SOURCES.md#o14) | Python property testing; repository license is MPL-2.0, with noted exceptions for included third-party code | Optional synthetic test dependency for missingness, duplicate/retry, correction, and coverage invariants. Not in the inspected manifests; not installed by this task. It tests software properties, not clinical validity or scoring efficacy |
| SurveyJS Form Library [O15](07_SOURCES.md#o15) | MIT form-rendering library | Consider only if existing Django forms cannot meet a demonstrated questionnaire UI need. Survey Creator, Dashboard, and PDF Generator are separate proprietary products requiring paid developer licenses; Form Library's MIT license does not cover them or the questionnaire content |

No new scoring engine is selected. Formal instruments retain their wording, recall period, response options, and scoring. UI/schema validation and property tests cannot establish that new Headspace weights or adapted instruments are valid; the existing evaluation gates remain.

## Selection and adoption gate

For each proposed addition, record the exact version or commit, license text and notices, supported Python or iOS version, transitive dependencies, model or dataset terms, vulnerability review, test coverage relevant to the feature, and removal path. Check compatibility with this project's existing Python 3.13 environment and locked dependencies in an isolated environment.

Compare the component against an existing simple implementation. For extraction, measure supported fields, negation, subject identity, time, and correction burden. For trends, compare with the current median/window baseline. For imports, validate source versions, units, revisions, and duplicates. Reject a dependency that adds operational burden without useful improvement.

Do not install all candidates as a stack. In particular, a new Kafka platform, second database, vector database, model server, and background AI agent are not prerequisites for the first Headspace release.

## Agent capabilities to specify later

These are proposed responsibilities, not skills installed by this planning task:

| Capability | Input and allowed output |
| --- | --- |
| Journal observation extraction | Authorized text to supported typed proposals with exact source spans |
| Evidence explanation | Authorized computed result and reasons to a concise explanation with source dates |
| Trend review | Comparable time series and known context to associations and questions, not causal diagnoses |
| Clinical context review | Selected permitted clinical records to a relevance summary with dates and uncertainty |
| Source reconciliation | Provenance metadata to duplicate candidates and a proposed source choice |
| Plan revision assistance | Owner request and current plan to a reviewable proposal; no silent rule activation |

Prefer the existing authorized conversational client first. The server validates, records, and computes. A later in-app model runtime must have explicit data access, cost, retention, failure, and retry behavior. When AI is unavailable, structured entry and deterministic scoring must still work.
