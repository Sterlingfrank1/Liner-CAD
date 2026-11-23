"""C1: DXF import evaluation (issue #76).  Metrics for lcad inspect / lcad init --from-dxf.

The script takes a directory of .dxf files (the user samples are NOT part of this repository) and
writes one JSON report: per-file and summary retention numbers.  What is measured, per file:

* entity_retention    - by DXF entity type: how many source entities become model elements;
                        HATCH / INSERT / POINT etc. (skipped by the importer) count as 0.
* layer_retention     - layers whose content would actually survive the import (zero-length edges
                        on their own layer do not count); names_preserved counts the source layer
                        names that the imported elements still carry in their dxf meta.
* dimension_retention - DIMENSION entities kept as dimensions (vs. downgraded to a text note).
* text_retention      - TEXT / MTEXT kept as an editable text element (as_text) vs. only as a
                        leader note (as_note); the importer currently has no regular text element,
                        so the main rate is 0 and note_rate is the provisional reading.
* hatch_retention     - HATCH entities kept as hatches (the importer has no hatch bucket: 0).
* frame_title         - sheet guess (available / fits), title / frame INSERTs, title attributes,
                        text on title / frame layers - all retained counts are read from the
                        imported drawing, not hard-coded.
* inspect             - the lcad inspect CLI on the same file (ok, maps_to, sheet): C1 evaluates
                        both entry points, not just the importer.
* edit_round          - end-to-end: lcad init --from-dxf, then move one dimension (along its side)
                        and change one note text via lcad edit + lcad build; both operations are
                        verified from the edit output ops and the rebuilt drawing.

Everything is deterministic: no timestamps, sorted dictionaries, one sha256 per source file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from linercad import Drawing, importdxf  # noqa: E402

EDGE_TYPES = tuple(importdxf.EDGE_TYPES)
RAW_TYPES = tuple(importdxf.RAW_TYPES)
NOTE_TYPES = tuple(importdxf.NOTE_TYPES)
TITLE_BLOCK_WORDS = ("TITLE", "FRAME", "\u56fe\u6846", "\u6807\u9898", "MXB")
TITLE_LAYER_WORDS = ("TITLE", "FRAME", "\u56fe\u6846", "\u6807\u9898")
TITLE_FIELD_WORDS = (
    "\u56fe\u53f7",
    "\u540d\u79f0",
    "\u6750\u6599",
    "\u6bd4\u4f8b",
    "\u56fe\u5e45",
    "\u8bbe\u8ba1",
    "\u5ba1\u6838",
    "\u65e5\u671f",
    "\u91cd\u91cf",
    "\u9636\u6bb5",
    "\u5355\u4f4d",
    "\u6570\u91cf",
    "\u7248\u672c",
    "TITLE",
    "NAME",
    "MATERIAL",
    "SCALE",
    "SHEET",
    "DATE",
    "MASS",
    "DRAWING",
)


# ---- small helpers --------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rate(retained: int, source: int):
    return None if not source else round(retained / source, 4)


def _source_text(e) -> str:
    # independent reading of the source entity (not the importer's parser)
    from ezdxf.lldxf.encoding import decode_dxf_unicode

    raw = e.plain_text(fast=False) if e.dxftype() == "MTEXT" else e.dxf.text
    try:
        raw = decode_dxf_unicode(raw)
    except Exception:  # noqa: BLE001
        pass
    parts = [importdxf.clean_text(part) for part in raw.split("\n")]
    return "\n".join(parts)


def _decode(name) -> str:
    r"""DXF layer / block names may store CJK as \U+XXXX escapes; decode for display / matching."""
    return re.sub(r"\\U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), str(name))


def _title_name(name) -> bool:
    # C4: strict block-name rule shared with the importer
    return importdxf.is_frame_block(name)


def _title_layer(name) -> bool:
    # C4: one detection rule shared with the importer (exact frame/title layer names only)
    return importdxf.is_frame_layer(name)


def _title_insert(e) -> bool:
    return e.dxftype() == "INSERT" and (_title_name(e.dxf.name) or _title_layer(e.dxf.layer))


def _title_field(tag) -> bool:
    up = _decode(tag).upper()
    return any(w in up for w in TITLE_FIELD_WORDS)


def _msp(doc):
    return list(doc.modelspace())


def _matched(source: list, available: Counter):
    """Match source texts against an available multiset; returns (matched, remaining)."""
    kept, remaining = [], []
    for text in source:
        if text and available.get(text, 0) > 0:
            available[text] -= 1
            kept.append(text)
        else:
            remaining.append(text)
    return kept, remaining


def _kept_texts(source: list, imported: Counter) -> int:
    kept = 0
    for text in source:
        if text and imported.get(text, 0) > 0:
            imported[text] -= 1
            kept += 1
    return kept


def _handle(e) -> str:
    return str(e.dxf.handle)


def _imported_handles(created) -> set:
    return {
        str(el._intent.get("dxf", {}).get("handle"))
        for el in created
        if el._intent.get("dxf", {}).get("handle") is not None
    }


def _created_of_kind(created, kinds) -> list:
    return [el for el in created if el.kind in kinds]


def _all_attribs(doc, inserts) -> list:
    out = [e for e in _msp(doc) if e.dxftype() == "ATTRIB" and _title_layer(e.dxf.layer)]
    for br in inserts:
        out.extend(getattr(br, "attribs", ()))
    return out


def _title_block_texts(doc, inserts) -> list:
    """TEXT / MTEXT inside the title / frame block definitions (currently skipped by the import)."""
    out = []
    for br in inserts:
        try:
            block = doc.blocks.get(br.dxf.name)
        except KeyError:
            continue
        for e in block:
            if e.dxftype() in NOTE_TYPES:
                out.append(e)
    return out


def _round_lookup(doc) -> list:
    """(cx, cy, r) of the source circles / arcs in mm, as the importer indexes them."""
    k, _unit = importdxf.unit_factor(doc)
    out = []
    for e in _msp(doc):
        if importdxf.classify(e)[0] != "edges":
            continue
        for seg in importdxf._segments(e):
            if seg[0] in ("circle", "arc"):
                out.append((round(seg[1][0] * k, 6), round(seg[1][1] * k, 6), round(seg[2] * k, 6)))
    return out


def _find_round(rounds, c, r):
    tol = 1e-3 * max(1.0, r)
    return any(
        abs(cx - c[0]) <= tol and abs(cy - c[1]) <= tol and abs(rr - r) <= tol
        for cx, cy, rr in rounds
    )


def _expected_fallback_texts(doc) -> list:
    """Texts the importer creates when a dimension cannot be tied to imported geometry."""
    from linercad.annotate import fmt_num

    k, _unit = importdxf.unit_factor(doc)
    rounds = _round_lookup(doc)
    out = []
    for e in _msp(doc):
        if importdxf.classify(e)[0] != "dims":
            continue
        kind = importdxf.dim_kind(e)
        if kind not in ("diameter", "radius"):
            continue
        if not (e.dxf.hasattr("defpoint") and e.dxf.hasattr("defpoint4")):
            continue
        dp, q = e.dxf.defpoint, e.dxf.defpoint4
        c = (dp[0] * k, dp[1] * k)
        r = ((q[0] - dp[0]) ** 2 + (q[1] - dp[1]) ** 2) ** 0.5 * k
        if kind == "diameter":
            c = ((dp[0] + q[0]) / 2 * k, (dp[1] + q[1]) / 2 * k)
            r = r / 2
        if not _find_round(rounds, c, r):
            meas = 2 * r if kind == "diameter" else r
            sym = "Φ" if kind == "diameter" else "R"
            out.append(importdxf.clean_text(sym + fmt_num(meas)))
    return out


def _created(d, imp):
    return [d._els[i] for i in imp._created if i in d._els]


def _edge_ok(seg) -> bool:
    if seg[0] == "line":
        return ((seg[1][0] - seg[2][0]) ** 2 + (seg[1][1] - seg[2][1]) ** 2) ** 0.5 > 1e-6
    return seg[2] > 1e-6


def _raw_would_import(e) -> bool:
    try:
        packed = importdxf._raw_pack(e, 1.0)
    except Exception:  # noqa: BLE001
        return False
    if packed is None:
        return False
    attribs, data = packed
    intent = {"dxftype": e.dxftype(), "attribs": attribs, "data": data}
    msp = importdxf._scratch_msp()
    try:  # must survive the DXF writer, exactly like the importer requires
        msp.delete_entity(importdxf.make_raw(msp, intent))
    except Exception:  # noqa: BLE001
        return False
    return True


def _dim_would_import(e) -> bool:
    """Mirror the importer's dimension requirements: missing defpoints make it fail."""
    kind = importdxf.dim_kind(e)

    def has(name):
        return e.dxf.hasattr(name)

    if kind in ("linear", "aligned"):
        if not (has("defpoint2") and has("defpoint3")):
            return False
        p1, p2 = e.dxf.get("defpoint2"), e.dxf.get("defpoint3")
        if kind == "aligned":
            return ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5 > 1e-9
        ang = e.dxf.get("angle", 0.0) % 180.0
        if ang < 0.05 or ang > 179.95:
            return abs(p2[0] - p1[0]) > 1e-9
        if abs(ang - 90.0) < 0.05:
            return abs(p2[1] - p1[1]) > 1e-9
        return True
    if kind in ("diameter", "radius"):
        return has("defpoint") and has("defpoint4")
    if kind in ("angular", "angular3p"):
        return all(has(n) for n in ("defpoint2", "defpoint3", "defpoint4")) and (
            has("defpoint") or kind == "angular3p"
        )
    return False


