"""C1: DXF import evaluation (issue #76).  Metrics for lcad inspect / lcad init --from-dxf.

The script takes a directory of .dxf files (the user samples are NOT part of this repository) and
writes one JSON report: per-file and summary retention numbers.  What is measured, per file:

* entity_retention    - by DXF entity type: how many source entities become model elements;
                        HATCH / INSERT / POINT etc. (skipped by the importer) count as 0.
* layer_retention     - source layers with content, how many of them get any content into the
                        model, and (0 by design) whether layer names survive into the model.
* dimension_retention - DIMENSION entities kept as dimensions (vs. downgraded to a text note).
* text_retention      - TEXT / MTEXT kept as notes (matched by cleaned text).
* hatch_retention     - HATCH entities kept (the importer has no hatch bucket today: 0).
* frame_title         - sheet guess from extents, title / frame INSERTs and their attributes,
                        text on title / frame layers (attributes and INSERTs are skipped today).
* edit_round          - end-to-end: lcad init --from-dxf, then move one dimension and change one
                        note text via lcad edit + lcad build.

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
    if e.dxftype() == "MTEXT":
        return importdxf.clean_text(e.plain_text())
    return importdxf.clean_text(e.dxf.text)


def _decode(name) -> str:
    r"""DXF layer / block names may store CJK as \U+XXXX escapes; decode for matching."""
    return re.sub(r"\\U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), str(name))


def _title_name(name) -> bool:
    up = _decode(name).upper()
    return any(w in up for w in TITLE_BLOCK_WORDS)


def _title_layer(name) -> bool:
    up = _decode(name).upper()
    return any(w in up for w in TITLE_LAYER_WORDS)


def _title_field(tag) -> bool:
    up = _decode(tag).upper()
    return any(w in up for w in TITLE_FIELD_WORDS)


def _msp(doc):
    return list(doc.modelspace())


def _imported_notes(d) -> list:
    return [el._intent.get("text", "") for el in d._els.values() if el.kind == "note"]


def _kept_texts(source: list, imported: Counter) -> int:
    kept = 0
    for text in source:
        if text and imported.get(text, 0) > 0:
            imported[text] -= 1
            kept += 1
    return kept


# ---- the metrics ----------------------------------------------------------------------------


def entity_retention(doc, counts: dict) -> dict:
    source = Counter(e.dxftype() for e in _msp(doc))
    retained = Counter()
    for bucket in ("edges", "raw", "notes"):
        for label, n in counts.get("from", {}).get(bucket, {}).items():
            if label in source:
                retained[label] += n
    # every DIMENSION that became a dimension or a fallback note is retained as an entity
    retained["DIMENSION"] += sum(counts.get("from", {}).get("dims", {}).values())
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


def layer_retention(doc) -> dict:
    layers = importdxf.layers_of(doc)
    with_content = [lay for lay in layers if lay["count"]]
    not_imported, imported = [], 0
    ents = _msp(doc)
    for lay in with_content:
        ok = False
        for e in ents:
            if e.dxf.layer != lay["name"]:
                continue
            bucket, _label = importdxf.classify(e)
            if bucket != "skipped" and importdxf._visible(doc, e):
                ok = True
                break
        if ok:
            imported += 1
        else:
            not_imported.append(_decode(lay["name"]))
    return {
        "source_layers": len(layers),
        "layers_with_content": len(with_content),
        "layers_with_content_imported": imported,
        "not_imported": sorted(not_imported),
        "names_preserved": 0,
        "note": "the model has no layer field today: layer names are not carried into drawing.py",
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


def text_retention(doc, d) -> dict:
    source = [_source_text(e) for e in _msp(doc) if e.dxftype() in NOTE_TYPES]
    source = [t for t in source if t]
    imported = Counter(_imported_notes(d))
    kept = _kept_texts(source, imported)
    return {"source": len(source), "retained_as_note": kept, "rate": _rate(kept, len(source))}


def hatch_retention(doc) -> dict:
    source = sum(1 for e in _msp(doc) if e.dxftype() == "HATCH")
    return {"source": source, "retained": 0, "rate": 0.0 if source else None}


def frame_title(doc, d) -> dict:
    ents = _msp(doc)
    inserts = [e for e in ents if e.dxftype() == "INSERT" and _title_name(e.dxf.name)]
    attribs = sum(len(getattr(br, "attribs", ())) for br in inserts)
    # PCCAD-style files keep the title-block attributes as top-level ATTRIB entities
    attribs += sum(1 for e in ents if e.dxftype() == "ATTRIB" and _title_field(e.dxf.tag))
    attribs += sum(1 for e in ents if e.dxftype() == "ATTDEF" and _title_field(e.dxf.tag))
    title_texts = [e for e in ents if e.dxftype() in NOTE_TYPES and _title_layer(e.dxf.layer)]
    texts = [_source_text(e) for e in title_texts]
    imported = Counter(_imported_notes(d))
    kept = _kept_texts(texts, imported)
    k, _unit = importdxf.unit_factor(doc)
    ext = importdxf._extents(doc, k)
    if ext:
        sheet, scale = importdxf.guess_sheet(ext[2] - ext[0], ext[3] - ext[1])
    else:
        sheet, scale = None, None
    return {
        "sheet_guess": {"ok": sheet is not None, "sheet": sheet, "scale": scale},
        "frame_inserts": len(inserts),
        "frame_inserts_retained": 0,
        "title_attrib_fields": attribs,
        "title_attrib_retained": 0,
        "title_layer_texts": len(title_texts),
        "title_layer_texts_retained": kept,
        "note": "INSERT / ATTRIB are skipped by the importer; only plain text on title layers survives",
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
        dims = sorted(i for i in ids if i.startswith("D."))
        notes = sorted(i for i in ids if i.startswith("N."))
        if not dims or not notes:
            return {
                "ok": False,
                "error": "no dimension / note to edit",
                "dimensions": len(dims),
                "notes": len(notes),
                "build_ok": False,
            }
        dim, note = dims[0], notes[0]
        script = part / ".linercad" / "tmp" / "c1_edit_round.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "def apply(d):\n"
            f'    el = d["{dim}"]\n'
            "    for dy in (1.0, -1.0):  # imported dimensions only move along their normal\n"
            "        try:\n"
            "            el.move(dy=dy)\n"
            "            break\n"
            "        except Exception:\n"
            "            continue\n"
            f'    d["{note}"].set(text="C1 \u6539\u4e00\u6bb5\u6587\u5b57")\n',
            encoding="utf-8",
        )
        code, out = _cli(part, "edit", str(script), "-m", "C1 edit round")
        errors = out.get("errors")
        ok_edit = code == 0
        ok_build = ok_edit and (part / ".linercad" / "build" / "drawing.dxf").is_file()
        return {
            "ok": bool(ok_edit and ok_build and not errors),
            "moved_dim": dim,
            "changed_note": note,
            "edit_code": code,
            "build_ok": bool(ok_build),
            "errors": errors,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def evaluate_file(path: Path) -> dict:
    path = Path(path)
    doc = importdxf.read_dxf(path)
    d = Drawing(sheet="A3")
    imp = importdxf.import_dxf(d, str(path))
    counts = imp.counts
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
        "metrics": {
            "entity_retention": entity_retention(doc, counts),
            "layer_retention": layer_retention(doc),
            "dimension_retention": dimension_retention(doc, counts),
            "text_retention": text_retention(doc, d),
            "hatch_retention": hatch_retention(doc),
            "frame_title": frame_title(doc, d),
            "edit_round": edit_round(path),
        },
    }


def _merge(files: list) -> dict:
    ok = [f for f in files if "metrics" in f]
    src = ret = 0
    by_type: dict = {}
    dims_src = dims_keep = dims_note = 0
    text_src = text_keep = 0
    hatch_src = hatch_keep = 0
    layer_src = layer_ok = 0
    title_src = title_keep = 0
    sheet_ok = edit_ok = 0
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
        text_keep += m["text_retention"]["retained_as_note"]
        hatch_src += m["hatch_retention"]["source"]
        hatch_keep += m["hatch_retention"]["retained"]
        layer_src += m["layer_retention"]["layers_with_content"]
        layer_ok += m["layer_retention"]["layers_with_content_imported"]
        title_src += m["frame_title"]["title_layer_texts"]
        title_keep += m["frame_title"]["title_layer_texts_retained"]
        sheet_ok += 1 if m["frame_title"]["sheet_guess"]["ok"] else 0
        edit_ok += 1 if m["edit_round"]["ok"] else 0
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
            "retained": text_keep,
            "rate": _rate(text_keep, text_src),
        },
        "hatch_retention": _rate(hatch_keep, hatch_src),
        "layer_content_retention": _rate(layer_ok, layer_src),
        "title_text_retention": _rate(title_keep, title_src),
        "sheet_guess_rate": round(sheet_ok / n, 4),
        "edit_round_rate": round(edit_ok / n, 4),
    }


def evaluate_dir(folder) -> dict:
    folder = Path(folder)
    if not folder.is_dir():
        return {"ok": False, "error": f"not a directory: {folder}"}
    dxfs = sorted(folder.glob("*.dxf"))
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
