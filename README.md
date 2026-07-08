# orderbook

A cross-company **order-book dashboard for Indian listed companies**.

Indian listed companies file BSE exchange announcements when they win orders or
contracts. This app polls those filings, uses an LLM to read each one and
extract five fields — **value, awarder, duration, target industry, description**
— plus a link to the source filing, then shows every order across **all**
companies in one dashboard, newest first, with per-company history.

Every data point stays **source- and evidence-backed**: each order links to its
original filing and shows where its data came from. Never a black box.

> **Status: Step 1 of ~12 — scaffold only.** The skeleton runs and can deploy.
> Real scraping, real LLM extraction, and the final DB schema come in later
> steps. The UI is a static, colorful placeholder with mock data.

---

## Architecture

- **Monorepo** deployed to **Cloudflare on push to `main`**.
- **`/web`** — Next.js (App Router + TypeScript + TailwindCSS), deployed to
  **Cloudflare Workers** via the **OpenNext** adapter
  (`@opennextjs/cloudflare`). Reads data from **Cloudflare D1** through a
  binding named **`DB`**.
- **`/ingestion`** — Python. Runs on **GitHub Actions** (manual "Run workflow"
  for now; scheduled later). Fetches BSE/Screener data via **Firecrawl** and
  **Scrape.do**, reads the filing PDF, calls **OpenAI** to extract the five
  fields, then writes rows into **Cloudflare D1 via D1's HTTP API**.
- **`/db`** — shared SQL schema + migrations for D1.
- **Database** — Cloudflare **D1** (SQLite). The dashboard reads it via the
  `DB` binding; Python writes to it via D1's HTTP API.

**Design principles** (apply to all UI): light, colorful, visual-heavy, and
modern — _not_ a dark "terminal/Bloomberg" look. Every order card links to its
original filing and shows where its data came from.

---

## Folder layout

```
orderbook/
├── web/                      # Next.js dashboard (Cloudflare Workers via OpenNext)
│   ├── app/                  # App Router: layout, page, global styles
│   │   ├── globals.css       # Tailwind v4 + design-system palette/tokens
│   │   ├── layout.tsx
│   │   └── page.tsx          # Light, colorful placeholder dashboard (mock data)
│   ├── components/           # Design system: Card, Badge, StatTile, OrderCard
│   ├── lib/                  # mockData.ts (types + placeholder orders), accents.ts
│   ├── next.config.ts
│   ├── open-next.config.ts   # OpenNext -> Cloudflare build config
│   ├── wrangler.jsonc        # Worker config + D1 binding "DB" (placeholder id)
│   ├── postcss.config.mjs
│   ├── tsconfig.json
│   └── package.json
├── ingestion/                # Python pipeline (runs on GitHub Actions)
│   ├── main.py               # Entrypoint — Phase 1 fetch+write, Phase 2 PDF-enrich
│   ├── config.py             # Loads env vars / GitHub Secrets (never logs values)
│   ├── d1_client.py          # Runs SQL against Cloudflare D1 via its HTTP API
│   ├── bse_client.py         # Reads BSE order announcements + value/duration parse
│   ├── security_master.py    # BSE scrip <-> NSE symbol <-> ISIN translator
│   ├── firecrawl_client.py   # Fetches + parses BSE pages / order PDFs
│   ├── scrapedo_client.py    # STUB: proxied fetch for BSE (fallback, TODO)
│   ├── openai_client.py      # Extracts value/duration/awarder from PDF text
│   └── requirements.txt
├── db/
│   ├── migrations/
│   │   ├── 0001_init.sql     # orders + industry_map schema
│   │   ├── 0002_pdf_checked.sql       # pdf_checked flag for the enrichment pass
│   │   └── 0003_security_master.sql   # BSE<->NSE<->ISIN translator table
│   └── README.md
├── .github/workflows/
│   └── ingest.yml            # Manual (workflow_dispatch) run of the pipeline
├── .env.example              # All env var names (no values)
├── .gitignore
└── README.md
```

---

## GitHub Secrets

Set these in **Settings → Secrets and variables → Actions**. They are consumed
by the ingestion pipeline (`.github/workflows/ingest.yml`) and mirror
`.env.example`.

**Required**

