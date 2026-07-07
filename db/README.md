# db

Shared SQL schema + migrations for the Cloudflare D1 database (`orderbook`).

- The web dashboard reads this database through the Worker binding **`DB`**
  (see `web/wrangler.jsonc`).
- The Python ingestion pipeline writes to it via D1's HTTP API
  (see `ingestion/d1_client.py`).

## Migrations

- `migrations/0001_init.sql` — **placeholder** only. The real schema is defined
  in the next step (Step 2: database schema) and will replace it.

Apply a migration with Wrangler (run from the repo root or `web/`):

```bash
# local (development) D1
wrangler d1 execute orderbook --local  --file=./db/migrations/0001_init.sql

# remote (production) D1
wrangler d1 execute orderbook --remote --file=./db/migrations/0001_init.sql
```
