"""The area this service has data for: Swindon (planning.data entity 8600027).

Bounding box of the borough boundary, widened by 0.02° (~1–2 km) so parcels on the
edge are kept. Used by the pipeline (prefilter) and by the API (input bounds).
"""

LON_MIN, LON_MAX = -1.8651 - 0.02, -1.6028 + 0.02
LAT_MIN, LAT_MAX = 51.4825 - 0.02, 51.6927 + 0.02
