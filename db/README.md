# db/ — the tracker ↔ API contract

`schema.sql` defines the **only** thing the tracker and the API agree on: the
`readings` table. This is deliberate so the two halves stay decoupled.

```
tracker/  (writer, you iterate on this constantly)  ──append──▶  readings
                                                                    │ read-only
api/      (reader, stable)                           ◀──SELECT──────┘
```

Rules that keep this working:

- **The API never writes.** It opens the DB `mode=ro`. Writes are the tracker's
  job alone.
- **The API never imports `tracker/` code.** Its only dependency on the tracker
  is the column names in `schema.sql`. Refactor the tracker however you like;
  just keep appending rows shaped like this and the API is unaffected.
- **One row per sampling pass**, `ts` in UTC. `total` is the number the site
  shows; `pier_1..5` are the raw per-feed counts (kept for your analysis, not
  served). `feeds_ok` flags partial passes when a feed is down.

The DB file location is configured by `KP_DB_PATH` (see `api/.env.example`);
default `db/data/readings.db`. Initialise a fresh/dev DB with
`python api/seed.py`, which applies this schema and fills it with synthetic
history so the API is fully functional before the real tracker exists.
