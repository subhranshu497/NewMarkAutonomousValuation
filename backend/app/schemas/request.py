from pydantic import BaseModel


class LeaseAssumptions(BaseModel):
    lease_type: str
    term_months: int
    concessions_assumed: str | None = None


class ValuationRequest(BaseModel):
    submarket_id: str
    property_type: str
    space_sf: int
    lease_assumptions: LeaseAssumptions
    requested_by: str
