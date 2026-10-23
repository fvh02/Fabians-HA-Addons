import * as THREE from "three";
import { OrbitControls } from "./orbit-controls.js";

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const NEEDS = { durst: ["Durst", "#3b82f6"], hunger: ["Hunger", "#f59e0b"], muedigkeit: ["Müdigkeit", "#8b5cf6"],
                langeweile: ["Langeweile", "#ef4444"], neugier: ["Neugier", "#10b981"] };
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Fehler ${r.status}`);
  return data;
}
const post = (path, body, method = "POST") => api(path, { method, body: JSON.stringify(body || {}) });
function toast(text) {
  const t = $("toast"); t.textContent = text; t.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => (t.hidden = true), 3500);
}
const fmtTime = (iso) => (iso || "").slice(0, 16).replace("T", " ");

// ---------- scene ----------
let world = { size: 32, version: -1, types: [], buildings: [] };
let state = null;
const types = () => Object.fromEntries(world.types.map((t) => [t.id, t]));
const half = () => world.size / 2;

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
$("scene").appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
camera.position.set(0, 21, 25);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 0);
controls.maxPolarAngle = Math.PI * 0.46;
controls.minDistance = 6; controls.maxDistance = 90;
controls.enableDamping = true;

const hemi = new THREE.HemisphereLight(0xffffff, 0x557755, 0.9);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xffffff, 1.2);
sun.position.set(20, 35, 15); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30 });
scene.add(sun);

let ground, grid;
function buildGround() {
  if (ground) scene.remove(ground, grid);
  ground = new THREE.Mesh(new THREE.PlaneGeometry(world.size, world.size), new THREE.MeshLambertMaterial({ color: 0x8cc66d }));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; ground.name = "ground";
  grid = new THREE.GridHelper(world.size, world.size, 0x5f9a48, 0x5f9a48);
  grid.material.transparent = true; grid.material.opacity = 0.5; grid.position.y = 0.01;
  scene.add(ground, grid);
}

function resize() {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
}
addEventListener("resize", resize); resize();

function dayLight() {
  const h = new Date().getHours() + new Date().getMinutes() / 60;
  const day = Math.max(0, Math.min(1, Math.sin(((h - 5) / 16) * Math.PI) * 1.4));   // light from about 5 to 21 o'clock
  scene.background = new THREE.Color().lerpColors(new THREE.Color(0x1c2340), new THREE.Color(0xbfe3f2), day);
  sun.intensity = 0.25 + day * 1.0; hemi.intensity = 0.35 + day * 0.6;
}

// ---------- building meshes ----------
function partMesh(p) {
  const [sx, sy, sz] = p.size;
  let geo;
  if (p.shape === "box") geo = new THREE.BoxGeometry(sx, sy, sz);
  else if (p.shape === "cylinder") geo = new THREE.CylinderGeometry(0.5, 0.5, 1, 20);
  else if (p.shape === "cone") geo = new THREE.ConeGeometry(0.5, 1, 20);
  else geo = new THREE.SphereGeometry(0.5, 20, 14);
  const m = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: p.color }));
  if (p.shape !== "box") m.scale.set(sx, sy, sz);
  m.position.set(p.pos[0], p.pos[1], p.pos[2]);
  m.rotation.y = ((p.rot || 0) * Math.PI) / 180;
  m.castShadow = true; m.receiveShadow = true;
  return m;
}
function typeMesh(t) {
  const g = new THREE.Group();
  for (const p of t.parts) g.add(partMesh(p));
  return g;
}
function footprint(t, rot) { const [w, d] = t.size; return rot === 90 || rot === 270 ? [d, w] : [w, d]; }
function placeGroup(g, t, x, z, rot) {
  const [w, d] = footprint(t, rot);
  g.position.set(x + w / 2 - half(), 0, z + d / 2 - half());
  g.rotation.y = (rot * Math.PI) / 180;
}

const buildingGroups = new Map();
function buildWorld() {
  for (const g of buildingGroups.values()) scene.remove(g);
  buildingGroups.clear();
  const T = types();
  for (const b of world.buildings) {
    const t = T[b.type]; if (!t) continue;
    const g = typeMesh(t);
    placeGroup(g, t, b.x, b.z, b.rot);
    g.userData.building = b;
    g.traverse((o) => (o.userData.building = b));
    scene.add(g); buildingGroups.set(b.id, g);
  }
  renderPalette();
}

// ---------- Pino ----------
const pino = new THREE.Group();
(function buildPino() {
  const brown = new THREE.MeshLambertMaterial({ color: 0x7a5230 });
  const beakMat = new THREE.MeshLambertMaterial({ color: 0xe8d8a8 });
  const legMat = new THREE.MeshLambertMaterial({ color: 0xcfa86a });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.5, 24, 16), brown);
  body.scale.set(0.62, 0.5, 0.75); body.position.y = 0.42; body.castShadow = true;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.17, 16, 12), brown);
  head.position.set(0, 0.6, 0.33);
  const beak = new THREE.Mesh(new THREE.ConeGeometry(0.035, 0.45, 10), beakMat);
  beak.rotation.x = Math.PI / 2 + 0.35; beak.position.set(0, 0.52, 0.62);
  const eyeMat = new THREE.MeshBasicMaterial({ color: 0x111111 });
  for (const s of [-1, 1]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.025, 8, 6), eyeMat);
    eye.position.set(0.09 * s, 0.65, 0.45); pino.add(eye);
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.22, 6), legMat);
    leg.position.set(0.1 * s, 0.1, 0.02); leg.name = s < 0 ? "legL" : "legR"; pino.add(leg);
  }
  pino.add(body, head, beak);
  pino.scale.setScalar(1.8);
  scene.add(pino);
})();

function pathLength(path) { let l = 0; for (let i = 1; i < path.length; i++) l += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]); return l; }
function pinoPosition(now) {
  const p = state?.pino; if (!p) return null;
  if (p.mode === "walking" && p.path) {
    let dist = Math.max(0, (now - p.path_start) * p.speed);
    for (let i = 1; i < p.path.length; i++) {
      const a = p.path[i - 1], b = p.path[i], seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (dist <= seg) { const t = seg ? dist / seg : 1; return { x: a[0] + (b[0] - a[0]) * t, z: a[1] + (b[1] - a[1]) * t, dir: Math.atan2(b[0] - a[0], b[1] - a[1]), walking: true }; }
      dist -= seg;
    }
    const last = p.path[p.path.length - 1]; return { x: last[0], z: last[1], walking: false };
  }
  return { x: p.cell[0], z: p.cell[1], walking: false };
}
let serverOffset = 0;   // server time − browser time
let lastDir = 0;
function animatePino() {
  const p = state?.pino;
  if (!p) { pino.visible = false; return; }
  const now = Date.now() / 1000 + serverOffset;
  const pos = pinoPosition(now);
  pino.visible = p.mode !== "inside";
  if (pos) {
    const tx = pos.x + 0.5 - half(), tz = pos.z + 0.5 - half();
    pino.position.x += (tx - pino.position.x) * 0.35; pino.position.z += (tz - pino.position.z) * 0.35;
    if (pos.dir !== undefined) lastDir = pos.dir;
    let diff = lastDir - pino.rotation.y; diff = Math.atan2(Math.sin(diff), Math.cos(diff));
    pino.rotation.y += diff * 0.2;
    const t = performance.now() / 1000;
    pino.position.y = pos.walking ? Math.abs(Math.sin(t * 9)) * 0.06 : (p.mode === "dozing" ? 0 : Math.sin(t * 2) * 0.01);
    pino.getObjectByName("legL").rotation.x = pos.walking ? Math.sin(t * 9) * 0.6 : 0;
    pino.getObjectByName("legR").rotation.x = pos.walking ? -Math.sin(t * 9) * 0.6 : 0;
  }
  // thought bubble above his head
  const bubble = $("bubble");
  if (pino.visible && p.thought) {
    const v = pino.position.clone(); v.y += 1.6; v.project(camera);
    if (v.z < 1) {
      bubble.style.left = `${(v.x * 0.5 + 0.5) * innerWidth}px`;
      bubble.style.top = `${(-v.y * 0.5 + 0.5) * innerHeight}px`;
      const text = p.mode === "dozing" ? "Zzz …" : p.thought;
      if (bubble.textContent !== text) bubble.textContent = text.length > 110 ? text.slice(0, 108) + " …" : text;
      bubble.hidden = false;
    } else bubble.hidden = true;
  } else bubble.hidden = true;
}

// ---------- placing ----------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let placing = null;   // {type, rot, x, z, moving: building id|null, ghost}
function cellAt(ev) {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObject(ground)[0];
  if (!hit) return null;
  return { x: Math.floor(hit.point.x + half()), z: Math.floor(hit.point.z + half()) };
}
function occupied(ignore) {
  const T = types(), cells = new Set(), doors = new Set();
  for (const b of world.buildings) {
    if (b.id === ignore) continue;
    const t = T[b.type]; if (!t) continue;
    const [w, d] = footprint(t, b.rot);
    for (let i = 0; i < w; i++) for (let j = 0; j < d; j++) cells.add(`${b.x + i},${b.z + j}`);
    if (b.door) doors.add(`${b.door[0]},${b.door[1]}`);
  }
  return { cells, doors };
}
function doorOf(t, x, z, rot) {
  if (t.decor) return null;
  const [w, d] = footprint(t, rot);
  return { 0: [x + Math.floor(w / 2), z + d], 180: [x + Math.floor(w / 2), z - 1], 90: [x + w, z + Math.floor(d / 2)], 270: [x - 1, z + Math.floor(d / 2)] }[rot];
}
function validPlace() {
  const t = types()[placing.type], [w, d] = footprint(t, placing.rot), { x, z } = placing, S = world.size;
  if (x < 0 || z < 0 || x + w > S || z + d > S) return "Passt nicht in die Welt";
  const { cells, doors } = occupied(placing.moving);
  for (let i = 0; i < w; i++) for (let j = 0; j < d; j++) {
    if (cells.has(`${x + i},${z + j}`)) return "Dort steht schon etwas";
    if (doors.has(`${x + i},${z + j}`)) return "Versperrt eine Tür";
  }
  const door = doorOf(t, x, z, placing.rot);
  if (door && (door[0] < 0 || door[1] < 0 || door[0] >= S || door[1] >= S)) return "Tür zeigt aus der Welt – drehen";
  if (door && cells.has(`${door[0]},${door[1]}`)) return "Vor der Tür steht etwas – drehen";
  return "";
}
function updateGhost() {
  if (!placing) return;
  const t = types()[placing.type];
  placeGroup(placing.ghost, t, placing.x, placing.z, placing.rot);
  const problem = validPlace();
  placing.ghost.traverse((o) => { if (o.material) { o.material.transparent = true; o.material.opacity = 0.6; o.material.emissive?.set(problem ? 0x660000 : 0x004400); } });
  $("placeMsg").textContent = problem || (placing.moving ? "Hier hin verschieben?" : "Hier bauen?");
  $("okBtn").disabled = !!problem;
}
function startPlacing(typeId, moving = null) {
  cancelPlacing();
  const t = types()[typeId]; if (!t) return;
  const ghost = typeMesh(t);
  ghost.traverse((o) => { if (o.material) o.material = o.material.clone(); });
  const b = moving ? world.buildings.find((x) => x.id === moving) : null;
  placing = { type: typeId, rot: b ? b.rot : 0, x: b ? b.x : Math.floor(half()) - 1, z: b ? b.z : Math.floor(half()) - 1, moving, ghost };
  if (b) buildingGroups.get(b.id).visible = false;
  scene.add(ghost);
  $("placeName").textContent = `${t.emoji} ${t.name}`;
  $("okBtn").textContent = moving ? "✓ Hier hin" : "✓ Hier bauen";
  $("placeBar").hidden = false; $("info").hidden = true;
  updateGhost(); renderPalette();
}
function cancelPlacing() {
  if (!placing) return;
  scene.remove(placing.ghost);
  if (placing.moving) { const g = buildingGroups.get(placing.moving); if (g) g.visible = true; }
  placing = null; $("placeBar").hidden = true; renderPalette();
}
async function confirmPlacing() {
  if (!placing || validPlace()) return;
  const { type, x, z, rot, moving } = placing;
  try {
    if (moving) await post(`api/buildings/${moving}`, { x, z, rot });
    else await post("api/buildings", { type, x, z, rot });
    const keep = !moving ? type : null;
    cancelPlacing(); await loadWorld(true);
    if (keep && !matchMedia("(max-width: 760px)").matches) startPlacing(keep);   // place several in a row on a PC
  } catch (e) { toast(e.message); }
}
$("rotBtn").onclick = () => { if (placing) { placing.rot = (placing.rot + 90) % 360; updateGhost(); } };
$("okBtn").onclick = confirmPlacing;
$("cancelBtn").onclick = cancelPlacing;
addEventListener("keydown", (e) => {
  if (e.target.tagName === "TEXTAREA") return;
  if (e.key === "Escape") { cancelPlacing(); $("info").hidden = true; }
  if ((e.key === "r" || e.key === "R") && placing) $("rotBtn").onclick();
});

// pointer: drag = turn the camera, click/tap = place or select
let down = null;
renderer.domElement.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6) return;
  if (placing) {
    const c = cellAt(e); if (!c) return;
    const [w, d] = footprint(types()[placing.type], placing.rot);
    placing.x = c.x - Math.floor(w / 2); placing.z = c.z - Math.floor(d / 2); updateGhost();
    if (e.pointerType === "mouse") confirmPlacing();
    return;
  }
  const r = renderer.domElement.getBoundingClientRect();
  pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects([...buildingGroups.values()], true)[0];
  if (hit) showInfo(hit.object.userData.building.id); else $("info").hidden = true;
});
renderer.domElement.addEventListener("pointermove", (e) => {
  if (placing && e.pointerType === "mouse") {
    const c = cellAt(e); if (!c) return;
    const [w, d] = footprint(types()[placing.type], placing.rot);
    placing.x = c.x - Math.floor(w / 2); placing.z = c.z - Math.floor(d / 2); updateGhost();
  }
});

// ---------- info about a building ----------
let infoId = null;
function effectText(eff) {
  return Object.entries(eff || {}).filter(([, v]) => v).map(([n, v]) => `${NEEDS[n]?.[0] || n} ${v > 0 ? "+" : ""}${v}`).join(", ");
}
const ACTION = { keine: "", frei: "erlebt etwas", schlafen: "schläft", tagebuch: "Tagebuch", wikipedia: "Wikipedia", youtube: "YouTube",
                 github: "GitHub", werkstatt: "baut Webseiten (Claude)", malen: "malt" };
function showInfo(id) {
  infoId = id;
  const b = world.buildings.find((x) => x.id === id); if (!b) { $("info").hidden = true; return; }
  const t = types()[b.type]; if (!t) return;
  const p = state?.pino, here = p?.mode === "inside" && p.inside?.building === id ? p.inside : null;
  const now = Date.now() / 1000 + serverOffset;
  let html = `<div class="row"><b>${esc(t.emoji)} ${esc(t.name)}</b><button class="small ghost" id="infoClose">✕</button></div>
    <div class="muted">${esc(t.description)}</div>`;
  if (here) {
    html += `<div class="here"><b>🥝 Pino ist hier:</b> ${esc(here.name)}${here.topic ? ` – Thema: ${esc(here.topic)}` : ""}<br>
      <span class="muted">${here.pending ? "ist noch dabei …" : ""} noch ${Math.max(0, Math.round((here.until - now) / 60))} Min.</span>
      ${here.result ? `<div>${esc(here.result)}</div>` : ""}<div class="thought">„${esc(p.thought)}“</div></div>`;
  }
  if (t.activities.length) html += `<div class="acts">${t.activities.map((a) => `<div><b>${esc(a.name)}</b> · ${a.minutes} Min.
      <span class="muted">${esc(effectText(a.effects))}${ACTION[a.action] ? " · " + ACTION[a.action] : ""}</span></div>`).join("")}</div>`;
  html += `<div class="tools"><button id="mvBtn">✥ Verschieben</button><button id="rtBtn" class="ghost">↻ Drehen</button>
    <button id="rmBtn" class="danger">Entfernen</button></div>`;
  $("info").innerHTML = html; $("info").hidden = false;
  if (matchMedia("(max-width: 760px)").matches) $("panel").classList.add("closed");
  $("infoClose").onclick = () => ($("info").hidden = true);
  $("mvBtn").onclick = () => startPlacing(b.type, b.id);
  $("rtBtn").onclick = async () => {
    try { await post(`api/buildings/${b.id}`, { x: b.x, z: b.z, rot: (b.rot + 90) % 360 }); await loadWorld(true); showInfo(b.id); }
    catch (e) { toast(e.message); }
  };
  $("rmBtn").onclick = async () => {
    if (!confirm(`${t.name} entfernen?`)) return;
    try { await api(`api/buildings/${b.id}`, { method: "DELETE" }); $("info").hidden = true; await loadWorld(true); } catch (e) { toast(e.message); }
  };
}

// ---------- side panel ----------
document.querySelectorAll("#tabs button").forEach((btn) => btn.addEventListener("click", () => {
  const tab = btn.dataset.tab, panel = $("panel");
  if (btn.classList.contains("on") && !panel.classList.contains("closed")) { panel.classList.add("closed"); return; }
  panel.classList.remove("closed");
  if (matchMedia("(max-width: 760px)").matches) $("info").hidden = true;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b === btn));
  document.querySelectorAll("[data-pane]").forEach((p) => (p.hidden = p.dataset.pane !== tab));
  if (tab === "leben") loadLife(); if (tab === "bilder") loadPictures(); if (tab === "seiten") loadSites();
}));
if (matchMedia("(max-width: 760px)").matches) $("panel").classList.add("closed");
$("pinoCard").onclick = () => $("pinoCard").classList.toggle("open");

function renderPalette() {
  const used = new Set(world.buildings.map((b) => b.type));
  $("palette").innerHTML = world.types.map((t) => `<div class="tile ${placing?.type === t.id && !placing.moving ? "on" : ""}" data-type="${t.id}">
      <div class="e">${esc(t.emoji)}</div><div class="n">${esc(t.name)}${t.custom ? '<span class="badge">eigen</span>' : ""}</div>
      <div class="acts">${t.decor ? "Deko" : esc(t.activities.map((a) => a.name).join(", "))}</div>
      ${t.custom ? `<div class="tools"><button class="small ghost" data-edit="${t.id}">Ändern</button>
        ${used.has(t.id) ? "" : `<button class="small ghost" data-del="${t.id}">Löschen</button>`}</div>` : ""}</div>`).join("");
  $("palette").querySelectorAll(".tile").forEach((el) => el.addEventListener("click", (e) => {
    if (e.target.dataset.edit) return editType(e.target.dataset.edit);
    if (e.target.dataset.del) return deleteType(e.target.dataset.del);
    if (placing?.type === el.dataset.type && !placing.moving) cancelPlacing(); else startPlacing(el.dataset.type);
    if (matchMedia("(max-width: 760px)").matches) $("panel").classList.add("closed");
  }));
}
async function editType(id) {
  const t = types()[id];
  const change = prompt(`Was soll sich an „${t.name}“ ändern? (Aussehen oder Funktion)`);
  if (!change) return;
  try { await post("api/types", { request: change, base: id }); toast("Claude baut um …"); } catch (e) { toast(e.message); }
}
async function deleteType(id) {
  if (!confirm(`„${types()[id].name}“ endgültig löschen?`)) return;
  try { await api(`api/types/${id}`, { method: "DELETE" }); await loadWorld(true); } catch (e) { toast(e.message); }
}
$("createBtn").onclick = async () => {
  const request = $("newRequest").value.trim();
  if (request.length < 5) return toast("Beschreib das Gebäude in ein paar Worten");
  try { await post("api/types", { request }); $("newRequest").value = ""; toast("Claude baut das Gebäude – dauert etwa eine Minute"); }
  catch (e) { toast(e.message); }
};
let seenJobs = {};
function renderJobs(jobs) {
  $("jobs").innerHTML = jobs.slice().reverse().map((j) => `<div class="job ${j.status === "fehler" ? "err" : ""}">
    ${j.status === "läuft" ? "⏳" : j.status === "fertig" ? "✅" : "⚠️"} ${esc(j.request.slice(0, 80))}
    ${j.status === "fertig" ? `→ <b>${esc(j.emoji)} ${esc(j.name)}</b>` : ""}${j.error ? `<br>${esc(j.error)}` : ""}</div>`).join("");
  for (const j of jobs) {
    if (seenJobs[j.id] === "läuft" && j.status === "fertig") toast(`${j.emoji} ${j.name} ist fertig – jetzt platzieren!`);
    seenJobs[j.id] = j.status;
  }
}

async function loadLife() {
  const [diary, events, knowledge] = await Promise.all([api("api/pino/tagebuch?n=20"), api("api/pino/erlebnisse?n=40"), api("api/pino/wissen")]);
  $("interests").innerHTML = (state?.pino.interests || []).map((i) => `<span class="chip">${esc(i.thema)} ${Math.round(i.staerke * 100)}%</span>`).join("")
    || '<span class="muted">Noch keine – Pino entdeckt die Welt gerade erst.</span>';
  $("diary").innerHTML = diary.map((d) => `<div class="entry"><div class="when">${esc(d.day)}</div>${esc(d.text)}</div>`).join("") || '<div class="muted">Noch kein Eintrag.</div>';
  $("events").innerHTML = events.map((e) => `<div class="entry"><div class="when">${esc(fmtTime(e.at))}</div>${esc(e.text)}</div>`).join("");
  $("knowledge").innerHTML = Object.entries(knowledge).map(([topic, items]) => `<div class="entry"><b>${esc(topic)}</b>
    ${items.slice(0, 3).map((k) => `<div><span class="muted">${esc(k.quelle)} · <a href="${esc(k.link)}" target="_blank" rel="noopener noreferrer">${esc(k.titel)}</a></span><br>${esc(k.text)}</div>`).join("")}</div>`).join("")
    || '<div class="muted">Noch nichts gelernt.</div>';
}
async function loadPictures() {
  const pics = await api("api/pino/bilder?n=60");
  $("pictures").innerHTML = pics.map((p) => `<figure><img src="bilder/${esc(p.id)}.svg" alt=""><figcaption>${esc(p.title)} · ${esc(fmtTime(p.at))}</figcaption></figure>`).join("")
    || '<p class="muted">Noch keine Bilder – baut ein Atelier!</p>';
}
async function loadSites() {
  const sites = await api("api/pino/webseiten");
  $("sites").innerHTML = sites.map((s) => `<div class="site"><b>${esc(s.title)}</b><div class="muted">${esc(s.description)}</div>
    <div class="muted">Zuletzt: ${esc(s.changes?.[0]?.text || "")} (${esc(fmtTime(s.updated))})</div>
    <button class="small" data-site="${esc(s.slug)}">Ansehen</button></div>`).join("")
    || `<p class="muted">Noch keine Webseiten. Pino baut in der Werkstatt (höchstens ${state?.pino.workshop.limit ?? 3}× am Tag, mit Claude).</p>`;
  $("sites").querySelectorAll("[data-site]").forEach((b) => (b.onclick = () => openSite(b.dataset.site)));
}

// ---------- website viewer (sandboxed, without access to Home Assistant) ----------
let viewerSlug = null;
async function openSite(slug, page = "index.html") {
  try {
    const r = await api(`api/webseiten/${slug}?seite=${encodeURIComponent(page)}`);
    viewerSlug = slug;
    $("viewerTitle").textContent = r.meta.title || slug;
    $("viewerPages").innerHTML = r.pages.map((p) => `<option ${p === r.page ? "selected" : ""}>${esc(p)}</option>`).join("");
    $("viewerFrame").srcdoc = r.html;
    $("viewer").hidden = false;
  } catch (e) { toast(e.message); }
}
$("viewerPages").onchange = () => openSite(viewerSlug, $("viewerPages").value);
$("viewerClose").onclick = () => { $("viewer").hidden = true; $("viewerFrame").srcdoc = ""; };
addEventListener("message", (e) => {
  if (e.source === $("viewerFrame").contentWindow && typeof e.data?.pinoPage === "string" && /^[\w\/.-]+\.html$/.test(e.data.pinoPage)) {
    openSite(viewerSlug, e.data.pinoPage);
  }
});

// ---------- Pino card ----------
function renderCard() {
  const p = state.pino;
  const MODE = { idle: "überlegt", walking: "unterwegs", inside: "drinnen", dozing: "döst" };
  $("mode").textContent = MODE[p.mode] || p.mode;
  let doing = "Steht draußen und überlegt";
  if (p.mode === "inside") doing = `Im ${p.inside.house}: ${p.inside.name}${p.inside.topic ? ` (${p.inside.topic})` : ""}`;
  if (p.mode === "walking") doing = "Ist unterwegs";
  if (p.mode === "dozing") doing = "Döst – sein Gehirn ist nicht erreichbar";
  $("doing").textContent = doing;
  $("thought").textContent = p.thought ? `„${p.thought}“` : "";
  $("needs").innerHTML = Object.entries(NEEDS).map(([k, [name, color]]) => `<div class="need"><span>${name}</span>
    <div class="bar"><i style="width:${p.needs[k]}%;background:${color}"></i></div><span>${p.needs[k]}</span></div>`).join("");
  const w = $("brainWarn");
  if (!p.brain.configured) { w.hidden = false; w.textContent = "⚠️ Kein Gehirn eingetragen: Ollama-Adresse in der Konfiguration des Add-ons setzen."; }
  else if (p.brain.error) { w.hidden = false; w.textContent = `⚠️ ${p.brain.error}`; }
  else w.hidden = true;
}

// ---------- loop ----------
async function loadWorld(force = false) {
  const w = await api("api/world");
  if (!force && w.version === world.version && world.buildings.length) return;
  const firstTime = world.version === -1;
  world = w;
  if (firstTime) buildGround();
  buildWorld();
  if (infoId && !$("info").hidden) showInfo(infoId);
}
async function poll() {
  try {
    const s = await api("api/state");
    serverOffset = s.pino.now - Date.now() / 1000;
    state = s;
    if (s.world_version !== world.version) await loadWorld(true);
    renderCard(); renderJobs(s.jobs);
    if (s.jobs.some((j) => j.status === "fertig" && !types()[j.type])) await loadWorld(true);
    if (infoId && !$("info").hidden && !placing) showInfo(infoId);
  } catch (e) { console.warn(e); }
  setTimeout(poll, 1500);
}
function frame() {
  controls.update(); animatePino(); renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
dayLight(); setInterval(dayLight, 60000);
await loadWorld(true);
poll(); frame();
