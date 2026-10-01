"""Read/write the shared manifest file (BOM-tolerant)."""
from __future__ import annotations

import json
from pathlib import Path

MANIFEST_FILE = "agentshield.manifest.json"


def load_manifest(directory="."):
    path = Path(directory) / MANIFEST_FILE
    if not path.exists():
        return {"pages": []}
    raw = path.read_text(encoding="utf-8").lstrip("﻿")
    data = json.loads(raw)
    if "pages" not in data or not isinstance(data["pages"], list):
        data["pages"] = []
    return data


def save_manifest(manifest, directory="."):
    path = Path(directory) / MANIFEST_FILE
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path
