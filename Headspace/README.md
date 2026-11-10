# Headspace

Research and product plan prepared November 10, 2026, Tulsa, Oklahoma.

Status: proposed design and research, ready for implementation planning. No new scoring rule, integration, alert, dependency, migration, or live release is enabled by these documents.

## The goal

Build a useful daily picture of a person's capacity and recovery support needs from their journal, selected routines, sleep, nutrition, and relevant health context. Show three familiar words: **Steady**, **Stretched**, and **Running low**. Keep any numeric calculation internal. Explain what changed, what helped, what information is missing, and one useful next action.

The journal is the center of this product. A person must be able to describe a difficult day, cravings, or a return to a behavior without earning a penalty for honesty. The underlying experience can change the picture; choosing to disclose it must not be a separate negative input. Missing check-ins and changes in participation still matter, with explicit distinctions between missing information, technical failure, and a confirmed change in routine.

This is a focused extension of CX83 Fit. Keep its Django application, private storage, journal history, provenance, authentication, imports, and existing connections. Build for the owner's current sources first: **Oura, Apple Health, MyFitnessPal, and medical records including MyChart**. Preserve a fully usable journal and manual entry mode.

## Read this package

| Document | Purpose |
| --- | --- |
| [01_PRODUCT_AND_JOURNAL.md](01_PRODUCT_AND_JOURNAL.md) | Daily experience, journal interpretation, short entries, honest disclosure, and missing participation |
| [02_SCORING_AND_VALIDATION.md](02_SCORING_AND_VALIDATION.md) | Deterministic scoring, candidate weights, uncertainty, behavior signals, and validation |
| [03_DATA_AND_INTEGRATIONS.md](03_DATA_AND_INTEGRATIONS.md) | Metric inventory, source preferences, deduplication, the four integrations, clinical and cycle context |
| [04_RESEARCH_AND_INSTRUMENTS.md](04_RESEARCH_AND_INSTRUMENTS.md) | Evidence, questionnaires, what transfers across behaviors, and what still needs testing |
| [05_OPEN_SOURCE.md](05_OPEN_SOURCE.md) | Evaluated software, licenses, maintenance observations, and reuse decisions |
| [06_BUILD_PLAN.md](06_BUILD_PLAN.md) | Ordered implementation milestones, acceptance cases, and future Holding Space boundaries |
| [07_SOURCES.md](07_SOURCES.md) | Dated primary sources, research limitations, and links |

## Decisions from the current request

1. Headspace dashboard and scoring come before the future Holding Space partner dashboard. Keep existing partner management intact; do not expand the partner product during this work.
2. Preserve the three existing state names. Remove the numeric Headspace presentation when the new UI is implemented. Provider metrics such as an Oura Sleep Score can still appear by their own names in detail views.
3. One useful daily check-in is the target. Additional entries are welcome. No minimum essay length, word count target, or reward for repeated submissions.
4. Prefer Oura for overlapping wearable metrics in the owner's configuration. Apple Health fills compatible gaps and supplies additional metrics. Preferences are per metric, editable, and recorded with each result.
5. Reuse native provider scores when available through a verified interface. Do not reverse engineer Apple's or Oura's proprietary score.
6. Make calculations fast, versioned, reproducible, and independent of an AI service. Use AI for constrained extraction, clarification, and explanations tied to recorded evidence.
7. Include manual and journal only users from the first slice. Buying a wearable or AI subscription is not a condition of getting a useful Headspace view.
8. Research alcohol recovery first. Keep a common architecture for other substances, gambling, and compulsive behaviors, but require separate validation and appropriate terminology for each.
9. Preserve medical records privately, then select relevant context. Importing a record does not make it a daily scoring input.
10. Keep location and automatic partner notifications on the future roadmap. Record the consent and data contracts needed now without implementing them.

## Recommended approach

Start with the working daily check-in and evidence ledger. Add source selection and reliable ingestion. Run a candidate composite beside the existing calculation in evaluation mode before it changes the user's state. Compare the candidate with the simpler journal calculation and discard added complexity that does not improve usefulness.

The proposed first comparison is 60% journal state, 20% sleep or recovery, 10% nutrition alignment, and 10% selected routines. These are **design hypotheses for evaluation, not weights established by psychological research**. Medical diagnoses, hormones, raw sentiment, and missing device data have no automatic penalty. Recovery concerns such as strong urges with low coping confidence remain explicit flags so a good sleep score cannot hide them. [The scoring document](02_SCORING_AND_VALIDATION.md) defines the gates and alternatives.

## What the research supports

Repeated brief reports of craving, coping confidence, recent behavior, and context are useful candidates. Research also supports measuring protective resources, rather than only counting problems. Some studies predict future alcohol lapses, but they do not supply a validated universal Headspace algorithm for all people and addictions. Wearable signals add context and need careful interpretation. See [R01](07_SOURCES.md#r01), [R03](07_SOURCES.md#r03), [R07](07_SOURCES.md#r07), and [R08](07_SOURCES.md#r08).

No production ready, independently validated open source package covering this entire use case was established in this review. Useful libraries and research code exist. The strongest route is to reuse those components while keeping the product rules small and testable.

## Relationship to existing work

The general product roadmap remains `docs/ROADMAP.md` in the owning working checkout. The original journal architecture remains `docs/journal-intelligence-handoff/00-MASTER-BUILD-BRIEF.md` there. Those two working documents were not present on GitHub main when inspected, so they are named here rather than linked to missing files. This Headspace package is self-contained, records the later November 10 request, and refines the next Headspace milestone. It does not silently change current runtime behavior or replace unrelated roadmap sections.

Current code inspected: `tracking/headroom.py`, `tracking/journal_continuity.py`, and `tracking/sobriety_pattern.py`. The current Daily State is based on confirmed mood, energy, and focus ratings; the displayed boundaries are 70 and 40. Sleep, food, and steps currently explain that result rather than changing its number. The existing sobriety pattern is separate. Keep those versioned results until an evaluated replacement is accepted.

The local checkout was dirty at `5573b0288b150da8cba3dbb650fd3033fee1b0da`. GitHub main was `c7c2d502c19759b5589f025064d8ef16563791b6` when inspected. Ongoing fixes and draft PR work are separate. This package contains generic product requirements and synthetic examples only, with no imported health records or private journal content.

## First implementation task

Complete milestone H1 in [06_BUILD_PLAN.md](06_BUILD_PLAN.md): one daily check-in, structured journal observations, clear missingness, three state labels, evidence drilldown, and synthetic acceptance cases. Do not start with a large prediction model or a replacement website.
