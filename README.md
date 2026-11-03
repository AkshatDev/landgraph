# landgraph

A data pipeline that loads public UK land data into **PostgreSQL/PostGIS**, and a small **FastAPI** service that answers *"what land parcel is at this point?"*

Scoped to one local authority, the **Borough of Swindon** (ONS `E06000030`, planning.data entity `8600027`), so the whole flow can be built, measured and explained end to end.

**Live API:** https://landgraph.fastapicloud.dev/docs

```bash
curl "https://landgraph.fastapicloud.dev/v1/site-snapshot?lat=51.561146&lng=-1.848042"
```
```json
{
  "lat": 51.561146,
  "lng": -1.848042,
  "parcels": [
    {
      "reference": "24397490",
      "area_m2": 11586.0,
      "geometry": {"type": "MultiPolygon", "coordinates": [[[[-1.847945988, 51.560794995], "..."]]]}
    }
  ]
}
```
That point is Lydiard House: one title of 1.2 hectares. Try `lat=51.5558&lng=-1.7797` for a 125 m² house plot.

## Architecture

```text
 files.planning.data.gov.uk          raw/ (landing zone)                    PostGIS (local or Neon)            FastAPI Cloud
┌────────────────────────┐  download ┌───────────────────────────┐  load   ┌───────────────────────────┐  query ┌──────────────────────┐
│ title-boundary.parquet │ ────────▶ │ raw/<dataset>/<date>/file │ ──────▶ │ title_boundaries (27700)  │ ◀───── │ GET /v1/site-snapshot│
│ 3.9 GB, 22.8M parcels  │  httpx    │ national, untouched       │ pyarrow │ pipeline_checkpoints      │  GiST  │ lat/lng → parcels    │
└────────────────────────┘  stream   └───────────────────────────┘ +Polars └───────────────────────────┘        └──────────────────────┘
```

Each step touches only one outside system, so it can be re-run on its own, and the same raw file loads into local Postgres or Neon by changing `DATABASE_URL`.

| Step | What it does | Safe to re-run because |
|---|---|---|
| `download` | HEAD to pick the smallest format, stream to disk in 1 MB chunks | skips a file that already exists; `.part` + rename means no half-files |
| `load` | read one parquet row group at a time → keep Swindon (Polars) → upsert → checkpoint | upsert on the parcel's stable ID; checkpoint commits **in the same transaction** as each batch |
| API | point → parcels containing it | read-only |

## Design decisions (with measurements)

**Bulk file, not the paged API.** The planning.data API took ~22 s per 100 rows and dropped the connection at `limit=500`; Swindon alone would take hours. The national bulk file downloads in **41 s** (3.9 GB at ~95 MB/s). The API client (`pipeline/extract.py`, retries with backoff, 429 vs 5xx handling) is kept for small incremental updates.

**Read one row group at a time.** The first load crashed WSL by running out of memory. Measured on the 3.9 GB file:

| Read pattern | Peak memory |
|---|---|
| Polars streaming over the whole file | 3.3–4.4 GB |
| pyarrow `iter_batches` over the whole file | 3.8 GB |
| **pyarrow, one row group at a time** | **0.7 GB** |

Batch size and pyarrow threads are set at runtime from free memory and the parquet footer (`pipeline/resources.py`), and the load refuses to start below 1.5 GB free.

**Resumable, exactly-once effect.** Each batch's rows and its checkpoint `(row_group, row_offset)` commit in one transaction. Tested by interrupting a load: the table held **27,517** rows at checkpoint `7:100000`, exactly the Swindon rows in groups 0–6 plus the first 100,000 rows of group 7 (recomputed from the file). The re-run resumed there and finished at **115,644**; a third run logs "already fully loaded".

**Cheap filter first, exact filter second.** Polars keeps parcels whose centroid falls inside Swindon's bounding box (+0.02°): four comparisons per row over 22.8M rows. Swindon's boundary has 10,068 vertices, so the exact cut belongs in PostGIS (`ST_Intersects`), on the ~115k rows that remain.

**Store in British National Grid (EPSG:27700).** Input is WGS84 lon/lat; geometry is transformed once during load (`ST_Transform(ST_GeomFromText(wkt, 4326), 27700)`), so areas and distances are in metres. Responses are transformed back to 4326 GeoJSON for web maps.

