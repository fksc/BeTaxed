# KB/40_permissions.md — Permission matrix
**Depends on:** `KB/00_mother_doc.md`, `KB/01_schema_core.md`, `KB/10_product_flow.md`

Context is always explicit: `intake_id` (pass 1) or `company_id` (workspace). BeTaxed staff have no home company.

Legend: **Y** = allowed, **—** = no, **ops** = BeTaxed staff only.

| Action | Anon / session (upload-first) | Company Admin | Company HR | Company Finance | BeTaxed staff |
|---|---|---|---|---|---|
| Upload SS pass 1 | Y | Y | Y | — | ops |
| See teaser aggregate | Y (own intake) | Y | Y | Y | ops |
| See recipe / per-employee eligibility / remaining months | — | — | — | — | ops |
| Decline + purge intake | Y (own) | Y | — | — | ops |
| Convert to workspace | Y (own) | Y | — | — | ops |
| Monthly SS upload | — | Y | Y | — | ops |
| Upload contracts | — | Y | Y | — | ops |
| Set first-sem-termo flag (company-reported) | — | Y | Y | — | ops |
| Upload SS/AT no-debt certificate | — | Y | — | Y | ops |
| Override employee status | — | Y | Y | — | ops |
| Resolve SS vs user conflict | — | Y | Y | — | ops |
| See invoices / pay | — | Y | — | Y | ops |
| Manual invoice resolve | — | — | — | — | ops |
| Read benefit_case / saving_month (incl. flag vs grant) | — | — | — | — | ops |
| Change commercial_terms | — | — | — | — | ops |

Company invoice payloads must not include `saving_amount` per employee, `ineligibility_code`, or regime parameters.

i18n: permissions are not language-specific; UI strings are.
