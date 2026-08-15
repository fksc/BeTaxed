# Git strategy — BeTaxed

Linear project: **BeTaxed**. Team: **DEV**. Issue keys: **`DEV-`**.

## Branches

| Branch | Purpose |
|---|---|
| `main` | Production only. Never commit directly. Merge via release PR. |
| `dev` | Default integration branch. |

## Flow

1. Branch **from `dev`** only (never from `main` for feature work).
2. Implement and test; open a **PR into `dev`**.
3. For a release, open a **PR from `dev` into `main`**.

## Branch naming

Format: `{Type}/{ISSUE-KEY}-{short-kebab-title}`

Allowed `Type` values (exact casing):

- `Feature/`
- `Bug/`
- `DevFix/`
- `Enhancement/`
- `Refactor/`

Examples: `Feature/DEV-12-ss-parser`, `Bug/DEV-5-niss-hash`.

When starting a Linear issue: fetch/pull `dev`, then `git checkout -b` using Linear’s `gitBranchName`.

## Commits and PRs

Include the issue id in branch names, commit messages, and/or PR title/body.

Magic words: `Fixes DEV-12`, `Closes DEV-12`, `Resolves DEV-12`, `Refs DEV-12`, `Addresses DEV-12`.

Never commit `.KB/Samples/` (PII). Never commit `.env` or credentials.
