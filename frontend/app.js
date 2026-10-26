/* Career Test Drive — front end (no framework, no build step). */
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (v) => (v == null ? "n/a" : "$" + Math.round(v).toLocaleString("en-US"));
const kmoney = (v) => (v == null ? "n/a" : v >= 1000 ? "$" + Math.round(v / 1000) + "K" : "$" + v);

const AGENTS = [
  { name: "Gatekeeper", role: "Screens your message for safety", icon: '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 12l2 2 4-4" fill="none" stroke="currentColor" stroke-width="2"/>' },
  { name: "Scout", role: "Finds the official job among 774", icon: '<circle cx="11" cy="11" r="6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l5 5" stroke="currentColor" stroke-width="2"/>' },
  { name: "Fact-Checker", role: "Tests each belief against BLS data", icon: '<path d="M4 6h16M4 12h10M4 18h7" stroke="currentColor" stroke-width="2"/><path d="M15 17l2 2 4-4" fill="none" stroke="currentColor" stroke-width="2"/>' },
  { name: "Test-Drive", role: "Writes 3 real moments from the job", icon: '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="2" fill="currentColor"/><path d="M12 4v6M5 15l5-2M19 15l-5-2" stroke="currentColor" stroke-width="2"/>' },
  { name: "Pathway", role: "Draws your road map and neighbors", icon: '<path d="M4 20c4-8 12-2 16-14" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 3"/><circle cx="4" cy="20" r="2" fill="currentColor"/><circle cx="20" cy="6" r="2" fill="currentColor"/>' },
];

const EXAMPLES = [
  ["lawyer", "Lawyers argue in court every day and make $300k right out of school. You need to be good at math."],
  ["video game designer", "Game designers play games all day and it's super chill. Anyone who games a lot can do it."],
  ["nurse", "Nurses just do what doctors say. The pay is low and you only need a short course."],
  ["electrician", "Electricians don't make much money and it's a dead-end job. You don't need any school."],
  ["veterinarian", "Vets get to play with puppies all day. It's easier to get into than medical school."],
];

const state = { facts: {}, career: null, wages: null, beliefs: "", drive: null, picks: [], feels: [], pathway: null, result: null };

/* ---------------- hero: career input, autosize + autocomplete ---------------- */
const careerEl = $("#career");
const suggestEl = $("#suggest");
let suggestTimer, activeIdx = -1, placeholderTimer;

function autosize() {
  const len = Math.max((careerEl.value || careerEl.placeholder).length, 5);
  careerEl.style.width = Math.min(len + 1, 14) + "ch";
}
careerEl.addEventListener("input", () => {
  autosize();
  clearTimeout(suggestTimer);
  const q = careerEl.value.trim();
  if (q.length < 2) return (suggestEl.innerHTML = "");
  suggestTimer = setTimeout(async () => {
    const res = await fetch("/api/suggest?q=" + encodeURIComponent(q)).then((r) => r.json()).catch(() => []);
    activeIdx = -1;
    suggestEl.innerHTML = res.map((r) => `<li role="option" data-title="${esc(r.matched_on)}">${esc(r.matched_on)}<small>${esc(r.title)}</small></li>`).join("");
  }, 180);
});
careerEl.addEventListener("keydown", (e) => {
  const items = [...suggestEl.children];
  if (e.key === "ArrowDown" && items.length) { activeIdx = (activeIdx + 1) % items.length; e.preventDefault(); }
  else if (e.key === "ArrowUp" && items.length) { activeIdx = (activeIdx - 1 + items.length) % items.length; e.preventDefault(); }
  else if (e.key === "Enter") {
    if (activeIdx >= 0 && items[activeIdx]) pickSuggestion(items[activeIdx]);
    else { suggestEl.innerHTML = ""; $("#beliefs").focus(); }
    e.preventDefault();
  } else if (e.key === "Escape") suggestEl.innerHTML = "";
  items.forEach((li, i) => li.classList.toggle("active", i === activeIdx));
});
suggestEl.addEventListener("mousedown", (e) => { const li = e.target.closest("li"); if (li) pickSuggestion(li); });
careerEl.addEventListener("blur", () => setTimeout(() => (suggestEl.innerHTML = ""), 150));
function pickSuggestion(li) { careerEl.value = li.dataset.title; suggestEl.innerHTML = ""; autosize(); $("#beliefs").focus(); }

