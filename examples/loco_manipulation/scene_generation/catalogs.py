"""Build and load the catalogs used by the v1 scene format."""

import hashlib
import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[2]
SOURCE = ROOT / "results/motiondisco_object_catalog.json"

ASSET_NAMES = {
    "table_short": "Short solid platform",
    "table_tall": "Tall solid platform",
    "green_box": "Green box",
    "white_box": "White box",
    "yellow_box": "Yellow box",
    "crate": "Wooden-colored crate",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def build_asset_catalog(source=SOURCE):
    original = read_json(source)
    assets = {}
    for asset_id, name in ASSET_NAMES.items():
        matches = [asset for asset in original["objects"] if asset_id in asset["names"]]
        if len(matches) != 1:
            raise ValueError(f"Expected one source definition for {asset_id}, found {len(matches)}")
        entry = matches[0]
        movable = entry["faro_type"] == "MovableBox"
        assets[asset_id] = {
            "name": name,
            "category": "movable_box" if movable else "platform",
            "movable": movable,
            "source_id": entry["id"],
            **{key: value for key, value in entry.items() if key not in ("id", "names", "occurrences")},
        }

    # Only the requested half extents will vary at runtime. All extracted
    # floors must agree on the remaining fields.
    floors = [{key: value for key, value in entry.items() if key not in
               ("id", "names", "occurrences", "half_extents", "full_size")}
              for entry in original["objects"] if entry["faro_type"] == "Plane"]
    if not floors or any(floor != floors[0] for floor in floors):
        raise ValueError("Extracted floors disagree on the Plane defaults")
    return {
        "schema_version": 1,
        "source": {"file": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "faro": original["faro"]},
        "units": original["units"],
        "contact_type_codes": original["contact_type_codes"],
        "contact_permissions": original["contact_permissions"],
        "floor_defaults": floors[0],
        "assets": assets,
    }


def load_assets():
    return read_json(DIRECTORY / "asset_catalog.json")


def load_tasks():
    return read_json(DIRECTORY / "task_catalog.json")


if __name__ == "__main__":
    write_json(DIRECTORY / "asset_catalog.json", build_asset_catalog())
