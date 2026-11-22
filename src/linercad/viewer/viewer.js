// Liner-CAD Viewer v0 — plain JS, no build step (M2 SPEC §2; M3 S2: versions, compare).
"use strict";
const TOKEN = document.querySelector('meta[name="lcad-token"]').content;
const $ = (id) => document.getElementById(id);
const S = { version: -1, model: null, byId: {}, sel: [], svg: null, vb: null, full: null, params: [],
  values: {}, dragging: false, previewTimer: null, previewSeq: 0, fitted: false,
  versions: [], pick: [], cmp: null, busy: false,
  previewIds: new Set(), previewFindings: [], paramError: null, resolved: {}, previewActive: false, unplaced: [], statusOrig: {} };  // B3

async function api(path, body) {
  const opt = body === undefined ? { headers: { "X-LCAD-Token": TOKEN } } : { method: "POST", body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "X-LCAD-Token": TOKEN } };
  const r = await fetch(path, opt);
  return r.json();
}

// ---- polling and refresh --------------------------------------------------------------------
async function poll() {
  try {
    const st = await api("/api/state");
    if (!st.preview && !st.param_errors && clearPreviewFindings()) { colour(); inspect(); }
    setStatus(st);
    if (st.version !== S.version) { S.version = st.version; await reload(st); }
  } catch (e) { $("st-edit").textContent = "与服务断开：" + e; }
  setTimeout(poll, 1000);
}

// B4: the canvas badge says what the preview is and, once the drag ends, how to commit it
function updatePreviewBadge() {
  const b = $("preview-badge");
  b.hidden = !S.previewActive;
  if (S.previewActive) {
    b.textContent = S.dragging ? "预览（未写回）· 拖动中…" : "预览（未写回）· 点「写回源码」提交";
  }
}

function setStatus(st) {
  S.previewActive = !!st.preview;
  if (typeof st.preview_seq === "number") S.previewSeq = Math.max(S.previewSeq, st.preview_seq);
  const bar = $("status");
  bar.classList.toggle("has-error", !!st.build_error || st.errors > 0);
  bar.classList.toggle("has-warn", !st.build_error && !st.errors && st.warnings > 0);
  bar.classList.toggle("is-preview", !!st.preview);
  $("canvas-wrap").classList.toggle("is-preview", !!st.preview);  // marked on the canvas too
  updatePreviewBadge();
  // B5: edit id, coloured counts and a one-line message that expands on click
  $("st-edit").textContent = st.edit || "";
  const errs = st.errors || 0, warns = st.warnings || 0;
  const el = $("st-errors"), wl = $("st-warnings"), ml = $("st-msg");
  el.textContent = errs + " error";
  el.className = "cnt " + (errs ? "st-error" : "st-ok");
  wl.textContent = warns + " warn";
  wl.className = "cnt " + (warns ? "st-warn" : "st-ok");
  ml.textContent = st.message ? "“" + st.message + "”" : "";
  ml.title = st.message || "";
  $("st-full").textContent = st.message || "";
  if (st.build_error) {
    $("st-full").textContent = "构建失败：" + st.build_error.message;
  }
}

async function reload(st) {
  const m = await api("/api/model");  // first: its content box sets the initial view
  if (m.ok) {
    S.model = m; S.byId = {};
    for (const e of m.elements) S.byId[e.id] = e;
    S.resolved = m.resolved || {};
    S.unplaced = m.unplaced || [];
    if (st.preview) {  // a page reload while a preview is active: keep the red marks (B3)
      S.previewFindings = m.issues || [];
      S.previewIds = new Set((m.issues || []).map((f) => f.id).concat(Object.keys(S.resolved)));
    }
  }
  const r = S.cmp ? null : await fetch("/svg?v=" + S.version);  // a compare overlay stays up
  if (r && r.ok) {
    const text = await r.text();
    $("canvas").innerHTML = text;
    S.svg = $("canvas").querySelector("svg");
    const vb = S.svg.viewBox.baseVal;
    S.full = [vb.x, vb.y, vb.width, vb.height];
    const first = !S.fitted;
    if (first) { S.fitted = true; S.vb = fitBox(); }  // first view: the content, not the whole sheet
    if (S.vb) setVB(S.vb); else S.vb = S.full.slice();
    S.svg.removeAttribute("width"); S.svg.removeAttribute("height");
    cacheBoxes();
    if (first) viewChanged();
  }
  if (m.ok && !S.cmp) colour();
  if (!S.dragging && (!st.preview || !S.params.length)) await loadParams();
  S.sel = S.sel.filter((id) => S.byId[id]);
  markSel(); inspect(); loadVersions();
}

