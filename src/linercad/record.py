"""Revision layer (SPEC §7): automatic recording of mutating API calls, the operation registry,
replay with stale-op reporting, and completion of layout operations.

Every public mutating API method is decorated with ``@mutator("op")``. While a temp script runs
the drawing carries a :class:`Recorder`; only the outermost mutator call is recorded.
"""

from __future__ import annotations

import functools
import inspect
import json

from .errors import BuildError, InvalidArgument, LinerError, StaleOp

CREATE_OPS = (
    "view",
    "line",
    "polyline",
    "polygon",
    "rect",
    "circle",
    "arc",
    "turned",
    "centerline",
    "center_mark",
    "holes_on_circle",
    "dim.linear",
    "dim.dia",
    "dim.rad",
    "note",
    "notes.tech",
    "hatch",
    "section",
    "raw_add",
    "removed_section",
    "detail",
    "oblique",
    "wavy",
    "datum",
    "gtol",
    "rough",
    "dim.aligned",
    "dim.angle",
    "dim.chamfer",
    "thread",
    "thread_end",
    "tapped_hole",
    "center_hole",
    "keyway",
    "keyway_end",
    "shaft_cut",
    "spline",
    "spline_end",
    "dim.thread",
    "dim.groove",
    "dim.hole",
    "dim.keyway",
    "dim.spline",
    "rough_default",
    "chain",
    "general_tol",
    "model",
    "project",
)
MODIFY_OPS = ("place", "move", "set", "suppress", "accept", "raw")
VIEW_SCOPED = (
    "line",
    "polyline",
    "polygon",
    "rect",
    "circle",
    "arc",
    "turned",
    "centerline",
    "center_mark",
    "holes_on_circle",
    "dim.linear",
    "dim.dia",
    "dim.rad",
    "note",
    "hatch",
    "wavy",
    "datum",
    "gtol",
    "rough",
    "dim.aligned",
    "dim.angle",
    "dim.chamfer",
    "thread",
    "thread_end",
    "tapped_hole",
    "center_hole",
    "keyway",
    "keyway_end",
    "shaft_cut",
    "spline",
    "spline_end",
    "dim.thread",
    "dim.groove",
    "dim.hole",
    "dim.keyway",
    "dim.spline",
    "project",
)
DRAWING_CREATE = (
    "model",
    "section",
    "raw_add",
    "removed_section",
    "detail",
    "oblique",
    "rough_default",
    "chain",
    "general_tol",
)
LAYOUT_GROUPS = {
    "linear": ("side", "row"),
    "circle": ("at",),
    "note": ("dir", "length"),
    "leader": ("at", "length"),
    "angle": ("r",),
}


def mutator(op: str):
    """Mark a public method as a modifying API call recorded under operation name ``op``."""

    def deco(fn):
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            d = self if hasattr(self, "_recorder") else self._d
            rec = d._recorder
            if rec is None:
                return fn(self, *args, **kwargs)
            return rec.call(op, fn, sig, self, args, kwargs)

        wrapper.__mutator__ = op
        return wrapper

    return deco


# ---- serialization ---------------------------------------------------------------------------------


def ser(v):
    from .model import Element
    from .params import Expr
    from .query import Query

    if isinstance(v, Expr):
        return {"expr": v.src}
    if isinstance(v, Element):
        return v.id
    if isinstance(v, Query):
        raise InvalidArgument(
            "查询结果不能直接作为参数记录进日志", hint="先 .one() 或 [k] 取出具体元素"
        )
    if isinstance(v, bool) or v is None or isinstance(v, (int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): ser(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)) or hasattr(v, "__iter__") and hasattr(v, "__len__"):
        return [ser(x) for x in v]
    raise InvalidArgument(f"参数 {v!r} 不能记录进日志（只支持数字、字符串、点、元素、参数表达式）")


def deser(v, d):
    if isinstance(v, dict):
        if set(v) == {"expr"}:
            from .params import Expr

            return Expr.from_src(v["expr"], d.P.values())
        return {k: deser(x, d) for k, x in v.items()}
    if isinstance(v, list):
        return [deser(x, d) for x in v]
    return v


def dumps(rec: dict) -> str:
    """One log line: fixed key order, compact, UTF-8."""
    out = {"edit": rec["edit"], "op": rec["op"], "id": rec.get("id"), "args": rec.get("args", {})}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


# ---- recording ----------------------------------------------------------------------------------------


class Recorder:
    """Collects the operations of one temp script (one edit)."""

    def __init__(self, d, edit: str):
        self.d = d
        self.edit = edit
        self.depth = 0
        self.ops: list[dict] = []

    def call(self, op, fn, sig, target, args, kwargs):
        if self.depth > 0:
            self.depth += 1
            try:
                return fn(target, *args, **kwargs)
            finally:
                self.depth -= 1
        bound = sig.bind(target, *args, **kwargs)
        params = dict(list(bound.arguments.items())[1:])
        for name, p in sig.parameters.items():
            if p.kind == inspect.Parameter.VAR_KEYWORD and name in params:
                params.update(params.pop(name))
        recorded = {k: ser(v) for k, v in params.items()}  # serialize before the call: fails early
        self.depth = 1
        try:
            result = fn(target, *args, **kwargs)
        finally:
            self.depth = 0
        self.ops.append(self._make(op, target, recorded, result))
        return result

    def _make(self, op, target, args, result):
        from .geometry import View

        if op in CREATE_OPS:
            rid = result.id
            if op in VIEW_SCOPED:
                view = target if isinstance(target, View) else target._view
                args = {"view": view.name, **args}
            return {"edit": self.edit, "op": op, "id": rid, "args": args}
        if op in ("accept", "raw"):
            args = dict(args)
            rid = args.pop("id")
            return {"edit": self.edit, "op": op, "id": rid, "args": args}
        if op == "move":  # freeze the layout fields the move is relative to (SPEC 7.2)
            args = dict(args)
            for k in _layout_group(target):
                v = target._layout.get(k, target._resolved.get(k))
                if v is not None and k not in args:
                    args[k] = v
        return {"edit": self.edit, "op": op, "id": target.id, "args": args}


