// Catbot UI: WebSocket client (reconnect), one store keyed by task id, renderers, PTT, corrections.
import { Voice } from "./audio.js";
import { MEOWS } from "./meow.js";
import { CHOICES, COLOR, STAGES, logLine, renderCall, renderCat, renderLaya, renderPlan,
  renderRail, renderResult, renderVerdict } from "./render.js";

const $ = (id) => document.getElementById(id);
const S = { cur: null, tasks: new Map(), lang: "hi-IN", filter: "all", lines: [], idle: null,
  lastListen: 0, countdown: null };

function newView(id) {
  return { id, steps: 0, plan: [], laya: {}, gate: null, call: null, result: null, rail: {}, total: null,
    confirm: null, lastOrigin: "user", lastFlag: false };
}
const view = () => S.tasks.get(S.cur) || newView(null);

function setRail(v, stage, state, extra = {}) { v.rail[stage] = { state, ...extra }; }

function catFor(v, stage, sub) {
  clearTimeout(S.idle);
  const map = { listen: ["listening", "listen"], think: ["thinking", "think"], risk: ["thinking", "risk"],
    execute: ["thinking", "execute"], result: ["thinking", "result"] };
  if (map[stage]) renderCat(map[stage][0], sub, S.lang, COLOR[map[stage][1]]);
  S.idle = setTimeout(() => renderCat("sleeping", "", S.lang, COLOR.idle), 20000);
}

function onEvent(e) {
  const p = e.payload || {};
  addLog(e);
  if (e.stage === "listen") {
    if (p.lang) S.lang = p.lang;
    $("partial").textContent = p.final == null ? p.partial || "" : "";
    if (p.final != null) { $("final").textContent = p.final; S.lastListen = Date.now(); }
    catFor(null, "listen", p.final ?? "live transcript");
    return;
  }
  if (e.stage === "risk" && !p.tier) {
    const v = newView(e.task_id);
    v.laya.floor = p.utterance_floor;
    STAGES.forEach((s) => setRail(v, s, "pending"));
    setRail(v, "listen", Date.now() - S.lastListen < 15000 ? "done" : "skipped");
    S.tasks.set(e.task_id, v);
    S.cur = e.task_id;
    if (S.tasks.size > 30) S.tasks.delete(S.tasks.keys().next().value);
    catFor(v, "think", p.utterance_floor ? `utterance floor ${p.utterance_floor}` : "");
    return renderAll();
  }
  const v = S.tasks.get(e.task_id);
  if (!v) return;
  if (e.task_id !== S.cur) return;
  if (e.stage === "think") {
    v.plan.push({ text: p.text, tools: (p.tool_calls || []).map((c) => c.tool), final: !(p.tool_calls || []).length });
    if ((p.tool_calls || []).length) {
      v.steps += 1;
      ["risk", "gate", "confirm", "execute", "result"].forEach((s) => setRail(v, s, "pending"));
    }
    setRail(v, "think", "done", { ms: e.latency_ms });
    catFor(v, "think", p.text);
  } else if (e.stage === "risk") {
    Object.assign(v.laya, { tier: p.tier, verify: p.verify, shadow: p.shadow, step: e.step, ms: e.latency_ms, reply: null });
    setRail(v, "risk", "done", { ms: e.latency_ms });
    catFor(v, "risk", `${e.tool}: ${p.tier.choice}`);
  } else if (e.stage === "gate") {
    const g = p.verdict;
    v.gate = g;
    if (g.verdict === "allow") { setRail(v, "gate", "done", { color: COLOR.allow }); setRail(v, "confirm", "skipped"); }
    else if (g.verdict === "confirm") setRail(v, "gate", "done", { color: COLOR.confirm });
    else {
      setRail(v, "gate", "failed");
      ["confirm", "execute", "result"].forEach((s) => setRail(v, s, "skipped"));
      renderCat("blocked", g.reason, S.lang, COLOR.deny);
    }
  } else if (e.stage === "confirm" && p.question) {
    sound(e, "question");
    v.confirm = { question: p.question, until: Date.now() + 8000 };
    setRail(v, "confirm", "active");
    renderCat("asking", p.question, S.lang, COLOR.confirm);
    $("stage-confirm").hidden = false;
    openSheet(p.question);
    startCountdown(v);
  } else if (e.stage === "confirm") {
    v.confirm = null;
    v.laya.reply = p.answer;
    setRail(v, "confirm", p.answer?.choice === "A" ? "done" : "failed");
    $("stage-confirm").hidden = true;
    closeSheet();
  } else if (e.stage === "execute") {
    v.call = p;
    setRail(v, "execute", "done");
    catFor(v, "execute", p.tool);
  } else if (e.stage === "result") {
    v.result = p.result;
    v.lastOrigin = p.result.origin;
    v.lastFlag = !!p.provenance_flag;
    setRail(v, "result", p.result.ok ? "done" : "failed");
  } else if (e.stage === "speak") {
    if (p.lang) S.lang = p.lang;
    setRail(v, "speak", "done");
    $("subline").textContent = p.text;
  } else if (e.stage === "done") {
    v.total = e.latency_ms;
    v.confirm = null;
    $("stage-confirm").hidden = true;
    closeSheet();
    const speak = S.lines.find((x) => x.e.task_id === e.task_id && x.e.stage === "speak");
    const said = speak ? speak.e.payload.text : "";
    sound(e, p.ok ? (p.steps ? "happy" : "chat")
      : p.stopped_by === "user_cancel" ? "sad" : p.stopped_by === "error" ? "error" : "angry", true);
    if (p.ok) renderCat("done", said, S.lang, COLOR.done);
    else if (p.stopped_by === "user_cancel") renderCat("sleeping", said, S.lang, COLOR.idle);
    else renderCat("blocked", said, S.lang, COLOR.deny);
  } else if (e.stage === "error") {
    renderCat("blocked", p.message, S.lang, COLOR.error);
  }
  renderAll();
}

