"""Brand contract loading and KCT-first resolution."""
from __future__ import annotations

from pathlib import Path

import yaml

from .contracts import BrandContract, FormatSpec

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BRAND_PATH = PROJECT_ROOT / "configs" / "brand_contracts.yaml"


class BrandNotFoundError(KeyError):
    pass


def load_brand_contracts(path: str | Path | None = None) -> dict[str, BrandContract]:
    """Load every brand contract from YAML, validating each record."""
    config_path = Path(path) if path else DEFAULT_BRAND_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Brand contract file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    records = raw.get("brands", raw)
    if not isinstance(records, dict) or not records:
        raise ValueError(f"No brand records found in {config_path}")

    contracts: dict[str, BrandContract] = {}
    for school_id, record in records.items():
        payload = dict(record)
        payload.setdefault("school_id", school_id)
        contracts[str(school_id).upper()] = BrandContract.model_validate(payload)
    return contracts


def get_brand(school_id: str, path: str | Path | None = None) -> BrandContract:
    """Return a brand contract by school id (case-insensitive)."""
    contracts = load_brand_contracts(path)
    key = school_id.strip().upper()
    if key not in contracts:
        available = ", ".join(sorted(contracts))
        raise BrandNotFoundError(f"Unknown school {school_id!r}. Available: {available}")
    return contracts[key]


def resolve_format(brand: BrandContract, name: str) -> FormatSpec:
    """Resolve a named format, accepting a few common aliases."""
    aliases = {
        "story": "story",
        "9:16": "story",
        "vertical": "story",
        "square": "square",
        "1:1": "square",
        "fourfive": "fourfive",
        "4:5": "fourfive",
        "a3": "A3",
        "a4": "A4",
    }
    key = aliases.get(name.strip().lower(), name.strip())
    if key in brand.formats:
        return brand.formats[key]
    for fmt_name, fmt in brand.formats.items():
        if fmt_name.lower() == key.lower():
            return fmt
    available = ", ".join(sorted(brand.formats))
    raise KeyError(f"Format {name!r} not defined for {brand.school_id}. Available: {available}")


def mm_to_px(mm: float, dpi: int) -> float:
    return mm / 25.4 * dpi
