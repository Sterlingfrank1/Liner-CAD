"""M2 V1: Viewer — SVG ids, selectors, issue colours, bridge files, preview and write-back,
and the local HTTP service's guards (SPEC §2, §4)."""

import json
import random
import re
import subprocess
import threading
import urllib.error
import urllib.request

import pytest

from linercad import commands, svgout, txn
from linercad.errors import LinerError
from linercad.runtime import build
from linercad.viewer import Viewer, make_handler, rewrite_param

EXAMPLES = ["shaft", "flange", "pulley", "end_cover"]

# B3 acceptance scenario: drag D until the preview build has a violation. Main's layout work (D1 moved
# the flange radial leaders / section label) can move this value: keep it in one place, and assert the
# semantics (a finding with the E1 fields on a drawn element) rather than one layout coordinate.
PREVIEW_VIOLATION = {"D": 150}
PREVIEW_VIOLATION_ID = "S.A"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = {}
    for name in EXAMPLES:
        p = tmp_path_factory.mktemp(name) / name
        txn.init(p, from_=name)
        out[name] = (p, build(p))
    return out


@pytest.mark.parametrize("name", EXAMPLES)
def test_every_drawn_element_is_clickable(built, name):
    p, res = built[name]
    svg = svgout.svg(res.d)
    ids = set(re.findall(r'data-id="([^"]+)"', svg))
    assert ids == {e.id for e in res.d._els.values() if e._prims}


def test_selectors_find_the_same_edge(built):
    rnd = random.Random(7)
    for name in EXAMPLES:
        d = built[name][1].d
        edges = [e for e in d._els.values() if e.kind == "edge" and re.search(r"\.\d+$", e.id)]
        for e in rnd.sample(edges, min(5, len(edges))):
            assert svgout.run_selector(d, svgout.selector(e)) is e, e.id


def test_selector_is_never_evaluated(built):
    d = built["shaft"][1].d
    with pytest.raises(LinerError):
        svgout.run_selector(d, "__import__('os').system('echo hi')")
    with pytest.raises(LinerError):
        svgout.run_selector(d, "d.q.lines(view='front').where(length=open('x'))")


def test_issue_colours_match_lcad_check(tmp_path):
    p = tmp_path / "f"
    txn.init(p, from_="flange")
    script = p / ".linercad" / "tmp" / "x.py"
    script.write_text(
        'def apply(d):\n    d.view("front").gtol("zz", "perpendicularity", 0.03, datums=["Z"], ref="D.D")\n',
        encoding="utf-8",
    )
    assert txn.edit(p, script, "加形位公差")["ok"]  # an undefined datum reference: an error finding
    v = Viewer(p)
    seen = {(i["rule"], i["id"], i["severity"]) for i in v.model()["issues"]}
    chk = commands.check(p)
    want = {(f["rule"], f["id"], f["severity"]) for fs in chk["packs"].values() for f in fs}
    assert seen == want and any(s == "error" for _, _, s in seen)


