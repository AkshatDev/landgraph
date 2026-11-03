"""The area this service has data for: Swindon (planning.data entity 8600027).

Bounding box of the borough boundary, widened by 0.02° (~1–2 km) so parcels on the
edge are kept. Used by the pipeline (prefilter) and by the API (input bounds).
"""

MARGIN = 0.02  # degrees, ~1–2 km
LON_MIN, LON_MAX = round(-1.8651 - MARGIN, 4), round(-1.6028 + MARGIN, 4)
LAT_MIN, LAT_MAX = round(51.4825 - MARGIN, 4), round(51.6927 + MARGIN, 4)