// the drawing's content (views, dimensions, notes) and the title block plus a margin, as an SVG
// viewBox (y runs down); the empty rest of the sheet is left out
function fitBox() {
  const c = S.model && S.model.content_bbox, t = S.model && S.model.title_bbox;
  if (!c || !S.full) return S.full ? S.full.slice() : null;
  const b = t ? [Math.min(c[0], t[0]), Math.min(c[1], t[1]), Math.max(c[2], t[2]), Math.max(c[3], t[3])] : c;
  const [fx, , fw, fh] = S.full;
  const m = Math.max(0.08 * Math.max(b[2] - b[0], b[3] - b[1]), 6);
  const x0 = Math.max(b[0] - m, fx), x1 = Math.min(b[2] + m, fx + fw);
  const y0 = Math.max(b[1] - m, 0), y1 = Math.min(b[3] + m, fh);
  return [x0, fh - y1, Math.max(x1 - x0, 1), Math.max(y1 - y0, 1)];
}

function clearPreviewFindings() {
  if (!S.previewIds.size && !S.previewFindings.length && !S.paramError) return false;
  S.previewIds = new Set(); S.previewFindings = []; S.paramError = null;
  return true;
}

function fmtObj(v) { return v && typeof v === "object" ? JSON.stringify(v) : String(v); }

// one finding with the E1 fields as the inspector and snapshot.json carry them
function issueHtml(i) {
  const rows = [["条款", i.clause], ["实测", i.measured], ["要求", i.expected], ["候选", i.candidates]];
  const kv = rows.map(([k, v]) => {
    const empty = v === undefined || v === null || v === "" ||
      (Array.isArray(v) && !v.length) ||
      (v && typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length);
    return "<div class=\"k\">" + esc(k) + "</div><div class=\"v\">" + esc(empty ? "无" : fmtObj(v)) + "</div>";
  }).join("");
  return "<div class=\"issue " + esc(i.severity) + "\"><b>" + esc(i.rule) + "</b> " + esc(i.message) +
    (kv ? "<div class=\"kv\">" + kv + "</div>" : "") +
    "<div class=\"muted\">" + esc(i.std || "") + "</div></div>";
}

// findings of the preview response: per-element issues + the red ids the canvas colours
function applyFindings(findings, isPreview, resolved, elementIssues) {
  const byId = elementIssues || {};
  if (!elementIssues) for (const f of findings || []) (byId[f.id] ||= []).push(f);
  for (const e of Object.values(S.byId)) {
    e.issues = byId[e.id] || [];
    if (isPreview) {
      if (!(e.id in S.statusOrig)) S.statusOrig[e.id] = e.status;
      if (e.issues.some((i) => i.severity === "error")) e.status = "error";
      else if (e.issues.length) e.status = "warn";
    } else {
      const orig = S.statusOrig[e.id];
      delete S.statusOrig[e.id];
      if (e.issues.some((i) => i.severity === "error")) e.status = "error";
      else if (e.issues.length) e.status = "warn";
      else if (orig !== undefined) e.status = orig;
    }
  }
  S.previewFindings = isPreview ? findings : [];
  S.previewIds = new Set(isPreview ? findings.map((f) => f.id).concat(Object.keys(resolved || {})) : []);
  if (resolved !== undefined) S.resolved = resolved || {};
  colour();
  inspect();
}

