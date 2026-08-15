# BeTaxed — KB Document Plan
**Version:** 1.0
**Purpose:** Master plan for knowledge-base documents. Written before Linear issues. Issues reference these docs by path + section anchor (e.g. `KB/02_schema_employment.md#table-employment_event`).

---

## Writing order

### Foundation
| Doc | Contents |
|---|---|
| `00_mother_doc.md` | Product, actors, object index, stack, global rules, open decisions, doc index |
| `10_product_flow.md` | Two-pass intake, teaser vs workspace, wipe-on-decline |
| `20_regime_ss_hiring_benefit.md` | Current product line: SS hiring benefit (rules to hammer later live here) |
| `GIT_STRATEGY.md` | `main` / `dev`, branch names, Linear `DEV-` keys |

### Schema
| Doc | Contents |
|---|---|
| `01_schema_core.md` | Users, company, membership, intake |
| `02_schema_employment.md` | Employee, employment, compensation, workplace, status events |
| `03_schema_ss_ingest.md` | SS batches, raw rows, diffs, headcount months |
| `04_schema_documents.md` | GCS files, contracts, certificates |
| `05_schema_benefit.md` | Regime, application, benefit case, saving month (**internal**) |
| `06_schema_billing.md` | Commercial terms, invoices, payments |
| `07_security_encryption.md` | What is encrypted, hashes, tenant isolation |

### Access
| Doc | Contents |
|---|---|
| `40_permissions.md` | Who can see/do what. Company APIs never expose the recipe. |

---

## Rules for later docs

- Do not duplicate table definitions. Link the schema doc.
- When the law or commercial terms change, version `incentive_regime` / `commercial_terms` — do not rewrite history in `saving_month`.
- Sample files stay in `.KB/Samples/` and are **not** in git.