const sigs = {};
function once(key, data, fn) {  // re-render a card only when its data changed (keeps entry animations)
  const sig = JSON.stringify(data);
  if (sigs[key] === sig) return;
  sigs[key] = sig;
  fn();
}
// ---- meow sounds: one per outcome, only for live events (not the replay on connect) ----------
function sound(e, kind, afterSpeech = false) {
  const age = Date.now() - Date.parse(e.ts || "");
  if (!(age < 5000) || typeof voice === "undefined") return;
  voice.meow(kind, { afterSpeech }).then((delayMs) => setTimeout(() => bubble(kind), delayMs))
    .catch(() => bubble(kind));
}
function bubble(kind) {
  const b = $("meow-bubble");
  b.textContent = MEOWS[kind]?.text || "meow";
  b.dataset.kind = kind;
  b.hidden = false;
  clearTimeout(bubble.t);
  bubble.t = setTimeout(() => { b.hidden = true; }, 1800);
}

function renderAll() {
  const v = view();
  renderRail(v);
  once("laya", [v.id, v.laya], () => renderLaya(v));
  once("verdict", [v.id, v.gate, !!v.confirm, v.lastOrigin, v.lastFlag, S.lang], () => renderVerdict(v, S.lang));
  once("plan", [v.id, v.plan, S.lang], () => renderPlan(v, S.lang));
  once("call", [v.id, v.call, v.laya.tier], () => renderCall(v));
  once("result", [v.id, v.result, v.lastFlag], () => renderResult(v));
}

// ---- log ----------------------------------------------------------------------------------------
const FILTERS = { all: () => true, decisions: (e) => ["risk", "confirm"].includes(e.stage), gate: (e) => e.stage === "gate",
  errors: (e) => e.stage === "error" || (e.stage === "gate" && e.payload.verdict.verdict === "deny") || (e.stage === "done" && !e.payload.ok) };
function addLog(e) { S.lines.unshift({ e, html: logLine(e) }); S.lines.length = Math.min(S.lines.length, 500); drawLog(); }
function drawLog() {
  const rows = S.lines.filter((x) => FILTERS[S.filter](x.e));
  $("log").innerHTML = rows.length ? rows.map((x) => `<li>${x.html}</li>`).join("")
    : '<li class="empty">Abhi tak kuch nahi hua. Space dabao aur bolo.</li>';
}
$("filters").onclick = (ev) => {
  const b = ev.target.closest("button"); if (!b) return;
  S.filter = b.dataset.f;
  $("filters").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  drawLog();
};