function colour() {
  if (!S.svg) return;
  for (const g of S.svg.querySelectorAll("g[data-id]")) {
    const e = S.byId[g.dataset.id];
    g.classList.remove("st-error", "st-warn", "st-accepted", "st-violation");
    if (!e) continue;
    if (S.previewIds.has(e.id)) { g.classList.add("st-violation"); continue; }  // B3: red
    const sev = e.issues.some((i) => i.severity === "error") ? "error" :
      e.issues.length ? "warn" : S.resolved[e.id] || null;
    if (sev) g.classList.add("st-" + sev);
    else if ((e.status || "").startsWith("accepted")) g.classList.add("st-accepted");
  }
}

// ---- pan / zoom -------------------------------------------------------------------------------
function setVB(vb) { S.vb = vb; if (S.svg) S.svg.setAttribute("viewBox", vb.join(" ")); }
function toSvg(ev) {  // client pixels → SVG units, plus SVG units per pixel
  const m = S.svg.getScreenCTM();
  const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(m.inverse());
  return [p.x, p.y, 1 / m.a];
}
let viewTimer = null;
function viewChanged() {
  clearTimeout(viewTimer);
  viewTimer = setTimeout(() => {
    const H = S.full[3], [x, y, w, h] = S.vb;  // sheet coordinates, y up
    api("/api/view", { viewport: [x, H - y - h, x + w, H - y] });
  }, 800);
}
const canvas = $("canvas");
canvas.addEventListener("wheel", (ev) => {
  if (!S.svg) return; ev.preventDefault();
  const [px, py] = toSvg(ev), k = ev.deltaY > 0 ? 1.2 : 1 / 1.2;
  const [x, y, w, h] = S.vb;
  setVB([px - (px - x) * k, py - (py - y) * k, w * k, h * k]); viewChanged();
}, { passive: false });
let down = null;
canvas.addEventListener("mousedown", (ev) => { if (S.svg) down = { x: ev.clientX, y: ev.clientY, vb: S.vb.slice(), moved: false }; });
window.addEventListener("mousemove", (ev) => {
  if (down) {
    const dx = ev.clientX - down.x, dy = ev.clientY - down.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) down.moved = true;
    if (down.moved) {
      const sc = toSvg(ev)[2];
      setVB([down.vb[0] - dx * sc, down.vb[1] - dy * sc, down.vb[2], down.vb[3]]);
      return;
    }
  }
  hover(pick(ev));
});
window.addEventListener("mouseup", (ev) => {
  if (!down) return;
  const d = down; down = null;
  if (d.moved) { viewChanged(); return; }
  if (ev.target.closest && ev.target.closest("#canvas")) click(pick(ev), ev.ctrlKey || ev.metaKey);
});
window.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") {
    if (S.cmp) exitCompare();
    else if (S.previewActive || S.previewIds.size || S.paramError) releasePreview();  // B3: Esc
    else { S.sel = []; sendSel(); }
  }
  const idle = document.activeElement === document.body;
  if (ev.key === "f" && idle && S.svg) { setVB(fitBox()); viewChanged(); }
  if (ev.key === "0" && idle && S.svg) { setVB(S.full.slice()); viewChanged(); }
});

