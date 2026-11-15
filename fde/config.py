"""Settings live in config/. The product reads catalog.json and product.json; the world reads catalog.json and its own file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load(name: str, root: Path | None = None) -> dict[str, Any]:
    return json.loads(((root or ROOT) / "config" / name).read_text(encoding="utf-8"))
