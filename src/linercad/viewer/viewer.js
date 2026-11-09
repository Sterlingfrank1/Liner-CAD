// Liner-CAD Viewer v0 — plain JS, no build step (M2 SPEC §2; M3 S2: versions, compare).
"use strict";
const TOKEN = document.querySelector('meta[name="lcad-token"]').content;
const $ = (id) => document.getElementById(id);
const S = { version: -1, model: null, byId: {}, sel: [], svg: null, vb: null, full: null, params: [],
  values: {}, dragging: false, previewTimer: null, previewSeq: 0, fitted: false,
  versions: [], pick: [], cmp: null, busy: false };

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
    setStatus(st);
    if (st.version !== S.version) { S.version = st.version; await reload(st); }
  } catch (e) { $("st-text").textContent = "与服务断开：" + e; }
  setTimeout(poll, 1000);
}

function setStatus(st) {
  const bar = $("status");
  bar.classList.toggle("has-error", !!st.build_error || st.errors > 0);
  bar.classList.toggle("has-warn", !st.build_error && !st.errors && st.warnings > 0);
  bar.classList.toggle("is-preview", !!st.preview);
  $("canvas-wrap").classList.toggle("is-preview", !!st.preview);  // marked on the canvas too
  $("preview-badge").hidden = !st.preview;
  $("st-text").title = st.status || "";
  $("st-text").textContent = (st.status || "") + (st.preview ? " · 预览中（未写回）" : "") +
    (st.build_error ? " · 构建失败：" + st.build_error.message : "");
}

async function reload(st) {
  const m = await api("/api/model");  // first: its content box sets the initial view
  if (m.ok) {
    S.model = m; S.byId = {};
    for (const e of m.elements) S.byId[e.id] = e;
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
  if (!S.dragging && !st.preview) await loadParams();
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

function colour() {
  if (!S.svg) return;
  for (const g of S.svg.querySelectorAll("g[data-id]")) {
    const e = S.byId[g.dataset.id];
    g.classList.remove("st-error", "st-warn", "st-accepted");
    if (!e) continue;
    const sev = e.issues.some((i) => i.severity === "error") ? "error" : e.issues.length ? "warn" : null;
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
  if (ev.key === "Escape") { if (S.cmp) exitCompare(); else { S.sel = []; sendSel(); } }
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

function inspect() {
  const box = $("insp-body");
  if (S.cmp) { cmpPanel(box); return; }
  if (!S.sel.length) { box.innerHTML = '<p class="muted">点选图上的元素（Ctrl 多选）</p>'; return; }
  const els = S.sel.map((id) => S.byId[id]).filter(Boolean);
  const refs = els.map((e) => e.ref).join(" ");
  let h = `<div class="row"><button class="primary" id="btn-copy">复制 @ID</button>
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
    for (const i of e.issues || []) h += `<div class="issue ${esc(i.severity)}"><b>${esc(i.rule)}</b> ${esc(i.message)}<br><span class="muted">${esc(i.std || "")}</span></div>`;
    if (e.selector) h += `<h3>选择器</h3><code class="sel">${esc(e.selector)}</code>`;
  }
  box.innerHTML = h;
  $("btn-copy").onclick = () => copy(refs);
  for (const a of box.querySelectorAll("a.ref")) a.onclick = () => { if (S.byId[a.dataset.ref]) { S.sel = [a.dataset.ref]; sendSel(); } };
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
  $("btn-reset").disabled = true; $("param-msg").textContent = "";
}
function paramRow(p) {
  const v0 = p.default, lo = p.min ?? +(v0 * 0.5).toFixed(3), hi = p.max ?? +(v0 * 1.5 || 10).toFixed(3);
  const step = p.step ?? (Math.abs(v0) >= 10 ? 1 : 0.1);
  const row = document.createElement("div"); row.className = "param"; row.dataset.name = p.name;
  row.innerHTML = `<div class="top"><span title="${esc(p.rule || "")}">${esc(p.label || p.name)} <span class="muted">${esc(p.name)}</span></span>
    <span class="val">${esc(p.value)} ${esc(p.unit || "")}</span></div>
    <input type="range" min="${lo}" max="${hi}" step="${step}" value="${p.value}">
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
    S.dragging = true; schedulePreview();
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
    const rows = [...document.querySelectorAll(".param")];
    for (const row of rows) row.classList.remove("pending");
    const msg = $("param-msg");
    if (!r.ok) {
      msg.className = "msg bad"; msg.textContent = r.error.message;
      const bad = new Set(Object.keys(values));  // the changed rows, and the row whose rule failed
      if (r.error.id) bad.add(r.error.id);
      for (const row of rows) { if (bad.has(row.dataset.name)) row.setBad(r.error.message); else row.sync(); }
      return;
    }
    for (const row of rows) row.clearBad();
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
$("btn-reset").onclick = async () => { S.values = {}; await api("/api/preview", { values: {} }); S.version = -2; await loadParams(); };

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

poll();