def _would_import(doc, e) -> bool:
    """Would the importer actually turn this entity into model content?"""
    bucket, _label = importdxf.classify(e)
    if bucket == "skipped" or not importdxf._visible(doc, e):
        return False
    if bucket == "edges":
        return any(_edge_ok(seg) for seg in importdxf._segments(e))
    if bucket in ("notes", "texts"):
        return bool(_source_text(e))
    if bucket == "hatches":
        return importdxf.hatch_would_import(e, importdxf.unit_factor(doc)[0])
    if bucket == "raw":
        return _raw_would_import(e)
    return _dim_would_import(e)


# ---- the metrics ----------------------------------------------------------------------------


def entity_retention(doc, counts: dict) -> dict:
    source = Counter(e.dxftype() for e in _msp(doc))
    retained = Counter()
    for bucket in ("edges", "raw", "texts", "hatches", "notes"):
        for label, n in counts.get("from", {}).get(bucket, {}).items():
            if label in source:
                retained[label] += n
    # every DIMENSION that became a dimension or a fallback note is retained as an entity
    retained["DIMENSION"] += sum(counts.get("from", {}).get("dims", {}).values())
    # C4: source frame / title geometry is absorbed into the template frame semantics; count it
    absorbed = counts.get("frame", {}).get("absorbed", {})
    for label, n in absorbed.items():
        if label in source:
            retained[label] += n
    by_type = {}
    for kind in sorted(set(source) | set(retained)):
        src = source.get(kind, 0)
        ret = min(retained.get(kind, 0), src)
        by_type[kind] = {"source": src, "retained": ret, "rate": _rate(ret, src)}
    total_src = sum(source.values())
    total_ret = sum(v["retained"] for v in by_type.values())
    return {
        "by_type": by_type,
        "totals": {"source": total_src, "retained": total_ret, "rate": _rate(total_ret, total_src)},
    }