// nearest element under the cursor: geometric picking on cached child boxes (hairline strokes are
// too thin for the browser's own hit-testing)
function cacheBoxes() {
  S.boxes = [];
  const inv = S.svg.getScreenCTM().inverse();
  for (const g of S.svg.querySelectorAll("g[data-id]")) {
    if (g.dataset.kind === "frame" || g.dataset.kind === "table.cell") continue;
    for (const c of g.children) {
      const b = c.getBBox();  // in the child's own user space: map its corners to SVG units
      const m = inv.multiply(c.getScreenCTM());
      const pts = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
        .map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
      const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      S.boxes.push({ id: g.dataset.id, x0, y0, x1, y1, area: Math.max((x1 - x0) * (y1 - y0), 1e-3),
        text: c.tagName === "text" });
    }
  }
}
function pick(ev) {
  if (!S.svg || !S.boxes || S.cmp) return null;  // no picking in the compare overlay
  const [px, py, sc] = toSvg(ev), tol = 8 * sc;
  let best = null;
  for (const b of S.boxes) {
    const dx = Math.max(b.x0 - px, 0, px - b.x1), dy = Math.max(b.y0 - py, 0, py - b.y1);
    const dist = Math.hypot(dx, dy);
    if (dist > tol) continue;
    // inside a filled box (text, hatch) counts as 0; prefer the closest, then the smallest
    const key = [dist, b.text ? 0 : 1, b.area];
    if (!best || key[0] < best.key[0] - 1e-9 || (Math.abs(key[0] - best.key[0]) < 1e-9 &&
        (key[1] < best.key[1] || (key[1] === best.key[1] && key[2] < best.key[2])))) best = { id: b.id, key };
  }
  return best && best.id;
}
let hovered = null;
function hover(id) {
  if (id === hovered || !S.svg || S.cmp) return;
  if (hovered) for (const g of S.svg.querySelectorAll(`g[data-id="${CSS.escape(hovered)}"]`)) g.classList.remove("hover");
  hovered = id;
  if (id) for (const g of S.svg.querySelectorAll(`g[data-id="${CSS.escape(id)}"]`)) g.classList.add("hover");
}

// ---- selection ---------------------------------------------------------------------------------
function click(id, multi) {
  if (S.cmp) return;
  if (!id) { if (!multi) S.sel = []; }
  else if (multi) S.sel = S.sel.includes(id) ? S.sel.filter((x) => x !== id) : S.sel.concat([id]);
  else S.sel = [id];
  sendSel();
}
function sendSel() { markSel(); inspect(); api("/api/select", { ids: S.sel }); }
function markSel() {
  if (!S.svg || S.cmp) return;
  for (const g of S.svg.querySelectorAll("g[data-id]")) g.classList.toggle("sel", S.sel.includes(g.dataset.id));
}

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
function fmt(v, k) {
  if (k === "tolerance" && v && typeof v === "object") {  // human form: H8 (+0.033 / 0)
    const d = (x) => (x > 0 ? "+" : "") + x;
    return `${v.code || (v.kind === "sym" ? "±" : "")} (${d(v.upper)} / ${d(v.lower)})${v.envelope ? " Ⓔ" : ""}`;
  }
  return typeof v === "object" ? JSON.stringify(v) : String(v);
}

// B3: preview violations in the inspector. Findings show the E1 fields (clause / measured /
// expected / candidates); a param-rule error shows only what ParamError really has.
function previewPanel() {
  let h = "";
  if (S.paramError) {
    const e = S.paramError;
    h += "<div class=\"issue error\"><b>参数违规</b> " + esc(e.message) + "<div class=\"kv\">" +
      (e.values ? "<div class=\"k\">值</div><div class=\"v\">" + esc(fmtObj(e.values)) + "</div>" : "") +
      (e.hint ? "<div class=\"k\">提示</div><div class=\"v\">" + esc(e.hint) + "</div>" : "") +
      (e.candidates && e.candidates.length ? "<div class=\"k\">候选</div><div class=\"v\">" + esc(fmtObj(e.candidates)) + "</div>" : "") +
      "</div>" +
      (e.affected && e.affected.length ? "<div class=\"row\">" + e.affected.map((id) =>
        "<a class=\"ref\" data-ref=\"" + esc(id) + "\">" + esc(id) + "</a>").join(" ") + "</div>" : "") +
      "</div>";
  }
  if (S.unplaced.length) {
    h += "<h3>未定位违规（" + S.unplaced.length + "）</h3><p class=\"muted\">finding 的 ID 不是可画元素（如参数），列在这里而不是画布</p>";
    for (const f of S.unplaced) h += issueHtml(f);
  }
  if (S.previewFindings.length) {
    const unplaced = new Set(S.unplaced.map((f) => f.rule + "|" + f.id));
    const shown = S.previewFindings.filter((f) => !unplaced.has(f.rule + "|" + f.id));
    h += "<h3>预览违规（" + shown.length + "）</h3>";
    for (const f of shown) h += issueHtml(f) +
      "<div class=\"row\"><a class=\"ref\" data-ref=\"" + esc(f.id) + "\">" + esc(f.id) + "</a></div>";
  }
  return h;
}

