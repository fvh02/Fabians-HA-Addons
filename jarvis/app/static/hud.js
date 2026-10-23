import { TOKEN, url, post, listen, Recorder } from "./common.js";

const $ = (id) => document.getElementById(id);
const canvas = $("bg"), g = canvas.getContext("2d");
let W = 0, H = 0, DPR = 1;
function resize() { DPR = Math.min(devicePixelRatio || 1, 2); W = innerWidth; H = innerHeight; canvas.width = W * DPR; canvas.height = H * DPR; g.setTransform(DPR, 0, 0, DPR, 0, 0); }
addEventListener("resize", resize); resize();

let state = { modus: "bereit" };
let level = 0, audioLevel = 0;      // microphone and voice level for the animation
let spin = 0, energy = 0.2;

// ---------- the reactor ----------
const COLORS = { normal: [69, 230, 255], warn: [255, 156, 69] };
function col(a, warn) { const c = warn ? COLORS.warn : COLORS.normal; return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }
const particles = Array.from({ length: 70 }, () => ({ a: Math.random() * Math.PI * 2, r: 0.35 + Math.random() * 0.75, s: (Math.random() - .5) * 0.004, z: Math.random() }));

function draw(t) {
  const mode = state.modus, warn = mode === "fehler" || !!state.fehler && mode === "bereit" && false;
  const target = { bereit: 0.25, hoert: 0.55 + level * 1.4, versteht: 0.8, denkt: 1.0, spricht: 0.5 + audioLevel * 1.6 }[mode] ?? 0.25;
  energy += (target - energy) * 0.08;
  spin += 0.002 + energy * 0.02;
  g.clearRect(0, 0, W, H);
  const cx = W / 2, cy = H * 0.42, R = Math.min(W, H) * 0.2;

  // faint grid
  g.strokeStyle = col(0.05); g.lineWidth = 1;
  for (let x = (cx % 60); x < W; x += 60) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
  for (let y = (cy % 60); y < H; y += 60) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }

  // glow
  const glow = g.createRadialGradient(cx, cy, R * 0.1, cx, cy, R * 2.2);
  glow.addColorStop(0, col(0.18 + energy * 0.2, warn)); glow.addColorStop(1, col(0, warn));
  g.fillStyle = glow; g.beginPath(); g.arc(cx, cy, R * 2.2, 0, Math.PI * 2); g.fill();

  g.save(); g.translate(cx, cy);
  // outer tick ring
  for (let i = 0; i < 120; i++) {
    const a = i / 120 * Math.PI * 2 + spin * 0.2, long = i % 10 === 0;
    g.strokeStyle = col(long ? 0.7 : 0.25, warn); g.lineWidth = long ? 2 : 1;
    g.beginPath(); g.moveTo(Math.cos(a) * R * 1.28, Math.sin(a) * R * 1.28); g.lineTo(Math.cos(a) * R * (long ? 1.38 : 1.33), Math.sin(a) * R * (long ? 1.38 : 1.33)); g.stroke();
  }
  // rotating segment rings
  const rings = [[1.18, 6, 0.6, 1], [1.02, 3, 1.2, -1.4], [0.86, 12, 0.25, 2.2], [0.7, 4, 0.9, -3]];
  rings.forEach(([rr, n, len, sp], k) => {
    g.lineWidth = k === 0 ? 3 : 2; g.strokeStyle = col(0.35 + energy * 0.5, warn);
    for (let i = 0; i < n; i++) {
      const a0 = spin * sp + i / n * Math.PI * 2;
      g.beginPath(); g.arc(0, 0, R * rr, a0, a0 + (Math.PI * 2 / n) * len); g.stroke();
    }
  });
  // voice / mic bars around the core
  if (mode === "spricht" || mode === "hoert") {
    const lv = mode === "spricht" ? audioLevel : level;
    for (let i = 0; i < 64; i++) {
      const a = i / 64 * Math.PI * 2, h = R * (0.05 + lv * (0.25 + 0.2 * Math.sin(t / 90 + i * 1.7)));
      g.strokeStyle = col(0.8, warn); g.lineWidth = 2;
      g.beginPath(); g.moveTo(Math.cos(a) * R * 0.52, Math.sin(a) * R * 0.52); g.lineTo(Math.cos(a) * (R * 0.52 + h), Math.sin(a) * (R * 0.52 + h)); g.stroke();
    }
  }
  // thinking: orbiting dots
  if (mode === "denkt" || mode === "versteht") {
    for (let i = 0; i < 3; i++) {
      const a = t / 300 + i * 2.1;
      g.fillStyle = col(0.9, warn); g.beginPath(); g.arc(Math.cos(a) * R * 0.95, Math.sin(a) * R * 0.95, 4, 0, Math.PI * 2); g.fill();
    }
  }
  // core
  const pulse = 1 + Math.sin(t / 400) * 0.04 + energy * 0.08;
  const core = g.createRadialGradient(0, 0, 0, 0, 0, R * 0.45 * pulse);
  core.addColorStop(0, "rgba(230,255,255,0.95)"); core.addColorStop(0.35, col(0.75, warn)); core.addColorStop(1, col(0, warn));
  g.fillStyle = core; g.beginPath(); g.arc(0, 0, R * 0.45 * pulse, 0, Math.PI * 2); g.fill();
  g.strokeStyle = col(0.9, warn); g.lineWidth = 2; g.beginPath(); g.arc(0, 0, R * 0.5, 0, Math.PI * 2); g.stroke();
  // triangle like the arc reactor
  g.strokeStyle = col(0.55, warn); g.lineWidth = 3; g.beginPath();
  for (let i = 0; i <= 3; i++) { const a = -Math.PI / 2 + i * Math.PI * 2 / 3 + spin * 0.3; g[i ? "lineTo" : "moveTo"](Math.cos(a) * R * 0.3, Math.sin(a) * R * 0.3); }
  g.stroke();
  // particles
  particles.forEach((p) => {
    p.a += p.s * (1 + energy * 4);
    const r = R * (1.4 + p.r * 1.6);
    g.fillStyle = col(0.15 + p.z * 0.4, warn);
    g.fillRect(Math.cos(p.a) * r, Math.sin(p.a) * r * 0.62, 1.5 + p.z * 1.5, 1.5 + p.z * 1.5);
  });
  g.restore();
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