def layer_retention(doc, created) -> dict:
    layers = importdxf.layers_of(doc)
    with_content = [lay for lay in layers if lay["count"]]
    # one pass over the modelspace: each entity is classified / validated exactly once
    grouped = {}
    for e in _msp(doc):
        grouped.setdefault(e.dxf.layer, []).append(_would_import(doc, e))
    absorbed_layers = [
        e.dxf.layer
        for e in _msp(doc)
        if importdxf.classify(e)[0] == "edges"
        and importdxf.is_frame_layer(e.dxf.layer)
        and importdxf.edge_has_geometry(e)
        and importdxf._visible(doc, e)
    ]
    absorbed_layers = list(dict.fromkeys(absorbed_layers))
    not_imported = [
        _decode(lay["name"])
        for lay in with_content
        if not any(grouped.get(lay["name"], ())) and lay["name"] not in absorbed_layers
    ]
    imported = len(with_content) - len(not_imported)
    source_names = {str(lay["name"]) for lay in layers}
    element_layers = {
        str(el._intent.get("dxf", {}).get("layer"))
        for el in created
        if el._intent.get("dxf", {}).get("layer") is not None
    }
    names_preserved = sorted(element_layers & source_names)
    absorbed_layer_names = [_decode(n) for n in absorbed_layers]
    return {
        "source_layers": len(layers),
        "layers_with_content": len(with_content),
        "layers_with_content_imported": imported,
        "not_imported": sorted(not_imported),
        "absorbed_layers": sorted(absorbed_layer_names),
        "names_preserved": len(names_preserved),
        "names_preserved_rate": _rate(len(names_preserved), len(with_content)),
        "names_preserved_list": [_decode(n) for n in names_preserved],
        "note": (
            "imported edge elements carry their source layer in intent.dxf.layer; dimensions and "
            "notes do not, so names_preserved is a per-element-kind reading. Absorbed frame-layer "
            "content counts as imported content (represented by the single template frame) and is "
            "listed separately in absorbed_layers; it is not counted as an element-carried name."
        ),
        "rate": _rate(imported, len(with_content)),
    }


