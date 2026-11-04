# Commands cheat sheet

Run everything from the `landgraph/` folder. Credentials live in `.env` (local) and
`.env.neon` (cloud); both are git-, docker- and deploy-ignored. Never paste a database
URL on the command line.

## Demo: download a dataset and load it into Neon

```bash
# 1. Download the national file into raw/<dataset>/<date>/ (no database involved).
#    Skips the download if today's file already exists.
uv run python -m landgraph.pipeline download title-boundary

# 2. Load it into Neon: reads one row group at a time, keeps Swindon, upserts,
#    checkpoints every batch. Safe to Ctrl-C and re-run: it resumes.
uv run --env-file .env.neon python -m landgraph.pipeline \
  load title-boundary raw/title-boundary/2026-11-02/title-boundary.parquet

# 3. Run it again: "already fully loaded, nothing to do".
```

Quick demo with a small dataset (24 MB, 54 Swindon conservation areas, loads in seconds):

```bash
uv run python -m landgraph.pipeline download conservation-area
uv run --env-file .env.neon python -m landgraph.pipeline \
  load conservation-area raw/conservation-area/2026-11-02/conservation-area.parquet
```

`load <dataset> <file>`: the **dataset** name (the same word you passed to `download`),
then the file path from `landgraph/`. Not the table name: the table is chosen from the
dataset (`title-boundary` → `title_boundaries`, `conservation-area` → `constraints`).

| Dataset | Table | Key | Swindon rows |
|---|---|---|---|
| `title-boundary` | `title_boundaries` | `reference` | 115,644 |
| `conservation-area` | `constraints` | `entity` | 54 |

Order for a new database: load data **before** deploying code that queries a new table,
or every snapshot request returns 500.

## Pipeline: local database (Docker)

```bash
docker compose up -d db                       # start Postgres + PostGIS
docker compose run --rm app python -m landgraph.pipeline \
  load title-boundary raw/title-boundary/2026-11-02/title-boundary.parquet
docker compose run --rm app python -m landgraph.pipeline \
  load conservation-area raw/conservation-area/2026-11-02/conservation-area.parquet
docker compose build app                      # after `uv add ...` (the container has its own venv)
```

## Send the data to Neon (release order)

Same commands as local, pointed at Neon with `--env-file .env.neon`. Run on the host
(not in Docker). Each load is resumable and safe to re-run.

```bash
# 0. Which Neon host/database will this write to? (no password shown)
grep '^DATABASE_URL=' .env.neon | sed -E 's#.*@##'

# 1. New Neon database only: in the Neon SQL editor, once
#      CREATE EXTENSION IF NOT EXISTS postgis;

# 2. Load every dataset (tables are created automatically)
uv run --env-file .env.neon python -m landgraph.pipeline \
  load title-boundary raw/title-boundary/2026-11-02/title-boundary.parquet
uv run --env-file .env.neon python -m landgraph.pipeline \
  load conservation-area raw/conservation-area/2026-11-02/conservation-area.parquet

# 3. Check in the Neon SQL editor (same SQL as "Check the data" below):
#      SELECT count(*) FROM title_boundaries;                -- 115644
#      SELECT dataset, count(*) FROM constraints GROUP BY 1; -- conservation-area 54
#      SELECT * FROM pipeline_checkpoints;                   -- 31:0 and 1:0

# 4. Only now deploy code that queries the new tables (see "API: FastAPI Cloud")
uv run fastapi deploy
```

Data first, code second: code deployed before its table exists returns 500 on every request.
`fastapi deploy` uploads the working directory, so check `git branch --show-current` first.

## Check the data (local)

```bash
docker compose exec db psql                   # local psql shell
```

```sql
SELECT count(*) FROM title_boundaries;        -- 115644
SELECT dataset, count(*) FROM constraints GROUP BY 1;   -- conservation-area 54
SELECT * FROM pipeline_checkpoints;           -- one row per dataset; row_group = total = finished
\d title_boundaries                           -- columns + GiST index on geom

-- Which parcel is at a point? (lng first!)
EXPLAIN ANALYZE
SELECT reference, round(ST_Area(geom)) AS area_m2
FROM title_boundaries
WHERE ST_Intersects(geom,
        ST_Transform(ST_SetSRID(ST_MakePoint(-1.848042, 51.561146), 4326), 27700));

-- Parcels affected by a conservation area (spatial join)
SELECT count(DISTINCT t.reference)
FROM title_boundaries t JOIN constraints c ON ST_Intersects(c.geom, t.geom);   -- 8178

-- Start a load from scratch: clear the data AND its checkpoint, or it says "done"
TRUNCATE title_boundaries; DELETE FROM pipeline_checkpoints WHERE dataset = 'title-boundary';
TRUNCATE constraints;      DELETE FROM pipeline_checkpoints WHERE dataset = 'conservation-area';
```

## API: run locally

```bash
docker compose run --rm -p 8000:8000 app fastapi dev --host 0.0.0.0
# open http://localhost:8000/docs
```

