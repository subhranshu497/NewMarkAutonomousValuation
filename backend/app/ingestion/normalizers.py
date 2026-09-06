import json
from typing import Any, Callable

from pydantic import ValidationError

from app.ingestion.schema import IngestDocument, IngestionError
from app.logic.groundedness_verifier import market_stat_id
from app.schemas.evidence import Comp, TimeSeries

# Maps alternate field names (from non-uniform exports) to the canonical
# Comp/TimeSeries field names, after keys have been lowercased and
# whitespace-normalized to underscores.
_COMP_ALIASES = {
    "id": "comp_id",
    "compid": "comp_id",
    "property_address": "address",
    "square_feet": "sf",
    "square_footage": "sf",
    "asking_rent": "asking_rent_psf",
    "effective_rent": "effective_rent_psf",
    "lease_start": "lease_start_date",
    "industry": "tenant_industry",
    "verified_at": "last_verified_at",
}

_MARKET_STAT_ALIASES = {
    "sub_market_id": "submarket_id",
    "metric_name": "metric",
}


def _canonicalize_keys(raw: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    """Normalizes incoming keys (case/whitespace) and remaps known aliases so
    records exported under slightly different field names still validate."""
    canonical: dict[str, Any] = {}
    for key, value in raw.items():
        norm_key = str(key).strip().lower().replace(" ", "_")
        norm_key = aliases.get(norm_key, norm_key)
        canonical[norm_key] = value if value != "" else None
    return canonical


def normalize_comp(raw: dict[str, Any], source_system: str) -> IngestDocument:
    canonical = _canonicalize_keys(raw, _COMP_ALIASES)
    try:
        comp = Comp(**canonical)
    except ValidationError as exc:
        raise IngestionError(raw, f"invalid comp record: {exc}") from exc

    text = (
        f"Comp {comp.comp_id}: {comp.sf:,} SF {comp.lease_type} lease at {comp.address} "
        f"({comp.submarket_id}), {comp.tenant_industry} tenant. "
        f"Asking ${comp.asking_rent_psf}/PSF, effective ${comp.effective_rent_psf}/PSF, "
        f"lease started {comp.lease_start_date}."
    )
    if comp.concessions:
        text += f" Concessions: {comp.concessions}."

    return IngestDocument(
        doc_id=comp.comp_id,
        doc_type="comp",
        text=text,
        metadata=json.loads(comp.model_dump_json()),
        source_system=comp.source_system or source_system,
    )


def normalize_market_stat(raw: dict[str, Any], source_system: str) -> IngestDocument:
    canonical = _canonicalize_keys(raw, _MARKET_STAT_ALIASES)
    try:
        series = TimeSeries(**canonical)
    except ValidationError as exc:
        raise IngestionError(raw, f"invalid market_stat record: {exc}") from exc

    recent_points = ", ".join(f"{point.period}={point.value}" for point in series.points[-4:])
    direction = "up" if series.yoy_change >= 0 else "down"
    text = (
        f"Market stat for {series.submarket_id} — {series.metric}: "
        f"{direction} {abs(series.yoy_change) * 100:.1f}% YoY, "
        f"percentile rank {series.percentile_rank * 100:.0f}. Recent values: {recent_points}."
    )

    return IngestDocument(
        doc_id=market_stat_id(series.submarket_id, series.metric),
        doc_type="market_stat",
        text=text,
        metadata=json.loads(series.model_dump_json()),
        source_system=source_system,
    )


NORMALIZERS: dict[str, Callable[[dict[str, Any], str], IngestDocument]] = {
    "comp": normalize_comp,
    "market_stat": normalize_market_stat,
}


def normalize_record(raw: dict[str, Any], doc_type: str, source_system: str) -> IngestDocument:
    normalizer = NORMALIZERS.get(doc_type)
    if normalizer is None:
        raise IngestionError(raw, f"no normalizer registered for doc_type={doc_type!r}")
    return normalizer(raw, source_system)
