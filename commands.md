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

`load` takes two arguments: the dataset name, then the file path.
Smaller dataset for a quick demo: `download conservation-area` (24 MB).

## Pipeline: local database (Docker)

```bash
docker compose up -d db                       # start Postgres + PostGIS
docker compose run --rm app python -m landgraph.pipeline \
  load title-boundary raw/title-boundary/2026-11-02/title-boundary.parquet
docker compose build app                      # after `uv add ...` (the container has its own venv)
```

## Check the data

```bash
docker compose exec db psql                   # local psql shell
```

```sql
SELECT count(*) FROM title_boundaries;        -- 115644
SELECT * FROM pipeline_checkpoints;           -- row_group 31 = finished
\d title_boundaries                           -- columns + GiST index on geom

-- Which parcel is at a point? (lng first!)
EXPLAIN ANALYZE
SELECT reference, round(ST_Area(geom)) AS area_m2
FROM title_boundaries
WHERE ST_Intersects(geom,
        ST_Transform(ST_SetSRID(ST_MakePoint(-1.848042, 51.561146), 4326), 27700));

-- Start a load from scratch (clear BOTH, or the checkpoint says "done")
TRUNCATE title_boundaries, pipeline_checkpoints;
```

New Neon database: run `CREATE EXTENSION IF NOT EXISTS postgis;` once in its SQL editor.

Check which host/database `.env.neon` points at without showing the password:

```bash
grep '^DATABASE_URL=' .env.neon | sed -E 's#.*@##'
```

## API: run locally

```bash
docker compose run --rm -p 8000:8000 app fastapi dev --host 0.0.0.0
# open http://localhost:8000/docs
```

## API: FastAPI Cloud

```bash
uv run fastapi login                          # once
uv run fastapi deploy                         # deploy current code
uv run fastapi cloud env list                 # which variables are set
uv run fastapi cloud logs --no-follow --since 30m   # recent logs (JSON, with correlation ids)
uv run fastapi cloud logs                     # stream live

# Set DATABASE_URL from .env.neon via stdin (never on the command line); redeploys
grep '^DATABASE_URL=' .env.neon | cut -d= -f2- \
  | uv run fastapi cloud env set DATABASE_URL --value-stdin --secret
```

## Try the live API

```bash
URL=https://landgraph.fastapicloud.dev
curl -s $URL/health                           # {"status":"ok"}
curl -s $URL/ready                            # {"status":"ready","checks":{"database":"ok"}}

# Lydiard House: parcel 24397490, 11,586 m²  (run twice: first call may wake Neon)
curl -s "$URL/v1/site-snapshot?lat=51.561146&lng=-1.848042"

# Town-centre house plot: parcel 24982948, 125 m²
curl -s "$URL/v1/site-snapshot?lat=51.5558&lng=-1.7797"

# No registered parcel here: "parcels": []
curl -s "$URL/v1/site-snapshot?lat=51.522762&lng=-1.790871"

# Outside Swindon (Bristol): 422
curl -s "$URL/v1/site-snapshot?lat=51.4545&lng=-2.5879"
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