// ---- websocket ----------------------------------------------------------------------------------
let backoff = 1000;
function connect() {
  const ws = new WebSocket(`ws://${location.host}/events`);
  ws.onopen = () => { backoff = 1000; $("live").classList.add("on"); $("live-text").textContent = "live"; };
  ws.onmessage = (m) => onEvent(JSON.parse(m.data));
  ws.onclose = () => {
    $("live").classList.remove("on");
    $("live-text").textContent = "Connection gaya. Dobara jod rahe hain…";
    setTimeout(connect, backoff); backoff = Math.min(backoff * 2, 8000);
  };
}

async function stats() {
  try {
    const s = await (await fetch("/api/stats")).json();
    const chips = [
      s.gate === "laya" ? `<span class="chip laya">gate: LAYA</span>` : `<span class="chip warn">gate: KEYWORD</span>`,
      s.shadow ? `<span class="chip">shadow</span>` : "",
      s.llm === "fake" || s.tools === "fake" ? `<span class="chip warn">fake mode</span>` : "",
      s.voice ? `<span class="chip ok">voice on</span>` : `<span class="chip">voice off</span>`,
    ];
    $("chips").innerHTML = chips.join("");
    $("corrections").textContent = s.corrections;
  } catch (_) { /* server restarting */ }
}

// ---- confirm ------------------------------------------------------------------------------------
async function reply(r) {
  const v = view();
  if (!v.confirm) return;
  await fetch("/api/confirm", { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ task_id: v.id, reply: r }) });
}
function startCountdown(v) {
  clearInterval(S.countdown);
  S.countdown = setInterval(() => {
    const el = $("countdown");
    const left = v.confirm ? Math.max(0, Math.ceil((v.confirm.until - Date.now()) / 1000)) : 0;
    if (el) el.textContent = `${left}s`;
    if (!v.confirm || left === 0) clearInterval(S.countdown);
  }, 250);
}
const phone = () => matchMedia("(max-width: 767px)").matches;
function openSheet(q) { if (!phone()) return; $("sheet-q").textContent = q; $("sheet").hidden = false; }
function closeSheet() { $("sheet").hidden = true; }
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-reply]");
  if (b) reply(b.dataset.reply);
  if (ev.target.closest("[data-close]")) reply("nahi");
});

// ---- corrections --------------------------------------------------------------------------------
$("laya-rows").addEventListener("click", (ev) => {
  const b = ev.target.closest(".wrong"); if (!b) return;
  const pop = $("popover");
  pop.innerHTML = CHOICES[b.dataset.key].map((c) => `<button role="menuitem" data-c="${c}">${c}</button>`).join("");
  const r = b.getBoundingClientRect();
  Object.assign(pop.style, { left: `${r.left + scrollX - 40}px`, top: `${r.bottom + scrollY + 4}px` });
  pop.hidden = false;
  pop.querySelector("button").focus();
  pop.onclick = async (e2) => {
    const c = e2.target.closest("button"); if (!c) return;
    pop.hidden = true;
    const res = await fetch("/api/correction", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ task_id: S.cur, step: Number(b.dataset.step), question_id: b.dataset.qid, correct_choice: c.dataset.c }) });
    $("corrections").textContent = (await res.json()).corrections;
    toast(S.lang.startsWith("en") ? "Thanks, logged for training." : "Shukriya, yaad rakhenge.");
  };
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("popover").hidden = true; });
function toast(msg) { const t = $("toast"); t.textContent = msg; t.hidden = false; setTimeout(() => { t.hidden = true; }, 2200); }

