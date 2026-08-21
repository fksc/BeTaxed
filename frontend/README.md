# BeTaxed frontend

Next.js App Router + shadcn/ui. Layout matches Talent Journey: `app/`, `components/ui/`, `lib/`, `hooks/`.

```bash
nvm use 24
cp .env.example .env.local
npm install
npm run dev
```

Needs the API on `:8080` and the Auth emulator (`docker compose up -d firebase-auth`).

- `/` and `/pt` — Portuguese (default)
- `/en` — English
- `GET /api/health` → `{"status":"ok"}`

UI copy lives in `messages/{locale}.json`. Add a language by creating a file and listing the code in `i18n/routing.ts`. The teaser never names people, shows rates, or explains how to file.
