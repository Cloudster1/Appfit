from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from appfit.config import SOFT_FLOOR_OFFSET, Settings

THRESHOLDS_FILE = Path(__file__).with_name("thresholds.yaml")


@dataclass(frozen=True)
class Thresholds:
    model: str
    covered: float
    partial: float
    nomatch: float
    min_top_coverage: float

    @property
    def floor(self) -> float:
        return self.partial - SOFT_FLOOR_OFFSET


@lru_cache
def _load(path: Path = THRESHOLDS_FILE) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
    return data


def thresholds_for(model_name: str, settings: Settings) -> Thresholds:
    data = _load()
    values = {**data["defaults"], **data.get("models", {}).get(model_name, {})}
    overrides = {
        "covered": settings.match_t_covered,
        "partial": settings.match_t_partial,
        "nomatch": settings.match_t_nomatch,
    }
    values.update({k: v for k, v in overrides.items() if v is not None})
    return Thresholds(
        model=model_name,
        covered=float(values["covered"]),
        partial=float(values["partial"]),
        nomatch=float(values["nomatch"]),
        min_top_coverage=float(values["min_top_coverage"]),
    )