// ---- input: text, PTT, keys ---------------------------------------------------------------------
$("text-form").onsubmit = async (ev) => {
  ev.preventDefault();
  const utterance = $("text-in").value.trim(); if (!utterance) return;
  const lang = /[஀-௿]/.test(utterance) ? "ta-IN" : /^[\x00-\x7F]*$/.test(utterance) ? undefined : "hi-IN";
  $("final").textContent = utterance; $("partial").textContent = "";
  await fetch("/api/text", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ utterance, lang }) });
  $("text-in").value = "";
};
const level = (l) => { $("cat").style.setProperty("--level", l); $("ptt").style.setProperty("--level", l); };
const voice = new Voice({
  onLevel: level,
  onWakeAck: () => {                    // "meow": chirp and stay active until paused
    voice.meow("chirp").then((ms) => setTimeout(() => bubble("chirp"), ms));
    renderCat("listening", "Bol, sun raha hoon…", S.lang, COLOR.listen);
  },
  onWakeState: (d) => setWakeUi(d.mode || (d.on ? "waiting" : "off"), d.live),
});
// ---- listening: off -> waiting for "meow" -> active (every sentence is a command) -> pause ----
let wakeWanted = true;
try { wakeWanted = localStorage.getItem("catbot.wake") !== "off"; } catch (_) { /* storage blocked */ }
const WAKE_NOTE = {
  off: "Paused. Mic is off.",
  waiting: "Say “meow” (or “Billu”) to start…",
  active: "Listening — just talk. Pause when you're done.",
};
function setWakeUi(mode, live = true) {
  const btn = $("wake-btn");
  btn.dataset.mode = mode;
  btn.setAttribute("aria-pressed", String(mode !== "off"));
  btn.textContent = mode === "off" ? "Start listening" : "Pause listening";
  $("wake-note").textContent = mode !== "off" && !live
    ? "Fake mode: listening needs the Sarvam key." : WAKE_NOTE[mode];
}
async function applyWake(on) {
  wakeWanted = on;
  try { localStorage.setItem("catbot.wake", on ? "on" : "off"); } catch (_) { /* storage blocked */ }
  try { await voice.setWake(on); setWakeUi(on ? "waiting" : "off"); }
  catch (err) { setWakeUi("off"); $("wake-note").textContent = `Mic blocked: ${err.message}`; }
}
$("wake-btn").onclick = () => applyWake(!wakeWanted);
// Browsers need a click before audio can start; Electron does not.
applyWake(wakeWanted).catch(() => {});
addEventListener("pointerdown", () => voice.ensureCtx().catch(() => {}), { once: true });
const down = () => { $("ptt").classList.add("on"); voice.start().catch((err) => toast(`mic: ${err.message}`)); };
const up = () => { $("ptt").classList.remove("on"); voice.stop(); };
$("ptt").addEventListener("pointerdown", (e) => { e.preventDefault(); down(); });
["pointerup", "pointerleave", "pointercancel"].forEach((n) => $("ptt").addEventListener(n, up));
const typing = (e) => ["INPUT", "TEXTAREA"].includes(e.target.tagName);
addEventListener("keydown", (e) => {
  if (typing(e)) return;
  if (e.code === "Space" && !e.repeat) { e.preventDefault(); down(); }
  else if (e.key === "/") { e.preventDefault(); $("text-in").focus(); }
  else if ((e.key === "y" || e.key === "Y") && view().confirm) reply("haan");
  else if ((e.key === "n" || e.key === "N") && view().confirm) reply("nahi");
});
addEventListener("keyup", (e) => { if (e.code === "Space" && !typing(e)) up(); });
if (window.catbot?.onPtt) window.catbot.onPtt((state) => (state === "down" ? down() : up()));
$("help-btn").onclick = () => $("help").showModal();
$("help-close").onclick = () => $("help").close();

// ---- Billu mode (just the cat) vs details mode -------------------------------------------------
function setView(view) {
  const billu = view === "billu";
  document.body.classList.toggle("view-billu", billu);
  $("view-btn").setAttribute("aria-pressed", String(billu));
  $("view-btn").textContent = billu ? "Show details" : "Billu mode";
  try { localStorage.setItem("catbot.view", billu ? "billu" : "details"); } catch (_) { /* blocked */ }
}
let startView = new URLSearchParams(location.search).get("view");
if (!startView) { try { startView = localStorage.getItem("catbot.view"); } catch (_) { /* blocked */ } }
setView(startView === "billu" ? "billu" : "details");
$("view-btn").onclick = () => setView(document.body.classList.contains("view-billu") ? "details" : "billu");

renderAll();
connect();
stats();
setInterval(stats, 5000);