function rotatePlaceholder() {
  let i = 0;
  placeholderTimer = setInterval(() => {
    if (careerEl.value) return;
    i = (i + 1) % EXAMPLES.length;
    careerEl.placeholder = EXAMPLES[i][0];
    $("#beliefs").placeholder = "e.g. " + EXAMPLES[i][1];
    autosize();
  }, 2600);
}

$("#belief-chips").innerHTML = EXAMPLES.map((e, i) => `<button class="chip" data-i="${i}">Try: ${esc(e[0])}</button>`).join("");
$("#belief-chips").addEventListener("click", (e) => {
  const b = e.target.closest(".chip"); if (!b) return;
  const [c, bel] = EXAMPLES[+b.dataset.i];
  careerEl.value = c; $("#beliefs").value = bel; autosize();
});

/* ---------------- run ---------------- */
$("#go").addEventListener("click", () => start());
$("#restart").addEventListener("click", () => resetToHero());

function resetToHero() {
  $("#results").hidden = true; $("#crew").hidden = true; $("#hero").hidden = false;
  if (location.hash !== "#/") history.replaceState(null, "", "#/");
  window.scrollTo({ top: 0, behavior: "smooth" });
  careerEl.focus();
}

async function start(override) {
  const career = override?.career ?? careerEl.value.trim() ?? "";
  const beliefs = override?.beliefs ?? $("#beliefs").value.trim();
  const likes = override?.likes ?? $("#likes").value.trim();
  const err = $("#hero-error");
  if (!career) { err.textContent = "Type a career you're curious about first."; err.hidden = false; return; }
  err.hidden = true;
  $("#fb-send").hidden = false; $("#fb-thanks").hidden = true; $("#fb-comment").value = ""; fbChange = null;
  [...$("#fb-change").children].forEach((x) => x.classList.remove("on"));
  Object.assign(state, { facts: {}, career: null, wages: null, beliefs, drive: null, picks: [], feels: [], pathway: null, result: null, likes });
  $("#go").disabled = true;
  $("#hero").hidden = true; $("#results").hidden = true;
  if (window.v2) window.v2.show("drive");
  $("#crew").hidden = false;
  ["#overview", "#score", "#verdicts", "#surprises", "#vibes", "#drive-stage", "#road", "#paybar", "#neighbors", "#hood-body", "#paystages", "#tilemap", "#statelists", "#majors", "#schools", "#eco", "#specs"].forEach((s) => ($(s).innerHTML = ""));
  renderCrew();
  window.scrollTo({ top: 0, behavior: "smooth" });

  try {
    const res = await fetch("/api/explore", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ career, beliefs, likes }) });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        const ev = /^event: (.*)$/m.exec(chunk)?.[1];
        const data = /^data: (.*)$/m.exec(chunk)?.[1];
        if (ev && data) handle(ev, JSON.parse(data));
      }
    }
  } catch (e) {
    showBlocked({ layer: "network", message: "We couldn't reach the server. Is it still running?" });
  } finally {
    $("#go").disabled = false;
  }
}

function handle(ev, d) {
  if (ev === "agent") updateAgent(d);
  else if (ev === "blocked") showBlocked(d);
  else if (ev === "career") renderCareer(d);
  else if (ev === "reality") renderReality(d);
  else if (ev === "test_drive") { state.drive = d; renderScene(0); }
  else if (ev === "pathway") { state.pathway = d; renderRoad(d); renderNeighbors(d); }
  else if (ev === "done") { state.result = d; renderHood(d); setTimeout(() => ($("#crew").hidden = d.status === "ok"), 600); }
  else if (ev === "error") showBlocked({ layer: "server", message: d.message });
}

