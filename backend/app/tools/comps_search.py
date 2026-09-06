from datetime import date

from app.schemas.evidence import Comp


def comps_search(
    submarket_id: str,
    property_type: str,
    min_sf: int,
    max_sf: int,
    lease_type: str,
    date_from: date,
    date_to: date,
    radius_miles: float,
    k: int,
) -> list[Comp]:
    raise NotImplementedError
