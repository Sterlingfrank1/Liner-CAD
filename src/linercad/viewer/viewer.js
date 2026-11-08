// Liner-CAD Viewer v0 — plain JS, no build step (M2 SPEC §2).
"use strict";
const TOKEN = document.querySelector('meta[name="lcad-token"]').content;
const $ = (id) => document.getElementById(id);
const S = { version: -1, model: null, byId: {}, sel: [], svg: null, vb: null, full: null, params: [],
  values: {}, dragging: false, previewTimer: null, previewSeq: 0 };

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", body: JSON.stringify(body),
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
  bar.classList.toggle("has-error", !!st.build_error);
  $("st-text").textContent = (st.status || "") + (st.preview ? " · 预览中（未写回）" : "") +
    (st.build_error ? " · 构建失败：" + st.build_error.message : "");
}

async function reload(st) {
  const r = await fetch("/svg?v=" + S.version);
  if (r.ok) {
    const text = await r.text();
    $("canvas").innerHTML = text;
    S.svg = $("canvas").querySelector("svg");
    const vb = S.svg.viewBox.baseVal;
    S.full = [vb.x, vb.y, vb.width, vb.height];
    if (S.vb) setVB(S.vb); else S.vb = S.full.slice();
    S.svg.removeAttribute("width"); S.svg.removeAttribute("height");
    cacheBoxes();
  }
  const m = await api("/api/model");
  if (m.ok) {
    S.model = m; S.byId = {};
    for (const e of m.elements) S.byId[e.id] = e;
    colour();
  }
  if (!S.dragging && !st.preview) await loadParams();
  S.sel = S.sel.filter((id) => S.byId[id]);
  markSel(); inspect();
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
  if (ev.key === "Escape") { S.sel = []; sendSel(); }
  if (ev.key === "f" && document.activeElement === document.body) { setVB(S.full.slice()); viewChanged(); }
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
  if (!S.svg || !S.boxes) return null;
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
  if (id === hovered || !S.svg) return;
  if (hovered) for (const g of S.svg.querySelectorAll(`g[data-id="${CSS.escape(hovered)}"]`)) g.classList.remove("hover");
  hovered = id;
  if (id) for (const g of S.svg.querySelectorAll(`g[data-id="${CSS.escape(id)}"]`)) g.classList.add("hover");
}

// ---- selection ---------------------------------------------------------------------------------
function click(id, multi) {
  if (!id) { if (!multi) S.sel = []; }
  else if (multi) S.sel = S.sel.includes(id) ? S.sel.filter((x) => x !== id) : S.sel.concat([id]);
  else S.sel = [id];
  sendSel();
}
function sendSel() { markSel(); inspect(); api("/api/select", { ids: S.sel }); }
function markSel() {
  if (!S.svg) return;
  for (const g of S.svg.querySelectorAll("g[data-id]")) g.classList.toggle("sel", S.sel.includes(g.dataset.id));
}

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
function fmt(v) { return typeof v === "object" ? JSON.stringify(v) : String(v); }

function inspect() {
  const box = $("insp-body");
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
      h += `<div class="k">${esc(k)}</div><div class="v">${esc(fmt(v))}</div>`;
    }
    h += `<div class="k">引用</div><div class="v">${(e.refs || []).map((r) =>
      `<a class="ref" data-ref="${esc(r)}">${esc(r)}</a>`).join(" ") || "—"}</div>`;
    const src = e.src ? `${e.src.file}:${e.src.line}` : "—";
    h += `<div class="k">来源</div><div class="v">${e.src_link ? `<a href="${esc(e.src_link)}">${esc(src)}</a>` : esc(src)}` +
      `${e.history && e.history.length ? " · 修改于 " + esc(e.history.join(", ")) : ""}</div>`;
    h += `<div class="k">状态</div><div class="v">${esc(e.status)}</div></div>`;
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
  const inp = row.querySelector("input"), btn = row.querySelector("button");
  inp.addEventListener("input", () => {
    const v = +inp.value; row.querySelector(".val").textContent = `${v} ${p.unit || ""}`;
    if (v === v0) delete S.values[p.name]; else S.values[p.name] = v;
    row.classList.toggle("changed", v !== v0); btn.hidden = v === v0;
    S.dragging = true; schedulePreview();
  });
  btn.onclick = () => writeback(p.name, +inp.value);
  return row;
}
function schedulePreview() {
  clearTimeout(S.previewTimer);
  S.previewTimer = setTimeout(async () => {
    const seq = ++S.previewSeq, values = { ...S.values };
    const r = await api("/api/preview", { values });
    if (seq !== S.previewSeq) return;  // a newer drag superseded this one
    S.dragging = false;
    for (const row of document.querySelectorAll(".param")) { row.classList.remove("bad"); row.querySelector(".err").textContent = ""; }
    const msg = $("param-msg");
    if (!r.ok) {
      msg.className = "msg bad"; msg.textContent = r.error.message;
      for (const n of Object.keys(values)) document.querySelector(`.param[data-name="${CSS.escape(n)}"]`)?.classList.add("bad");
      return;
    }
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

poll();
