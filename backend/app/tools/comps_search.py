from datetime import date

from app.data import mock_store
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
    """This is the seam where a real OpenSearch-backed call replaces the
    mock store, without changing the contract callers rely on."""
    return mock_store.search_comps(
        submarket_id=submarket_id,
        property_type=property_type,
        min_sf=min_sf,
        max_sf=max_sf,
        lease_type=lease_type,
        date_from=date_from,
        date_to=date_to,
        radius_miles=radius_miles,
        k=k,
    )
