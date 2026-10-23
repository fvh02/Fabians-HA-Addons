import * as THREE from "three";
import { OrbitControls } from "./orbit-controls.js";
import { STLLoader } from "./stl-loader.js";

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(data.error || `Fehler ${r.status}`); e.data = data; throw e; }
  return data;
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });
function toast(text) { const t = $("toast"); t.textContent = text; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 4000); }
const fmt = (n) => (Math.round(n * 10) / 10).toLocaleString("de-DE");
const COLORS = [0x2e7d4f, 0x3b82f6, 0xea580c, 0x9333ea, 0xca8a04, 0xdc2626, 0x0d9488];

let project = null, version = null, pollTimer = null;

// ---------- 3D viewer ----------
const box = $("view3d");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
box.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.5, 5000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.0));
const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(200, 400, 300); scene.add(sun);
const plate = new THREE.GridHelper(256, 16, 0x9aa69d, 0xc9d1ca); scene.add(plate);
const model = new THREE.Group(); model.rotation.x = -Math.PI / 2; scene.add(model);   // CAD z up → three y up
function themeBg() { scene.background = new THREE.Color(matchMedia("(prefers-color-scheme: dark)").matches ? 0x1b211d : 0xf1f4f0); }
themeBg();
function resize() {
  const w = box.clientWidth, h = box.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(box);
(function loop() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop); })();

let shownKey = "";
async function showModel(p, v) {
  const key = `${p.id}/${v?.n}`;
  if (key === shownKey) return;
  shownKey = key;
  model.clear();
  if (!v || !v.ok) return;
  const loader = new STLLoader();
  const meshes = await Promise.all(v.teile.map((t, i) => new Promise((res) => loader.load(
    `api/projekte/${p.id}/v/${v.n}/teil-${encodeURIComponent(t.name)}.stl`,
    (geo) => { geo.computeVertexNormals(); res(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: COLORS[i % COLORS.length], roughness: 0.6, metalness: 0.05 }))); },
    undefined, () => res(null)))));
  meshes.filter(Boolean).forEach((m) => model.add(m));
  // centre on the build plate and fit the camera
  const bb = new THREE.Box3().setFromObject(model);
  const c = bb.getCenter(new THREE.Vector3());
  model.position.x -= c.x; model.position.z -= c.z; model.position.y -= bb.min.y;
  const size = bb.getSize(new THREE.Vector3()).length() || 100;
  camera.position.set(size * 0.9, size * 0.75, size * 1.0);
  controls.target.set(0, (bb.max.y - bb.min.y) / 3, 0);
  camera.near = size / 100; camera.far = size * 50; camera.updateProjectionMatrix();
}

// ---------- start page ----------
async function showStart() {
  project = null; shownKey = ""; clearTimeout(pollTimer);
  $("start").hidden = false; $("project").hidden = true; $("projName").textContent = "";
  history.replaceState(null, "", "#");
  const list = await api("api/projekte");
  $("projects").innerHTML = list.map((p) => `<div class="card pcard" data-id="${p.id}">
    ${p.letzte ? `<img src="api/projekte/${p.id}/v/${p.letzte}/vorschau.png" alt="" loading="lazy">` : '<img alt="">'}
    <div class="t"><b>${esc(p.name)}</b><div class="muted">${p.versionen} Version(en)${p.groesse_mm ? ` · ${p.groesse_mm.map(fmt).join(" × ")} mm` : ""}</div></div></div>`).join("");
  $("projects").querySelectorAll(".pcard").forEach((el) => (el.onclick = () => openProject(el.dataset.id)));
  pollPending();
}
$("home").onclick = showStart;
$("newBtn").onclick = () => { showStart(); $("newName").focus(); };
$("createBtn").onclick = async () => {
  const name = $("newName").value.trim(), desc = $("newDesc").value.trim();
  if (!desc && !name) return toast("Beschreib kurz, was du brauchst");
  const p = await post("api/projekte", { name: name || desc.slice(0, 40), beschreibung: desc });
  $("newName").value = ""; $("newDesc").value = "";
  await openProject(p.id);
  if (desc) await post(`api/projekte/${p.id}/chat`, { text: desc }).catch((e) => toast(e.message));
  refresh();
};