| Secret               | Used for                                   |
| -------------------- | ------------------------------------------ |
| `OPENAI_API_KEY`     | LLM field extraction                       |
| `FIRECRAWL_API_KEY`  | Fetch + parse pages/PDFs                    |
| `SCRAPEDO_API_KEY`   | Proxied fetch for BSE                       |
| `CF_ACCOUNT_ID`      | Cloudflare account (D1 write target)       |
| `CF_D1_DATABASE_ID`  | Cloudflare D1 database id                   |
| `CF_API_TOKEN`       | Cloudflare API token (D1 edit permission)  |

**Optional**

| Secret              | Used for                     |
| ------------------- | ---------------------------- |
| `SCREENER_EMAIL`    | screener.in login (optional) |
| `SCREENER_PASSWORD` | screener.in login (optional) |
| `MUNS_TOKEN`        | internal token (optional)    |

The web dashboard does **not** use these secrets — it reads D1 through the
Cloudflare Worker binding **`DB`** (configured in `web/wrangler.jsonc`).

---

## Run `/web` locally

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

You should see the **light, colorful placeholder dashboard**: an app header, a
KPI/stat row, and an "Orders" grid of mock order cards (each showing the five
fields plus a "View source filing" link).

Other scripts:

```bash
npm run build        # Next.js production build
npm run preview      # Build with OpenNext and preview the Worker locally
npm run deploy       # Build with OpenNext and deploy to Cloudflare Workers
npm run cf-typegen   # Generate cloudflare-env.d.ts from wrangler.jsonc bindings
```

### Deploying to Cloudflare

Pushing to `main` triggers the connected Worker (Workers Builds), which runs
`npx wrangler deploy` from the repo root. The root **`wrangler.jsonc`** makes
that work with **no dashboard build settings**: its `build` command builds the
Next.js app in `web/` via OpenNext, then wrangler deploys the generated Worker.

There are two wrangler configs — keep them in sync:

- **`wrangler.jsonc`** (root) — used **only** by the automated deploy.
- **`web/wrangler.jsonc`** — used for local dev (`npm run dev` / `preview`, D1
  migrations, seeding); carries the local D1 `DB` binding.

**Production D1:** the root config intentionally **omits** the `DB` binding until
the remote database exists (deploying a binding to a missing DB fails the
deploy). Until then the live dashboard renders demo/mock data — `getOrders()`
falls back when the binding is absent. To go live with real data:

```bash
cd web
npx wrangler d1 create orderbook          # copy the returned database_id
npm run db:migrate:remote                 # apply the schema to remote D1
```

Then add the binding to the **root** `wrangler.jsonc`, put the real id in
`web/wrangler.jsonc`, and set the `CF_D1_DATABASE_ID` GitHub secret (used by
ingestion):

```jsonc
"d1_databases": [
  { "binding": "DB", "database_name": "orderbook", "database_id": "<real-id>" }
]
```

## Run `/ingestion` locally

```bash
cd ingestion
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
cp ../.env.example ../.env    # then fill in values (optional for the readiness check)
python main.py
```

`main.py` prints a **readiness check** — which env vars are set (never their
values) — and exits `0`. Missing secrets are reported but don't fail the run at
this stage.

---

## What's stubbed for later

- **Scrape.do client** — `scrapedo_client.py` is a fallback fetcher; the direct
  BSE fetch is primary, so it's rarely exercised.
- **Industry mapping** — `target_industry` is left NULL by ingestion; a later
  Stock-Scan step maps each company to its industry.
- **Scheduling** — `ingest.yml` runs manually; the `schedule:` block is
  commented out for later.
- **Dashboard** — filters/search/history still to come.

## PDF enrichment (Phase 2)

After writing new BSE orders, `main.py` runs a second pass over orders **already
in D1** that are still missing a value or a duration (and haven't been PDF-checked
yet). For each one it downloads the filing's PDF via Firecrawl (which parses it
to text server-side, `AttachLive` with an `AttachHis` fallback), asks OpenAI to
pull *only* the missing fields as verbatim phrases, normalizes them to
crore/months in code, stores the PDF text as evidence, and marks `pdf_checked`
so repeat runs don't re-download it. `INGEST_LIMIT` caps how many PDFs per run.
