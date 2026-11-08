## Release to production

Merge **`dev` → `main`**. Production Cloud Run is not finished, so **Deploy Production** does not run on this merge. Run that workflow by hand after the production services exist. It then completes the **Anteater-Production** release in Linear.

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
