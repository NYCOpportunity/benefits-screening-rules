from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import yaml

from src.models.schemas import AggregateEligibilityRequest

THRESHOLDS_PATH = Path(__file__).parent / "thresholds.yaml"


@lru_cache(maxsize=1)
def _load_thresholds() -> dict:
    with THRESHOLDS_PATH.open() as thresholds_file:
        return yaml.safe_load(thresholds_file)


def limits_for(program: str) -> dict[int, float]:
    """Return the by-size limit table for a program."""
    return _load_thresholds()[program]["by_size"]


def pathway_limit(program: str, pathway: str, household_size: int) -> float | None:
    """Return the income limit for a multi-pathway program (e.g. SNAP FPL)."""
    return _load_thresholds()[program][pathway]["by_size"].get(household_size)


def scalar_limit(program: str, key: str) -> float | None:
    """Return a single numeric limit for a program (e.g. EITC investment limit)."""
    value = _load_thresholds()[program].get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def income_at_or_below(
    request: AggregateEligibilityRequest,
    program: str,
    household_size: int,
) -> bool:
    program_config = _load_thresholds()[program]
    field = program_config["field"]
    income = getattr(request, field)
    limit = limits_for(program).get(household_size)
    if limit is None:
        return False
    return income <= limit
