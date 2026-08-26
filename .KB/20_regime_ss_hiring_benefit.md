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

## Internal vs customer

The engine uses this doc. Company-facing product uses `KB/10` (teaser + workspace). Never paste this table into the teaser UI.
