"""Build pipeline (SPEC §1.1): run drawing.py → replay the log → layout → DXF → checks."""

from __future__ import annotations

import contextlib
import json
import runpy
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import checks, dxfout, record
from .errors import BuildError, LinerError, ScriptError, StaleOp
from .layout import layout
from .model import BUILD, DRAW_DIR

SRC = "drawing.py"
LOG = "drawing.actions.jsonl"
BUILD_DIR = Path(".linercad") / "build"
TMP_DIR = Path(".linercad") / "tmp"


@dataclass
class BuildResult:
    d: object
    doc: object
    index: dict
    findings: list
    stale: list
    log_ops: list = field(default_factory=list)

    @property
    def opportunities(self):
        """{rule: objects checked} of this build, reported by ``checks.run``."""
        return dict(getattr(self.findings, "opportunities", {}))


def frames_in(exc, path: Path):
    """'file:line  code' entries of the traceback frames that belong to ``path``."""
    path = Path(path).resolve()
    out = []
    for fr in traceback.extract_tb(exc.__traceback__):
        try:
            same = Path(fr.filename).resolve() == path
        except OSError:
            same = False
        if same:
            out.append(f"{path.name}:{fr.lineno}  {(fr.line or '').strip()}")
    return out


def attach_where(err: LinerError, exc, path: Path) -> LinerError:
    trace = frames_in(exc, path)
    err.trace = trace
    err.where = trace[-1].split("  ", 1)[0] if trace else None
    return err


def load_log(dir) -> list[dict]:
    p = Path(dir) / LOG
    if not p.exists():
        return []
    ops = []
    for n, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise BuildError(f"{LOG} 第 {n} 行不是合法 JSON：{e.msg}", values={"line": n}) from e
        if not isinstance(rec, dict) or "edit" not in rec or "op" not in rec:
            raise BuildError(f"{LOG} 第 {n} 行缺少 edit/op", values={"line": n})
        rec["_line"] = n
        ops.append(rec)
    return ops


def run_drawing(dir):
    path = Path(dir) / SRC
    if not path.exists():
        raise BuildError(f"{path} 不存在", hint="先 lcad init <目录>")
    box = []
    tok, dir_tok = BUILD.set(box), DRAW_DIR.set(Path(dir))
    try:
        with contextlib.redirect_stdout(sys.stderr):
            runpy.run_path(str(path), run_name="__lcad_drawing__")
    except LinerError as e:
        raise attach_where(e, e, path)
    except (Exception, SystemExit) as e:  # reported to the agent with drawing.py frames
        raise attach_where(BuildError(f"drawing.py 出错：{type(e).__name__}: {e}"), e, path) from e
    finally:
        BUILD.reset(tok)
        DRAW_DIR.reset(dir_tok)
    if len(box) != 1:
        raise BuildError(f"drawing.py 必须创建且只创建一个 Drawing（实际 {len(box)} 个）")
    return box[0]


def build(dir, extra_ops=(), current_edit=None, params=None, dxf=True) -> BuildResult:
    """``params``: in-memory overrides of Param defaults (Viewer preview); ``dxf=False`` skips the
    DXF document (the Viewer draws SVG from the same prims)."""
    from .model import PARAM_OVERRIDES

    tok = PARAM_OVERRIDES.set(dict(params) if params else None)
    try:
        d = run_drawing(dir)
    finally:
        PARAM_OVERRIDES.reset(tok)
    log_ops = load_log(dir)
    stale = record.replay(d, log_ops + list(extra_ops), current_edit)
    layout(d)
    if not dxf:
        return BuildResult(d, None, {}, checks.run(d, stale, log_ops), stale, log_ops)
    doc, index, raw_fail = dxfout.to_doc(d)
    for f in raw_fail:
        if current_edit is not None and f["edit"] == current_edit:
            raise StaleOp(f"本次修改的 raw 操作无法应用：{f['reason']}", id=f["id"])
    stale += raw_fail
    d._dxf_index = index
    findings = checks.run(d, stale, log_ops)
    return BuildResult(d, doc, index, findings, stale, log_ops)


def write_artifacts(dir, res: BuildResult, edit=None) -> dict:
    out = Path(dir) / BUILD_DIR
    dxf = dxfout.save_doc(res.doc, out / "drawing.dxf")
    model = dxfout.write_model(res.d, out / "model.json", res.findings, edit)
    return {"dxf": dxf.relative_to(dir).as_posix(), "model": model.relative_to(dir).as_posix()}


def run_script(d, script, edit) -> list[dict]:
    """Run a temp script's ``apply(d)`` with recording on; returns the recorded operations."""
    path = Path(script)
    if not path.exists():
        raise ScriptError(f"脚本 {script} 不存在")
    rec = record.Recorder(d, edit)
    d._recorder, d._scope = rec, edit
    try:
        with contextlib.redirect_stdout(sys.stderr):
            ns = runpy.run_path(str(path), run_name="__lcad_script__")
        fn = ns.get("apply")
        if not callable(fn):
            raise ScriptError(
                "临时脚本需要定义函数 apply(d)",
                hint="def apply(d):\n    d['D.x'].place(side='top')",
            )
        with contextlib.redirect_stdout(sys.stderr):
            fn(d)
    except LinerError as e:
        raise attach_where(e, e, path)
    except (Exception, SystemExit) as e:
        raise attach_where(ScriptError(f"{type(e).__name__}: {e}"), e, path) from e
    finally:
        d._recorder, d._scope = None, None
    return rec.ops


def edit_number(rec_edit: str) -> int:
    try:
        return int(str(rec_edit).lstrip("e"))
    except ValueError:
        return -1
