"""Strict v1 SceneSpec parsing and cross-reference validation."""

from collections import Counter
from dataclasses import dataclass, field
import json
from math import dist, pi
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .catalogs import DIRECTORY, load_assets, write_json

ASSETS = load_assets()["assets"]
ASSET_IDS = tuple(ASSETS)
ASSETS_BY_CATEGORY = {
    category: [asset for asset, data in ASSETS.items() if data["category"] == category]
    for category in ("platform", "movable_box")
}
CATEGORY_LIMIT = 2
REACH_DISTANCE = (0.8, 3.0)
ID_PATTERN = r"^[a-z][a-z0-9_]{0,47}$"

Name = Annotated[str, Field(pattern=ID_PATTERN)]
X = Annotated[float, Field(ge=-4, le=4)]
Y = Annotated[float, Field(ge=-2.5, le=2.5)]
Yaw = Annotated[float, Field(ge=-pi, le=pi)]
FloorX = Annotated[float, Field(ge=1.5, le=4)]
FloorY = Annotated[float, Field(ge=1, le=2.5)]
AssetID = Literal[ASSET_IDS]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class Floor(StrictModel):
    half_extents: tuple[FloorX, FloorY]


class Robot(StrictModel):
    initial_xy_yaw: tuple[X, Y, Yaw]


class Placement(StrictModel):
    asset_id: AssetID
    instance_id: Name
    support_object: Name
    support_surface: Literal["surface", "top"]
    relative_xy_yaw: tuple[X, Y, Yaw]


class ReachParameters(StrictModel):
    target_xy: tuple[X, Y]


class ReachTask(StrictModel):
    type: Literal["reach_position"]
    parameters: ReachParameters


class SceneSpec(StrictModel):
    schema_version: Literal[1]
    scene_id: Name
    floor: Floor
    robot: Robot
    objects: list[Placement] = Field(min_length=1, max_length=4)
    task: ReachTask


def scene_schema():
    schema = SceneSpec.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["properties"]["objects"]["allOf"] = [
        {"contains": {"properties": {"asset_id": {"enum": ids}}, "required": ["asset_id"]},
         "minContains": 0, "maxContains": CATEGORY_LIMIT}
        for ids in ASSETS_BY_CATEGORY.values()
    ]
    return schema


@dataclass
class Issue:
    code: str
    subject: str
    message: str
    details: dict = field(default_factory=dict)


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"Duplicate JSON field {key!r}")
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError(f"Invalid JSON number {value!r}")


def parse_spec(raw):
    try:
        decoded = json.loads(raw, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        return None, [Issue("INVALID_JSON", "$", str(exc))]
    # Pydantic's strict JSON mode accepts JSON arrays for fixed-size tuples.
    if isinstance(decoded, dict) and type(decoded.get("schema_version")) is bool:
        return None, [Issue("INVALID_SCHEMA", "schema_version", "Expected integer version 1")]
    try:
        spec = SceneSpec.model_validate_json(raw)
    except ValidationError as exc:
        errors = []
        for error in exc.errors(include_input=False, include_url=False, include_context=False):
            path = ".".join(map(str, error["loc"])) or "$"
            code = "UNKNOWN_ASSET" if path.endswith(".asset_id") else "INVALID_SCHEMA"
            errors.append(Issue(code, path, error["msg"]))
        return None, errors
    return spec, []


def check_references(spec, reserved_names):
    errors = []
    instances = {}
    for obj in spec.objects:
        name = obj.instance_id
        if name in instances or name in reserved_names:
            errors.append(Issue("INVALID_INSTANCE_ID", name, "Instance ID must be unique and cannot name a robot channel or floor"))
        instances[name] = obj
    counts = Counter(ASSETS[obj.asset_id]["category"] for obj in spec.objects)
    for category, count in counts.items():
        if count > CATEGORY_LIMIT:
            errors.append(Issue("OBJECT_LIMIT", category, f"Found {count}; maximum is {CATEGORY_LIMIT}"))

    for name, obj in instances.items():
        support = obj.support_object
        if support != "floor" and support not in instances:
            errors.append(Issue("UNKNOWN_SUPPORT", name, f"Support {support!r} does not exist"))
            continue
        required = "surface" if support == "floor" else "top"
        if obj.support_surface != required:
            errors.append(Issue("INVALID_SUPPORT_SURFACE", name, f"{support!r} must use face {required!r}"))
        if support != "floor" and ASSETS[instances[support].asset_id]["movable"] and not ASSETS[obj.asset_id]["movable"]:
            errors.append(Issue("INVALID_SUPPORT", name, "FARO requires a fixed platform to have a fixed support"))
        visited = {name}
        while support in instances:
            if support in visited:
                errors.append(Issue("SUPPORT_CYCLE", name, "Support chain must reach the floor"))
                break
            visited.add(support)
            support = instances[support].support_object

    distance = dist(spec.robot.initial_xy_yaw[:2], spec.task.parameters.target_xy)
    if not REACH_DISTANCE[0] - 1e-9 <= distance <= REACH_DISTANCE[1] + 1e-9:
        errors.append(Issue("TARGET_DISTANCE", "robot", "Start-to-target distance must be 0.8–3 m", {"distance_m": distance}))
    return errors


if __name__ == "__main__":
    write_json(DIRECTORY / "scene_spec.schema.json", scene_schema())
