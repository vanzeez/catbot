// Voice I/O for the renderer: mic -> 16 kHz mono int16, 100 ms frames over WS /audio.
// Two input modes share one mic pipeline: push-to-talk (sends every frame while held) and the
// "meow" wake word (always on; frames pass a loudness gate with 300 ms pre-roll). Output: TTS
// playback and meow sounds, sequenced so they never overlap; the mic is muted while Catbot makes
// any sound (+0.5 s) so it cannot wake itself. A PTT press stops playback at once (barge-in).
import { meow } from "./meow.js";

const WORKLET = `
class Pcm16k extends AudioWorkletProcessor {
  constructor() { super(); this.ratio = sampleRate / 16000; this.pos = 0; this.buf = []; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    let i = this.pos;
    while (i < ch.length - 1) {
      const i0 = Math.floor(i), f = i - i0;
      this.buf.push(ch[i0] * (1 - f) + ch[i0 + 1] * f); i += this.ratio;
    }
    this.pos = i - (ch.length - 1);
    while (this.buf.length >= 1600) {
      const out = new Int16Array(1600);
      for (let k = 0; k < 1600; k++) out[k] = Math.max(-1, Math.min(1, this.buf[k])) * 32767;
      this.buf.splice(0, 1600);
      this.port.postMessage(out.buffer, [out.buffer]);
    }
    return true;
  }
}
registerProcessor("pcm16k", Pcm16k);`;

const GATE_MIN = 0.012;      // RMS that opens the wake gate (about -38 dBFS)
const HANGOVER = 12;         // frames (1.2 s) kept open after the last loud frame
const PREROLL = 3;           // frames (300 ms) sent from before the gate opened

export class Voice {
  constructor({ url, onTts = () => {}, onLevel = () => {}, onState = () => {}, onWakeAck = () => {},
                onWakeState = () => {} } = {}) {
    this.url = url || `ws://${location.host}/audio`;
    Object.assign(this, { onTts, onLevel, onState, onWakeAck, onWakeState });
    this.ctx = null; this.stream = null; this.node = null; this.src = null;
    this.ws = null; this.talking = false; this.wakeOn = false;
    this.busyUntil = 0;          // ctx time when the last scheduled sound ends
    this.ring = []; this.hang = 0; this.floor = 0.004;
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.binaryType = "arraybuffer";
    this.ws.onopen = () => { this.onState("open"); if (this.wakeOn) this.send({ type: "wake", action: "on" }); };
    this.ws.onclose = () => { this.onState("closed"); setTimeout(() => this.connect(), 1500); };
    this.ws.onmessage = (m) => {
      if (typeof m.data === "string") {
        const d = JSON.parse(m.data);
        if (d.type === "tts") this.onTts(d);
        else if (d.type === "wake_ack") this.onWakeAck();
        else if (d.type === "wake_state") this.onWakeState(d);
      } else if (!this.talking) this.play(m.data);
    };
  }

  async ensureCtx() {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      const url = URL.createObjectURL(new Blob([WORKLET], { type: "text/javascript" }));
      await this.ctx.audioWorklet.addModule(url);
    }
    if (this.ctx.state === "suspended") await this.ctx.resume();
  }

  async ensureMic() {
    await this.ensureCtx();
    if (this.node) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    this.mic = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm16k");
    this.node.port.onmessage = (e) => this.onFrame(e.data);
    this.mic.connect(this.node);
  }

  onFrame(buf) {
    const pcm = new Int16Array(buf);
    let sum = 0;
    for (let i = 0; i < pcm.length; i += 4) sum += (pcm[i] / 32768) ** 2;
    const rms = Math.sqrt(sum / (pcm.length / 4));
    this.onLevel(Math.min(1, rms * 6));
    if (this.talking) { this.ws.send(buf); return; }
    if (!this.wakeOn || this.muted()) { this.ring = []; this.hang = 0; return; }
    const loud = rms > Math.max(GATE_MIN, this.floor * 3);
    if (!loud) this.floor = this.floor * 0.98 + rms * 0.02;   // track the room's noise floor
    if (loud) {
      if (this.hang === 0) this.ring.forEach((b) => this.ws.send(b));   // pre-roll
      this.ring = []; this.hang = HANGOVER; this.ws.send(buf);
    } else if (this.hang > 0) { this.hang -= 1; this.ws.send(buf); }
    else { this.ring.push(buf); if (this.ring.length > PREROLL) this.ring.shift(); }
  }

  muted() { return this.ctx && this.ctx.currentTime < this.busyUntil + 0.5; }

  async setWake(on) {
    this.wakeOn = on;
    if (on) await this.ensureMic();
    this.send({ type: "wake", action: on ? "on" : "off" });
  }

  async start(extra = {}) {
    if (this.talking) return;
    this.stopPlayback();                                   // barge-in, renderer side
    this.send({ type: "ptt", action: "start", ...extra });
    this.talking = true;
    await this.ensureMic();
  }

  stop() {
    if (!this.talking) return;
    this.talking = false;
    this.send({ type: "ptt", action: "stop" });
    this.onLevel(0);
  }

  send(obj) { if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(obj)); }

  async play(buf) {
    await this.ensureCtx();
    const audio = await this.ctx.decodeAudioData(buf.slice(0));
    const when = Math.max(this.ctx.currentTime + 0.02, this.busyUntil);
    this.src = this.ctx.createBufferSource();
    this.src.buffer = audio;
    this.src.connect(this.ctx.destination);
    this.src.start(when);
    this.busyUntil = when + audio.duration;
  }

  async meow(kind, { afterSpeech = false } = {}) {
    await this.ensureCtx();
    if (afterSpeech) await new Promise((r) => setTimeout(r, 300));   // let the reply's audio arrive
    const when = Math.max(this.ctx.currentTime + 0.02, this.busyUntil);
    this.busyUntil = meow(this.ctx, kind, when);
    return (when - this.ctx.currentTime) * 1000;   // ms until it starts
  }

  stopPlayback() {
    if (this.src) { try { this.src.stop(); } catch (_) { /* already stopped */ } this.src = null; }
    if (this.ctx) this.busyUntil = this.ctx.currentTime;
  }
}
