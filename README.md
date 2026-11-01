# landgraph

Data pipelines that bring public UK land and planning data into **PostgreSQL/PostGIS**, and a small **FastAPI** service that answers the question *"what do we know about this piece of land?"*

The project is limited to one local authority, **Swindon** (`E06000030`), so the whole flow can be built, tested and explained end to end: messy public data in, clean spatial data out.

## What it does

1. **Ingests** open datasets: land title boundaries, planning constraints, planning applications and house sale prices.
2. **Cleans and normalises** them: consistent schemas, one coordinate system, postcodes geocoded to points.
3. **Validates** every load with data-quality checks, so bad rows are caught and reported before they reach users.
4. **Loads** them into PostGIS with spatial indexes. Every load can be re-run safely (idempotent) and resumed if interrupted.
5. **Serves** a site snapshot over HTTP: for a location, the title parcel, the constraints that affect it, nearby planning applications and nearby sales. _(planned)_

## Data sources

| Dataset                                                                                             | Source                                                                                           | Geometry             | Licence            |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------- | ------------------ |
| Title boundaries (INSPIRE polygons)                                                                 | HM Land Registry via [planning.data.gov.uk](https://www.planning.data.gov.uk)                     | Polygon              | HMLR INSPIRE terms |
| Conservation areas, flood risk zones, listed buildings, scheduled monuments, SSSIs, brownfield land | [planning.data.gov.uk](https://www.planning.data.gov.uk)                                          | Polygon / point      | OGL                |
| Planning applications                                                                               | [PlanIt](https://www.planit.org.uk)                                                               | Point                | See PlanIt terms   |
| Price Paid (house sales)                                                                            | [HM Land Registry](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads) | None (postcode only) | OGL                |
| Postcode locations, used for geocoding                                                              | [OS Code-Point Open](https://www.ordnancesurvey.co.uk/products/code-point-open)                   | Point                | OGL                |

## Tech stack

- **Python 3.14**, managed with **uv**
- **PostgreSQL 18 + PostGIS 3.6** (`postgis/postgis` image)
- **Docker Compose** for local development (app and database in containers)
- **pytest**: unit tests and integration tests against a real PostGIS
- **FastAPI**, deployed to **FastAPI Cloud** with **Neon** Postgres _(planned)_
- **Polars** for streaming large files (the full Price Paid file is 5.5 GB) _(planned)_

## Running locally

Requires Docker with Compose.

```bash
cp .env.example .env          # then set POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
docker compose build
docker compose run --rm app   # runs the test suite (default command: pytest)
```

## Project layout

```
src/landgraph/   application package
tests/           unit and integration tests
compose.yaml     app + PostGIS services
Dockerfile       development image (uv, dependencies cached in their own layer)
```

## Design notes

Possible next steps for a larger system, which are not part of this project:

- **Bulk indexing into OpenSearch** through an SQS queue with S3 buffering
- **Orchestration with Airflow**
- **Running batch jobs on AWS** (ECS or Kubernetes)

These will be documented as decisions once the core pipelines are working.