def dimension_retention(doc, counts: dict) -> dict:
    source = sum(1 for e in _msp(doc) if e.dxftype() == "DIMENSION")
    as_dim = counts.get("dims", 0)
    as_note = counts.get("dims_as_notes", 0)
    return {
        "source": source,
        "as_dimension": as_dim,
        "as_note": as_note,
        "skipped": max(0, source - as_dim - as_note),
        "rate": _rate(as_dim, source),
    }


def text_retention(doc, d, created) -> dict:
    source = [_source_text(e) for e in _msp(doc) if e.dxftype() in NOTE_TYPES]
    source = [t for t in source if t]
    texts = Counter(el._intent.get("text", "") for el in created if el.kind in ("text", "label"))
    # dimension fallback notes are counted in dimension_retention.as_note, not as text:
    # remove their expected texts from the note multiset before matching
    fallback = _expected_fallback_texts(doc)
    notes = Counter(el._intent.get("text", "") for el in created if el.kind == "note")
    for text in fallback:
        if notes.get(text, 0) > 0:
            notes[text] -= 1
    as_text_list, remaining = _matched(source, texts)  # disjoint partition: text first
    as_note_list, _unmatched = _matched(remaining, notes)
    return {
        "source": len(source),
        "as_text": len(as_text_list),
        "as_note": len(as_note_list),
        "rate": _rate(len(as_text_list), len(source)),
        "note_rate": _rate(len(as_note_list), len(source)),
        "dims_fallback_notes": len(fallback),
        "note": (
            "as_text / as_note are disjoint; dimension fallback notes are excluded from the text "
            "reading; C2 introduces the regular text element so as_text can grow"
        ),
    }


def hatch_retention(doc, created) -> dict:
    sources = [e for e in _msp(doc) if e.dxftype() == "HATCH"]
    handlers = _imported_handles(created)
    retained = sum(1 for e in sources if _handle(e) in handlers)  # by source handle, <= source
    return {"source": len(sources), "retained": retained, "rate": _rate(retained, len(sources))}


def _sheet_fits(width, height, sheet, scale, std="GB") -> bool:
    from linercad.std import load_template

    try:
        tpl = load_template(std, sheet)
        factor = 1.0 / float(str(scale).split(":")[1])
        f, tb = tpl["frame"], tpl["title_block"]["size"]
        return (
            width * factor + 2 * importdxf.DIM_MARGIN <= f[2] - f[0]
            and height * factor + 2 * importdxf.DIM_MARGIN + tb[1] <= f[3] - f[1]
        )
    except (KeyError, ValueError, IndexError):
        return False


