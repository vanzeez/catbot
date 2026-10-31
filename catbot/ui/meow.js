// Synthesised cat sounds (WebAudio, no audio files). meow(ctx, kind, when) -> end time (ctx seconds).
// Each kind is a pitch contour through two vocal formants; "roll" adds the rrr of a trill,
// "growl" a low rumble, "hiss" a burst of filtered noise.
export const MEOWS = {
  happy:    { text: "meow!",         parts: [{ at: 0, dur: 0.42, f: [[0, 520], [0.12, 830], [0.42, 560]] },
                                             { at: 0.5, dur: 0.16, f: [[0, 600], [0.16, 790]], roll: 1 }] },
  chirp:    { text: "mrrp?",         parts: [{ at: 0, dur: 0.2, f: [[0, 480], [0.2, 770]], roll: 1 }] },
  question: { text: "mrrow?",        parts: [{ at: 0, dur: 0.5, f: [[0, 460], [0.22, 520], [0.5, 840]] }] },
  angry:    { text: "hsss… MROWR!",  hiss: 0.38,
              parts: [{ at: 0.42, dur: 0.62, f: [[0, 330], [0.2, 390], [0.62, 230]], growl: 1 }] },
  sad:      { text: "mew…",          parts: [{ at: 0, dur: 0.85, f: [[0, 700], [0.25, 620], [0.85, 320]], gain: 0.16 }] },
  error:    { text: "mew mew?",      parts: [{ at: 0, dur: 0.18, f: [[0, 650], [0.18, 520]] },
                                             { at: 0.27, dur: 0.18, f: [[0, 650], [0.18, 520]] }] },
  chat:     { text: "mew.",          parts: [{ at: 0, dur: 0.22, f: [[0, 600], [0.22, 700]], gain: 0.18 }] },
};

function syllable(ctx, out, t0, p) {
  const end = t0 + p.dur;
  const env = ctx.createGain();
  const peak = p.gain ?? 0.24;
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(peak, t0 + 0.035);
  env.gain.setValueAtTime(peak, Math.max(t0 + 0.04, end - 0.1));
  env.gain.exponentialRampToValueAtTime(0.0001, end);
  // formants: "m-e-ow" opens (F1 rises) then closes
  const f1 = ctx.createBiquadFilter(); f1.type = "bandpass"; f1.Q.value = 5;
  f1.frequency.setValueAtTime(700, t0);
  f1.frequency.linearRampToValueAtTime(1500, t0 + p.dur * 0.35);
  f1.frequency.linearRampToValueAtTime(800, end);
  const f2 = ctx.createBiquadFilter(); f2.type = "bandpass"; f2.Q.value = 7; f2.frequency.value = 2600;
  const mix = ctx.createGain(); mix.gain.value = 1;
  f1.connect(mix); f2.connect(mix); mix.connect(env); env.connect(out);
  const oscs = ["sawtooth", "square"].map((type, i) => {
    const o = ctx.createOscillator(); o.type = type; o.detune.value = i ? 7 : 0;
    o.frequency.setValueAtTime(p.f[0][1], t0);  // anchor first, then glide through the contour
    for (const [dt, hz] of p.f.slice(1)) o.frequency.linearRampToValueAtTime(hz, t0 + dt);
    const g = ctx.createGain(); g.gain.value = i ? 0.35 : 0.65;
    o.connect(g); g.connect(f1); g.connect(f2);
    return o;
  });
  const vib = ctx.createOscillator(); vib.frequency.value = 6;
  const vibDepth = ctx.createGain(); vibDepth.gain.value = 10;
  vib.connect(vibDepth); oscs.forEach((o) => vibDepth.connect(o.frequency));
  const extra = [vib];
  if (p.roll) {   // trill: fast amplitude flutter
    const lfo = ctx.createOscillator(); lfo.frequency.value = 28;
    const depth = ctx.createGain(); depth.gain.value = peak * 0.8;
    lfo.connect(depth); depth.connect(env.gain); extra.push(lfo);
  }
  if (p.growl) {  // low rumble under the meow
    const g = ctx.createOscillator(); g.type = "sawtooth"; g.frequency.value = 85;
    const gg = ctx.createGain(); gg.gain.value = 0.5; g.connect(gg); gg.connect(f1); extra.push(g);
  }
  [...oscs, ...extra].forEach((o) => { o.start(t0); o.stop(end + 0.02); });
  return end;
}

function hiss(ctx, out, t0, dur) {
  const len = Math.ceil(ctx.sampleRate * dur);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
  const src = ctx.createBufferSource(); src.buffer = buf;
  const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 3200;
  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(0.12, t0 + 0.05);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  src.connect(hp); hp.connect(env); env.connect(out);
  src.start(t0); src.stop(t0 + dur);
  return t0 + dur;
}

export function meow(ctx, kind, when) {
  const spec = MEOWS[kind] || MEOWS.chat;
  const out = ctx.createGain(); out.gain.value = 0.9; out.connect(ctx.destination);
  let end = when;
  if (spec.hiss) end = Math.max(end, hiss(ctx, out, when, spec.hiss));
  for (const p of spec.parts) end = Math.max(end, syllable(ctx, out, when + p.at, p));
  return end;
}
