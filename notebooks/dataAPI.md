# planning.data.gov.uk: Search entity API

Source: https://www.planning.data.gov.uk/docs

This endpoint searches for a subset of entities from all entities, filtered by the given parameters, and returns the entity set in the requested format.

## Request

| Request type | URL |
|---|---|
| `GET` | `/entity.{extension}` |

## Parameters

| Name | Required? | Type | Description |
|---|---|---|---|
| `extension` | Required | string | Must be one of: `json` or `geojson` |
| `q` | Optional | string | Search by a postcode, or a Unique Property Reference Number (UPRN) |
| `typology` | Optional | array(string) | Search for entities by typology |
| `dataset` | Optional | array(string) | Search for entities by dataset |
| `organisation_entity` | Optional | array(integer) | Search for entities managed by organisation |
| `entity` | Optional | array(integer) | Search for entities by entity number |
| `curie` | Optional | array(string) | Search for entities by CURIE |
| `prefix` | Optional | array(string) | Search for entities by prefix |
| `reference` | Optional | array(string) | Search for entities by reference |
| `period` | Optional | array | Results to include: current, or all entries |
| `start_date_year` | Optional | integer | Search for entities by start date year before or after the given year. Depends on `start_date_match` |
| `start_date_month` | Optional | integer | Search for entities by start date month before or after the given month. Depends on `start_date_match` |
| `start_date_day` | Optional | integer | Search for entities by start date day before or after the given day. Depends on `start_date_match` |
| `start_date_match` | Optional | string | Must be one of: `match`, `before`, `since` or empty |
| `end_date_year` | Optional | integer | Search by end date year before or after the given year. Depends on `end_date_match` |
| `end_date_month` | Optional | integer | Search for entities by end date month before or after the given month. Depends on `end_date_match` |
| `end_date_day` | Optional | integer | Search for entities by end date day before or after the given day. Depends on `end_date_match` |
| `end_date_match` | Optional | string | Must be one of: `match`, `before`, `since` or empty |
| `entry_date_year` | Optional | integer | Search for entities by entry date year before or after the given year. Depends on `entry_date_match` |
| `entry_date_month` | Optional | integer | Search for entities by entry date month before or after the given month. Depends on `entry_date_match` |
| `entry_date_day` | Optional | integer | Search for entities by entry date day before or after the given day. Depends on `entry_date_match` |
| `entry_date_match` | Optional | string | Must be one of: `match`, `before`, `since` or empty |
| `longitude` | Optional | number | Search for entities with geometries intersected by a point constructed with this longitude. Requires `latitude` |
| `latitude` | Optional | number | Search for entities with geometries intersected by a point constructed with this latitude. Requires `longitude` |
| `geometry` | Optional | array(string) | Search for entities with geometries interacting with one or more geometries provided in WKT format. The type of relation is set with `geometry_relation` |
| `geometry_entity` | Optional | array(integer) | Search for entities with geometries interacting with the geometries of each of the given entities. The type of relation is set with `geometry_relation` |
| `geometry_reference` | Optional | array(string) | Search for entities with geometries interacting with the geometries of entities with the given references. The type of relation is set with `geometry_relation` |
| `geometry_curie` | Optional | array(string) | Search for entities with geometries interacting with the geometries of entities matching the given CURIEs. The type of relation is set with `geometry_relation` |
| `geometry_relation` | Optional | string | Must be one of: `within`, `equals`, `disjoint`, `intersects`, `touches`, `contains`, `covers`, `coveredby`, `overlaps` or `crosses` |
| `limit` | Optional | integer | Limit for the number of results |
| `offset` | Optional | integer | Paginate results from this entity |
| `field` | Optional | array(string) | Fields to include in the response |
| `exclude_field` | Optional | array(string) | Fields to exclude. `field` takes priority over any fields given in `exclude_field` |
| `quality` | Optional | array(string) | Search for entities by quality |
