"""Detect coordinate-only rewrites of the existing MotionDisCo scenes."""

from functools import lru_cache
from pathlib import Path

from faro.configs.scene import OnFace
from scenes.common.registry import get_initial_condition, make_scene
import scenes.motiondisco

from .spec import ASSETS, Issue


def _signature(nodes):
    """Rooted support forest, invariant to instance labels and poses."""
    children = {}
    for name, (_, parent) in nodes.items():
        children.setdefault(parent, []).append(name)

    def subtree(name):
        return (nodes[name][0], tuple(sorted(map(subtree, children.get(name, ())))))

    return tuple(sorted(map(subtree, children.get("floor", ()))))


def _physical_key(kind, half, mass, color):
    return kind, tuple(half), mass, tuple(color)


@lru_cache(maxsize=1)
def reference_layouts():
    by_physics = {_physical_key(a["faro_type"], a["half_extents"], a["mass"], a["color_rgba"]): asset
                  for asset, a in ASSETS.items()}
    references = {}
    for root in scenes.motiondisco.__path__:
        for path in sorted(Path(root).glob("*/scene.py")):
            name = "motiondisco." + path.parent.name
            scene = make_scene(name)
            state = get_initial_condition(name, scene=scene)
            nodes = {}
            for obj, cfg in scene.objects.items():
                if obj == "floor":
                    continue
                asset = by_physics.get(_physical_key(type(cfg).__name__, cfg.half_extents,
                                                     getattr(cfg, "mass", None), cfg.color))
                placement = state.objects[obj]
                if asset is None or not isinstance(placement, OnFace):
                    break
                nodes[obj] = (asset, placement.on[0])
            else:
                signature = _signature(nodes)
                references.setdefault(signature, []).append(name)
    return references


def check_novelty(spec):
    signature = _signature({obj.instance_id: (obj.asset_id, obj.support_object) for obj in spec.objects})
    matches = reference_layouts().get(signature, [])
    if not matches:
        return []
    return [Issue("DUPLICATE_LAYOUT", spec.scene_id,
                  "This asset inventory and support graph match an existing MotionDisCo scene. "
                  "Change the selected assets, instance counts or support graph.",
                  {"existing_scenes": matches})]