**Spatial index.** A point lookup uses the GiST index: candidates by bounding box, then the exact `ST_Intersects` test.
```
Index Scan using idx_title_boundaries_geom on title_boundaries
  Index Cond: (geom && <point>)    Filter: st_intersects(geom, <point>)
  Rows Removed by Filter: 2        Execution Time: 1.733 ms
```

**`parcels` is a list.** INSPIRE outlines are indicative and overlap: in 5,000 random Swindon points, 93.2% hit one parcel, **0.6% hit 2–3**, 6.2% hit none (roads, rivers, unregistered land). The API returns every match and leaves ranking to the client.

**Input validation from one source of truth.** `coverage.py` holds the Swindon box used by both the pipeline filter and the API's `Query(ge=…, le=…)` bounds, so points outside the loaded data get a **422** instead of a misleading empty answer.

**Fail fast under load.** Every database wait is bounded: pool wait 2 s, connect 5 s, and a server-side `statement_timeout` of 2 s for API connections only (the pipeline is exempt). Tested: with a 5 s query the endpoint returns **503 after 2.3 s** instead of queueing. Only temporary failures (connection, timeouts) become 503; anything else, such as a missing table, is a 500 with an ERROR log.

**Observability.** JSON logs from one central config, a correlation ID per request (`X-Request-ID`) and per pipeline run, and progress logs for downloads and loads.

## API

| Endpoint | Purpose |
|---|---|
| `GET /v1/site-snapshot?lat=&lng=` | parcels at a point in Swindon. 200 (list, may be empty), 422 (invalid or outside coverage), 503 (database unavailable) |
| `GET /health` | the process is up |
| `GET /ready` | the database is reachable (used by the platform) |

Versioned under `/v1`: additive changes stay in v1, breaking changes get `/v2`. Health checks are unversioned because they serve infrastructure, not clients.

## Running it

Requires Docker with Compose and [uv](https://docs.astral.sh/uv/). See [`commands.md`](commands.md) for the full cheat sheet.

```bash
cp .env.example .env                       # set POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
docker compose up -d db

uv run python -m landgraph.pipeline download title-boundary
docker compose run --rm app python -m landgraph.pipeline \
  load title-boundary raw/title-boundary/<date>/title-boundary.parquet

docker compose run --rm -p 8000:8000 app fastapi dev --host 0.0.0.0   # http://localhost:8000/docs
```

## Project layout

```text
src/landgraph/
  app.py              FastAPI app: middleware, /health, /ready
  api_v1.py           /v1 router: site-snapshot
  queries.py          spatial queries (SQLAlchemy Core + PostGIS functions)
  coverage.py         Swindon bounding box, shared by pipeline and API
  models.py, db.py    tables (GeoAlchemy2) and engine with bounded timeouts
  pipeline/
    __main__.py       CLI: download | load
    website_client.py download with format check and progress logs
    load.py           row-group loop, upsert, checkpoint per batch
    transform.py      Polars: Swindon box, clean columns
    checkpoint.py     load/save checkpoint (same transaction as data)
    resources.py      memory check, pyarrow threads, batch size
    extract.py        paged API client (alternative source)
notebooks/            data exploration and memory measurements
```

## Data

| Dataset | Source | Rows loaded | Licence |
|---|---|---|---|
| Title boundaries (HM Land Registry INSPIRE polygons) | [planning.data.gov.uk](https://www.planning.data.gov.uk) bulk parquet | 115,644 (Swindon box) | HMLR INSPIRE terms |
| Local authority boundary (for the Swindon box) | planning.data.gov.uk `local-authority-district` | 1 | OGL |

Public government data only. INSPIRE polygons show where a title is, not who owns it.

## Next steps

- **Constraints** (conservation areas, listed buildings, flood zones) in one `constraints` table keyed on planning.data `entity` (council references like `CA10` repeat across 41 councils), joined to parcels with `ST_Intersects` in the snapshot
- **Exact Swindon cut** with `ST_Intersects` against the borough boundary
- **Tests** for the endpoint (cases already exercised manually: 200, empty, 422, 503, 500)
- **Load protection**: concurrency limit (503 + `Retry-After`), circuit breaker, `Cache-Control`
- **At scale**: scheduled runs (GitHub Actions cron or Airflow), raw files in S3 with SQS-triggered loads, OpenSearch for text search over parcels and constraints

Built with AI pair programming (Claude Code) as a tutor and reviewer; every decision above was measured or tested before it was kept.