def frame_title(doc, d, created) -> dict:
    ents = _msp(doc)
    handlers = _imported_handles(created)
    inserts = [e for e in ents if _title_insert(e)]
    attribs = _all_attribs(doc, inserts)
    # title texts: modelspace texts on title / frame layers PLUS the template texts inside the
    # title block definitions (4 samples x 16 template texts were previously not in the denominator)
    msp_texts = [e for e in ents if e.dxftype() in NOTE_TYPES and _title_layer(e.dxf.layer)]
    block_texts = _title_block_texts(doc, inserts)
    title_sources = msp_texts + block_texts
    source_strings = [_source_text(e) for e in title_sources]
    texts = Counter(el._intent.get("text", "") for el in created if el.kind in ("text", "label"))
    fallback = _expected_fallback_texts(doc)
    notes = Counter(el._intent.get("text", "") for el in created if el.kind == "note")
    for text in fallback:
        if notes.get(text, 0) > 0:
            notes[text] -= 1
    as_text_list, remaining = _matched(source_strings, texts)
    as_note_list, _unmatched = _matched(remaining, notes)
    # the drawing frame itself is ordinary geometry on a title / frame layer: count the edges
    frame_edges = [
        e
        for e in ents
        if importdxf.classify(e)[0] == "edges"
        and _title_layer(e.dxf.layer)
        and importdxf.edge_has_geometry(e)
    ]
    frame_edges_retained = sum(1 for e in frame_edges if _handle(e) in handlers)
    absorbed = importdxf._frame_absorbed(doc)
    frame_edges_absorbed = sum(absorbed.values())
    frame_raw = [
        e
        for e in ents
        if importdxf.classify(e)[0] == "raw"
        and _title_layer(e.dxf.layer)
        and importdxf._visible(doc, e)
    ]
    frame_raw_retained = sum(1 for e in frame_raw if _handle(e) in handlers)
    inserts_retained = sum(1 for e in inserts if _handle(e) in handlers)
    attrib_retained = sum(1 for e in attribs if _handle(e) in handlers)  # handle-matched only
    k, _unit = importdxf.unit_factor(doc)
    ext = importdxf._extents(doc, k)
    if ext:
        width, height = ext[2] - ext[0], ext[3] - ext[1]
        sheet, scale = importdxf.guess_sheet(width, height)
        fits = _sheet_fits(width, height, sheet, scale)
    else:
        width = height = 0.0
        sheet = scale = None
        fits = False
    # the final drawing always carries its own template frame (T.frame); the imported frame
    # geometry is duplicated edges, which C4 has to reconcile into "exactly one frame"
    model_frames = sum(1 for el in getattr(d, "_els", {}).values() if el.kind == "frame")
    single_frame_ok = (
        model_frames == 1
        and frame_edges_retained == 0
        and frame_edges_absorbed == len(frame_edges)
        and frame_raw_retained == 0
    )
    return {
        "sheet_guess": {
            "available": sheet is not None,
            "fits": fits,
            "sheet": sheet,
            "scale": scale,
        },
        "frame_inserts": len(inserts),
        "frame_inserts_retained": inserts_retained,
        "frame_edges": len(frame_edges),
        "frame_edges_retained": frame_edges_retained,
        "frame_edges_absorbed": frame_edges_absorbed,
        "frame_raw_retained": frame_raw_retained,
        "model_frames": model_frames,
        "single_frame_ok": single_frame_ok,
        "title_attrib_fields": len(attribs),
        "title_attrib_retained": attrib_retained,
        "title_texts": len(title_sources),
        "title_texts_as_text": len(as_text_list),
        "title_texts_as_note": len(as_note_list),
        "title_text_rate": _rate(len(as_text_list), len(title_sources)),
        "title_note_rate": _rate(len(as_note_list), len(title_sources)),
        "note": (
            "title texts include the title block template texts; as_text is the C2 target reading, "
            "as_note the leader-note fallback; retained INSERT / ATTRIB counts are dxf-handle matches; "
            "C4: source frame edges are absorbed into the template frame semantics "
            "(frame_edges_absorbed); single_frame_ok requires one model frame, zero frame edges "
            "imported as geometry and every detected source frame edge accounted for. Detection "
            "uses exact frame/title layer names (shared with the importer), so a frame drawn on "
            "an unnamed layer is outside the ruler's reach (documented limitation)."
        ),
    }


