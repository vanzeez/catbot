// Card renderers. Pure DOM updates from a task view object built in app.js.
import { svg } from "./icons.js";

export const STAGES = ["listen", "think", "risk", "gate", "confirm", "execute", "result", "speak"];
const ICON = { listen: "mic", think: "brain", risk: "gauge", gate: "shield", confirm: "circle-help",
  execute: "zap", result: "list-checks", speak: "volume-2" };
export const COLOR = { listen: "--c-magenta", think: "--c-violet", risk: "--c-saffron", gate: "--c-saffron",
  allow: "--c-catnip", confirm: "--c-saffron", deny: "--c-chili", execute: "--c-cyan", result: "--c-cyan",
  speak: "--c-catnip", done: "--c-catnip", error: "--c-chili", idle: "--c-faint" };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const v = (name) => `var(${name})`;

const HEAD = {
  sleeping: ["Zzz…", "Zzz…"], listening: ["Kya hai? Bolo jaldi.", "Listening."],
  thinking: ["Uff… karta hoon.", "On it…"], asking: ["Pakka? Baad me rona mat.", "Sure?"],
  blocked: ["Arre pagal hai kya?", "Not doing that."], done: ["Billu ka kaam, pakka kaam.", "Done."],
};

export function renderCat(state, sub, lang, color) {
  const cat = $("cat");
  cat.dataset.state = state;
  cat.setAttribute("aria-label", `Catbot is ${state}`);
  $("stage").style.setProperty("--stage-color", v(color));
  $("headline").textContent = HEAD[state][String(lang || "hi").startsWith("en") ? 1 : 0];
  $("subline").textContent = sub || (state === "sleeping" ? "bol “meow” ya “Billu”, main jaag jaunga" : "");
}

export function renderRail(view) {
  $("rail").innerHTML = STAGES.map((s) => {
    const st = view.rail[s] || { state: "pending" };
    const color = st.color || COLOR[s];
    return `<li class="pill ${st.state}" style="--pc:${v(color)}">${svg(ICON[s], 16)}<span>${s}</span>` +
      `${st.ms != null ? `<span class="ms">${st.ms} ms</span>` : ""}</li>`;
  }).join("");
  $("total-ms").textContent = view.total != null ? `${view.total} ms` : "—";
  $("step-count").textContent = view.steps ? `step ${view.steps}` : "";
}

const THRESH = { tier: 0.8, verify: 0.7, reply: 0.8 };
const QID = { tier: "risk_tier", verify: "verify_call", reply: "confirm_reply" };
export const CHOICES = { tier: ["T0", "T1", "T2", "T3"], verify: ["execute", "wrong_tool", "unclear"], reply: ["A", "B", "C"] };

function barColor(conf, thr) {
  return conf >= thr ? "--c-catnip" : conf >= thr - 0.2 ? "--c-saffron" : "--c-chili";
}

function row(key, ans, step) {
  if (!ans) return "";
  const pct = Math.round(ans.confidence * 100);
  const tick = key === "reply" ? "" : `<i class="tick" style="left:${THRESH[key] * 100}%"></i>`;
  const chip = ans.source === "laya" ? "laya" : "warn";
  return `<div class="lrow"><span class="lab">${key}</span><span class="choice">${esc(ans.choice)}</span>` +
    `<span class="bar" role="img" aria-label="${key} confidence ${pct}%"><i class="fill" data-scale="${ans.confidence}" style="--bar:${v(barColor(ans.confidence, THRESH[key]))}"></i>${tick}</span>` +
    `<span class="pct">${pct}</span><span><span class="chip ${chip}">${esc(ans.source)}</span>` +
    `<button class="wrong" data-key="${key}" data-qid="${QID[key]}" data-step="${step ?? 0}">wrong?</button></span></div>`;
}

export function renderLaya(view) {
  const L = view.laya;
  if (!L.tier && !L.reply) {
    $("laya-rows").innerHTML = `<p class="empty">${L.floor ? `Utterance floor ${esc(L.floor)} — waiting for the model…` : "Abhi tak kuch nahi hua."}</p>`;
  } else {
    let html = row("tier", L.tier, L.step);
    if (L.shadow) {
      const s = L.shadow.tier;
      html += `<div class="lrow"><span class="lab">shadow</span><span class="choice">${esc(s.choice)}</span>` +
        `<span class="bar shadow-bar"><i class="fill" data-scale="${s.confidence}" style="--bar:${v("--c-violet")}"></i></span>` +
        `<span class="pct">${Math.round(s.confidence * 100)}</span><span><span class="chip">shadow</span></span></div>`;
    }
    html += row("verify", L.verify, L.step) + row("reply", L.reply, L.step);
    $("laya-rows").innerHTML = html;
    setTimeout(() => document.querySelectorAll("#laya-rows .fill").forEach((f, i) => {
      setTimeout(() => { f.style.transform = `scaleX(${f.dataset.scale})`; }, i * 40);
    }), 30);
  }
  const foot = [];
  if (L.floor) foot.push(`<span class="chip ${L.floor === "T3" ? "bad" : "warn"}">floor: ${esc(L.floor)}</span>`);
  if (L.tier?.checkpoint) foot.push(`<span class="chip laya">ckpt: ${esc(L.tier.checkpoint)}</span>`);
  if (L.tier && L.tier.source === "keyword") foot.push(`<span class="chip warn">keyword fallback</span>`);
  if (L.ms != null) foot.push(`<span class="chip">${L.ms} ms</span>`);
  $("laya-foot").innerHTML = foot.join("");
}