/* ---------------- pit crew ---------------- */
function renderCrew() {
  $("#crew-list").innerHTML = AGENTS.map((a) => `
    <li class="agent" id="agent-${a.name}">
      <div class="ico"><svg viewBox="0 0 24 24">${a.icon}</svg></div>
      <h4>${a.name}</h4><div class="role">${a.role}</div>
      <div class="state">Waiting</div><div class="tok"></div>
    </li>`).join("");
}
function updateAgent(d) {
  const el = document.getElementById("agent-" + d.agent); if (!el) return;
  el.className = "agent " + d.state;
  $(".state", el).textContent = d.state === "working" ? d.note || "Working…" : d.state === "done" ? d.note || "Done" : "Error: " + (d.note || "");
  const u = d.usage;
  if (u) $(".tok", el).textContent = u.cache_hit ? "0 tokens · reused" : `${(u.input_tokens + u.output_tokens).toLocaleString()} tokens · ${u.seconds}s`;
}

function showBlocked(d) {
  $("#crew").hidden = false;
  const titles = { regex: "Blocked before any AI saw it", gatekeeper: "The Gatekeeper stopped this one", budget: "Spending limit reached", network: "Connection problem", server: "Something went wrong" };
  $("#crew").insertAdjacentHTML("beforeend", `
    <div class="blocked-card">
      <div class="layer">Safety layer: ${esc(d.layer)}${d.category ? " · " + esc(d.category) : ""}</div>
      <h3>${esc(titles[d.layer] || "Stopped")}</h3>
      <p>${esc(d.message)}</p>
      <button class="btn-ghost" onclick="location.reload()">Start over</button>
    </div>`);
}

/* ---------------- career header + vibes + pay ---------------- */
function renderCareer(d) {
  state.career = d.career; state.wages = d.wages;
  d.facts.forEach((f) => (state.facts[f.id] = f));
  const c = d.career;
  const growth = c.growth_pct;
  const growthTxt = growth == null ? "n/a" : (growth > 0 ? "+" : "") + growth + "%";
  $("#overview").innerHTML = `
    <div class="label">You're test-driving</div>
    <h1>${esc(c.title)}</h1>
    <p class="match">${esc(d.match_note)}</p>
    <div id="plain" class="plain"><div class="plain-loading">Explaining this job in plain words…</div></div>
    <details class="desc-official"><summary>Official description (O*NET)</summary><p class="desc">${esc(c.description)}</p></details>
    <div class="stats">
      <div class="stat"><div class="k">U.S. median pay (2024)</div><div class="v">${money(c.median)}</div><div class="s">Half earn more, half less</div></div>
      <div class="stat"><div class="k">Job growth 2025–35</div><div class="v ${growth >= 3.5 ? "up" : growth < 0 ? "down" : ""}">${growthTxt}</div><div class="s">All US jobs: +3.5%</div></div>
      <div class="stat"><div class="k">Openings per year</div><div class="v">${c.openings == null ? "n/a" : c.openings.toLocaleString()}</div><div class="s">New jobs + people leaving</div></div>
      <div class="stat"><div class="k">Typical entry education</div><div class="v small">${esc(c.education || "n/a")}</div><div class="s">${c.pct_over_40_hours != null ? Math.round(c.pct_over_40_hours) + "% work 40+ hr weeks" : ""}</div></div>
    </div>`;
  const lvl = { "very low": 10, low: 30, moderate: 52, high: 76, "very high": 96 };
  const order = Object.entries(c.work_context).sort((a, b) => lvl[b[1]] - lvl[a[1]]);
  $("#vibes").innerHTML = order.map(([k, v]) => `<div class="vibe"><span>${esc(k)}</span><div class="bar"><i style="width:${lvl[v]}%"></i></div><span class="lvl">${esc(v)}</span></div>`).join("");
  renderPaybar(c);
  $("#results").hidden = false;
  $("#overview").scrollIntoView({ behavior: "smooth" });
  if (window.v2) window.v2.onCareer(c);
}