function bindRefs(box) {
  for (const a of box.querySelectorAll("a.ref")) a.onclick = () => {
    if (S.byId[a.dataset.ref]) { S.sel = [a.dataset.ref]; sendSel(); }
  };
}

function inspect() {
  const box = $("insp-body");
  if (S.cmp) { cmpPanel(box); return; }
  if (!S.sel.length) {
    // B2: an empty inspector still tells the user how to work and what the drawing contains
    const sum = (S.model && S.model.summary) || { elements: 0, errors: 0, warnings: 0 };
    let h = '<div id="insp-empty"><h3>用法</h3><div class="kv">' +
      '<div class="k">点选</div><div class="v">单击画布元素（Ctrl 多选）</div>' +
      '<div class="k">@ID</div><div class="v">选中后点「复制 @ID」，直接粘给 Agent</div></div>';
    h += '<h3>图纸摘要</h3><div id="insp-summary" class="kv">' +
      '<div class="k">元素</div><div class="v">' + sum.elements + '</div>' +
      '<div class="k">错误</div><div class="v ' + (sum.errors ? "st-error" : "muted") + '">' + sum.errors + '</div>' +
      '<div class="k">警告</div><div class="v ' + (sum.warnings ? "st-warn" : "muted") + '">' + sum.warnings + '</div></div>';
    h += previewPanel();
    box.innerHTML = h; bindRefs(box); return;
  }
  const els = S.sel.map((id) => S.byId[id]).filter(Boolean);
  const refs = els.map((e) => e.ref).join(" ");
  let h = previewPanel() + `<div class="row"><button class="primary" id="btn-copy">复制 @ID</button>
    <span class="muted">${els.length} 个已写入 selection.json</span></div>`;
  for (const e of els) {
    h += `<h3>${esc(e.kind)}</h3><div class="idline">${esc(e.id)}</div><div class="kv">`;
    h += `<div class="k">显示</div><div class="v">${esc(e.label)}</div>`;
    if (e.view) h += `<div class="k">视图</div><div class="v">${esc(e.view)}</div>`;
    for (const [k, v] of Object.entries(e.intent || {})) {
      if (v === null || v === "" || (Array.isArray(v) && !v.length)) continue;
      h += `<div class="k">${esc(k)}</div><div class="v">${esc(fmt(v, k))}</div>`;
    }
    h += `<div class="k">引用</div><div class="v">${(e.refs || []).map((r) =>
      `<a class="ref" data-ref="${esc(r)}">${esc(r)}</a>`).join(" ") || "—"}</div>`;
    const src = e.src ? `${e.src.file}:${e.src.line}` : "—";
    h += `<div class="k">来源</div><div class="v">${e.src_link ? `<a href="${esc(e.src_link)}">${esc(src)}</a>` : esc(src)}` +
      `${e.history && e.history.length ? " · 修改于 " + esc(e.history.join(", ")) : ""}</div>`;
    h += `<div class="k">状态</div><div class="v st-${esc((e.status || "").split("(")[0])}">${esc(e.status)}</div></div>`;
    for (const i of e.issues || []) h += issueHtml(i);
    if (e.selector) h += `<h3>选择器</h3><code class="sel">${esc(e.selector)}</code>`;
  }
  box.innerHTML = h;
  $("btn-copy").onclick = () => copy(refs);
  bindRefs(box);
}
function copy(text) {
  (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).catch(() => {
    const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select();
    document.execCommand("copy"); t.remove();
  });
  $("st-extra").textContent = "已复制 " + text;
}