def git_log(p):
    r = subprocess.run(
        ["git", "-C", str(p), "log", "--format=%s"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return r.stdout.splitlines()


@pytest.fixture
def shaft(tmp_path):
    p = tmp_path / "s"
    txn.init(p, from_="shaft")
    return p


def test_selection_bridge_and_context_at_sel(shaft):
    v = Viewer(shaft)
    edge = next(
        e.id for e in v.res.d._els.values() if e.kind == "edge" and re.search(r"\.\d+$", e.id)
    )
    out = v.select(["D.L", edge])
    sel = json.loads((shaft / ".linercad/selection.json").read_text(encoding="utf-8"))
    assert sel["ids"] == ["D.L", edge] and sel["items"][0]["ref"].startswith("@D.L（")
    assert out["items"][1]["selector"].startswith("d.q.")
    snap = json.loads((shaft / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    assert snap["selection"][0]["id"] == "D.L" and snap["version"] == "e0"
    ctx = commands.context(shaft, ["@sel"])
    assert [x["element"]["id"] for x in ctx["items"]] == ["D.L", edge]
    src = shaft / "drawing.py"  # broken drawing.py: fall back to the last model.json
    src.write_text(
        src.read_text(encoding="utf-8") + "\nraise RuntimeError('half')\n", encoding="utf-8"
    )
    ctx = commands.context(shaft, ["@sel"])
    assert ctx["stale"] and ctx["items"][0]["element"]["id"] == "D.L"
    assert v.state()["build_error"] and v.current_svg()  # the Viewer keeps the last good version


def test_preview_is_memory_only_and_rule_checked(shaft):
    v = Viewer(shaft)
    before = (shaft / "drawing.py").read_bytes(), git_log(shaft)
    p0 = {p["name"]: p for p in v.params()["params"]}
    name = next(n for n, p in p0.items() if p["max"] and p["max"] > p["value"] and not p["rule"])
    val = p0[name]["value"] + 1
    r = v.do_preview({name: val})
    assert r["ok"] and r["timing_ms"] < 2000 and v.state()["preview"]
    snap = json.loads((shaft / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    assert snap["params"] == {name: val}
    ruled = next(n for n, p in p0.items() if p["rule"])
    bad = v.do_preview({ruled: -1e6})
    assert not bad["ok"] and bad["error"]["code"] == "param"
    assert ((shaft / "drawing.py").read_bytes(), git_log(shaft)) == before


def test_writeback_changes_one_line_and_commits_once(shaft):
    v = Viewer(shaft)
    p0 = {p["name"]: p for p in v.params()["params"]}
    name = next(n for n, p in p0.items() if p["max"] and p["max"] > p["value"] and not p["rule"])
    val = int(p0[name]["value"] + 1)
    old = (shaft / "drawing.py").read_text(encoding="utf-8").splitlines()
    n0 = len(git_log(shaft))
    out = v.writeback(name, val)
    assert out["ok"] and out["edit"] == "e1"
    new = (shaft / "drawing.py").read_text(encoding="utf-8").splitlines()
    diff = [(a, b) for a, b in zip(old, new) if a != b]
    assert len(old) == len(new) and len(diff) == 1 and f"Param({val}" in diff[0][1]
    log = git_log(shaft)
    assert len(log) == n0 + 1 and log[0] == f"e1 · 参数 {name}={val}（Viewer 写回）"
    ruled = next(n for n, p in p0.items() if p["rule"])
    with pytest.raises(LinerError):
        v.writeback(ruled, -1e6)  # violates its rule: nothing written
    assert len(git_log(shaft)) == n0 + 1 and not txn.dirty_sources(shaft)


def test_writeback_refuses_dirty_sources_and_expressions(shaft):
    v = Viewer(shaft)
    name = v.params()["params"][0]["name"]
    src = shaft / "drawing.py"
    src.write_text(src.read_text(encoding="utf-8") + "\n# agent half-way\n", encoding="utf-8")
    with pytest.raises(LinerError) as e:
        v.writeback(name, 1)
    assert "未提交" in str(e.value)
    with pytest.raises(LinerError):
        rewrite_param("P = d.params(a=Param(2 * 3))\n", "a", 7)
    got = rewrite_param("P = d.params(a=Param(-2, min=-5))\n", "a", -3)
    assert got == "P = d.params(a=Param(-3, min=-5))\n"


def test_auto_refresh_after_an_edit(shaft):
    v = Viewer(shaft)
    s0 = v.state()
    script = shaft / ".linercad" / "tmp" / "m.py"
    script.write_text('def apply(d):\n    d["D.L"].place(side="top")\n', encoding="utf-8")
    assert txn.edit(shaft, script, "总长挪到上方")["ok"]
    s1 = v.state()
    assert s1["version"] > s0["version"] and s1["edit"] == "e1" and "总长挪到上方" in s1["status"]


# ---- HTTP service --------------------------------------------------------------------------------


@pytest.fixture
def server(shaft):
    from http.server import ThreadingHTTPServer

    v = Viewer(shaft)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(v))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield v, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def req(url, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    h = {"Content-Type": "application/json"} if body is not None else {}
    r = urllib.request.Request(url, data=data, headers={**h, **(headers or {})})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_service_guards(server):
    v, base = server
    code, page = req(base + "/")
    assert code == 200 and v.token.encode() in page
    assert req(base + "/svg")[0] == 200
    assert req(base + "/viewer.js")[0] == 200
    assert req(base + "/..%2Fpyproject.toml")[0] == 404
    assert req(base + "/api/select", {"ids": ["D.L"]})[0] == 403  # no token
    hdr = {"X-LCAD-Token": v.token, "Origin": "http://evil.example"}
    assert req(base + "/api/select", {"ids": ["D.L"]}, hdr)[0] == 403
    assert req(base + "/api/state", headers={"Host": "evil.example"})[0] == 403
    code, body = req(base + "/api/select", {"ids": ["D.L"]}, {"X-LCAD-Token": v.token})
    assert code == 200 and json.loads(body)["ids"] == ["D.L"]


def test_writeback_keeps_crlf_and_restores_bytes_on_failure(shaft, monkeypatch):
    v = Viewer(shaft)
    p = v.params()["params"][0]
    src = shaft / "drawing.py"
    raw = src.read_bytes()
    monkeypatch.setattr(
        txn, "build_commit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    with pytest.raises(RuntimeError):
        v.writeback(p["name"], p["value"])
    assert src.read_bytes() == raw and not txn.dirty_sources(shaft)


def test_late_preview_is_ignored_and_errors_recorded(shaft):
    v = Viewer(shaft)
    ps = {p["name"]: p for p in v.params()["params"]}
    n = next(k for k, p in ps.items() if not p["rule"])
    assert v.do_preview({n: ps[n]["value"] + 1}, seq=2)["ok"]
    assert v.do_preview({n: ps[n]["value"] + 2}, seq=1).get("superseded")
    ruled = next(k for k, p in ps.items() if p["rule"])
    v.do_preview({ruled: -1e6}, seq=3)
    snap = json.loads((shaft / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    assert snap["param_errors"]["error"]["code"] == "param"


def test_context_at_sel_refuses_an_old_selection(shaft):
    v = Viewer(shaft)
    v.select(["D.L"])
    script = shaft / ".linercad" / "tmp" / "m.py"
    script.write_text('def apply(d):\n    d["D.L"].place(side="top")\n', encoding="utf-8")
    txn.edit(shaft, script, "挪")
    with pytest.raises(LinerError) as err:
        commands.context(shaft, ["@sel"])
    assert err.value.code == "selection_stale"
    assert "当前没有有效选中" in err.value.message
    assert "e0" in err.value.message and "e1" in err.value.message
    assert err.value.hint and "@ID" in err.value.hint


def test_context_at_sel_refuses_an_expired_selection(shaft):
    from datetime import UTC, datetime

    v = Viewer(shaft)
    v.select(["D.L"])
    path = shaft / ".linercad/selection.json"
    sel = json.loads(path.read_text(encoding="utf-8"))
    sel["time"] = datetime(2000, 1, 1, tzinfo=UTC).isoformat(timespec="seconds")
    path.write_text(json.dumps(sel), encoding="utf-8")
    with pytest.raises(LinerError) as err:
        commands.context(shaft, ["@sel"])
    assert err.value.code == "selection_stale" and "当前没有有效选中" in err.value.message
    assert "超时" in err.value.message or "过期" in err.value.message


def test_context_at_sel_reports_no_selection(shaft):
    with pytest.raises(LinerError) as err:
        commands.context(shaft, ["@sel"])
    assert err.value.code == "selection_stale" and "当前没有有效选中" in err.value.message


def test_selection_refs_carry_value_tolerance_and_view(shaft):
    from datetime import datetime

    v = Viewer(shaft)
    v.select(["D.d2", "D.d1", "D.L"])
    sel = json.loads((shaft / ".linercad/selection.json").read_text(encoding="utf-8"))
    line = " ".join(item["ref"] for item in sel["items"])
    assert line == "@D.d2（Φ30k6，主视图） @D.d1（M24×1.5-6g，主视图） @D.L（200，主视图）"
    ctx = commands.context(shaft, ["@sel"])
    assert [x["element"]["id"] for x in ctx["items"]] == ["D.d2", "D.d1", "D.L"]
    assert ctx["selection"]["fresh"] is True and ctx["selection"]["ids"] == ["D.d2", "D.d1", "D.L"]
    assert datetime.fromisoformat(ctx["selection"]["time"]).year >= 2026


def test_viewer_copy_reference_ui():
    from importlib import resources

    js = (resources.files("linercad.viewer") / "viewer.js").read_text(encoding="utf-8")
    for needle in ("复制引用", "Ctrl+Shift+C", "selectionRefs", 'join(" ")'):
        assert needle in js, needle


@pytest.fixture
def flange_dir(tmp_path):
    p = tmp_path / "fl"
    txn.init(p, from_="flange")
    return p


# ---- B3: preview findings on the canvas, the four E1 fields in the inspector / snapshot ---------


def test_preview_returns_e1_finding_fields(flange_dir):
    v = Viewer(flange_dir)
    r = v.do_preview(
        PREVIEW_VIOLATION
    )  # the flange drags D out until the section label hits the frame
    assert r["ok"] and r["findings"], r
    for f in r["findings"]:  # every preview violation carries the E1 fields
        assert {"rule", "id", "severity", "message"} <= set(f)
        assert {"clause", "measured", "expected", "candidates"} <= set(f), f
    hit = [f for f in r["findings"] if f["id"] == PREVIEW_VIOLATION_ID]
    assert hit, r["findings"]
    f = hit[0]
    assert f["severity"] == "warn" and f["rule"] == "overlap"
    assert "GB/T 4458.4-2003" in f["clause"] and "尺寸" in f["clause"]  # E1 clause statement
    assert isinstance(f["measured"], dict) and f["measured"]  # E1 measured values
    assert f["expected"]["overlap"] == 0.0  # E1 expectation
    assert f["candidates"] == [] and isinstance(f["candidates"], list)  # E1 candidates
    assert f["pack"] == "layout" and f["std"] == "GB/T 4458.4-2003"
    assert r["resolved"] == {}  # every finding points at a drawn element directly
    assert r["element_issues"][PREVIEW_VIOLATION_ID][0]["clause"] == f["clause"]  # inspector data


def test_preview_findings_reach_model_and_snapshot(flange_dir):
    v = Viewer(flange_dir)
    r = v.do_preview(PREVIEW_VIOLATION)
    assert v.params()["params"][0]["value"] == PREVIEW_VIOLATION["D"]  # a reload can restore it
    ids = {f["id"] for f in r["findings"]}
    model = v.model()
    drawn = {e["id"] for e in model["elements"]}
    assert (
        ids and ids <= drawn
    )  # every violation points at a drawn element: the canvas can colour it
    by_id = {e["id"]: e for e in model["elements"]}
    issue = next(i for i in by_id[PREVIEW_VIOLATION_ID]["issues"] if i["rule"] == "overlap")
    assert {"clause", "measured", "expected", "candidates"} <= set(issue)
    assert "GB/T 4458.4-2003" in issue["clause"]
    global_issue = next(
        i for i in model["issues"] if i["rule"] == "overlap" and i["id"] == PREVIEW_VIOLATION_ID
    )
    assert {"clause", "measured", "expected", "candidates"} <= set(global_issue)
    snap = json.loads((flange_dir / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    s = next(
        i for i in snap["issues"] if i["rule"] == "overlap" and i["id"] == PREVIEW_VIOLATION_ID
    )
    assert s["clause"] == issue["clause"] and s["measured"] == issue["measured"]
    assert s["expected"] == issue["expected"] and s["candidates"] == issue["candidates"]
    # releasing the slider / undoing the preview clears the findings again
    assert v.do_preview({})["ok"]
    assert v.state()["preview"] is False
    assert v.model()["issues"] == []
    snap = json.loads((flange_dir / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    assert snap["issues"] == []


def test_preview_param_rule_error_lists_affected_elements_only(flange_dir):
    v = Viewer(flange_dir)
    r = v.do_preview({"Dh": 120})  # violates Dh < pcd - dh
    assert not r["ok"] and r["error"]["code"] == "param" and r["error"]["id"] == "Dh"
    assert "D.Dh" in r["affected"]  # the dimension that covers the parameter
    assert {"message", "values", "hint", "candidates"} <= set(r["error"])
    # ParamError has no E1 finding fields: do not fabricate them
    assert not {"clause", "measured", "expected"} & set(r["error"])
    snap = json.loads((flange_dir / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    assert snap["param_errors"]["error"]["id"] == "Dh" and snap["param_errors"]["affected"] == [
        "D.Dh"
    ]
    # the page keeps the failed preview's marks until the next user action: state tells it so
    state = v.state()
    assert state["param_errors"] is True and isinstance(state["preview_seq"], int)
    # a rebuild (refresh) must not leave the failed preview in snapshot.json
    assert v.refresh(force=True)
    assert v.state()["param_errors"] is False
    snap = json.loads((flange_dir / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    assert snap["param_errors"] == {}
    # withdrawing the preview must also clear the param error from snapshot.json (B3 review)
    assert v.do_preview({"Dh": 120})["ok"] is False
    assert v.do_preview({})["ok"]
    snap = json.loads((flange_dir / ".linercad/snapshot.json").read_text(encoding="utf-8"))
    assert snap["param_errors"] == {}


def test_non_drawn_finding_ids_are_resolved_to_view_elements(flange_dir):
    v = Viewer(flange_dir)
    assert v._finding_targets({"id": "V.left"}, v.res)  # a view has no prims: mark its elements
    assert v._finding_targets({"id": "V.nope"}, v.res) == []
    # a view-level finding (view_align) as the checks produce it: the canvas targets the view's elements
    v.res.findings.append(
        {"rule": "view_align", "id": "V.left", "severity": "warn", "message": "m"}
    )
    model = v.model()
    resolved = model["resolved"]
    left_ids = {e["id"] for e in model["elements"] if e["view"] == "left"}
    assert left_ids and left_ids <= set(resolved)  # the canvas can mark the view's elements
    assert all(resolved[i] in ("warn", "error") for i in left_ids)
    assert "V.left" not in resolved  # the view id itself is not drawn
    # selecting a target element must list the view-level finding and its E1 fields as well
    by_id = {e["id"]: e for e in model["elements"]}
    shown = next(s for s in left_ids if by_id[s]["issues"])
    issue = by_id[shown]["issues"][0]
    assert issue["id"] == "V.left" and {"clause", "measured", "expected", "candidates"} <= set(
        issue
    )


def test_viewer_consumes_preview_findings_on_the_canvas():
    from importlib import resources

    pkg = resources.files("linercad.viewer")
    js = (pkg / "viewer.js").read_text(encoding="utf-8")
    css = (pkg / "viewer.css").read_text(encoding="utf-8")
    for needle in (
        "applyFindings",
        "previewIds",
        "st-violation",
        "r.findings",
        "i.clause",
        "i.measured",
        "i.expected",
        "i.candidates",
        "resolved",
        "element_issues",
        "previewActive",
        "unplaced",
        "statusOrig",
        "st.preview_seq",
        "预览值已从服务端恢复",
        "releasePreview",
        "++S.previewSeq",
        "无",
        "条款",
        "实测",
        "要求",
        "候选",
    ):
        assert needle in js, needle
    assert ".st-violation" in css and "var(--err)" in css


def test_withdrawn_preview_cannot_be_restored_by_a_stale_request(flange_dir):
    v = Viewer(flange_dir)
    assert v.do_preview(PREVIEW_VIOLATION, seq=5)["ok"]
    # a freshly reloaded page starts its seq at 1 while the server still knows seq 5: withdrawal wins
    assert v.do_preview({}, seq=1)["ok"] and v.preview is None
    late = v.do_preview(
        PREVIEW_VIOLATION, seq=5
    )  # the old page's in-flight preview arrives after it
    assert late["ok"] is False and late.get("superseded") and v.preview is None
    state = v.state()
    assert (
        state["preview"] is False and state["preview_seq"] == 6
    )  # client adopts the server baseline


def test_unplaced_finding_is_listed_with_the_e1_fields(tmp_path):
    p = tmp_path / "d"
    txn.init(p)
    (p / "drawing.py").write_text(
        "from linercad import Drawing, Param\n"
        "d = Drawing(sheet='A3', std='GB', scale='1:1')\n"
        "P = d.params(L=Param(50, min=20, max=100, step=1, label='总长'))\n"
        "f = d.view('front')\n"
        "f.turned('b', [(0, 10), (P.L, 10)])\n"
        "f.dim.dia('d1', (5, 10), (5, -10), value=20)\n"
        "d.title(name='t')\n",
        encoding="utf-8",
    )
    v = Viewer(p)
    model = v.model()
    hit = [f for f in model["unplaced"] if f["rule"] == "param_cover"]
    assert (
        hit and hit[0]["id"] == "P.L"
    )  # a parameter is not a drawn element: the inspector lists it
    assert {"clause", "measured", "expected", "candidates"} <= set(hit[0])
    assert model["resolved"] == {}


def test_preview_api_returns_findings_with_fields(tmp_path):
    from http.server import ThreadingHTTPServer

    p = tmp_path / "fl"
    txn.init(p, from_="flange")
    v = Viewer(p)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(v))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        tok = {"X-LCAD-Token": v.token}
        code, body = req(base + "/api/preview", {"values": PREVIEW_VIOLATION, "seq": 1}, tok)
        got = json.loads(body)
        assert code == 200 and got["ok"], got
        hit = next(f for f in got["findings"] if f["id"] == PREVIEW_VIOLATION_ID)
        assert "GB/T 4458.4-2003" in hit["clause"] and hit["expected"]["overlap"] == 0.0
        assert got["affected"] == []
        code, body = req(base + "/api/preview", {"values": {}, "seq": 2}, tok)
        got = json.loads(body)
        assert code == 200 and got["findings"] == []
    finally:
        httpd.shutdown()


# ---- B1–B6: Viewer UI polish (slider scale, inspector empty state, preview marking, status bar,
# version list persistence) shared PR, one section per card ---------------------------------------


def test_b1_params_api_reports_slider_ranges(flange_dir, tmp_path):
    v = Viewer(flange_dir)
    ps = v.params()["params"]
    assert ps and all("range" in p for p in ps)  # every slider says which range it spans
    d = next(p for p in ps if p["name"] == "D")
    assert d["range"] == {"min": 80, "max": 200} and d["step"] == 1
    # a Param without min/max falls back to 0.5–1.5 × its default (v0.1.0 review #1)
    p = tmp_path / "d"
    txn.init(p)
    (p / "drawing.py").write_text(
        "from linercad import Drawing, Param\n"
        "d = Drawing(sheet='A3', std='GB', scale='1:1')\n"
        "P = d.params(L=Param(10))\n"
        "f = d.view('front')\n"
        "f.turned('b', [(0, 5), (P.L, 5)])\n"
        "f.dim.linear('L', (0, 5), (P.L, 5), value=P.L, side='bottom')\n"
        "d.title(name='t')\n",
        encoding="utf-8",
    )
    q = Viewer(p).params()["params"][0]
    assert q["name"] == "L" and q["range"] == {"min": 5.0, "max": 15.0}


def test_b1_fallback_range_is_step_aligned(tmp_path):
    p = tmp_path / "d"
    txn.init(p)
    (p / "drawing.py").write_text(
        "from linercad import Drawing, Param\n"
        "d = Drawing(sheet='A3', std='GB', scale='1:1')\n"
        "P = d.params(A=Param(11), B=Param(5, min=5, max=5))\n"
        "f = d.view('front')\n"
        "f.turned('b', [(0, 5), (P.A, 5)])\n"
        "f.dim.linear('A', (0, 5), (P.A, 5), value=P.A, side='bottom')\n"
        "d.title(name='t')\n",
        encoding="utf-8",
    )
    ps = {q["name"]: q for q in Viewer(p).params()["params"]}
    a = ps["A"]
    assert a["range"]["min"] < 11 < a["range"]["max"]
    assert (11 - a["range"]["min"]) % 1 == 0  # the default is on the auto-step grid
    assert ps["B"]["range"] == {"min": 5.0, "max": 5.0}  # a declared fixed range is kept


def test_b1_slider_scale_rendered():
    from importlib import resources

    pkg = resources.files("linercad.viewer")
    js = (pkg / "viewer.js").read_text(encoding="utf-8")
    css = (pkg / "viewer.css").read_text(encoding="utf-8")
    for needle in ("p-scale", "p-min", "p-max", "p-ticks", "tick"):
        assert needle in js, needle
    for cls in (".p-scale", ".p-min", ".p-max", ".p-tick"):
        assert cls in css, cls


def test_b2_model_summary_counts(flange_dir):
    v = Viewer(flange_dir)
    m = v.model()
    assert m["summary"]["elements"] == len(m["elements"]) > 0
    assert m["summary"]["errors"] == 0 and m["summary"]["warnings"] == 0
    v.do_preview(PREVIEW_VIOLATION)  # a preview with warnings: the inspector summary follows it
    m = v.model()
    assert m["summary"]["warnings"] >= 1
    assert m["summary"]["errors"] == sum(1 for f in m["issues"] if f["severity"] == "error")


def test_b2_inspector_empty_state_shows_usage_and_summary():
    from importlib import resources

    js = (resources.files("linercad.viewer") / "viewer.js").read_text(encoding="utf-8")
    for needle in ("Ctrl 多选", "@ID", "insp-empty", "insp-summary", "元素"):
        assert needle in js, needle


def test_b4_state_switches_with_the_preview(flange_dir):
    v = Viewer(flange_dir)
    assert v.state()["preview"] is False
    v.do_preview(PREVIEW_VIOLATION)
    assert v.state()["preview"] is True
    v.do_preview({})
    assert v.state()["preview"] is False


def test_b4_preview_marking_text_exists():
    from importlib import resources

    js = (resources.files("linercad.viewer") / "viewer.js").read_text(encoding="utf-8")
    html = (resources.files("linercad.viewer") / "index.html").read_text(encoding="utf-8")
    assert "preview-badge" in html and "未写回" in html
    for needle in ("拖动中", "写回源码", "preview-badge", "计算中", "被规则拒绝"):
        assert needle in js, needle


def test_b5_state_exposes_status_bar_parts(flange_dir):
    v = Viewer(flange_dir)
    st = v.state()
    assert {"message", "errors", "warnings"} <= set(st)
    assert st["errors"] == 0 and st["warnings"] == 0 and isinstance(st["message"], str)
    # an error finding (undefined datum reference) must be counted for the coloured status bar
    script = flange_dir / ".linercad" / "tmp" / "err.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        'def apply(d):\n    d.view("front").gtol("zz", "perpendicularity", 0.03, datums=["Z"], ref="D.D")\n',
        encoding="utf-8",
    )
    assert txn.edit(flange_dir, script, "加一个未定义基准的形位公差")["ok"]
    v = Viewer(flange_dir)
    assert v.state()["errors"] >= 1
    v.do_preview(PREVIEW_VIOLATION)  # warnings are counted too
    assert v.state()["warnings"] >= 1


def test_b5_status_bar_rendering():
    from importlib import resources

    pkg = resources.files("linercad.viewer")
    js = (pkg / "viewer.js").read_text(encoding="utf-8")
    css = (pkg / "viewer.css").read_text(encoding="utf-8")
    html = (pkg / "index.html").read_text(encoding="utf-8")
    for needle in ("st-errors", "st-warnings", "st-msg", "expanded", "构建失败"):
        assert needle in js, needle
    for needle in ("st-errors", "st-warnings", "st-msg"):
        assert needle in html, needle
    assert "st-error" in css and "st-warn" in css
    assert "text-overflow" in css  # a long commit message is clipped, click to expand


def test_b6_versions_open_state_and_scroll_are_preserved():
    from importlib import resources

    js = (resources.files("linercad.viewer") / "viewer.js").read_text(encoding="utf-8")
    for needle in ("verOpen", "sessionStorage", "preserveScroll", "versions"):
        assert needle in js, needle


def test_viewer_compare_panel_shows_merged_view_moves():
    from importlib import resources

    js = (resources.files("linercad.viewer") / "viewer.js").read_text(encoding="utf-8")
    # the banner counts the merged moves and the panel renders one line per view
    for needle in ("view_moves", "视图平移 ${c.view_moves}", "fmt(m.dx)", "m.elements"):
        assert needle in js, needle


def test_b7_viewer_diff_api_returns_view_moves(tmp_path):
    from http.server import ThreadingHTTPServer

    p = tmp_path / "v"
    txn.init(p, from_="flange")
    s = p / ".linercad" / "tmp" / "mv.py"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text('def apply(d):\n    d.view("left").move(dx=2)\n', encoding="utf-8")
    assert txn.edit(p, s, "左视图右移 2mm")["ok"]
    v = Viewer(p)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(v))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, body = req(base + "/api/diff?a=e0&b=e1", None, {"X-LCAD-Token": v.token})
        got = json.loads(body)
        assert code == 200 and got["ok"], got
        summary = got["summary"]
        moves = {m["view"]: m for m in summary["view_moves"]}
        assert set(moves) == {"front", "left"} and moves["left"]["dx"] == 1.0
        assert summary["counts"]["view_moves"] == len(summary["view_moves"]) == 2
        assert summary["layout_changed"] == []
    finally:
        httpd.shutdown()


# ---- M3 S2: versions, compare, fit-to-content ---------------------------------------------------


def two_edits(p):
    for name, body, msg in (
        ("a.py", 'd["D.L"].tol = "±0.2"', "总长加公差"),
        ("b.py", 'd.notes.tech("去毛刺。")', "加技术要求"),
    ):
        s = p / ".linercad" / "tmp" / name
        s.write_text(f"def apply(d):\n    {body}\n", encoding="utf-8")
        assert txn.edit(p, s, msg)["ok"]


def test_versions_and_diff_api_behind_the_guards(server):
    v, base = server
    two_edits(v.dir)
    tok = {"X-LCAD-Token": v.token}
    assert req(base + "/api/versions")[0] == 403  # no token
    assert req(base + "/api/diff?a=e0&b=e2")[0] == 403
    assert req(base + "/api/versions", headers={**tok, "Origin": "http://evil.example"})[0] == 403
    assert req(base + "/api/versions", headers={**tok, "Host": "evil.example"})[0] == 403
    assert req(base + "/api/diff?a=e0&b=e2", headers={**tok, "Host": "evil.example"})[0] == 403
    code, body = req(base + "/api/versions", headers=tok)
    got = json.loads(body)
    assert code == 200 and got["ok"]
    assert [r["edit"] for r in got["versions"]] == ["e2", "e1", "e0"]
    assert set(got["versions"][0]) == {"edit", "commit", "message", "time"}
    assert got["versions"][0]["message"] == "加技术要求"
    code, body = req(base + "/api/diff?a=e1&b=e2", headers=tok)
    got = json.loads(body)
    assert code == 200 and got["ok"] and got["svg"].startswith("<svg")
    s = got["summary"]
    assert any(i.startswith("N.tech") for i in s["added"]) and s["removed"] == []
    assert s["a"]["ref"] == "e1" and s["b"]["ref"] == "e2" and "svg" not in s
    assert 'class="df-add"' in got["svg"] and "<style>" not in got["svg"]  # the page CSP
    code, body = req(base + "/api/diff?a=e0&b=e1", headers=tok)
    assert json.loads(body)["summary"]["intent_changed"] == ["D.L"]
    code, body = req(base + "/api/diff?a=e0", headers=tok)  # b omitted: the working tree
    assert code == 200 and json.loads(body)["summary"]["b"]["ref"] == "working"
    code, body = req(base + "/api/diff?a=e9&b=e1", headers=tok)
    assert code == 400 and json.loads(body)["error"]["code"] == "not_found"
    assert req(base + "/api/diff?b=e1", headers=tok)[0] == 400  # a is required
    assert not txn.dirty_sources(v.dir)
    wt = subprocess.run(
        ["git", "-C", str(v.dir), "worktree", "list"], capture_output=True, text=True
    ).stdout
    assert len(wt.splitlines()) == 1


def test_model_carries_the_content_box_without_frame_and_title(shaft):
    v = Viewer(shaft)
    d = v.res.d
    box = v.model()["content_bbox"]
    boxes = [
        e.bbox
        for e in d._els.values()
        if e.bbox and e._prims and e.kind not in ("frame", "table.cell")
    ]
    want = [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]
    assert box == pytest.approx(want)
    W, H = d.template["size"]
    assert 0 < box[0] < box[2] < W and 0 < box[1] < box[3] < H
    assert box[2] - box[0] < W - 40  # smaller than the sheet: the initial view can zoom in
    tb = v.model()["title_bbox"]  # the view keeps the title block in sight
    assert tb == pytest.approx([W - 5 - 180, 5, W - 5, 5 + 56]) and tb[3] - tb[1] == 56


def test_viewer_page_has_the_compare_and_preview_hooks():
    from importlib import resources

    pkg = resources.files("linercad.viewer")
    html = (pkg / "index.html").read_text(encoding="utf-8")
    js = (pkg / "viewer.js").read_text(encoding="utf-8")
    css = (pkg / "viewer.css").read_text(encoding="utf-8")
    for needle in ("ver-list", "cmp-banner", "btn-exit-cmp", "preview-badge"):
        assert needle in html, needle
    for needle in ("/api/versions", "/api/diff", "content_bbox", "exitCompare"):
        assert needle in js, needle
    for c in ("df-a", "df-b", "df-add", "df-del", "df-chg", "is-preview"):
        assert c in css, c
