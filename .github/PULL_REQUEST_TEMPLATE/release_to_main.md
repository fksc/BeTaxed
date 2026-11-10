## Release to production

Merge **`dev` → `main`**. That merge runs **Deploy Production** for the backend and frontend files included in the release, then completes the **Anteater-Production** release in Linear.

### Version

Target version: `v<!-- for example 2026.11.08 -->`

### Issues in this release

- DEV-

### Pre-merge checklist

- [ ] Staging QA complete on latest `dev`
- [ ] Database migrations reviewed and safe to run on production
- [ ] Frontend `NEXT_PUBLIC_*` and backend env vars updated in the GitHub **production** environment if needed
- [ ] No open hotfix on `main` that still needs a backport to `dev`

### Post-merge

- [ ] Verify GitHub Actions **Deploy Production** succeeded
- [ ] Generate release notes in Linear, edit them, and publish
- [ ] Move included issues to **Done** in Linear