// ---- parameters -------------------------------------------------------------------------------
async function loadParams() {
  const r = await api("/api/params");
  if (!r.ok) return;
  S.params = r.params; S.values = {};
  const list = $("param-list"); list.innerHTML = "";
  const groups = {};
  for (const p of r.params) (groups[p.group || ""] ||= []).push(p);
  for (const [g, ps] of Object.entries(groups)) {
    const div = document.createElement("div"); div.className = "pgroup";
    if (g) div.innerHTML = `<div class="gname">${esc(g)}</div>`;
    for (const p of ps) div.appendChild(paramRow(p));
    list.appendChild(div);
  }
  S.values = {};
  for (const p of r.params) if (p.value !== p.default) S.values[p.name] = p.value;
  for (const row of list.querySelectorAll(".param")) {
    const p = r.params.find((q) => q.name === row.dataset.name);
    row.classList.toggle("changed", !!p && p.value !== p.default);
  }
  $("btn-reset").disabled = !Object.keys(S.values).length;
  $("param-msg").textContent = Object.keys(S.values).length ? "预览值已从服务端恢复（页面 reload）" : "";
}
function paramRow(p) {
  const v0 = p.default;
  const range = p.range || { min: p.min ?? +(v0 * 0.5).toFixed(3), max: p.max ?? +(v0 * 1.5 || 10).toFixed(3) };
  const lo = range.min, hi = range.max;
  const step = p.step ?? (Math.abs(v0) >= 10 ? 1 : 0.1);
  const fnum = (x) => (Number.isInteger(x) ? String(x) : String(+x.toFixed(3)));
  // B1: min / max labels at both ends and four tick marks on the slider track
  const ticks = Array.from({ length: 6 }, (_, i) =>
    `<i class="p-tick" style="left:${(100 * i) / 5}%"></i>`).join("");
  const row = document.createElement("div"); row.className = "param"; row.dataset.name = p.name;
  row.innerHTML = `<div class="top"><span title="${esc(p.rule || "")}">${esc(p.label || p.name)} <span class="muted">${esc(p.name)}</span></span>
    <span class="val">${esc(p.value)} ${esc(p.unit || "")}</span></div>
    <input type="range" min="${lo}" max="${hi}" step="${step}" value="${p.value}">
    <div class="p-scale"><span class="p-min">${fnum(lo)}</span><span class="p-ticks">${ticks}</span><span class="p-max">${fnum(hi)}</span></div>
    <div class="err"></div><button type="button" hidden>写回源码</button>`;
  const inp = row.querySelector("input"), btn = row.querySelector("button"), err = row.querySelector(".err");
  // [写回源码] only for a changed value whose preview the rules accepted: not while the preview is
  // pending, never for a value that breaks a rule (the reason is shown in the row instead)
  row.sync = () => { btn.hidden = +inp.value === v0 || row.classList.contains("pending") || row.classList.contains("bad"); };
  row.setBad = (msg) => { row.classList.add("bad"); err.textContent = "不能写回：" + msg; row.sync(); };
  row.clearBad = () => { row.classList.remove("bad"); err.textContent = ""; row.sync(); };
  inp.addEventListener("input", () => {
    const v = +inp.value; row.querySelector(".val").textContent = `${v} ${p.unit || ""}`;
    if (v === v0) delete S.values[p.name]; else S.values[p.name] = v;
    row.classList.toggle("changed", v !== v0);
    row.classList.add("pending"); row.clearBad();
    S.dragging = true; S.previewActive = true;  // B3: Esc can withdraw while the request is in flight
    updatePreviewBadge();
    schedulePreview();
  });
  btn.onclick = () => writeback(p.name, +inp.value);
  return row;
}
function schedulePreview() {
  clearTimeout(S.previewTimer);
  S.previewTimer = setTimeout(async () => {
    const seq = ++S.previewSeq, values = { ...S.values };
    let r;
    try { r = await api("/api/preview", { values, seq }); } catch (e) { r = { ok: false, error: { message: String(e) } }; }
    if (seq !== S.previewSeq || r.superseded) return;  // a newer drag superseded this one
    S.dragging = false;
    updatePreviewBadge();
    const rows = [...document.querySelectorAll(".param")];
    for (const row of rows) row.classList.remove("pending");
    const msg = $("param-msg");
    if (!r.ok) {
      msg.className = "msg bad"; msg.textContent = r.error.message;
      S.paramError = { message: r.error.message, values: r.error.values || null,
        hint: r.error.hint || "", candidates: r.error.candidates || [], affected: r.affected || [] };
      S.previewFindings = [];
      S.previewIds = new Set(r.affected || []);  // B3: red on the elements that cover the parameter
      S.previewActive = true;
      S.unplaced = [];
      colour(); inspect();
      const bad = new Set(Object.keys(values));  // the changed rows, and the row whose rule failed
      if (r.error.id) bad.add(r.error.id);
      for (const row of rows) { if (bad.has(row.dataset.name)) row.setBad(r.error.message); else row.sync(); }
      return;
    }
    for (const row of rows) row.clearBad();
    applyFindings(r.findings || [], Object.keys(values).length > 0, r.resolved, r.element_issues);
    S.previewActive = true;
    S.unplaced = r.unplaced || [];
    S.paramError = null;
    msg.className = "msg";
    msg.textContent = Object.keys(values).length ? `预览 ${r.timing_ms} ms` +
      (r.stale_ops && r.stale_ops.length ? `\n失效的日志操作：${r.stale_ops.map((s) => `${s.edit} ${s.op} ${s.id || ""}`).join("；")}` : "") : "";
    $("btn-reset").disabled = !Object.keys(values).length;
    S.version = -2;  // force reload of the preview SVG on the next poll
  }, 250);
}
async function writeback(name, value) {
  const r = await api("/api/writeback", { name, value });
  const msg = $("param-msg");
  if (r.ok) { msg.className = "msg"; msg.textContent = `已写回 ${name}=${value}（${r.edit || ""}）`; S.version = -2; }
  else { msg.className = "msg bad"; msg.textContent = r.error.message + (r.error.hint ? "\n" + r.error.hint : ""); }
}
async function releasePreview() {
  // withdraw the preview: values back to the committed ones, red marks and the panels clear.
  // Bump the sequence first so a preview request still in flight cannot bring the old preview back.
  S.values = {};
  S.previewActive = false;
  S.unplaced = [];
  updatePreviewBadge();
  const seq = ++S.previewSeq;
  const r = await api("/api/preview", { values: {}, seq });
  clearPreviewFindings();
  if (r && r.findings) applyFindings(r.findings, false, r.resolved, r.element_issues);
  colour(); inspect();
  S.version = -2;
  await loadParams();
}
$("btn-reset").onclick = () => releasePreview();