# ---- replay -------------------------------------------------------------------------------------------


def _layout_group(el):
    i = el._intent
    if el.kind == "dim":
        if i["type"] in ("chamfer", "groove", "hole", "spline"):
            return LAYOUT_GROUPS["note"]
        if i["type"] == "angle":
            return LAYOUT_GROUPS["angle"]
        return LAYOUT_GROUPS["circle"] if i.get("circle") else LAYOUT_GROUPS["linear"]
    if el.kind in ("datum", "gtol", "rough") and not i.get("default"):
        return LAYOUT_GROUPS["leader"]
    if el.kind == "note" and not i.get("tech"):
        return LAYOUT_GROUPS["note"]
    return ()


def apply_op(d, rec):
    op, rid, args = rec["op"], rec.get("id"), deser(rec.get("args", {}), d)
    edit = rec["edit"]
    if op in CREATE_OPS:
        if rid in d._els:
            raise StaleOp(f"要创建的 {rid} 已存在", id=rid)
        d._forced_id = rid
        if op == "view":
            d._new_view(**args)
        elif op in DRAWING_CREATE:
            getattr(d, op)(**args)
        elif op == "notes.tech":
            d.notes._tech_one(**args)
        else:
            view = args.pop("view")
            v = d._els.get(f"V.{view}")
            if v is None:
                raise StaleOp(f"视图 V.{view} 不存在", id=f"V.{view}")
            if op.startswith("dim."):
                getattr(v.dim, op[4:])(**args)
            else:
                getattr(v, op)(**args)
        if rid not in d._els:
            raise BuildError(f"重放 {op} 没有建出 {rid}", id=rid)
        d._els[rid]._history.append(edit)
        return
    if op not in MODIFY_OPS:
        raise StaleOp(f"未知操作 {op}", candidates=list(CREATE_OPS + MODIFY_OPS))
    if op == "accept":
        d.accept(args["rule"], rid, args["reason"])
        return
    target = d[rid]
    if op == "set":
        target.set(**args)
    elif op == "place":
        target.place(**args)
    elif op == "move":
        absolute = {k: args[k] for k in _layout_group(target) if args.get(k) is not None}
        if absolute:
            target.place(**absolute)
        target.move(args.get("dx", 0), args.get("dy", 0))
    elif op == "suppress":
        target.suppress()
        return
    elif op == "raw":
        target._raw.append({**args, "edit": edit, "line": rec.get("_line")})
    if not target._history or target._history[-1] != edit:
        target._history.append(edit)


def replay(d, ops, current_edit=None):
    """Apply log operations in order. Stale ones are skipped and returned; the current edit's own
    operations must not fail (they raise instead)."""
    stale = []
    for rec in ops:
        line = rec.get("_line")
        d._src_override = {"edit": rec["edit"], "line": line}
        try:
            apply_op(d, rec)
        except LinerError as e:
            if current_edit is not None and rec["edit"] == current_edit:
                raise StaleOp(
                    f"本次修改的操作 {rec['op']} {rec.get('id')} 无法重放：{e.message}",
                    id=rec.get("id"),
                    candidates=e.candidates,
                    values=e.values,
                    hint=e.hint,
                ) from e
            stale.append(_stale(rec, e.message, e.candidates))
        except Exception as e:  # noqa: BLE001
            if current_edit is not None and rec["edit"] == current_edit:
                raise BuildError(
                    f"本次修改的操作 {rec['op']} 重放时出错：{type(e).__name__}: {e}"
                ) from e
            stale.append(_stale(rec, f"内部错误：{type(e).__name__}: {e}", []))
        finally:
            d._src_override = None
            d._forced_id = None
    return stale


def _stale(rec, reason, candidates):
    return {
        "edit": rec["edit"],
        "line": rec.get("_line"),
        "op": rec["op"],
        "id": rec.get("id"),
        "reason": reason,
        "candidates": list(candidates),
    }


def fill_layout(ops, d):
    """Complete place/move ops with the layout values the engine chose (SPEC §7.2)."""
    out = []
    for rec in ops:
        rec = dict(rec, args=dict(rec.get("args", {})))
        if rec["op"] in ("place", "move"):
            el = d._els.get(rec["id"])
            if el is not None:
                for k in _layout_group(el):
                    if rec["args"].get(k) is None:
                        v = el._resolved.get(k)
                        if v is not None:
                            rec["args"][k] = v
                if rec["op"] == "place" and el.kind == "dim" and "offset" in el.LAYOUT:
                    if rec["args"].get("offset") is None:
                        rec["args"]["offset"] = el._resolved.get("offset", 0) or 0
        out.append(rec)
    return out
