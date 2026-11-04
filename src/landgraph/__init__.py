"""landgraph: public UK land data in PostGIS, served over FastAPI.

Re-exports the two things most callers need, so they can be imported from the
package root: ``from landgraph import Database, configure_logging``.
"""

from .db import Database
from .log_config import configure_logging

__all__ = ["Database", "configure_logging"]