// ---------- project ----------
async function openProject(id, n = null) {
  $("start").hidden = true; $("project").hidden = false;
  history.replaceState(null, "", `#${id}`);
  project = await api(`api/projekte/${id}`);
  version = pickVersion(n);
  render(); resize();
  schedule();
}
function pickVersion(n) {
  const vs = project.versionen;
  if (!vs.length) return null;
  if (n != null) return vs.find((v) => v.n === n) || vs[vs.length - 1];
  return vs[vs.length - 1];
}
async function refresh(keepVersion = false) {
  if (!project) return;
  const before = project.versionen.length;
  project = await api(`api/projekte/${project.id}`);
  if (!keepVersion || project.versionen.length !== before) version = pickVersion(keepVersion && project.versionen.length === before ? version?.n : null);
  render();
}
function schedule() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => { try { await refresh(true); } catch (e) { console.warn(e); } schedule(); }, project?.arbeitet ? 1500 : 5000);
}

function render() {
  const p = project, v = version;
  $("projName").textContent = p.name;
  $("versionSel").innerHTML = p.versionen.slice().reverse().map((x) => `<option value="${x.n}" ${x.n === v?.n ? "selected" : ""}>Version ${x.n}</option>`).join("") || "<option>noch keine Version</option>";
  $("stats").textContent = v ? `${v.gesamt.groesse_mm.map(fmt).join(" × ")} mm · ${fmt(v.gesamt.gewicht_g)} g ${v.material}${v.warnungen.length ? " · ⚠️ " + v.warnungen.length : ""}` : "";
  for (const id of ["sendBtn", "printBtn"]) $(id).disabled = !v;
  $("stepLink").href = v ? `api/projekte/${p.id}/v/${v.n}/modell.step?download=1` : "#";
  $("stlLink").href = v ? `api/projekte/${p.id}/v/${v.n}/${v.druckdatei}?download=1` : "#";
  $("stlLink").textContent = v?.druckdatei === "druck.zip" ? "STL (zip)" : "STL";
  $("busy").hidden = !p.arbeitet; $("busy").textContent = p.arbeitet || "";
  $("chatBtn").disabled = !!p.arbeitet;
  showModel(p, v);
  renderChat(); renderParams(); renderMeasures(); renderDetails(); renderPending(p.druck);
}

function renderChat() {
  const el = $("chat"), atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  const intro = project.chat.length ? "" : `<div class="msg claude">Beschreib, was du brauchst – mit Maßen, wenn du sie hast. Fotos mit einem A4-Blatt kannst du unter „📏 Maße“ vermessen.</div>`;
  el.innerHTML = intro + project.chat.map((m) => `<div class="msg ${m.rolle === "du" ? "du" : "claude"}">${esc(m.text)}
    <div class="meta">${esc((m.zeit || "").slice(11, 16))}${m.version ? ` · <a href="#" data-v="${m.version}">Version ${m.version}</a>` : ""}${m.von === "assistent" ? " · per iMessage" : ""}</div></div>`).join("")
    + (project.arbeitet ? `<div class="msg claude">⏳ ${esc(project.arbeitet)}</div>` : "");
  el.querySelectorAll("[data-v]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); version = pickVersion(+a.dataset.v); render(); }));
  if (atBottom || renderChat.first !== project.id) el.scrollTop = el.scrollHeight;
  renderChat.first = project.id;
}
$("chatBtn").onclick = async () => {
  const text = $("chatText").value.trim(); if (!text) return;
  try { await post(`api/projekte/${project.id}/chat`, { text }); $("chatText").value = ""; await refresh(); schedule(); } catch (e) { toast(e.message); }
};
$("chatText").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("chatBtn").onclick(); });
$("versionSel").onchange = () => { version = pickVersion(+$("versionSel").value); render(); };