function guessFromBeliefs(text) {
  const m = /\$?\s?(\d{2,3}(?:,\d{3})*|\d+(?:\.\d+)?)\s?(k|K|thousand)?\b/.exec(text || "");
  if (!m) return null;
  let v = parseFloat(m[1].replace(/,/g, ""));
  if (m[2]) v *= 1000;
  return v >= 15000 && v <= 2000000 ? v : null;
}

function renderPaybar(c) {
  if (c.median == null) { $("#paybar").innerHTML = ""; return; }
  const guess = guessFromBeliefs(state.beliefs);
  const max = Math.max(c.p90 * 1.12, (guess || 0) * 1.08);
  const pos = (v) => (v / max) * 100;
  const tick = (v, label) => `<div class="tick" style="left:${pos(v)}%">${kmoney(v)}${c.top_coded && v === c.p90 ? "+" : ""}<small>${label}</small></div><div class="mark" style="left:${pos(v)}%"></div>`;
  $("#paybar").innerHTML = `
    <h4>What people actually earn</h4>
    <p class="sub2">Each mark is a BLS wage percentile for ${esc(c.title.toLowerCase())}${c.top_coded ? ". BLS caps reported wages at $239,200, so top earners may make more" : ""}.</p>
    <div class="scale">
      <div class="band" style="left:${pos(c.p10)}%;width:${pos(c.p90) - pos(c.p10)}%"></div>
      ${tick(c.p10, "10th")}${tick(c.p25, "25th")}${tick(c.median, "median")}${tick(c.p75, "75th")}${tick(c.p90, "90th")}
      ${guess ? `<div class="mark guessmark" style="left:${pos(guess)}%"></div><div class="you" style="left:${Math.min(pos(guess), 88)}%">↑ your guess: ${kmoney(guess)}</div>` : ""}
    </div><div style="height:46px"></div>`;
}

/* ---------------- reality check ---------------- */
const STAMP = { true: "True", partly: "Partly", myth: "Myth", no_data: "No data" };
function factChips(ids) {
  return `<div class="facts">${ids.map((id) => {
    const f = state.facts[id];
    return f ? `<span class="fact" tabindex="0" data-tip="${esc(f.text + " — " + f.source)}">${esc(id)} · ${esc(f.source.split(",")[0].replace("O*NET 31.0 ", "O*NET "))}</span>` : "";
  }).join("")}</div>`;
}
function vcard(v, i) {
  return `<article class="vcard v-${v.verdict}" style="animation-delay:${i * 120}ms">
    <div class="claim">${esc(v.claim)}</div><div class="stamp">${STAMP[v.verdict]}</div>
    <h4>${esc(v.headline)}</h4><p>${esc(v.explanation)}</p>${factChips(v.fact_ids)}</article>`;
}
function renderReality(d) {
  const judged = d.verdicts.filter((v) => v.verdict !== "no_data");
  const right = judged.filter((v) => v.verdict === "true").length + 0.5 * judged.filter((v) => v.verdict === "partly").length;
  const pct = judged.length ? Math.round((right / judged.length) * 100) : 0;
  const myths = d.verdicts.filter((v) => v.verdict === "myth").length;
  if (!judged.length) {
    $("#score").innerHTML = `<p>The official data couldn't settle your beliefs this time. Try adding a belief about pay, hours, or what people do all day.</p>`;
  } else $("#score").innerHTML = `<div class="ring" style="--p:${pct}"><span>${pct}%</span></div>
    <p>Your picture of this job was <b>${pct}% accurate</b>. ${myths ? `We busted <b>${myths} myth${myths > 1 ? "s" : ""}</b>.` : "Nice, no big myths!"} Hover over the grey tags to see the exact data behind each verdict.</p>`;
  $("#verdicts").innerHTML = d.verdicts.map(vcard).join("");
  $("#surprises").innerHTML = d.surprises.map((v, i) => vcard({ ...v, verdict: "true" }, i)).join("");
}