// ---- versions and compare (M3 S2) -----------------------------------------------------------------
const vref = (v) => v.edit || v.commit;
async function loadVersions() {
  let r;
  try { r = await api("/api/versions"); } catch (e) { return; }
  if (!r.ok) return;
  S.versions = r.versions;
  S.pick = S.pick.filter((i) => i < S.versions.length);
  renderVersions();
}
function renderVersions() {
  const list = $("ver-list");
  list.innerHTML = "";
  S.versions.forEach((v, i) => {
    const row = document.createElement("div");
    row.className = "ver" + (S.pick.includes(i) ? " picked" : "");
    row.title = `${vref(v)} ${v.message}\n${v.time}`;
    row.innerHTML = `<span class="vid">${esc(vref(v))}</span><span class="vmsg">${esc(v.message)}</span>` +
      `<span class="vtime">${esc((v.time || "").slice(5, 16).replace("T", " "))}</span>`;
    row.onclick = () => pickVersion(i);
    list.appendChild(row);
  });
  $("ver-count").textContent = S.versions.length ? ` (${S.versions.length})` : "";
  $("ver-hint").textContent = S.pick.length === 1 ? "再点一个版本进入对比" : S.cmp ? "" :
    S.versions.length > 1 ? "点选两个版本，在画布上叠加对比" : "";
}
async function pickVersion(i) {
  if (S.busy) return;
  if (S.pick.length >= 2) S.pick = [];
  S.pick = S.pick.includes(i) ? S.pick.filter((x) => x !== i) : S.pick.concat([i]);
  renderVersions();
  if (S.pick.length === 2) await compare(Math.max(...S.pick), Math.min(...S.pick));  // older first
}
async function compare(ia, ib) {
  const a = vref(S.versions[ia]), b = vref(S.versions[ib]);
  S.busy = true;
  $("cmp-banner").hidden = false; $("cmp-text").textContent = `对比 ${a} → ${b}：计算中…`;
  let r;
  try { r = await api(`/api/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`); }
  catch (e) { r = { ok: false, error: { message: String(e) } }; }
  S.busy = false;
  if (!r.ok) { $("cmp-text").textContent = `对比 ${a} → ${b} 失败：${r.error.message}`; return; }
  S.cmp = { a, b, summary: r.summary };
  $("canvas").innerHTML = r.svg;
  S.svg = $("canvas").querySelector("svg");
  const vb = S.svg.viewBox.baseVal;
  S.full = [vb.x, vb.y, vb.width, vb.height];
  S.svg.removeAttribute("width"); S.svg.removeAttribute("height");
  S.boxes = []; hovered = null;
  setVB(S.vb || S.full.slice());  // keep the view the user had
  const c = r.summary.counts;
  $("cmp-text").textContent = `对比 ${a} → ${b}：新增 ${c.added} · 删除 ${c.removed} · 意图改动 ${c.intent_changed} · 位置改动 ${c.layout_changed}`;
  $("canvas-wrap").classList.add("is-compare");
  renderVersions(); inspect();
}
async function exitCompare() {
  S.cmp = null; S.pick = [];
  $("cmp-banner").hidden = true; $("canvas-wrap").classList.remove("is-compare");
  renderVersions();
  const st = await api("/api/state");
  S.version = st.version; setStatus(st);
  await reload(st);  // puts the live drawing back, same view
}
$("btn-exit-cmp").onclick = exitCompare;