// parameters
let paramKey = "";
function renderParams() {
  const v = version, key = `${project.id}/${v?.n}`;
  if (key === paramKey) return;
  paramKey = key;
  if (!v || !Object.keys(v.params || {}).length) { $("params").innerHTML = '<p class="muted">Noch keine Parameter.</p>'; return; }
  $("params").innerHTML = Object.entries(v.params).map(([k, spec]) => {
    const val = v.werte[k] ?? spec.wert, label = `${esc(spec.info || k)}${spec.einheit ? ` (${esc(spec.einheit)})` : ""}`;
    if (typeof val === "boolean") return `<div class="param"><label><input type="checkbox" data-k="${k}" ${val ? "checked" : ""}> ${label}</label></div>`;
    if (typeof val !== "number") return `<div class="param"><label>${label}</label><input data-k="${k}" value="${esc(val)}"></div>`;
    const min = spec.min ?? 0, max = spec.max ?? Math.max(val * 3, 10), step = Number.isInteger(val) && Number.isInteger(min) ? 1 : 0.1;
    return `<div class="param"><label>${label}</label><div class="row">
      <input type="range" min="${min}" max="${max}" step="${step}" value="${val}" data-r="${k}">
      <input type="number" min="${min}" max="${max}" step="${step}" value="${val}" data-k="${k}"></div></div>`;
  }).join("");
  $("params").querySelectorAll("[data-r]").forEach((r) => (r.oninput = () => ($("params").querySelector(`[data-k="${r.dataset.r}"]`).value = r.value)));
  $("params").querySelectorAll('input[type=number]').forEach((n) => (n.oninput = () => { const r = $("params").querySelector(`[data-r="${n.dataset.k}"]`); if (r) r.value = n.value; }));
}
$("paramBtn").onclick = async () => {
  const werte = {};
  $("params").querySelectorAll("[data-k]").forEach((el) => {
    werte[el.dataset.k] = el.type === "checkbox" ? el.checked : el.type === "number" ? parseFloat(el.value) : el.value;
  });
  $("paramBtn").disabled = true; $("paramBtn").textContent = "Wird berechnet …";
  try { const v = await post(`api/projekte/${project.id}/parameter`, { version: version.n, werte }); await refresh(); toast(v.zusammenfassung); }
  catch (e) { toast(e.message); }
  $("paramBtn").disabled = false; $("paramBtn").textContent = "Neu berechnen";
};

