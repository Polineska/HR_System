from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
from django.conf import settings

try:
    import catboost as cb
except Exception:  # pragma: no cover
    cb = None  # type: ignore[assignment]


class AssetNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class Assets:
    model_burnout: object
    model_leave: object


def _candidate_dirs() -> list[Path]:
    base = Path(settings.BASE_DIR)
    return [
        base,
        base / "assets",
        base / "data",
        base / "models",
    ]


def _find_asset(filename: str) -> Path:
    for directory in _candidate_dirs():
        path = directory / filename
        if path.exists():
            return path
    raise AssetNotFoundError(
        f"Не найден файл '{filename}'. Положите его в одну из папок: "
        + ", ".join(str(d) for d in _candidate_dirs())
    )


@lru_cache(maxsize=1)
def load_assets() -> Assets:
    if cb is None:
        raise RuntimeError("catboost не установлен. Установите зависимости из requirements.txt.")

    model_burnout = cb.CatBoostRegressor()
    model_burnout.load_model(str(_find_asset("burnout_model.cbm")))

    model_leave = joblib.load(_find_asset("catboost_model.pkl"))

    return Assets(
        model_burnout=model_burnout,
        model_leave=model_leave,
    )