function cmpPanel(box) {
  const s = S.cmp.summary;
  const sect = (title, ids) => !ids.length ? "" : `<h3>${title}（${ids.length}）</h3><div class="idlist">` +
    ids.slice(0, 60).map((id) => `<a class="ref" data-zoom="${esc(id)}">${esc(id)}</a>`).join(" ") +
    (ids.length > 60 ? ` … 等 ${ids.length} 个` : "") + "</div>";
  let h = `<div class="muted">${esc(s.a.ref)} → ${esc(s.b.ref)}　点 ID 缩放到该元素</div>`;
  h += sect("新增", s.added) + sect("删除", s.removed) + sect("意图改动", s.intent_changed) + sect("位置改动", s.layout_changed);
  const rows = s.intent_changed.slice(0, 30).map((id) => {
    const f = (s.details[id] || {}).intent || {};
    const txt = Object.entries(f).map(([k, [x, y]]) => `${k}: ${fmt(x ?? "—", k)} → ${fmt(y ?? "—", k)}`).join("；");
    return `<div class="k">${esc(id)}</div><div class="v">${esc(txt)}</div>`;
  });
  if (rows.length) h += `<h3>意图变化</h3><div class="kv">${rows.join("")}</div>`;
  if (!s.added.length && !s.removed.length && !s.intent_changed.length && !s.layout_changed.length) h += '<p class="muted">两个版本没有差别</p>';
  box.innerHTML = h;
  for (const a of box.querySelectorAll("a[data-zoom]")) a.onclick = () => zoomTo(a.dataset.zoom);
}
function zoomTo(id) {
  if (!S.svg) return;
  const gs = S.svg.querySelectorAll(`g[data-id="${CSS.escape(id)}"]`);
  if (!gs.length) return;
  const b = gs[gs.length - 1].getBBox();  // B's drawing when both versions have the element
  const m = Math.max(0.6 * Math.max(b.width, b.height), 12);
  setVB([b.x - m, b.y - m, b.width + 2 * m, b.height + 2 * m]); viewChanged();
}

// B5: click the one-line message to expand the full commit message above the status bar
$("st-msg").onclick = () => {
  const full = $("st-full");
  full.hidden = !full.hidden;
  $("st-msg").classList.toggle("expanded", !full.hidden);
};

poll();