// measurements and photos
function renderMeasures() {
  $("masse").innerHTML = project.masse.map((m, i) => `<div class="measure"><span><b>${esc(m.name)}</b>: ${fmt(m.wert_mm)} mm <span class="muted">${esc(m.quelle || "")}</span></span>
    <button class="small ghost" data-del="${i}">✕</button></div>`).join("") || '<p class="muted">Noch keine Maße.</p>';
  $("masse").querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => { await api(`api/projekte/${project.id}/masse/${b.dataset.del}`, { method: "DELETE" }); refresh(true); }));
}
async function addMeasure(name, mm, quelle) {
  await post(`api/projekte/${project.id}/masse`, { name, wert_mm: mm, quelle }); await refresh(true); toast(`${name}: ${fmt(mm)} mm gespeichert`);
}
$("mAdd").onclick = async () => {
  const name = $("mName").value.trim(), val = parseFloat($("mVal").value);
  if (!name || !(val > 0)) return toast("Name und Maß in mm");
  await addMeasure(name, val, "eingegeben"); $("mName").value = ""; $("mVal").value = "";
};
function refQuery() {
  const ref = $("refSel").value;
  if (ref !== "eigen") return `referenz=${ref}`;
  const dims = prompt("Größe der Referenz in mm, z. B. 100 x 150", "100 x 150") || "";
  const m = dims.match(/([\d.,]+)\D+([\d.,]+)/);
  if (!m) throw new Error("Bitte Breite x Höhe in mm");
  return `breite=${m[1].replace(",", ".")}&hoehe=${m[2].replace(",", ".")}`;
}
$("photoIn").onchange = async () => {
  const file = $("photoIn").files[0]; $("photoIn").value = "";
  if (!file) return;
  let q; try { q = refQuery(); } catch (e) { return toast(e.message); }
  $("photoBox").innerHTML = '<p class="muted">⏳ Wird vermessen …</p>';
  try {
    const r = await fetch(`api/fotos?${q}&projekt=${project.id}`, { method: "POST", body: file });
    const data = await r.json();
    if (!r.ok) { if (data.ecken_noetig) return pickCorners(data.foto, data.error, q); throw new Error(data.error); }
    showMeasured(data);
  } catch (e) { $("photoBox").innerHTML = `<p class="warn">${esc(e.message)}</p>`; }
};
function pickCorners(fid, message, q) {
  const pts = [];
  $("photoBox").innerHTML = `<p class="warn">${esc(message)}</p><p><b>Tippe die 4 Ecken der Referenz an</b> (Reihenfolge egal).</p>
    <div class="photo"><img id="cornerImg" src="api/fotos/${fid}/original.jpg"><svg id="cornerSvg"></svg></div>`;
  const img = $("cornerImg");
  img.onclick = async (e) => {
    const r = img.getBoundingClientRect();
    pts.push([(e.clientX - r.left) * img.naturalWidth / r.width, (e.clientY - r.top) * img.naturalHeight / r.height]);
    $("cornerSvg").innerHTML += `<circle cx="${(e.clientX - r.left) / r.width * 100}%" cy="${(e.clientY - r.top) / r.height * 100}%" r="7" fill="#2e7d4f"/>`;
    if (pts.length === 4) {
      const params = Object.fromEntries(new URLSearchParams(q));
      try { showMeasured(await post(`api/fotos/${fid}/ecken`, { ecken: pts, ...params })); } catch (err) { toast(err.message); }
    }
  };
}
function showMeasured(d) {
  const o = d.objekt;
  $("photoBox").innerHTML = `<p>${o ? `Gegenstand (${esc(o.lage)}): <b>${fmt(o.laenge_mm)} × ${fmt(o.breite_mm)} mm</b>
      <button class="small" id="takeL">Länge übernehmen</button> <button class="small" id="takeB">Breite übernehmen</button>` : "Kein Gegenstand erkannt – miss selbst:"}</p>
    <p class="muted">Zum Messen zwei Punkte im Bild antippen. ${esc(d.hinweis)}</p>
    <div class="photo"><img id="measImg" src="api/fotos/${d.id}/entzerrt.jpg?${Date.now()}"><svg id="measSvg"></svg></div><div id="measOut"></div>`;
  if (o) {
    $("takeL").onclick = () => addMeasure(prompt("Name für dieses Maß", "Länge Gegenstand") || "Länge", o.laenge_mm, `Foto (${d.referenz})`);
    $("takeB").onclick = () => addMeasure(prompt("Name für dieses Maß", "Breite Gegenstand") || "Breite", o.breite_mm, `Foto (${d.referenz})`);
  }
  let first = null;
  const img = $("measImg");
  img.onclick = (e) => {
    const r = img.getBoundingClientRect();
    const px = [(e.clientX - r.left) * img.naturalWidth / r.width, (e.clientY - r.top) * img.naturalHeight / r.height];
    const pct = [(e.clientX - r.left) / r.width * 100, (e.clientY - r.top) / r.height * 100];
    const svg = $("measSvg");
    if (!first) { first = { px, pct }; svg.innerHTML = `<circle cx="${pct[0]}%" cy="${pct[1]}%" r="6" fill="#ea580c"/>`; return; }
    const mm = Math.hypot(px[0] - first.px[0], px[1] - first.px[1]) / d.px_pro_mm;
    svg.innerHTML += `<line x1="${first.pct[0]}%" y1="${first.pct[1]}%" x2="${pct[0]}%" y2="${pct[1]}%" stroke="#ea580c" stroke-width="3"/><circle cx="${pct[0]}%" cy="${pct[1]}%" r="6" fill="#ea580c"/>`;
    $("measOut").innerHTML = `<div class="row"><b>${fmt(mm)} mm</b><input id="mpName" placeholder="Name, z. B. Lochabstand"><button class="small" id="mpAdd">Übernehmen</button></div>`;
    $("mpAdd").onclick = () => addMeasure($("mpName").value.trim() || "Maß aus Foto", Math.round(mm * 10) / 10, `Foto (${d.referenz})`);
    first = null;
  };
}

