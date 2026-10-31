// Voice I/O for the renderer: mic -> 16 kHz mono int16, 100 ms frames over WS /audio; TTS playback;
// barge-in (a new PTT press stops playback at once). Shared by the UI and scripts/audio_probe.html.
const WORKLET = `
class Pcm16k extends AudioWorkletProcessor {
  constructor() { super(); this.ratio = sampleRate / 16000; this.pos = 0; this.buf = []; this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    let i = this.pos, peak = 0;
    while (i < ch.length - 1) {
      const i0 = Math.floor(i), f = i - i0, s = ch[i0] * (1 - f) + ch[i0 + 1] * f;
      this.buf.push(s); peak = Math.max(peak, Math.abs(s)); i += this.ratio;
    }
    this.pos = i - (ch.length - 1);
    while (this.buf.length >= 1600) {
      const out = new Int16Array(1600);
      for (let k = 0; k < 1600; k++) out[k] = Math.max(-1, Math.min(1, this.buf[k])) * 32767;
      this.buf.splice(0, 1600);
      this.port.postMessage(out.buffer, [out.buffer]);
    }
    if (++this.n % 8 === 0) this.port.postMessage({ level: peak });
    return true;
  }
}
registerProcessor("pcm16k", Pcm16k);`;

export class Voice {
  constructor({ url, onTts = () => {}, onLevel = () => {}, onState = () => {} } = {}) {
    this.url = url || `ws://${location.host}/audio`;
    Object.assign(this, { onTts, onLevel, onState });
    this.ctx = null; this.stream = null; this.node = null; this.src = null;
    this.ws = null; this.pendingMime = null; this.talking = false;
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.binaryType = "arraybuffer";
    this.ws.onopen = () => this.onState("open");
    this.ws.onclose = () => { this.onState("closed"); setTimeout(() => this.connect(), 1500); };
    this.ws.onmessage = (m) => {
      if (typeof m.data === "string") {
        const d = JSON.parse(m.data);
        if (d.type === "tts") { this.pendingMime = d.mime; this.onTts(d); }
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

  async start(extra = {}) {
    if (this.talking) return;
    this.talking = true;
    this.stopPlayback();                                   // barge-in, renderer side
    this.send({ type: "ptt", action: "start", ...extra });
    await this.ensureCtx();
    this.stream = this.stream || await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    const mic = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm16k");
    this.node.port.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) { if (this.talking) this.ws.send(e.data); }
      else this.onLevel(e.data.level);
    };
    mic.connect(this.node);
    this.mic = mic;
  }

  stop() {
    if (!this.talking) return;
    this.talking = false;
    if (this.mic) this.mic.disconnect();
    if (this.node) this.node.disconnect();
    this.send({ type: "ptt", action: "stop" });
    this.onLevel(0);
  }

  send(obj) { if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(obj)); }

  async play(buf) {
    await this.ensureCtx();
    this.stopPlayback();
    const audio = await this.ctx.decodeAudioData(buf.slice(0));
    this.src = this.ctx.createBufferSource();
    this.src.buffer = audio;
    this.src.connect(this.ctx.destination);
    this.src.start();
  }

  stopPlayback() {
    if (this.src) { try { this.src.stop(); } catch (_) { /* already stopped */ } this.src = null; }
  }
}