const LABEL = { allow: ["ALLOWED", "ALLOWED", "shield-check"], confirm: ["PUCHHNA PADEGA", "NEEDS A YES", "circle-help"],
  deny: ["BLOCKED", "BLOCKED", "shield-x"] };

export function renderVerdict(view, lang) {
  const g = view.gate;
  if (!g) { $("verdict").innerHTML = '<p class="empty">—</p>'; return; }
  const [hi, en, icon] = LABEL[g.verdict];
  const label = String(lang || "hi").startsWith("en") ? en : hi;
  const prov = view.lastFlag ? `<span class="chip bad">instruction-like text in ${esc(view.lastOrigin)}</span>`
    : view.lastOrigin && view.lastOrigin !== "user" ? `<span class="chip data">origin: ${esc(view.lastOrigin)} — data only</span>` : "";
  let html = `<div class="sticker ${g.verdict}" ${g.verdict === "deny" ? 'role="alert"' : ""}>${svg(icon, 24)} ${label}</div>` +
    `<div class="vmeta"><code>${esc(g.policy)}</code><span>${esc(g.reason)}</span>` +
    `${g.corrective_context ? `<span class="inset">${esc(g.corrective_context)}</span>` : ""}${prov}</div>`;
  if (view.confirm) {
    html += `<div class="confirm-actions"><button class="btn-yes" data-reply="haan">Haan, karo</button>` +
      `<button class="btn-no" data-reply="nahi">Cancel</button><span class="countdown" id="countdown"></span></div>`;
  }
  $("verdict").innerHTML = html;
}

export function renderPlan(view, lang) {
  $("plan-head").innerHTML = `<span class="chip">${esc(lang || "hi-IN")}</span>` +
    (view.steps ? `<span class="chip">${view.steps} step${view.steps > 1 ? "s" : ""}</span>` : "");
  $("plan").innerHTML = view.plan.map((p, i) => {
    const cls = p.final ? "final" : i === view.plan.length - 1 ? "cur" : "";
    const tools = (p.tools || []).map((t) => `<code>${esc(t)}</code>`).join("");
    return `<li class="${cls}">${esc(p.text || "(no text)")}${tools}</li>`;
  }).join("");
}

const TIER_CHIP = { T0: "data", T1: "data", T2: "warn", T3: "bad" };

export function renderCall(view) {
  const c = view.call;
  if (!c) { $("call").innerHTML = '<p class="empty">—</p>'; return; }
  const tier = view.laya.tier?.choice;
  const kv = Object.entries(c.args || {}).filter(([, x]) => x !== null)
    .map(([k, x]) => `<dt>${esc(k)}</dt><dd>${esc(typeof x === "string" ? x : JSON.stringify(x))}</dd>`).join("");
  $("call").innerHTML = `<div class="callname">${svg("zap", 18)} ${esc(c.tool)} ${tier ? `<span class="chip ${TIER_CHIP[tier]}">${tier}</span>` : ""}</div>` +
    `${kv ? `<dl class="kv">${kv}</dl>` : ""}<div class="argv code">${esc(JSON.stringify(c.argv))}</div>`;
}

export function renderResult(view) {
  const r = view.result;
  if (!r) { $("result").innerHTML = '<p class="empty">—</p>'; return; }
  const flag = view.lastFlag ? '<span class="chip bad">instruction-like text</span>' : "";
  $("result").innerHTML = `<div class="rsum"><span class="${r.ok ? "ok" : "bad"}">${svg(r.ok ? "check" : "x", 20)}</span>${esc(r.summary)}</div>` +
    `<div class="laya-foot"><span class="chip data">origin: ${esc(r.origin)}</span>${flag}${r.error ? `<span class="chip bad">${esc(r.error)}</span>` : ""}</div>` +
    (r.data ? `<details><summary>data</summary><pre>${esc(JSON.stringify(r.data, null, 2))}</pre></details>` : "");
}

export function logLine(e) {
  const p = e.payload || {};
  const t = (e.ts || "").slice(11, 19);
  let color = COLOR[e.stage] || "--c-faint";
  let msg = "";
  if (e.stage === "gate") { color = COLOR[p.verdict.verdict]; msg = `${p.verdict.verdict} · ${p.verdict.policy}`; }
  else if (e.stage === "risk") msg = p.tier ? `${e.tool} ${p.tier.choice} ${Math.round(p.tier.confidence * 100)}% ${p.tier.source}` : `floor ${p.utterance_floor ?? "none"}`;
  else if (e.stage === "think") msg = `${p.text || ""} ${(p.tool_calls || []).map((c) => "→ " + c.tool).join(" ")}`;
  else if (e.stage === "confirm") msg = p.question || `reply ${p.reply ?? "(timeout)"} → ${p.answer?.choice}`;
  else if (e.stage === "execute") msg = `${p.tool} ${JSON.stringify(p.argv)}`;
  else if (e.stage === "result") msg = `${p.result.ok ? "ok" : "FAIL"} ${p.result.summary}`;
  else if (e.stage === "speak") msg = p.text;
  else if (e.stage === "listen") msg = p.final ?? p.partial ?? "";
  else if (e.stage === "done") { color = p.ok ? "--c-catnip" : "--c-chili"; msg = `ok=${p.ok} ${p.stopped_by ?? ""}`; }
  else msg = JSON.stringify(p);
  const ms = e.latency_ms != null ? ` · ${e.latency_ms} ms` : "";
  return `<span class="t">${esc(t)}</span><span class="dot" style="--dc:${v(color)}"></span><span>${esc(e.stage)}</span><span class="msg">${esc(msg)}${ms}</span>`;
}
