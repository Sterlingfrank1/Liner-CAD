"""Drawing model (SPEC §3): elements = intent + placement, stable readable IDs, the Drawing container."""

from __future__ import annotations

import contextvars
import copy
import difflib
import math
import re
import sys
from pathlib import Path

from .errors import DuplicateId, InvalidArgument, NotFound, ParamError, UnknownAttribute
from .record import mutator

VIEW_NAMES = ("front", "top", "bottom", "left", "right", "rear")
ROLES = ("thick", "thin", "hidden", "center", "phantom")

_NAME_RE = re.compile(r"^[^\W\d_][\w\-]*$")
_PKG_DIR = str(Path(__file__).resolve().parent)
_SYNONYMS = {
    "delete": "suppress",
    "remove": "suppress",
    "hide": "suppress",
    "move_to": "place",
    "set_side": "place",
    "update": "set",
}

# Drawings created while a build runs register here (runtime captures the one drawing.py made).
BUILD = contextvars.ContextVar("linercad_build", default=None)


def check_name(name, what="名字") -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise InvalidArgument(
            f"{what} {name!r} 不合法：只允许字母、数字、_、-，且以字母开头",
            values={"name": name},
        )
    return name


def num(v, what="数值") -> float:
    """A number or a parameter expression → float."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise InvalidArgument(f"{what} 应为数字或参数表达式，收到 {v!r}", values={what: repr(v)})
    if not math.isfinite(x):
        raise InvalidArgument(f"{what} 不是有限数：{v!r}", values={what: repr(v)})
    return x


def caller_src() -> dict | None:
    """The first stack frame outside the linercad package: drawing.py:line during a build."""
    f = sys._getframe(1)
    while f is not None:
        fn = f.f_code.co_filename
        if not fn.startswith(_PKG_DIR) and not fn.startswith("<"):
            return {"file": Path(fn).name, "line": f.f_lineno}
        f = f.f_back
    return None


def _round(v):
    if isinstance(v, float):
        r = round(v, 4)
        return 0.0 if r == 0 else r
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_round(x) for x in v]
    return v


class Element:
    """One semantic element. Public fields are read-only; changes go through set/place/move."""

    kind = "element"
    SETTABLE: tuple = ()  # intent fields accepted by set()
    LAYOUT: tuple = ()  # placement fields accepted by place()
    READ: tuple = ()  # extra read-only properties, listed in error hints

    def __init__(self, d, id, intent, refs=(), covers=(), tags=()):
        o = object.__setattr__
        o(self, "_d", d)
        o(self, "_id", id)
        o(self, "_intent", dict(intent))
        o(self, "_layout", {})  # requested layout fields (written by build script or place/move)
        o(self, "_auto", [])  # fields chosen by the engine
        o(self, "_resolved", {})  # layout result, sheet coordinates
        o(self, "_reason", "")
        o(self, "_refs", list(refs))
        o(self, "_covers", list(covers))
        o(self, "_tags", list(tags))
        o(self, "_src", None)
        o(self, "_history", [])
        o(self, "_status", "ok")
        o(self, "_prims", [])

    # ---- read-only fields -------------------------------------------------------------
    id = property(lambda s: s._id)
    intent = property(lambda s: copy.deepcopy(s._intent))
    refs = property(lambda s: list(s._refs))
    covers = property(lambda s: list(s._covers))
    tags = property(lambda s: list(s._tags))
    src = property(lambda s: dict(s._src) if s._src else None)
    history = property(lambda s: list(s._history))
    status = property(lambda s: s._status)
    view = property(lambda s: s._intent.get("view"))
    bbox = property(lambda s: s._resolved.get("bbox"))

    @property
    def placement(self) -> dict:
        p = {f: self._layout.get(f) for f in self.LAYOUT}
        for k, v in self._layout.items():
            p.setdefault(k, v)
        p["auto"] = list(self._auto)
        p["resolved"] = dict(self._resolved)
        p["reason"] = self._reason
        return copy.deepcopy(p)

    def to_dict(self) -> dict:
        return _round(
            {
                "id": self._id,
                "kind": self.kind,
                "intent": self._intent,
                "placement": self.placement,
                "refs": self._refs,
                "covers": self._covers,
                "tags": self._tags,
                "src": self._src,
                "history": self._history,
                "status": self._status,
            }
        )

    def info(self) -> dict:
        return self.to_dict()

    def __repr__(self):
        return f"<{type(self).__name__} {self._id}>"

    # ---- agent-facing attribute errors ---------------------------------------------------
    def _api_names(self):
        names = {n for n in dir(type(self)) if not n.startswith("_")}
        return sorted(names | set(self.SETTABLE))

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        hint = None
        if name in _SYNONYMS:
            hint = f"用 {_SYNONYMS[name]}()"
        close = difflib.get_close_matches(name, self._api_names(), n=3, cutoff=0.6)
        raise UnknownAttribute(
            f"{self._id}（{self.kind}）没有 {name}",
            id=self._id,
            candidates=close or self._api_names(),
            hint=hint or "可用的方法和字段见 candidates",
        )

    def __setattr__(self, name, value):
        if name.startswith("_"):  # internal state (layout results etc.)
            object.__setattr__(self, name, value)
            return
        if name in self.SETTABLE:
            self.set(**{name: value})
            return
        raise UnknownAttribute(
            f"不能直接给 {self._id}.{name} 赋值",
            id=self._id,
            candidates=list(self.SETTABLE),
            hint="意图字段用 set(...) 或直接赋值 candidates 里的字段；布局用 place(...)/move(...)",
        )

    # ---- modifications (recorded in temp scripts) --------------------------------------
    @mutator("set")
    def set(self, **fields):
        bad = [k for k in fields if k not in self.SETTABLE]
        if bad:
            raise InvalidArgument(
                f"{self._id} 不能 set {', '.join(bad)}",
                id=self._id,
                candidates=list(self.SETTABLE),
            )
        self._apply_set(fields)
        return self

    def _apply_set(self, fields):
        self._intent.update(fields)

    @mutator("place")
    def place(self, **fields):
        if not self.LAYOUT:
            raise InvalidArgument(f"{self._id}（{self.kind}）没有可改的布局字段", id=self._id)
        bad = [k for k in fields if k not in self.LAYOUT]
        if bad:
            raise InvalidArgument(
                f"{self._id} 的布局字段没有 {', '.join(bad)}",
                id=self._id,
                candidates=list(self.LAYOUT),
            )
        self._apply_place(fields)
        return self

    def _apply_place(self, fields):
        for k, v in fields.items():
            if v is None:
                self._layout.pop(k, None)
            else:
                self._layout[k] = v

    @mutator("move")
    def move(self, dx=0, dy=0):
        self._apply_move(num(dx, "dx"), num(dy, "dy"))
        return self

    def _apply_move(self, dx, dy):
        raise InvalidArgument(f"{self._id}（{self.kind}）不能 move", id=self._id)

    @mutator("suppress")
    def suppress(self):
        self._d._remove(self._id)

    def _children(self):
        """IDs removed together with this element."""
        return []


class Drawing:
    """One drawing = one sheet. ``drawing.py`` creates exactly one."""

    def __init__(self, sheet="A3", std="GB", scale="1:1"):
        from .params import ParamSet
        from .std import load_std, load_template

        self._recorder = None
        self._src_override = None  # replay sets {"edit","line"} while applying a log operation
        self._forced_id = None  # replay sets the recorded ID of the element an op creates
        self._scope = None  # "e7" while a temp script runs: auto names become e7_<n> (SPEC §3.2)
        self._els: dict[str, Element] = {}
        self._removed: list[str] = []
        self._counters: dict[tuple, int] = {}
        self._P = ParamSet({})
        self._params_declared = False
        self.std_name = std
        self.std = load_std(std)
        self.sheet = sheet
        self.template = load_template(std, sheet)
        self.scale_text, self.scale = parse_scale(scale)
        self._src = caller_src()
        ctx = BUILD.get()
        if ctx is not None:
            ctx.append(self)
        self._init_sheet()

    def _init_sheet(self):
        from .annotate import init_sheet

        init_sheet(self)

    # ---- sheet-level annotations ---------------------------------------------------------
    @property
    def notes(self):
        from .annotate import NotesNS

        return NotesNS(self)

    def title(self, **fields):
        """Fill title-block fields (each one recorded as a ``set`` on ``T.title.<field>``)."""
        from .annotate import drawing_title

        drawing_title(self, **fields)

    @mutator("section")
    def section(self, letter, view, cut_in, through, look=None):
        from .annotate import drawing_section

        return drawing_section(self, letter, view, cut_in, through, look)

    # ---- parameters -----------------------------------------------------------------
    def params(self, **params):
        from .params import ParamSet, validate

        if self._recorder is not None:
            raise ParamError(
                "参数只能在 drawing.py 里声明和修改",
                hint="改 drawing.py 里 Param 的默认值，再 lcad build -m",
            )
        if self._params_declared:
            raise ParamError("d.params(...) 一张图只调用一次", hint="把全部参数写进同一个调用")
        validate(params)
        self._P = ParamSet(params)
        self._params_declared = True
        return self._P

    @property
    def P(self):
        return self._P

    # ---- views ------------------------------------------------------------------------
    def view(self, name):
        vid = f"V.{name}"
        if vid in self._els:
            return self._els[vid]
        return self._new_view(name)

    @mutator("view")
    def _new_view(self, name):
        from .geometry import View

        if name not in VIEW_NAMES:
            raise InvalidArgument(
                f"视图名 {name!r} 不支持（M0 只有基本视图）",
                candidates=list(VIEW_NAMES),
                values={"name": name},
            )
        return self._add(View(self, f"V.{name}", {"name": name}))

    def views(self):
        return [e for e in self._els.values() if e.kind == "view"]

    # ---- lookup -----------------------------------------------------------------------
    def __getitem__(self, id):
        el = self._els.get(id)
        if el is None:
            raise NotFound(f"找不到元素 {id}", id=id, candidates=self._close_ids(id), hint="用 lcad context 查看全部 ID")
        return el

    def __contains__(self, id):
        return id in self._els

    def get(self, id, default=None):
        return self._els.get(id, default)

    def _close_ids(self, id, n=6):
        ids = list(self._els)
        close = difflib.get_close_matches(str(id), ids, n=n, cutoff=0.5)
        prefix = str(id).rsplit(".", 1)[0]
        for i in ids:
            if len(close) >= n:
                break
            if i.startswith(prefix + ".") and i not in close:
                close.append(i)
        return close

    @property
    def elements(self):
        return list(self._els.values())

    @property
    def q(self):
        from .query import QueryRoot

        return QueryRoot(self)

    def near(self, x, y, r=5.0):
        from .query import near_sheet

        return near_sheet(self, num(x, "x"), num(y, "y"), num(r, "r"))

    # ---- element bookkeeping --------------------------------------------------------
    def _alloc(self, prefix: str, scope: tuple = (), name=None) -> str:
        """Allocate an ID ``prefix.scope....name`` or, without a name, the next free number."""
        parts = [prefix, *scope]
        if name is not None:
            check_name(name)
            return ".".join([*parts, name])
        if self._forced_id is not None:
            fid, self._forced_id = self._forced_id, None
            return fid
        key = (*parts, self._scope)
        n = self._counters.get(key, 0)
        while True:
            n += 1
            stem = f"{self._scope}_{n}" if self._scope else str(n)
            cand = ".".join([*parts, stem])
            if cand not in self._els:
                self._counters[key] = n
                return cand

    def _auto_name(self, prefix: str, scope: tuple, stem: str) -> str:
        """Next free name ``<stem>_<n>`` for ``prefix.scope.<name>`` (honours a forced ID on replay)."""
        if self._forced_id is not None:
            fid, self._forced_id = self._forced_id, None
            return fid.rsplit(".", 1)[-1]
        key = (prefix, *scope, stem, self._scope)
        n = self._counters.get(key, 0)
        while True:
            n += 1
            name = f"{stem}_{self._scope}_{n}" if self._scope else f"{stem}_{n}"
            if ".".join([prefix, *scope, name]) not in self._els:
                self._counters[key] = n
                return name

    def _add(self, el: Element) -> Element:
        if el._id in self._els:
            base = el._id
            k = 2
            while f"{base}_{k}" in self._els:
                k += 1
            raise DuplicateId(
                f"ID {base} 已存在",
                id=base,
                candidates=[f"{base}_{k}"],
                hint="换一个名字",
            )
        object.__setattr__(el, "_src", self._src_override or caller_src())
        self._els[el._id] = el
        return el

    def _owned(self, id) -> list[str]:
        """The element and everything it owns, depth first."""
        out = [id]
        for cid in self._els[id]._children():
            if cid in self._els and cid not in out:
                out += [c for c in self._owned(cid) if c not in out]
        return out

    def _remove(self, id):
        self[id]
        gone = self._owned(id)
        gone_set = set(gone)
        deps = [
            e._id
            for e in self._els.values()
            if e._id not in gone_set and any(r in gone_set for r in e._refs)
        ]
        if deps:
            raise InvalidArgument(
                f"{id} 还被其它元素引用，不能删除",
                id=id,
                candidates=deps,
                hint="先 suppress 这些依赖元素，或改它们的引用",
            )
        for gid in gone:
            del self._els[gid]
            self._removed.append(gid)


def parse_scale(scale) -> tuple[str, float]:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*", str(scale))
    if not m or float(m.group(1)) <= 0 or float(m.group(2)) <= 0:
        raise InvalidArgument(f"比例 {scale!r} 应写成 '1:2' 这样的形式", values={"scale": scale})
    a, b = float(m.group(1)), float(m.group(2))
    return f"{m.group(1)}:{m.group(2)}", a / b