// details
function renderDetails() {
  const v = version;
  $("details").innerHTML = v ? `<h3>Version ${v.n}</h3><div class="muted">${esc(v.erstellt.slice(0, 16).replace("T", " "))} · von ${esc(v.von)}${v.notiz ? " · " + esc(v.notiz) : ""}</div>
    ${v.teile.map((t) => `<div class="measure"><span><b>${esc(t.name)}</b>: ${t.groesse_mm.map(fmt).join(" × ")} mm, ${fmt(t.gewicht_g)} g</span>
      <span class="${t.warnungen.length ? "warn" : "ok"}">${t.warnungen.length ? "⚠️" : "✓"}</span></div>
      ${t.warnungen.map((w) => `<div class="warn">• ${esc(w)}</div>`).join("")}`).join("")}` : '<p class="muted">Noch keine Version.</p>';
  $("versions").innerHTML = project.versionen.slice().reverse().map((x) => `<div class="ver ${x.n === v?.n ? "on" : ""}" data-n="${x.n}">
    Version ${x.n} · ${esc(x.von)} · ${esc(x.erstellt.slice(5, 16).replace("T", " "))}<div class="muted">${esc(x.notiz || "")}</div></div>`).join("");
  $("versions").querySelectorAll(".ver").forEach((el) => (el.onclick = () => { version = pickVersion(+el.dataset.n); render(); }));
  if (v) fetch(`api/projekte/${project.id}/v/${v.n}/skript.py`).then((r) => r.text()).then((t) => ($("script").textContent = t));
  else $("script").textContent = "";
}
$("delBtn").onclick = async () => {
  if (!confirm(`„${project.name}“ mit allen Versionen löschen?`)) return;
  await api(`api/projekte/${project.id}`, { method: "DELETE" }); showStart();
};
document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll("[data-pane]").forEach((p) => (p.hidden = p.dataset.pane !== b.dataset.tab));
}));

// ---------- phone and printer ----------
$("sendBtn").onclick = async () => {
  try { const r = await post(`api/projekte/${project.id}/zeigen`, { version: version.n }); toast(r.gesendet ? "Vorschau ist unterwegs aufs Handy" : "Senden fehlgeschlagen (Master/iMessage)"); }
  catch (e) { toast(e.message); }
};
$("printBtn").onclick = async () => {
  const material = prompt("Material (PLA, PETG, ABS, ASA, TPU)?", version.material || "PLA");
  if (!material) return;
  $("printBtn").disabled = true;
  try {
    const r = await post(`api/projekte/${project.id}/drucken`, { version: version.n, material: material.toUpperCase() });
    toast(`Bereit: ${r.zeit}, ${r.gewicht_g} g – Bild ist aufs Handy unterwegs. Bestätigen hier oder per iMessage mit „Ja“.`);
    await refresh(true);
  } catch (e) { toast(e.message); }
  $("printBtn").disabled = false;
};
function renderPending(d) {
  const b = $("printBanner");
  if (!d) { b.hidden = true; return; }
  b.hidden = false;
  b.innerHTML = `🖨️ <b>${esc(d.name)}</b> (Version ${d.version}) wartet auf Bestätigung: ${esc(d.zeit || "?")}, ca. ${esc(d.gewicht_g ?? "?")} g ${esc(d.material)}
    ${d.warnung ? `<span class="warn">⚠️ ${esc(d.warnung)}</span>` : ""}<span class="grow"></span>
    <button id="pOk">Jetzt drucken</button><button class="ghost" id="pNo">Abbrechen</button>`;
  $("pOk").onclick = async () => {
    if (!confirm("Ist die Druckplatte frei? Druck jetzt starten?")) return;
    try { await post("api/druck/bestaetigen"); toast("Druck gestartet"); } catch (e) { toast(e.message); }
    project ? refresh(true) : pollPending();
  };
  $("pNo").onclick = async () => { await post("api/druck/abbrechen"); project ? refresh(true) : pollPending(); };
}
async function pollPending() { if (!project) renderPending(await api("api/druck").catch(() => null)); }

// ---------- start ----------
const start = location.hash.slice(1);
if (start) openProject(start).catch(showStart); else showStart();
