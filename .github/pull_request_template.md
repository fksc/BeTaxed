## Summary

<!-- What changed and why. Include the Linear issue key. -->

Refs DEV-

## Type

- [ ] Feature
- [ ] Bug fix
- [ ] Enhancement
- [ ] Refactor
- [ ] DevFix / CI

## Checklist

- [ ] Linear issue key in branch name, commits, or PR title (`DEV-###`)
- [ ] Linear magic words in commits and this PR (`Closes` / `Fixes` / `Refs` / `Addresses DEV-###`)
- [ ] Backend tests pass locally (`cd backend && pytest tests/ -q`) if `backend/**` changed
- [ ] Frontend lint/build pass locally if `frontend/**` changed
- [ ] Migrations included if schema changed (`backend/alembic/versions/`)
- [ ] KB / env examples updated if new env vars or API behaviour

## Test plan

<!-- How you verified the change. -->
