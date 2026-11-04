landgraph
=========

A data pipeline that loads public UK land data into **PostgreSQL/PostGIS**, and a
small **FastAPI** service that answers *"what land parcel is at this point, and what
planning constraints affect it?"* Scoped to the Borough of Swindon.

* **Live API:** https://landgraph.fastapicloud.dev/docs
* **Source:** https://github.com/AkshatDev/landgraph

.. code-block:: text

   files.planning.data.gov.uk ──download──▶ raw/<dataset>/<date>/ ──load──▶ PostGIS ◀──query── GET /v1/site-snapshot
   (national parquet files)                (landing zone)          (row groups,        (title_boundaries,
                                                                    checkpoints)        constraints)

The design decisions, with the measurements behind them, are in the README. This
site is the code reference, generated from the docstrings.

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/api
   reference/pipeline
   reference/data