/* ---------------- test drive ---------------- */
function renderScene(i) {
  const s = state.drive.scenarios[i];
  const dots = state.drive.scenarios.map((_, j) => `<i class="${j <= i ? "on" : ""}"></i>`).join("");
  $("#drive-stage").innerHTML = `<div class="progress-dots">${dots}</div>
    <div class="scene">
      <div class="scene-top"><span class="moment">${esc(s.moment)}</span><span class="count">Moment ${i + 1} of 3</span></div>
      <div class="scene-body">
        <h3>${esc(s.title)}</h3><p class="situation">${esc(s.situation)}</p>
        <div class="choices">${s.choices.map((c, j) => `<button class="choice" data-j="${j}">${esc(c.text)}<span class="tag"></span></button>`).join("")}</div>
        <div id="after"></div>
      </div></div>`;
  $("#drive-stage .choices").addEventListener("click", (e) => {
    const b = e.target.closest(".choice"); if (!b || b.disabled) return;
    const j = +b.dataset.j;
    state.picks[i] = s.choices[j];
    [...document.querySelectorAll("#drive-stage .choice")].forEach((el, k) => {
      el.disabled = true;
      const c = s.choices[k];
      el.classList.toggle("picked", k === j);
      el.classList.toggle("aligned", c.aligned);
      $(".tag", el).textContent = (c.aligned ? "✓ How pros usually handle it · " : "Shows ") + c.trait;
    });
    const task = state.facts[s.task_id];
    $("#after").innerHTML = `<div class="insight"><b>From people in the job:</b> ${esc(s.pro_insight)}${task ? `<br><small class="trace">Built on a real task: ${esc(task.text.replace("Task: ", ""))}</small>` : ""}</div>
      <div class="feel"><p>Honestly, how did that moment feel?</p><div class="row">
        <button data-f="2">I'd enjoy this</button><button data-f="1">It's okay</button><button data-f="0">Not for me</button></div></div>`;
    $("#after .feel").addEventListener("click", (e2) => {
      const f = e2.target.closest("button"); if (!f) return;
      state.feels[i] = +f.dataset.f;
      if (i < state.drive.scenarios.length - 1) renderScene(i + 1); else renderFit();
      $("#drive").scrollIntoView({ behavior: "smooth" });
    });
  });
}
function renderFit() {
  const aligned = state.picks.filter((p) => p.aligned).length;
  const enjoy = state.feels.filter((f) => f === 2).length;
  const meh = state.feels.filter((f) => f === 1).length;
  let verdict;
  if (aligned >= 2 && enjoy >= 2) verdict = "Strong match. Your instincts and your gut both say yes. Go talk to someone who does this job.";
  else if (aligned >= 2) verdict = "Your instincts fit how pros work, but the day-to-day didn't excite you. Check the careers next door. One might fit better.";
  else if (enjoy >= 2) verdict = "You liked the work, but you'd handle it differently from most pros. That's a skill you can build. Look at the work styles below.";
  else verdict = "Maybe not this one, and finding that out now is a win. Try a career next door.";
  const styles = state.career.work_styles.slice(0, 4).join(", ");
  $("#drive-stage").innerHTML = `<div class="fit">
    <h3>Your test-drive result</h3><p>${verdict}</p>
    <div class="meters">
      <div class="meter"><b>${aligned}/3</b><div>moments you handled like a pro</div></div>
      <div class="meter"><b>${enjoy}/3</b><div>moments you'd enjoy${meh ? ` (+${meh} okay)` : ""}</div></div>
    </div>
    <p class="note">People who thrive as ${esc(state.career.title.toLowerCase())} score high on: <b>${esc(styles)}</b> (O*NET).</p>
    <button class="btn-ghost" id="redrive">Drive it again</button></div>`;
  $("#redrive").onclick = () => { state.picks = []; state.feels = []; renderScene(0); };
}

