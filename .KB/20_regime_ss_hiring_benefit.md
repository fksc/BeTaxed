# KB/20_regime_ss_hiring_benefit.md — SS hiring benefit (current product line)
**Depends on:** `KB/00_mother_doc.md`, `KB/10_product_flow.md`
**Referenced by:** `KB/05_schema_benefit.md`
**Status:** Working assumptions for the engine. Edge cases to **hammer later** — do not treat every bullet as locked law.

Source samples (local, not in git): SS extract + client deck under `.KB/Samples/`.

---

## What we sell (now)

One line: **unrealized Portuguese Social Security hiring-benefit savings** for companies.

- **Today:** people who already qualify (age at **permanent contract** ≤ 30, contrato **sem termo**, still on full TSU) and are not getting the reduction.
- **If they optimize:** people in the age band on **term** contracts — converting to sem termo can open the regime. We may recommend that **after** they are a client (ops/filing), not as a teaser recipe.

Later: other saving types on the same spine. Not in v1 schema as first-class regimes until they exist.

---

## Working rules (engine v1)

These match the client deck and the locked call: age at hire/sem termo **≤ 30** (under 31).

| Parameter | Working value | Notes |
|---|---|---|
| Employer TSU | 23.75% | Employee share is not the product. Combined 34.75% in the sample = standard, no reduction applied. |
| Reduction | 50% of employer rate | ≈ 11.875% of base (the ~11.9% in the analyst sheet). |
| Duration | 60 months from **sem termo start** | Not from application date. |
| Age | ≤ 30 at signing the **permanent** contract | **Locked (OD-4):** clock is age at **sem termo**, 60 months from that date. Conversion at 31 after a term hire at 29 → fail. |
| First permanent job | Never signed another sem termo (legal test) | SS extract of **this** employer cannot prove other employers. Companies sometimes tell us from onboarding. Store as `employee.first_permanent_elsewhere`. **Always file anyway** — SS history is incomplete; a prior sem termo may be missing. Monitor grant/reject vs the flag (`KB/02`, `KB/05`). |
| Late application | Remaining time to 60 months; benefit from **next month** after apply | Apply within 10 days of sem termo start for the full window (deck). |
| Contract | Permanent, full-time or part-time, including conversion from fixed-term | |
| Company gates at application | Headcount this month **>** average of previous 12 months; SS + AT regularized; salaries not in arrears; duly registered | Headcount test is one-off at application (deck). SS/AT no-debt certs: on demand, **4 months** from issue date (`company_certificate`, OD-4). |
| Our fee | % of **realized** saving | Period follows the remaining benefit window (commercial 5-year story). % is commercial_terms, not this doc. **Leave months are not billable** (OD-4). |

---

## Cease and clawback (track in schema, hammer UX later)

Benefit can end: period over, access conditions fail, remuneration declarations late/missing people, contract ends.

If the **employer** ends the contract in listed ways (no fair motive, collective, job extinction, unsuitability), SS may **reclaim** reduced contributions (deck: without penalties) and also if the contract ends **within 24 months after** the 5-year period. New exemptions blocked 24 months.

Schema implication: `employment_event` on termination stores `initiator` + `reason`. `benefit_case.state` can become `CLAWBACK`. Do not keep charging a success fee on money that is clawed back. Company UI does not need a legal essay.

---

## What the SS extract gives vs what it does not

**Gives:** employer NISS (in query metadata), employee NISS, DOB, vínculo dates, taxa %, workplace, contract modality, profession, rendimento periods and base pay.

**Does not give:** first-job at another employer (company onboarding / ops flag — still file), trailing-12 headcount if we have no history, who initiated a termination, official remunerações/DR leave **codes** (samples have no DR file; BeTaxed leave ingest uses documented NISS + tipo de ausência + início ausência, DEV-849). AT/SS no-debt PDFs are **separate uploads**, not the extract.

**Can be wrong:** modality and dates on Direct are what the employer (or a previous declaration) sent. Worked example (Aug 2026 extract, no names in this doc): two people coded **sem termo** from early 2021 → engine remaining months = 0. Paper contracts were **termo certo** starting Feb 2022 and May 2022 → clock from those dates still has months left. Pass 1 cannot see that. After workspace, check each contract vs the CSV (`KB/10`, `KB/04`). `source = CONTRACT` wins on modality/`signed_on` when ops mark `MISMATCH`.

Analyst columns on the sample (idade, fee/ano, VLOOKUP) are **not** SS. Ignore on parse. 14× monthly on a sales sheet is often **14 pays/year** (holiday + Christmas), not remaining benefit months.

---

## Staff flag: term contract that can still open the benefit (DEV-877)

Ops only. Company APIs and the company people page do not show it, and it does not file anything with Segurança Social.

For an **active** open term employment, with a date of birth, base salary above zero, and the employer rate still unused:

- **Termo certo:** sem termo after the first term plus one renewal of the same length, when a contract PDF has both `signed_on` and `term_end_on`. The length is whole calendar months on the earliest such PDF. Also report three historical readings from the same start: +2 years, +3 years, +4 years. Each line is its own yes or no.
- **Termo incerto:** +4 years only.
- A line is a yes when age on that date is ≤ 30 and some of the 60 months from that date are still left. “Still left” is counted to the latest applied Segurança Social period, or to today when no file has been applied.
- When that primary date would already be age 31 or older, look at the first contract date. A declaration is still possible on any day from the day after the contract started through the day before the 31st birthday, including when those are the same day. Staff usually pick about a month before the birthday. Flag that window only when the 60 months counted from its last day are not already over. Certo’s primary date is the one-renewal date when the PDF length is known; without that length, the window opens only when all three historical caps fail the age test. Incerto’s primary date is the 4-year date.

`first_permanent_elsewhere` does not remove the flag. A prior permanent contract elsewhere is still filed.

The staff Employees hiring-benefit filter keeps everyone until a choice is made. **Already benefiting** is the reduced employer rate. **Not on the reduced rate** is everyone else. **Might benefit** is this flag, or a permanent contract that can still open the 60 months (age ≤ 30 on the start, salary above zero, rate unused, months left). **Won't benefit** is a known dead end: the window is over, the age test fails, the employment has ended, or the contract is not a path to this benefit. A missing date of birth or salary stays out of Might and Won't. The staff table shows the contract start. While Won't benefit is selected, the name explains the first closed path, in the staff member's language, and repeats that date.

The flag is not a case. Staff add a flagged person to the request pipeline when they start work. Stages, waits, and close won / close lost are `KB/05_schema_benefit.md#request-case`.

---

## Internal vs customer

The engine uses this doc. Company-facing product uses `KB/10` (teaser + workspace). Never paste this table into the teaser UI.
