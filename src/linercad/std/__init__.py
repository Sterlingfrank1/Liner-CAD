"""Standard profiles and sheet templates (SPEC §6).

A profile (``gb.toml``) holds styles and numbers, every group with its ``basis`` (a standard
number, or ``convention``); ``iso.toml`` says ``extends = "GB"`` and overrides only what differs.
A template (``templates/GB-A3.toml`` ...) holds one sheet: size, margins, title-block lines, fixed
labels, named field slots and the projection-method symbol per first/third angle. Both are
package data, read with ``importlib.resources`` and ``tomllib``; every call returns a fresh dict
the caller may edit. An enterprise overlay (``<drawing dir>/templates/<name>.toml``, written by
``lcad template import``) carries ``[std.*]`` overrides and a replacement ``[title_block]``.
"""

from __future__ import annotations

import copy
import tomllib
from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path

from ..errors import InvalidArgument

__all__ = ["deep_merge", "load_overlay", "load_std", "load_template"]

# Built-in profiles: name -> data file.
_PROFILES = {"GB": "gb.toml", "ISO": "iso.toml"}


def _read_toml(*parts: str) -> dict:
    node = resources.files(__package__)
    for part in parts:
        node = node / part
    return tomllib.loads(node.read_text(encoding="utf-8"))


def _check_std(name: object) -> str:
    if isinstance(name, str) and name in _PROFILES:
        return name
    raise InvalidArgument(f"未知标准档 {name!r}", candidates=list(_PROFILES))


def _profile(file: str) -> dict:
    """A profile file with its ``extends`` chain resolved (the parent first, the child over it)."""
    data = _read_toml(file)
    parent = data.pop("extends", None)
    return deep_merge(_profile(_PROFILES[parent]), data) if parent else data


def _template_sheets(std: str) -> list[str]:
    prefix = f"{std}-"
    folder = resources.files(__package__) / "templates"
    stems = [p.name[: -len(".toml")] for p in folder.iterdir() if p.name.endswith(".toml")]
    return sorted(s[len(prefix) :] for s in stems if s.startswith(prefix))


def deep_merge(base: Mapping, over: Mapping) -> dict:
    """Return ``base`` overlaid with ``over`` as a new dict; neither input is changed or shared.

    Dicts merge recursively; scalars and lists in ``over`` replace the ``base`` value whole
    (also when the types differ); keys only in ``over`` are added.
    """
    out: dict = {}
    for key, value in base.items():
        if key not in over:
            out[key] = copy.deepcopy(value)
        elif isinstance(value, Mapping) and isinstance(over[key], Mapping):
            out[key] = deep_merge(value, over[key])
        else:
            out[key] = copy.deepcopy(over[key])
    for key, value in over.items():
        if key not in base:
            out[key] = copy.deepcopy(value)
    return out


def load_std(name: str, overlays: Sequence[Mapping] = ()) -> dict:
    """Load the built-in standard profile ``name`` and merge ``overlays`` on top, in order."""
    name = _check_std(name)
    if isinstance(overlays, Mapping):
        raise InvalidArgument(
            "overlays 应是 dict 的序列，收到的是单个 dict",
            hint="把叠加档放进列表：load_std(name, [overlay])",
        )
    std = _profile(_PROFILES[name])
    for index, overlay in enumerate(overlays):
        if not isinstance(overlay, Mapping):
            raise InvalidArgument(
                f"overlays[{index}] 不是 dict，而是 {type(overlay).__name__}",
                values={"index": index},
                hint="每个叠加档是一个 dict，结构同标准档（如 {'dim': {'text_height': 2.5}}）",
            )
        std = deep_merge(std, overlay)
    return std


def load_overlay(name: str, base: str | Path) -> dict:
    """Read the enterprise overlay ``<base>/templates/<name>.toml`` (``lcad template import``)."""
    folder = Path(base) / "templates"
    path = folder / f"{name}.toml"
    if not path.is_file():
        have = sorted(p.stem for p in folder.glob("*.toml")) if folder.is_dir() else []
        raise InvalidArgument(
            f"找不到企业档 {name!r}（{path}）",
            candidates=have,
            hint="lcad template import <file.dxf> --name <名> 生成 templates/<名>.toml",
        )
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_template(std: str, sheet: str, title_block: Mapping | None = None) -> dict:
    """Load the sheet template ``<std>-<sheet>`` and add the computed ``title_block.origin``
    (lower-left corner of the title block, sheet coordinates) and ``frame`` (inner frame
    ``[x0, y0, x1, y1]``). ``title_block`` (an enterprise overlay's) replaces the built-in one."""
    std = _check_std(std)
    available = _template_sheets(std)
    if not (isinstance(sheet, str) and sheet in available):
        raise InvalidArgument(
            f"标准档 {std} 没有图幅 {sheet!r} 的模板",
            candidates=available,
            hint=f"{std} 档内置 {', '.join(available)} 的模板",
        )
    template = _read_toml("templates", f"{std}-{sheet}.toml")
    if title_block is not None:
        missing = [k for k in ("size", "lines", "fields") if k not in title_block]
        if missing:
            raise InvalidArgument(
                f"企业档的 [title_block] 缺 {', '.join(missing)}", values={"missing": missing}
            )
        template["title_block"] = copy.deepcopy(dict(title_block))
    width, height = template["size"]
    left, bottom, right, top = template["margins"]
    block_width = template["title_block"]["size"][0]
    template["title_block"]["origin"] = [width - right - block_width, bottom]
    template["frame"] = [left, bottom, width - right, height - top]
    return template