/* ---------------- road map + neighbors ---------------- */
function renderRoad(p) {
  const w = state.wages || {};
  const stage = (lvl) => p.stages.find((s) => s.level === lvl) || {};
  const band = (b) => (b ? `${kmoney(b.low)}–${kmoney(b.high)}${state.career?.top_coded && b.high === state.career.p90 ? "+" : ""}` : "");
  const stops = [
    { pin: "Now", h: "High school", p: p.hs_courses.slice(0, 3).map((c) => c.subject).join(" · ") },
    { pin: "After HS", h: "Education", p: state.career?.education || "" },
    { pin: "License", h: "Credentials", p: p.credentials.length ? p.credentials.map((c) => c.name).join(" · ") : "Usually none required" },
    ...["entry", "mid", "senior"].map((lvl) => {
      const s = stage(lvl);
      return { pin: lvl[0].toUpperCase() + lvl.slice(1), h: s.title, yrs: s.years, p: s.what_changes, pay: band(w[lvl]), sub: w[lvl]?.label, money: true };
    }),
  ];
  $("#road").innerHTML = stops.map((s) => `<div class="stop ${s.money ? "money" : ""}">
      <div class="pin">${esc(s.pin)}</div><h4>${esc(s.h || "")}</h4>
      ${s.yrs ? `<div class="yrs">${esc(s.yrs)}</div>` : ""}
      ${s.p ? `<p>${esc(s.p)}</p>` : ""}
      ${s.pay ? `<div class="pay">${s.pay}<div class="verify">${esc(s.sub)} (BLS)</div></div>` : ""}
    </div>`).join("") + `
    <div class="prep">
      <div class="prep-card"><h5>Classes to take now</h5><ul>${p.hs_courses.map((c) => `<li><b>${esc(c.subject)}</b>: ${esc(c.why)}</li>`).join("")}</ul></div>
      <div class="prep-card"><h5>Education route</h5><ol>${p.education_steps.map((x) => `<li>${esc(x)}</li>`).join("")}</ol></div>
      <div class="prep-card"><h5>Licenses &amp; certifications</h5><ul>${p.credentials.length ? p.credentials.map((c) => `<li><b>${esc(c.name)}</b>: ${esc(c.note)}</li>`).join("") : "<li>Usually none required.</li>"}</ul>
        <div class="verify">AI-suggested. Check your state's rules on <a href="https://www.careeronestop.org/Toolkit/Training/find-licenses.aspx" target="_blank" rel="noopener">CareerOneStop's License Finder</a>.</div></div>
    </div>`;
}
function renderNeighbors(p) {
  const base = state.career;
  $("#neighbors").innerHTML = p.neighbors.map((n) => {
    const c = n.card;
    const diff = c.median && base?.median ? c.median - base.median : null;
    return `<div class="ncard"><h4>${esc(c.title)}</h4><p>${esc(n.why_consider)}</p>
      <div class="mini"><span>Median <b>${money(c.median)}</b>${diff != null ? ` <span class="${diff >= 0 ? "up" : "down"}">(${diff >= 0 ? "+" : "−"}${kmoney(Math.abs(diff))})</span>` : ""}</span>
      <span>Growth <b>${c.growth_pct == null ? "n/a" : (c.growth_pct > 0 ? "+" : "") + c.growth_pct + "%"}</b></span>
      <span>${esc(c.education || "")}</span></div>
      <button class="btn-ghost" data-title="${esc(c.title)}">Test-drive this →</button></div>`;
  }).join("");
  $("#neighbors").onclick = (e) => {
    const b = e.target.closest("button[data-title]"); if (!b) return;
    careerEl.value = b.dataset.title; $("#beliefs").value = "";
    start({ career: b.dataset.title, beliefs: "", likes: state.likes || "" });
  };
}

