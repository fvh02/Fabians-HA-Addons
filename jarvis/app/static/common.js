// Shared by HUD and remote: token from the URL (projector app / LAN) or none (Home Assistant ingress).
export const TOKEN = new URLSearchParams(location.search).get("t") || "";
export const url = (path) => path + (TOKEN ? (path.includes("?") ? "&" : "?") + "t=" + encodeURIComponent(TOKEN) : "");

export async function post(path, body, raw = null, type = "application/json") {
  const r = await fetch(url(path), { method: "POST", headers: { "Content-Type": type }, body: raw ?? JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Fehler ${r.status}`);
  return data;
}

// Live events with automatic reconnect.
export function listen(onEvent, onStatus) {
  let es = null, retry = null;
  const open = () => {
    es = new EventSource(url("api/ereignisse"));
    es.onopen = () => onStatus?.(true);
    es.onmessage = (e) => { try { onEvent(JSON.parse(e.data)); } catch (err) { console.warn(err); } };
    es.onerror = () => { onStatus?.(false); es.close(); clearTimeout(retry); retry = setTimeout(open, 3000); };
  };
  open();
}

// Recording: tap to start, tap again (or 20 s) to stop; the recording goes to the server.
// In the projector app the app records natively (browsers only allow the microphone over HTTPS).
export class Recorder {
  constructor(onState) {
    this.onState = onState; this.rec = null; this.timer = null; this.level = 0; this.native = false;
    window.jarvisRecording = (on) => { this.native = !!on; this.onState?.(!!on); if (!on) this.level = 0; };
    window.jarvisLevel = (v) => { this.level = v; };
    window.jarvisError = (msg) => this.onError?.(new Error(msg));
  }
  get active() { return !!this.rec || this.native; }
  async start(source) {
    if (window.JarvisApp) {                    // Android app on the projector
      if (this.native) { window.JarvisApp.stopRecording(); return; }
      window.JarvisApp.startRecording(source);
      return;
    }
    if (this.rec) return this.stop();
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      throw new Error("Mikrofon geht hier nur über HTTPS – nutze die Diktier-Taste 🎤 deiner Tastatur im Textfeld");
    }
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
    catch (e) { throw new Error("Kein Zugriff aufs Mikrofon – sonst die Diktier-Taste 🎤 der Tastatur nutzen"); }
    const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"].find((t) => MediaRecorder.isTypeSupported(t)) || "";
    const rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    const chunks = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    try {                                      // level meter for the animation
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const an = ctx.createAnalyser(); an.fftSize = 256;
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      const tick = () => { if (!this.rec) { ctx.close(); return; } an.getByteTimeDomainData(buf); let m = 0; for (const v of buf) m = Math.max(m, Math.abs(v - 128)); this.level = m / 128; requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    } catch (e) { /* no meter */ }
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      this.rec = null; clearTimeout(this.timer); this.onState?.(false);
      post("api/hoert", { an: false }).catch(() => {});
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      if (blob.size > 1500) post(`api/sprache?quelle=${source}`, null, blob, blob.type || "audio/webm").catch((e) => this.onError?.(e));
    };
    this.rec = rec; rec.start(); this.onState?.(true);
    post("api/hoert", { an: true }).catch(() => {});
    this.timer = setTimeout(() => this.stop(), 20000);
  }
  stop() {
    if (window.JarvisApp && this.native) { window.JarvisApp.stopRecording(); return; }
    if (this.rec && this.rec.state !== "inactive") this.rec.stop();
  }
}