// ---------- clock ----------
function clock() {
  const d = new Date();
  $("clock").textContent = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  $("date").textContent = d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
}
clock(); setInterval(clock, 10000);

// ---------- speaking ----------
let audio = null, audioCtx = null, typing = null;
function stopAudio() { if (audio) { audio.pause(); audio = null; } audioLevel = 0; }
async function play(src) {
  stopAudio();
  audio = new Audio(url(src));
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const an = audioCtx.createAnalyser(); an.fftSize = 256;
    audioCtx.createMediaElementSource(audio).connect(an); an.connect(audioCtx.destination);
    const buf = new Uint8Array(an.frequencyBinCount), me = audio;
    const tick = () => { if (audio !== me) return; an.getByteTimeDomainData(buf); let m = 0; for (const v of buf) m = Math.max(m, Math.abs(v - 128)); audioLevel = audioLevel * 0.6 + (m / 128) * 0.4; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  } catch (e) { /* plays without meter */ }
  try { await audio.play(); }
  catch (e) {           // a normal browser needs one click before it may play sound
    $("unlock").hidden = false;
    $("unlock").onclick = () => { $("unlock").hidden = true; audioCtx?.resume(); audio?.play(); };
  }
}
function typeOut(text, seconds) {
  clearInterval(typing);
  const el = $("answer"); el.textContent = "";
  if (!text) return;
  const step = Math.max(12, Math.min(60, (seconds ? seconds * 1000 * 0.92 : 1500) / text.length));
  let i = 0;
  typing = setInterval(() => {
    i += 1; el.innerHTML = escapeHtml(text.slice(0, i)) + (i < text.length ? '<span class="cursor">▍</span>' : "");
    if (i >= text.length) clearInterval(typing);
  }, step);
}
const escapeHtml = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// ---------- state from the server ----------
let lastAudio = "", lastAnswer = "";
const STATUS = { bereit: "Bereit", hoert: "Ich höre …", versteht: "Verstehe …", denkt: "Analysiere …", spricht: "Antworte", fehler: "Störung" };
function show(s) {
  state = s;
  document.body.classList.toggle("fehler", !!s.fehler && s.modus !== "denkt");
  $("status").textContent = `${STATUS[s.modus] || s.modus} · Assistent ${s.assistent === "fehler" ? "nicht erreichbar" : "online"}`;
  $("question").textContent = s.frage || "";
  if (s.modus === "denkt" || s.modus === "versteht" || s.modus === "hoert") { clearInterval(typing); $("answer").textContent = s.modus === "denkt" ? "" : $("answer").textContent; }
  if (s.antwort && s.antwort !== lastAnswer) { lastAnswer = s.antwort; typeOut(s.antwort, s.dauer); }
  if (!s.antwort) lastAnswer = "";
  if (s.audio && s.audio !== lastAudio && s.modus === "spricht") { lastAudio = s.audio; play(s.audio); }
  $("actions").innerHTML = (s.aktionen || []).map((a) => `<div>${escapeHtml(String(a))}</div>`).join("");
  $("history").innerHTML = (s.verlauf || []).slice(1, 4).map((v) => `<div class="q">${escapeHtml(v.frage)}</div><div class="a">${escapeHtml(v.antwort)}</div>`).join("");
}
let noteTimer = null;
function note(text) { $("note").textContent = text; $("note").hidden = false; clearTimeout(noteTimer); noteTimer = setTimeout(() => ($("note").hidden = true), 4000); }
listen((e) => {
  if (e.typ === "zustand") show(e);
  else if (e.typ === "stopp") stopAudio();
  else if (e.typ === "hinweis") note(e.text);
}, (ok) => { if (!ok) $("status").textContent = "Verbindung zu Jarvis unterbrochen …"; });

// ---------- talking from the projector ----------
const recorder = new Recorder((on) => { level = 0; });
recorder.onError = (e) => note(e.message);
setInterval(() => { if (recorder.active) level = recorder.level; }, 50);
addEventListener("keydown", async (e) => {
  if (["Enter", " ", "MediaPlayPause"].includes(e.key) || e.keyCode === 23 || e.keyCode === 66) {
    e.preventDefault();
    if (state.modus === "spricht") { post("api/stopp").catch(() => {}); stopAudio(); return; }
    try { await recorder.start("beamer"); } catch (err) { note(err.message); }
  } else if (e.key === "Escape" || e.key === "Backspace") {
    if (recorder.active) recorder.stop(); else { post("api/stopp").catch(() => {}); stopAudio(); }
  }
});
if (!TOKEN && location.pathname.endsWith("/hud")) $("hint").textContent = "Vorschau in Home Assistant · OK/Leertaste zum Sprechen";