/* ---------------- under the hood ---------------- */
function renderHood(d) {
  if (d.status !== "ok") return;
  const t = d.totals;
  const rows = d.usage.map((u) => {
    const steps = (u.trace || []).map((s) =>
      s.kind === "tool_call" ? `called <code>${esc(s.tool)}(${esc(Object.values(s.args || {}).join(", "))})</code>`
      : s.kind === "tool_result" ? `got ${s.items ?? ""} results${s.preview ? ": " + esc((Array.isArray(s.preview) ? s.preview.slice(0, 3).join(", ") : s.preview)) + "…" : ""}`
      : `<b style="color:var(--myth)">retry</b>: ${esc(s.reason.slice(0, 120))}…`).join(" → ");
    return `<tr><td><b>${esc(u.agent)}</b>${u.cache_hit ? " <span class='trace'>(reused from cache)</span>" : ""}<div class="trace">${steps || (u.cache_hit ? "0 model calls" : `${u.requests} model call${u.requests > 1 ? "s" : ""}`)}</div></td>
      <td class="num">${u.input_tokens.toLocaleString()}</td><td class="num">${u.cached_tokens.toLocaleString()}</td>
      <td class="num">${u.output_tokens.toLocaleString()}</td><td class="num">${u.seconds}s</td><td class="num">$${u.cost_usd.toFixed(5)}</td></tr>`;
  }).join("");
  const perThousand = t.cost_usd * 1000;
  $("#hood-body").innerHTML = `
    <div class="callout">
      <div class="stat"><div class="k">This run cost</div><div class="v">$${t.cost_usd.toFixed(4)}</div><div class="s">gpt-6-luna · ${t.requests} model calls</div></div>
      <div class="stat"><div class="k">Tokens (in / cached / out)</div><div class="v small">${t.input_tokens.toLocaleString()} / ${t.cached_tokens.toLocaleString()} / ${t.output_tokens.toLocaleString()}</div><div class="s">Cached input is billed at 10%</div></div>
      <div class="stat"><div class="k">1,000 students like this</div><div class="v">$${perThousand.toFixed(2)}</div><div class="s">If each student ran one exploration</div></div>
    </div>
    <table><thead><tr><th>Agent and what it did</th><th class="num">Input</th><th class="num">Cached</th><th class="num">Output</th><th class="num">Time</th><th class="num">Cost</th></tr></thead>
    <tbody>${rows}</tbody>
    <tfoot><tr><td>Total</td><td class="num">${t.input_tokens.toLocaleString()}</td><td class="num">${t.cached_tokens.toLocaleString()}</td><td class="num">${t.output_tokens.toLocaleString()}</td><td></td><td class="num">$${t.cost_usd.toFixed(5)}</td></tr></tfoot></table>
    ${d.rejections && d.rejections.length ? `<div class="reject"><b>Safety check caught ${d.rejections.length} problem${d.rejections.length > 1 ? "s" : ""}.</b> An agent's draft included something not in the official data, so it was sent back and fixed before you saw it:<ul>${d.rejections.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>` : `<div class="reject" style="background:#f2fbf6;border-color:#bfe3cf"><b style="color:var(--true)">All numbers verified.</b> Every figure on this page matched the official data on the first try.</div>`}
    <p class="note" style="margin-top:12px">Run ID ${esc(d.run_id)} · logged to logs/runs.jsonl</p>`;
}

/* ---------------- feedback (evidence from real users) ---------------- */
let fbChange = null;
$("#fb-change").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  fbChange = b.dataset.v;
  [...$("#fb-change").children].forEach((x) => x.classList.toggle("on", x === b));
});
["before", "after"].forEach((k) => $("#fb-" + k).addEventListener("input", (e) => ($("#fb-" + k + "-val").textContent = e.target.value)));
$("#fb-send").addEventListener("click", async () => {
  await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    run_id: state.result?.run_id, career: state.career?.title, changed: fbChange,
    sure_before: +$("#fb-before").value, sure_after: +$("#fb-after").value, comment: $("#fb-comment").value.trim(),
    fit_aligned: state.picks.filter((p) => p?.aligned).length, fit_enjoy: state.feels.filter((f) => f === 2).length,
  }) }).catch(() => {});
  $("#fb-send").hidden = true; $("#fb-thanks").hidden = false;
});

window.ctdStart = (o) => { careerEl.value = o.career; $("#beliefs").value = o.beliefs || ""; start(o); };
autosize();
rotatePlaceholder();