## API: FastAPI Cloud

```bash
uv run fastapi login                          # once
uv run fastapi deploy                         # deploy current code (load new tables into Neon first)
uv run fastapi cloud env list                 # which variables are set
uv run fastapi cloud logs --no-follow --since 30m   # recent logs (JSON, with correlation ids)
uv run fastapi cloud logs                     # stream live

# Point the app at the Neon database in .env.neon, via stdin (never on the command line).
# Redeploys. Must be the same database the data was loaded into.
grep '^DATABASE_URL=' .env.neon | cut -d= -f2- \
  | uv run fastapi cloud env set DATABASE_URL --value-stdin --secret
```

## Try the live API

```bash
URL=https://landgraph.fastapicloud.dev
curl -s $URL/health                           # {"status":"ok"}
curl -s $URL/ready                            # {"status":"ready","checks":{"database":"ok"}}

# Compact view: parcel, area and constraint names only (needs python3)
snap() { curl -s "$URL/v1/site-snapshot?lat=$1&lng=$2" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if "parcels" not in d: print(d); sys.exit()
for p in d["parcels"] or [{}]:
    print(p.get("reference", "no parcel"), p.get("area_m2", ""), [c["name"] for c in p.get("constraints", [])])'; }
```

Run each twice if the first is slow (Neon wakes up). Use `curl -s "$URL/v1/site-snapshot?lat=..&lng=.."` for the full JSON with geometry.

### With constraints

```bash
# Swindon Old Town: 4,827 m² title in the Old Town conservation area (the historic hilltop town)
snap 51.550581 -1.771605      # 25063524 4827.0 ['Swindon Old Town']

# Town Gardens: a 590 m² house plot in the Town Gardens conservation area
snap 51.552766 -1.788171      # 24912362 590.0 ['Swindon Town Gardens']

# Railway Village: 3.9 ha title in the GWR railway works area. Note the name: the source
# publishes it as "Swindonâ€™s Railway" (mojibake: a broken curly apostrophe)
snap 51.562681 -1.797963      # 62900375 38578.0 ['Swindonâ€™s Railway']

# Highworth: hilltop market town in the north of the borough
snap 51.631022 -1.707934      # 25502335 6940.0 ['Highworth']

# Wroughton: village just south of Swindon
snap 51.521415 -1.785550      # 56384012 4786.0 ['Wroughton']

# TWO constraints on one parcel: a 179 ha title that overlaps both the Chiseldon and the
# Hodson conservation areas. Shows why the join tests the whole parcel, not the point
snap 51.523762 -1.737149      # 63178668 1786055.0 ['Hodson', 'Chiseldon']

# Outside Swindon but inside the box: a 352 ha estate in Oxfordshire overlapping the
# Buscot and Kelmscott conservation areas. Shows the bounding-box margin (neighbours' data)
snap 51.680404 -1.650165      # 26059665 3515689.0 ['Buscot Conservation Area', 'Kelmscott Conservation Area']
```

### Without constraints

```bash
# Lydiard House: a 1.2 ha title, no conservation area
snap 51.561146 -1.848042      # 24397490 11586.0 []

# Town-centre house plot: 125 m², no conservation area
snap 51.5558 -1.7797          # 24982948 125.0 []

# Largest title within 3 km of the centre with no constraint at all: 147 ha.
# The kind of site a land screen looks for (big, unconstrained)
snap 51.546268 -1.810449      # 59787806 1466852.0 []
```

### No parcel and errors

```bash
# Inside Swindon, no registered title here (road, verge or gap between plots)
snap 51.522762 -1.790871      # no parcel
curl -s "$URL/v1/site-snapshot?lat=51.522762&lng=-1.790871"     # {"lat":..,"lng":..,"parcels":[]}

# Outside the data (Bristol): 422 with the allowed range
curl -s "$URL/v1/site-snapshot?lat=51.4545&lng=-2.5879"

# Not a number: 422 "unable to parse string as a number"
curl -s "$URL/v1/site-snapshot?lat=abc&lng=-1.78"

# Missing parameter: 422 "Field required"
curl -s "$URL/v1/site-snapshot?lat=51.55"

# Status codes only
curl -s -o /dev/null -w "%{http_code}\n" "$URL/v1/site-snapshot?lat=51.4545&lng=-2.5879"   # 422
```

Interactive docs: `$URL/docs`

## Code quality and tests

```bash
docker compose run --rm app sh -c "ruff format . && ruff check . && ty check && pytest -q"
docker compose run --rm --build app pytest    # rebuild first (after dependency changes)
```

## Notebooks

```bash
uv add --group notebook <package>             # notebook-only dependency
uv run --with nbconvert jupyter nbconvert --to html notebooks/<name>.ipynb
```

`nbstripout` is installed as a git filter: notebook outputs are stripped on commit.
To show outputs on GitHub, export to HTML/PDF or check `uv run nbstripout --status`.
