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


def test_context_at_sel_warns_on_an_old_selection(shaft):
    v = Viewer(shaft)
    v.select(["D.L"])
    script = shaft / ".linercad" / "tmp" / "m.py"
    script.write_text('def apply(d):\n    d["D.L"].place(side="top")\n', encoding="utf-8")
    txn.edit(shaft, script, "挪")
    ctx = commands.context(shaft, ["@sel"])
    assert "e0" in ctx["warning"] and ctx["items"][0]["element"]["id"] == "D.L"


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