def _cli(cwd: Path, *args):
    r = subprocess.run(
        [sys.executable, "-m", "linercad", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        out = json.loads(r.stdout)
    except ValueError:
        out = {"error": (r.stdout or "") + (r.stderr or "")}
    return r.returncode, out


def inspect_cli(path: Path, doc=None) -> dict:
    folder = Path(tempfile.mkdtemp(prefix="lcad-dxf-inspect-"))
    try:
        code, out = _cli(folder, "inspect", str(path))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if code != 0 or not out.get("ok"):
        return {"ok": False, "exit": code, "error": out.get("error")}
    if out.get("png_error"):
        return {"ok": False, "png_ok": False, "error": out.get("png_error")}
    maps_match = sheet_match = None
    if doc is not None:
        expected = importdxf.scan(doc)
        got = out.get("maps_to") or {}
        expected = {b: dict(sorted(v.items())) for b, v in expected.items()}
        maps_match = got == expected
        k, _unit = importdxf.unit_factor(doc)
        ext = importdxf._extents(doc, k)
        if ext:
            sheet, scale = importdxf.guess_sheet(ext[2] - ext[0], ext[3] - ext[1])
            sheet_match = out.get("sheet") == {"sheet": sheet, "scale": scale}
        else:
            sheet_match = out.get("sheet") is None
    return {
        "ok": True,
        "png_ok": True,
        "maps_match": maps_match,
        "sheet_match": sheet_match,
        "maps_to": out.get("maps_to"),
        "sheet": out.get("sheet"),
        "entities": out.get("entities"),
    }


def _move_candidates(model) -> list:
    """[(dim id, move kwargs)] ordered so the first one is most likely to move successfully."""
    out = []
    groups = {"dim": [], "text": []}
    for e in model["elements"]:
        if e.get("kind") in groups:
            groups[e["kind"]].append(e)
    for kind in ("dim", "text"):
        for e in groups[kind]:
            eid = e["id"]
            if kind == "dim":
                side = (e.get("placement") or {}).get("side")
                order = ("dx", "dy") if side in ("left", "right") else ("dy", "dx")
            else:
                order = ("dx", "dy")
            for axis in order:
                for delta in (1.0, -1.0):
                    out.append((eid, axis, delta))
    return out


def edit_round(path: Path) -> dict:
    """One end-to-end edit round: init --from-dxf, move a dimension, change a note, build."""
    root = Path(tempfile.mkdtemp(prefix="lcad-dxf-eval-"))
    part = root / "part"
    try:
        code, out = _cli(root, "init", str(part), "--from-dxf", str(path))
        if code != 0:
            return {"ok": False, "error": "init failed", "detail": out, "build_ok": False}
        model_path = part / ".linercad" / "build" / "model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        ids = [e["id"] for e in model["elements"]]
        notes = sorted(i for i in ids if i.startswith("N."))
        texts = sorted(e["id"] for e in model["elements"] if e["kind"] == "text")
        editable = notes + texts
        candidates = _move_candidates(model)
        if not candidates or not editable:
            return {
                "ok": False,
                "error": "no movable dimension / editable text to edit",
                "candidates": len(candidates),
                "editable": len(editable),
                "build_ok": False,
            }
        note = editable[0]
        script = part / ".linercad" / "tmp" / "c1_edit_round.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        body = [
            "def apply(d):",
            "    moved = False",
        ]
        for eid, axis, delta in candidates:
            body.append(
                f"    if not moved:\n"
                f"        try:\n"
                f'            d["{eid}"].move({axis}={delta!r})\n'
                f"            moved = True\n"
                f"        except Exception:\n"
                f"            pass"
            )
        body.append(f'    d["{note}"].set(text="C1 \u6539\u4e00\u6bb5\u6587\u5b57")')
        script.write_text("\n".join(body) + "\n", encoding="utf-8")
        before = {e["id"]: e for e in model["elements"]}
        code, out = _cli(part, "edit", str(script), "-m", "C1 edit round")
        ops = out.get("ops") or []
        moved = [op for op in ops if op.get("op") == "move"]
        changed = [op for op in ops if op.get("op") == "set" and op.get("id") == note]
        ok_edit = code == 0
        ok_build = ok_edit and (part / ".linercad" / "build" / "drawing.dxf").is_file()
        moved_ok = text_ok = False
        if ok_build and moved and changed:
            try:
                after = {
                    e["id"]: e
                    for e in json.loads(model_path.read_text(encoding="utf-8"))["elements"]
                }
                mid = moved[0]["id"]
                moved_ok = mid in after and after[mid] != before.get(mid)
                text_ok = after.get(note, {}).get("intent", {}).get("text") == "C1 改一段文字"
            except (OSError, ValueError):
                moved_ok = text_ok = False
        return {
            "ok": bool(ok_edit and ok_build and moved and changed and moved_ok and text_ok),
            "moved_element": moved[0]["id"] if moved else None,
            "move_args": moved[0].get("args") if moved else None,
            "changed_element": note if changed else None,
            "moved_ok": moved_ok,
            "text_ok": text_ok,
            "edit_code": code,
            "build_ok": bool(ok_build),
            "errors": out.get("errors"),
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def evaluate_file(path: Path) -> dict:
    path = Path(path)
    doc = importdxf.read_dxf(path)
    d = Drawing(sheet="A3")
    imp = importdxf.import_dxf(d, str(path))
    counts = imp.counts
    created = _created(d, imp)
    k, unit = importdxf.unit_factor(doc)
    ext = importdxf._extents(doc, k)
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "source": {
            "dxfversion": doc.dxfversion,
            "units": unit,
            "entities": dict(sorted(Counter(e.dxftype() for e in _msp(doc)).items())),
            "layers": len(importdxf.layers_of(doc)),
            "extents": [round(v, 3) for v in ext] if ext else None,
        },
        "import": {"counts": counts},
        "inspect": inspect_cli(path, doc),
        "metrics": {
            "entity_retention": entity_retention(doc, counts),
            "layer_retention": layer_retention(doc, created),
            "dimension_retention": dimension_retention(doc, counts),
            "text_retention": text_retention(doc, d, created),
            "hatch_retention": hatch_retention(doc, created),
            "frame_title": frame_title(doc, d, created),
            "edit_round": edit_round(path),
        },
    }


def _merge(files: list) -> dict:
    ok = [f for f in files if "metrics" in f]
    src = ret = 0
    by_type: dict = {}
    dims_src = dims_keep = dims_note = 0
    text_src = text_text = text_note = 0
    hatch_src = hatch_keep = 0
    layer_src = layer_ok = names_src = 0
    title_src = title_text = title_note = 0
    model_frames = single_frame_ok = 0
    sheet_available = sheet_fits = 0
    frame_edges = frame_edges_kept = 0
    frame_edges_absorbed = 0
    edit_ok = inspect_ok = inspect_match = 0
    for f in ok:
        m = f["metrics"]
        totals = m["entity_retention"]["totals"]
        src += totals["source"]
        ret += totals["retained"]
        for kind, row in m["entity_retention"]["by_type"].items():
            slot = by_type.setdefault(kind, {"source": 0, "retained": 0})
            slot["source"] += row["source"]
            slot["retained"] += row["retained"]
        dims_src += m["dimension_retention"]["source"]
        dims_keep += m["dimension_retention"]["as_dimension"]
        dims_note += m["dimension_retention"]["as_note"]
        text_src += m["text_retention"]["source"]
        text_text += m["text_retention"]["as_text"]
        text_note += m["text_retention"]["as_note"]
        hatch_src += m["hatch_retention"]["source"]
        hatch_keep += m["hatch_retention"]["retained"]
        layer_src += m["layer_retention"]["layers_with_content"]
        layer_ok += m["layer_retention"]["layers_with_content_imported"]
        names_src += m["layer_retention"]["names_preserved"]
        title_src += m["frame_title"]["title_texts"]
        title_text += m["frame_title"]["title_texts_as_text"]
        title_note += m["frame_title"]["title_texts_as_note"]
        model_frames += m["frame_title"]["model_frames"]
        single_frame_ok += 1 if m["frame_title"]["single_frame_ok"] else 0
        frame_edges += m["frame_title"]["frame_edges"]
        frame_edges_kept += m["frame_title"]["frame_edges_retained"]
        frame_edges_absorbed += m["frame_title"]["frame_edges_absorbed"]
        sheet_available += 1 if m["frame_title"]["sheet_guess"]["available"] else 0
        sheet_fits += 1 if m["frame_title"]["sheet_guess"]["fits"] else 0
        edit_ok += 1 if m["edit_round"]["ok"] else 0
        insp = f.get("inspect", {})
        inspect_ok += 1 if insp.get("ok") else 0
        inspect_match += (
            1 if insp.get("ok") and insp.get("maps_match") and insp.get("sheet_match") else 0
        )
    for row in by_type.values():
        row["rate"] = _rate(row["retained"], row["source"])
    n = len(ok) or 1
    return {
        "files": len(files),
        "evaluated": len(ok),
        "entities": {"source": src, "retained": ret, "rate": _rate(ret, src)},
        "by_type": {k: by_type[k] for k in sorted(by_type)},
        "dimension_retention": {
            "source": dims_src,
            "as_dimension": dims_keep,
            "as_note": dims_note,
            "rate": _rate(dims_keep, dims_src),
        },
        "text_retention": {
            "source": text_src,
            "as_text": text_text,
            "as_note": text_note,
            "rate": _rate(text_text, text_src),
            "note_rate": _rate(text_note, text_src),
        },
        "hatch_retention": _rate(hatch_keep, hatch_src),
        "layer_content_retention": _rate(layer_ok, layer_src),
        "layer_names_preserved": names_src,
        "title_text_retention": _rate(title_text, title_src),
        "title_note_retention": _rate(title_note, title_src),
        "model_frames": model_frames,
        "single_frame_ok_rate": round(single_frame_ok / n, 4),
        "sheet_guess_available_rate": round(sheet_available / n, 4),
        "sheet_guess_fits_rate": round(sheet_fits / n, 4),
        "edit_round_rate": round(edit_ok / n, 4),
        "inspect_ok_rate": round(inspect_ok / n, 4),
        "inspect_match_rate": round(inspect_match / n, 4),
        "frame_edges": {
            "source": frame_edges,
            "retained": frame_edges_kept,
            "absorbed": frame_edges_absorbed,
            "rate": _rate(frame_edges_kept, frame_edges),
        },
    }


def evaluate_dir(folder) -> dict:
    folder = Path(folder)
    if not folder.is_dir():
        return {"ok": False, "error": f"not a directory: {folder}"}
    dxfs = sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() == ".dxf")
    if not dxfs:
        return {"ok": False, "error": f"no .dxf files in {folder}"}
    files = []
    for path in dxfs:
        try:
            files.append(evaluate_file(path))
        except Exception as e:  # noqa: BLE001 - one broken file must not hide the others
            files.append({"file": path.name, "ok": False, "error": f"{type(e).__name__}: {e}"})
    ok = all("metrics" in f for f in files)
    return {
        "ok": ok,
        "sample_dir": str(folder),
        "method": "evals/dxf_import.py (issue #76 C1); see the module docstring for metric definitions",
        "files": files,
        "summary": _merge(files),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", help="directory of .dxf samples (never committed)")
    ap.add_argument("--out", help="write the JSON report here")
    a = ap.parse_args(argv)
    rep = evaluate_dir(a.folder)
    text = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8", newline="\n")
    if rep["ok"]:
        print(json.dumps(rep["summary"], ensure_ascii=False))
        return 0
    print(
        json.dumps(
            {
                "ok": False,
                "error": rep.get("error", "some files failed"),
                "files": rep.get("files"),
            },
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
