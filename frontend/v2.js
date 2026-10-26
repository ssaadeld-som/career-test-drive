/* Career Test Drive v2: discover, saved careers + compare, career map, day-in-the-life player,
   pay by state, where to study, field ecosystem. Plain JS, no build step. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (v) => (v == null ? "n/a" : "$" + Math.round(v).toLocaleString("en-US"));
  const k = (v) => (v == null ? "n/a" : "$" + Math.round(v / 1000) + "K");
  const pct = (v) => (v == null ? "n/a" : Math.round(v * 100) + "%");
  const api = (u) => fetch(u).then((r) => r.json());
  const store = {
    get(key, d) { try { return JSON.parse(localStorage.getItem(key)) ?? d; } catch { return d; } },
    set(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* private mode */ } },
  };

  let META = null;
  let current = null; // career profile being viewed
  const state = () => $("#state").value || "";

  /* ---------------- routing ---------------- */
  const VIEWS = ["drive", "discover", "compare", "map"];
  function show(view) {
    VIEWS.forEach((v) => ($("#view-" + v).hidden = v !== view));
    $$("#tabs a").forEach((a) => a.classList.toggle("on", a.dataset.tab === view));
  }
  function route() {
    const h = location.hash || "#/";
    if (h.startsWith("#/discover")) { show("discover"); }
    else if (h.startsWith("#/compare")) { show("compare"); renderCompare(); }
    else if (h.startsWith("#/map")) { show("map"); renderMatrix(); }
    else { show("drive"); }
    window.scrollTo({ top: 0 });
  }
  window.addEventListener("hashchange", route);

  /* ---------------- saved careers ("garage") ---------------- */
  const garage = () => store.get("ctd_garage", []);
  function setGarage(g) { store.set("ctd_garage", g); $("#garage-count").textContent = g.length; syncSave(); }
  function isSaved(id) { return garage().some((x) => x.id === id); }
  function toggleSave(id, title) {
    let g = garage();
    if (isSaved(id)) g = g.filter((x) => x.id !== id);
    else g = [...g, { id, title, saved: Date.now() }];
    setGarage(g);
  }
  function syncSave() {
    const b = $("#save-btn");
    if (!b || !current) return;
    const on = isSaved(current.id);
    b.textContent = on ? "♥ Saved" : "♡ Save";
    b.classList.toggle("on", on);
  }
  $("#save-btn").addEventListener("click", () => current && toggleSave(current.id, current.title));
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-save]");
    if (b) { toggleSave(b.dataset.save, b.dataset.title); b.textContent = isSaved(b.dataset.save) ? "♥ Saved" : "♡ Save"; }
    const t = e.target.closest("[data-drive]");
    if (t) { e.preventDefault(); location.hash = "#/"; setTimeout(() => window.ctdStart({ career: t.dataset.drive, beliefs: "", likes: "" }), 50); }
  });

  /* ---------------- state picker ---------------- */
  async function loadMeta() {
    META = await api("/api/meta");
    const opts = Object.entries(META.states).sort((a, b) => a[1].localeCompare(b[1]));
    $("#state").insertAdjacentHTML("beforeend", opts.map(([c, n]) => `<option value="${c}">${esc(n)}</option>`).join(""));
    $("#f-state").innerHTML = `<option value="">All states</option>` + opts.map(([c, n]) => `<option value="${c}">${esc(n)}</option>`).join("");
    const saved = store.get("ctd_state", "");
    $("#state").value = saved; $("#f-state").value = saved;
    buildDiscoverForm();
  }
  $("#state").addEventListener("change", () => {
    store.set("ctd_state", state());
    $("#f-state").value = state();
    if (current && !$("#results").hidden) { loadProfile(current.id); loadSchools(); }
    if (!$("#view-compare").hidden) renderCompare();
  });

  /* ================================================================ career page extras */
  async function onCareer(card) {
    current = { id: card.id, title: card.title };
    syncSave();
    $("#player").innerHTML = `<div class="player-loading">Loading the day…</div>`;
    loadProfile(card.id);
    loadSchools();
    loadStory(card.id);
  }

  async function loadProfile(id) {
    const p = await api(`/api/career/${id}?state=${state()}`);
    current.profile = p;
    renderPayStages(p);
    renderTileMap(p);
    renderMajors(p);
    loadEcosystem(p);
  }

  /* ---------- plain words + day-in-the-life player ---------- */
  async function loadStory(id) {
    let s;
    try { s = await api(`/api/story/${id}`); } catch { s = null; }
    if (!s || s.error) { $("#plain").innerHTML = ""; $("#player").innerHTML = `<p class="note">The day-in-the-life story isn't available right now.</p>`; return; }
    $("#plain").innerHTML = `
      <div class="plain-card">
        <div class="plain-k">In plain words</div>
        <div class="plain-t">${esc(s.plain_title)}</div>
        <p>${esc(s.eli12)}</p>
        ${s.not_to_confuse ? `<p class="confuse"><b>Not to be confused with:</b> ${esc(s.not_to_confuse)}</p>` : ""}
      </div>`;
    $("#specs").innerHTML = s.specializations.length ? `<h3 class="sub">Different kinds of this job</h3>
      <div class="spec-grid">${s.specializations.map((x) => `<div class="spec"><b>${esc(x.name)}</b><span>${esc(x.plain)}</span></div>`).join("")}</div>` : "";
    Player(s);
  }

  const ICON = { desk: "🗂️", computer: "💻", meeting: "👥", phone: "📞", email: "📧", court: "⚖️", classroom: "🏫", patient: "🩺", lab: "🔬",
    tools: "🛠️", outdoors: "🌤️", vehicle: "🚗", kitchen: "🍳", studio: "🎨", warehouse: "📦", store: "🛒", travel: "✈️", home: "🏠", reading: "📖", presentation: "📊" };
  const SKY = (t) => { // background by time of day
    const h = parseInt(t, 10) + (/pm/i.test(t) && parseInt(t, 10) !== 12 ? 12 : 0);
    if (h < 9) return ["#ffd9a8", "#7fb3ff"]; if (h < 16) return ["#bfe0ff", "#5a9cff"]; if (h < 18) return ["#ffc59e", "#5f7fd1"]; return ["#5a6fb8", "#1b2a5c"];
  };
  function Player(story) {
    const scenes = story.scenes;
    let i = 0, playing = false, timer = null, voice = store.get("ctd_voice", false);
    const el = $("#player");
    el.innerHTML = `
      <div class="pl-stage" id="pl-stage">
        <div class="pl-progress">${scenes.map(() => `<i><b></b></i>`).join("")}</div>
        <div class="pl-scene" id="pl-scene"></div>
        <div class="pl-caption" id="pl-caption"></div>
      </div>
      <div class="pl-controls">
        <button id="pl-prev" aria-label="Previous scene">⏮</button>
        <button id="pl-play" class="big" aria-label="Play">▶</button>
        <button id="pl-next" aria-label="Next scene">⏭</button>
        <button id="pl-voice" class="${voice ? "on" : ""}" aria-label="Narration">${voice ? "🔊 Narration on" : "🔈 Narration off"}</button>
        <span class="pl-count" id="pl-count"></span>
      </div>
      <div class="pl-strip">${scenes.map((s, j) => `<button data-j="${j}"><span>${esc(s.time)}</span>${esc(s.title)}</button>`).join("")}</div>`;
    const bars = $$(".pl-progress b", el);
    function paint() {
      const s = scenes[i];
      const [a, b] = SKY(s.time);
      $("#pl-stage").style.background = `linear-gradient(160deg, ${a}, ${b})`;
      const [hh, mm] = (s.time.match(/(\d+):(\d+)/) || [0, 9, 0]).slice(1).map(Number);
      const hourDeg = ((hh % 12) + mm / 60) * 30, minDeg = mm * 6;
      $("#pl-scene").innerHTML = `
        <div class="pl-clock"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="#fff" stroke="#00356b" stroke-width="4"/>
          <line class="h" x1="50" y1="50" x2="50" y2="26" stroke="#00356b" stroke-width="6" stroke-linecap="round" style="transform:rotate(${hourDeg}deg)"/>
          <line class="m" x1="50" y1="50" x2="50" y2="14" stroke="#63aaff" stroke-width="4" stroke-linecap="round" style="transform:rotate(${minDeg}deg)"/>
          <circle cx="50" cy="50" r="4" fill="#00356b"/></svg><b>${esc(s.time)}</b></div>
        <div class="pl-icon">${ICON[s.icon] || "💼"}</div>
        <div class="pl-place">📍 ${esc(s.place)}</div>
        <h3 class="pl-title">${esc(s.title)}</h3>`;
      $("#pl-caption").innerHTML = `<span>${esc(s.narration)}</span>${story.facts?.[s.task_id] ? `<small>Based on: ${esc(story.facts[s.task_id].replace(/^Task: /, ""))}</small>` : ""}`;
      bars.forEach((bar, j) => { bar.style.transition = "none"; bar.style.width = j < i ? "100%" : "0%"; });
      $("#pl-count").textContent = `Scene ${i + 1} of ${scenes.length}`;
      $$(".pl-strip button", el).forEach((b2, j) => b2.classList.toggle("on", j === i));
    }
    function dur() { return Math.max(5200, scenes[i].narration.split(" ").length * 380); }
    function advance() { if (i < scenes.length - 1) { i++; run(); } else { stop(); } }
    function run() {
      clearTimeout(timer);
      paint();
      if (!playing) return;
      const bar = bars[i];
      requestAnimationFrame(() => { bar.style.transition = `width ${voice ? 30000 : dur()}ms linear`; bar.style.width = "100%"; });
      if (voice && "speechSynthesis" in window) {
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(`${scenes[i].time}. ${scenes[i].narration}`);
        u.rate = 1.02;
        u.onend = () => { bar.style.transition = "width .2s"; bar.style.width = "100%"; if (playing) timer = setTimeout(advance, 500); };
        speechSynthesis.speak(u);
      } else timer = setTimeout(advance, dur());
    }
    function play() { playing = true; $("#pl-play").textContent = "⏸"; if (i === scenes.length - 1 && bars[i].style.width === "100%") i = 0; run(); }
    function stop() { playing = false; clearTimeout(timer); if ("speechSynthesis" in window) speechSynthesis.cancel(); $("#pl-play").textContent = "▶"; }
    $("#pl-play").onclick = () => (playing ? stop() : play());
    $("#pl-next").onclick = () => { if (i < scenes.length - 1) { i++; run(); } };
    $("#pl-prev").onclick = () => { if (i > 0) { i--; run(); } };
    $("#pl-voice").onclick = (e) => { voice = !voice; store.set("ctd_voice", voice); e.target.classList.toggle("on", voice); e.target.textContent = voice ? "🔊 Narration on" : "🔈 Narration off"; if (playing) run(); };
    $(".pl-strip", el).onclick = (e) => { const b2 = e.target.closest("button"); if (b2) { i = +b2.dataset.j; run(); } };
    $("#pl-stage").onclick = (e) => { if (!e.target.closest("button")) playing ? stop() : play(); };
    paint();
  }

  /* ---------- pay ---------- */
  function renderPayStages(p) {
    const pay = p.pay;
    const scope = pay.scope === "U.S." ? "U.S." : pay.scope;
    const pre = pay.major_is_pre_professional;
    $("#paystages").innerHTML = `
      <div class="ps-grid">
        <div class="ps"><div class="ps-k">Starting out</div><div class="ps-v">${money(pay.bls_start)}</div><div class="ps-s">Lowest-paid 10% in ${esc(scope)} (BLS). A fair guide to a first job.</div></div>
        <div class="ps"><div class="ps-k">Typical (about 5–10 years in)</div><div class="ps-v">${money(pay.bls_median)}</div><div class="ps-s">Median in ${esc(scope)} (BLS)</div></div>
        <div class="ps"><div class="ps-k">Senior / top earners</div><div class="ps-v">${money(pay.bls_senior)}${pay.bls_senior === 239200 ? "+" : ""}</div><div class="ps-s">Top 10% in ${esc(scope)} (BLS)</div></div>
      </div>
      ${pay.major ? `<div class="ps-major">
        <div><b>${pre ? "Before the professional degree: " : ""}${esc(pay.major)}</b> graduates (College Scorecard, national)</div>
        <div class="ps-bars">
          ${bar("1 year after graduating", pay.major_1yr, Math.max(pay.major_5yr || 0, pay.major_1yr || 0, 1))}
          ${bar("5 years after graduating", pay.major_5yr, Math.max(pay.major_5yr || 0, pay.major_1yr || 0, 1))}
        </div>
        ${pre ? `<p class="note">This job needs graduate or professional school, so these are earnings for the usual <i>undergraduate</i> major on the way there, not for the job itself.</p>` : ""}
      </div>` : ""}`;
  }
  function bar(label, v, max) {
    return `<div class="hb"><span>${label}</span><div><i style="width:${v ? (v / max) * 100 : 0}%"></i></div><b>${money(v)}</b></div>`;
  }

  const TILES = { AK: [0, 0], ME: [10, 0], VT: [9, 1], NH: [10, 1], WA: [0, 2], ID: [1, 2], MT: [2, 2], ND: [3, 2], MN: [4, 2], IL: [5, 2], WI: [6, 2], MI: [7, 2], NY: [8, 2], RI: [9, 2], MA: [10, 2],
    OR: [0, 3], NV: [1, 3], WY: [2, 3], SD: [3, 3], IA: [4, 3], IN: [5, 3], OH: [6, 3], PA: [7, 3], NJ: [8, 3], CT: [9, 3], CA: [0, 4], UT: [1, 4], CO: [2, 4], NE: [3, 4], MO: [4, 4], KY: [5, 4],
    WV: [6, 4], VA: [7, 4], MD: [8, 4], DE: [9, 4], AZ: [1, 5], NM: [2, 5], KS: [3, 5], AR: [4, 5], TN: [5, 5], NC: [6, 5], SC: [7, 5], DC: [8, 5], OK: [3, 6], LA: [4, 6], MS: [5, 6], AL: [6, 6], GA: [7, 6],
    HI: [0, 7], TX: [3, 7], FL: [8, 7] };
  function renderTileMap(p) {
    const rows = p.state_wages.by_state;
    const by = Object.fromEntries(rows.map((r) => [r.state, r]));
    const vals = rows.map((r) => r.median).filter(Boolean);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const shade = (v) => { if (!v) return "#e6ebf2"; const t = hi === lo ? 1 : (v - lo) / (hi - lo); return `hsl(212, ${55 + t * 35}%, ${88 - t * 60}%)`; };
    $("#tilemap").innerHTML = Object.entries(TILES).map(([s, [x, y]]) => {
      const r = by[s];
      const v = r?.median;
      const dark = v && (v - lo) / (hi - lo || 1) > 0.5;
      return `<button class="tile ${s === state() ? "sel" : ""}" style="grid-column:${x + 1};grid-row:${y + 1};background:${shade(v)};color:${dark ? "#fff" : "#0b1f3a"}"
        title="${esc(r ? `${r.name}: median ${money(v)}, ${r.employment?.toLocaleString() ?? "n/a"} jobs` : s + ": no data")}" data-st="${s}"><b>${s}</b><small>${v ? k(v) : "–"}</small></button>`;
    }).join("");
    $("#tilemap").onclick = (e) => { const t = e.target.closest(".tile"); if (t) { $("#state").value = t.dataset.st; $("#state").dispatchEvent(new Event("change")); } };
    const topPay = rows.slice(0, 5);
    const topJobs = [...rows].sort((a, b) => (b.employment || 0) - (a.employment || 0)).slice(0, 5);
    const sel = p.state_wages.selected;
    $("#statelists").innerHTML = `
      ${sel ? `<div class="sl sel"><h4>${esc(sel.name)}</h4><p>Median <b>${money(sel.median)}</b> · range ${k(sel.p10)}–${k(sel.p90)} · ${sel.employment?.toLocaleString() ?? "n/a"} jobs${sel.concentration ? ` · ${sel.concentration >= 1 ? "more" : "fewer"} of these jobs than average (${sel.concentration}×)` : ""}</p></div>` : `<div class="sl"><p class="note">Pick your state at the top to see local pay everywhere on this page.</p></div>`}
      <div class="sl"><h4>Highest pay</h4><ol>${topPay.map((r) => `<li>${esc(r.name)} <b>${money(r.median)}</b></li>`).join("")}</ol></div>
      <div class="sl"><h4>Most jobs</h4><ol>${topJobs.map((r) => `<li>${esc(r.name)} <b>${r.employment?.toLocaleString() ?? "n/a"}</b></li>`).join("")}</ol></div>`;
  }

  /* ---------- majors + schools ---------- */
  function renderMajors(p) {
    if (!p.majors.length) { $("#majors").innerHTML = `<p class="note">No matching college programs. Most people enter this job through training on the job, an apprenticeship, or a short course (BLS: ${esc(p.training || "n/a")}).</p>`; return; }
    $("#majors").innerHTML = `
      <h3 class="sub" style="margin-top:6px">${p.majors_are_pre_professional ? "Undergraduate majors that lead toward this job (then graduate/professional school)" : "College majors that lead to this job"}</h3>
      <table class="dt"><thead><tr><th>Major</th><th>Credential</th><th class="r">Earnings 1 yr after</th><th class="r">5 yrs after</th><th class="r">Schools offering it</th></tr></thead>
      <tbody>${p.majors.map((m) => `<tr><td>${esc(m.title)}</td><td>${esc(m.credential)}</td><td class="r">${money(m.earn_1yr)}</td><td class="r">${money(m.earn_5yr)}</td><td class="r">${m.programs.toLocaleString()}</td></tr>`).join("")}</tbody></table>
      <p class="note">Earnings: national median for graduates of that major (U.S. Dept. of Education College Scorecard). High-school classes to take now: <b>${esc(p.hs_subjects.join(" · ") || "n/a")}</b></p>`;
  }
  ["#f-state", "#f-level", "#f-control", "#f-sort"].forEach((s) => $(s).addEventListener("change", loadSchools));
  async function loadSchools() {
    if (!current) return;
    const q = new URLSearchParams({ career: current.id, state: $("#f-state").value, levels: $("#f-level").value, sort: $("#f-sort").value });
    if ($("#f-control").value) q.set("control", $("#f-control").value);
    const r = await api("/api/schools?" + q);
    if (!r.rows.length) { $("#schools").innerHTML = `<p class="note">No matching programs with these filters. Try "All states" or another program type.</p>`; return; }
    $("#schools").innerHTML = `
      <table class="dt schools"><thead><tr><th>School</th><th>Program</th><th class="r">Grads/yr</th><th class="r">Earnings 1 yr</th><th class="r">5 yrs</th><th class="r">Grad rate</th><th class="r">Admit rate</th><th class="r">Avg net price/yr</th></tr></thead>
      <tbody>${r.rows.map((s) => `<tr><td><b>${esc(s.school)}</b><small>${esc(s.city)}, ${esc(s.state)} · ${esc(s.type)}${s.url ? ` · <a href="https://${esc(s.url)}" target="_blank" rel="noopener">site</a>` : ""}</small></td>
        <td>${esc(s.program)}<small>${esc(s.credential)}</small></td><td class="r">${s.grads_per_year ?? "–"}</td><td class="r">${money(s.earn_1yr)}</td><td class="r">${money(s.earn_5yr)}</td>
        <td class="r">${pct(s.grad_rate)}</td><td class="r">${pct(s.admit_rate)}</td><td class="r">${money(s.net_price)}</td></tr>`).join("")}</tbody></table>
      <p class="note">Showing ${r.rows.length} of ${r.total.toLocaleString()} programs. Ranked by ${$("#f-sort").selectedOptions[0].text.toLowerCase()} (College Scorecard), not prestige. "n/a" means the government withholds small-sample data.</p>`;
  }

  /* ---------- field ecosystem ---------- */
  const ZONES = { 5: "Extensive prep (grad school)", 4: "Bachelor's level", 3: "Some training (2-yr / apprenticeship)", 2: "Some prep (HS + training)", 1: "Little prep" };
  async function loadEcosystem(p) {
    $("#eco").innerHTML = `<p class="note">Mapping the ${esc(p.vertical.name)} field…</p>`;
    const e = await api(`/api/ecosystem/${p.vertical.code}`);
    const big = e.careers.length > 30;
    let onlySub = big;
    function draw() {
      const list = e.careers.filter((c) => !onlySub || c.sub === p.vertical.sub);
      const caps = e.capabilities.filter((cap) => list.some((c) => c.capability === cap));
      const zones = [5, 4, 3, 2, 1].filter((z) => list.some((c) => (c.job_zone || 2) === z));
      const related = new Set(p.related.map((r) => r.id));
      const cell = (z, cap) => list.filter((c) => (c.job_zone || 2) === z && c.capability === cap).map((c) => `
          <button class="node ${c.id === p.id ? "me" : related.has(c.id) ? "rel" : ""}" data-id="${c.id}" title="${esc(e.plain?.[c.id] || c.title)}">
            <b>${esc(c.title)}</b><span>${esc(e.plain?.[c.id] || "")}</span>${c.median ? `<em>${k(c.median)}</em>` : ""}</button>`).join("");
      const outside = p.related.filter((r) => !e.careers.some((c) => c.id === r.id));
      $("#eco").innerHTML = `
        ${e.intro ? `<p class="lede">${esc(e.intro)}</p>` : ""}
        <div class="eco-legend"><span class="lg me"></span> this job <span class="lg rel"></span> closely related <span class="lg"></span> same field
          ${big ? `<label class="eco-toggle"><input type="checkbox" id="eco-all" ${onlySub ? "" : "checked"}> Show the whole field (${e.careers.length} jobs)</label>` : ""}</div>
        <div class="eco-grid" style="grid-template-columns: 160px repeat(${caps.length}, minmax(170px, 1fr))">
          <div class="eco-h corner">Preparation ↓ · What you'd mostly do →</div>
          ${caps.map((c) => `<div class="eco-h">${esc(c)}</div>`).join("")}
          ${zones.map((z) => `<div class="eco-z">${esc(ZONES[z])}</div>${caps.map((cap) => `<div class="eco-c">${cell(z, cap)}</div>`).join("")}`).join("")}
        </div>
        ${outside.length ? `<h3 class="sub">Connected jobs in other fields</h3><div class="eco-out">${outside.map((r) => `<a href="#" data-drive="${esc(r.title)}">${esc(r.title)} →</a>`).join("")}</div>` : ""}
        <p class="note">Rows: how much preparation the job needs (O*NET Job Zone). Columns: the main type of work (O*NET interest profile). Click a job to test-drive it.</p>`;
      const t = $("#eco-all");
      if (t) t.onchange = () => { onlySub = !t.checked; draw(); };
      $("#eco .eco-grid").onclick = (ev) => {
        const n = ev.target.closest(".node");
        if (n && n.dataset.id !== p.id) window.ctdStart({ career: e.careers.find((c) => c.id === n.dataset.id).title, beliefs: "", likes: "" });
      };
    }
    draw();
  }

  /* ================================================================ compare */
  async function renderCompare() {
    const g = garage();
    if (!g.length) {
      $("#compare").innerHTML = `<div class="empty"><h3>Nothing saved yet</h3><p>While you test-drive a career or browse your matches, tap <b>♡ Save</b>. Then come back here to compare.</p>
        <p><a class="btn-ghost" href="#/discover">Find careers that fit me</a> <a class="btn-ghost" href="#/">Test-drive a career</a></p></div>`;
      return;
    }
    const ids = g.slice(0, 4).map((x) => x.id);
    const cs = await api(`/api/compare?ids=${ids.join(",")}&state=${state()}`);
    const ctx = (c, key) => c.work_context[key] || "n/a";
    const LV = { "very low": 1, low: 2, moderate: 3, high: 4, "very high": 5 };
    const rows = [
      ["Basics", null],
      ["Field", (c) => esc(c.vertical.name)],
      ["Mostly", (c) => esc(c.capability.primary)],
      ["Pay" + (state() ? ` (${$("#state").selectedOptions[0].text})` : " (U.S.)"), null],
      ["Starting pay (BLS 10th pct.)", (c) => money(c.pay.bls_start), (c) => c.pay.bls_start],
      ["Typical pay (BLS median)", (c) => money(c.pay.bls_median), (c) => c.pay.bls_median],
      ["Top earners (BLS 90th pct.)", (c) => money(c.pay.bls_senior), (c) => c.pay.bls_senior],
      ["Grads of the main major: 1 yr after", (c) => c.pay.major ? `${money(c.pay.major_1yr)}<small>${esc(c.pay.major)}${c.pay.major_is_pre_professional ? " (undergrad route)" : ""}</small>` : "n/a", (c) => c.pay.major_1yr],
      ["…and 5 yrs after", (c) => money(c.pay.major_5yr), (c) => c.pay.major_5yr],
      ["Outlook", null],
      ["Job growth 2025–35 (all jobs +3.5%)", (c) => c.growth_pct == null ? "n/a" : (c.growth_pct > 0 ? "+" : "") + c.growth_pct + "%", (c) => c.growth_pct],
      ["Openings per year", (c) => c.openings?.toLocaleString() ?? "n/a", (c) => c.openings],
      ["Getting there", null],
      ["Typical entry education", (c) => esc(c.education || "n/a")],
      ["Years of school after HS", (c) => c.edu_years ?? "n/a", (c) => (c.edu_years == null ? null : -c.edu_years)],
      ["On-the-job training", (c) => esc(c.training || "None")],
      ["College majors", (c) => esc(c.majors.slice(0, 3).map((m) => m.title).join("; ") || "Training on the job")],
      ["High-school classes", (c) => esc(c.hs_subjects.join(" · ") || "n/a")],
      ["Skills & personality", null],
      ["Key skills", (c) => esc(c.skills.slice(0, 5).join(", "))],
      ["People who thrive are…", (c) => esc(c.work_styles.slice(0, 4).join(", "))],
      ["Day to day", null],
      ["Work weeks over 40 hrs", (c) => (c.pct_over_40_hours == null ? "n/a" : Math.round(c.pct_over_40_hours) + "%"), (c) => (c.pct_over_40_hours == null ? null : -c.pct_over_40_hours)],
      ["Sitting", (c) => ctx(c, "Time spent sitting")],
      ["Outdoors", (c) => ctx(c, "Working outdoors")],
      ["Face-to-face with people", (c) => ctx(c, "Face-to-face talking")],
      ["Deadline pressure", (c) => ctx(c, "Deadline pressure"), (c) => -(LV[ctx(c, "Deadline pressure")] || 3)],
      ["Self-employed", (c) => (c.self_employed_pct == null ? "n/a" : c.self_employed_pct + "%")],
    ];
    const best = (fn) => { const v = cs.map(fn); const m = Math.max(...v.filter((x) => x != null)); return v.map((x) => x != null && x === m && v.filter((y) => y === m).length < cs.length); };
    $("#compare").innerHTML = `
      <div class="cmp-wrap"><table class="cmp">
        <thead><tr><th></th>${cs.map((c) => `<th><div class="cmp-t">${esc(c.title)}</div>
          <div class="cmp-a"><a href="#" data-drive="${esc(c.title)}">Test-drive</a> · <a href="#" class="rm" data-rm="${c.id}">Remove</a></div></th>`).join("")}</tr></thead>
        <tbody>${rows.map(([label, f, num]) => {
          if (!f) return `<tr class="grp"><td colspan="${cs.length + 1}">${label}</td></tr>`;
          const win = num ? best(num) : cs.map(() => false);
          return `<tr><th>${label}</th>${cs.map((c, j) => `<td class="${win[j] ? "win" : ""}">${f(c)}</td>`).join("")}</tr>`;
        }).join("")}</tbody></table></div>
      ${g.length > 4 ? `<p class="note">Showing your first 4 saved careers. Remove one to compare others.</p>` : ""}`;
    $$("#compare [data-rm]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); setGarage(garage().filter((x) => x.id !== a.dataset.rm)); renderCompare(); }));
  }

  /* ================================================================ career map (verticals x capabilities) */
  let MATRIX = null;
  async function renderMatrix() {
    MATRIX = MATRIX || (await api("/api/matrix"));
    const m = MATRIX;
    const max = Math.max(...m.rows.flatMap((r) => m.capabilities.map((c) => r.cells[c].length)));
    $("#matrix").innerHTML = `
      <div class="mx-wrap"><table class="mx"><thead><tr><th>Field ↓ / Mostly… →</th>${m.capabilities.map((c) => `<th>${esc(c)}</th>`).join("")}<th>All</th></tr></thead>
      <tbody>${m.rows.map((r) => `<tr><th>${esc(r.name)}</th>${m.capabilities.map((c) => {
        const n = r.cells[c].length;
        return `<td><button class="mx-c" data-v="${r.code}" data-c="${esc(c)}" style="background:rgba(0,53,107,${n ? 0.08 + 0.85 * (n / max) : 0});color:${n / max > 0.45 ? "#fff" : "#0b1f3a"}" ${n ? "" : "disabled"}>${n || ""}</button></td>`;
      }).join("")}<td class="mx-t">${r.total}</td></tr>`).join("")}</tbody></table></div>
      <div id="mx-list" class="mx-list"><p class="note">Click a number to see those careers.</p></div>`;
    $("#matrix .mx").onclick = (e) => {
      const b = e.target.closest(".mx-c"); if (!b) return;
      $$("#matrix .mx-c").forEach((x) => x.classList.remove("sel")); b.classList.add("sel");
      const r = m.rows.find((x) => x.code === b.dataset.v);
      const list = r.cells[b.dataset.c];
      $("#mx-list").innerHTML = `<h3>${esc(r.name)} · ${esc(b.dataset.c)} <small>${list.length} careers</small></h3>
        <div class="mx-items">${list.map((c) => `<div class="mx-i"><span>${esc(c.title)}</span><span><a href="#" data-drive="${esc(c.title)}">Test-drive</a> <button class="link" data-save="${c.id}" data-title="${esc(c.title)}">${isSaved(c.id) ? "♥ Saved" : "♡ Save"}</button></span></div>`).join("")}</div>`;
      $("#mx-list").scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
  }

  /* ================================================================ discover */
  const profile = { strengths: [], subjects_like: [], subjects_dislike: [], work_with: [], values: [], interests: [], setting: null, activity: null, max_school_years: null };
  function buildDiscoverForm() {
    const sources = {
      strengths: META.strengths.map((x) => [x, x]), work_with: META.work_with.map((x) => [x, x]), values: META.values.map((x) => [x, x]),
      subjects_like: META.subjects.map((s) => [s.key, s.label]), subjects_dislike: META.subjects.map((s) => [s.key, s.label]),
    };
    $$(".chipset").forEach((box) => {
      const key = box.dataset.key;
      const opts = box.dataset.opts ? box.dataset.opts.split("|").map((x) => [x, x]) : sources[key];
      box.innerHTML = opts.map(([v, l]) => `<button type="button" class="ch" data-v="${esc(v)}">${esc(l)}</button>`).join("");
      box.onclick = (e) => {
        const b = e.target.closest(".ch"); if (!b) return;
        let v = b.dataset.v;
        if (box.classList.contains("single")) {
          if (key === "max_school_years") v = v === "8+" ? 8 : +v;
          const on = profile[key] === v;
          profile[key] = on ? null : v;
          $$(".ch", box).forEach((x) => x.classList.toggle("on", !on && x === b));
        } else {
          const other = key === "subjects_like" ? "subjects_dislike" : key === "subjects_dislike" ? "subjects_like" : null;
          const arr = profile[key];
          const at = arr.indexOf(v);
          if (at >= 0) arr.splice(at, 1); else { arr.push(v); if (other) { const o = profile[other].indexOf(v); if (o >= 0) { profile[other].splice(o, 1); $(`.chipset[data-key="${other}"] .ch[data-v="${CSS.escape(v)}"]`).classList.remove("on"); } } }
          b.classList.toggle("on", at < 0);
        }
        updateMeter();
      };
    });
  }
  $("#interest-input").addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== ",") return;
    e.preventDefault();
    const v = e.target.value.trim();
    if (v && !profile.interests.includes(v) && profile.interests.length < 12) profile.interests.push(v);
    e.target.value = ""; renderTags(); updateMeter();
  });
  function renderTags() {
    $("#interest-tags").innerHTML = profile.interests.map((t, i) => `<span class="tag">${esc(t)}<button type="button" data-i="${i}" aria-label="Remove">×</button></span>`).join("");
  }
  $("#interest-tags").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { profile.interests.splice(+b.dataset.i, 1); renderTags(); updateMeter(); } });
  $("#free-text").addEventListener("input", updateMeter);

  function signals() {
    const ft = $("#free-text").value.trim().split(/\s+/).filter(Boolean).length;
    return profile.strengths.length + profile.subjects_like.length + profile.subjects_dislike.length + profile.work_with.length + profile.values.length
      + profile.interests.length + !!profile.setting + !!profile.activity + (profile.max_school_years != null) + Math.min(3, Math.floor(ft / 6));
  }
  function updateMeter() {
    const n = signals();
    $("#sig-n").textContent = n;
    $("#sig-bar").style.width = Math.min(100, (n / 16) * 100) + "%";
    const msg = n < 5 ? `Tell us ${5 - n} more thing${5 - n > 1 ? "s" : ""} to unlock suggestions.`
      : n < 9 ? `Unlocked: <b>fields to explore</b> and 5 careers. ${9 - n} more for sharper picks.`
      : n < 14 ? `Unlocked: <b>8 specific careers</b>. ${14 - n} more to add majors and schools.`
      : `Unlocked: <b>10 careers, majors and schools</b>${state() ? " in " + esc($("#state").selectedOptions[0].text) : ""}.`;
    $("#sig-msg").innerHTML = msg;
    $("#disc-go").disabled = n < 5;
  }
  $("#disc-go").addEventListener("click", async () => {
    const body = { ...profile, setting: profile.setting === "Mix of both" ? null : profile.setting, activity: profile.activity === "Mix" ? null : profile.activity,
      free_text: $("#free-text").value.trim(), state: state() || null };
    const out = $("#disc-results");
    out.hidden = false;
    out.innerHTML = `<div class="crew-mini"><span class="spin"></span> Reading your profile and matching 774 careers…</div>`;
    out.scrollIntoView({ behavior: "smooth" });
    $("#disc-go").disabled = true;
    const r = await fetch("/api/discover", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((x) => x.json()).catch(() => ({ status: "error" }));
    $("#disc-go").disabled = false;
    if (r.status !== "ok") { out.innerHTML = `<div class="blocked-card"><h3>${r.status === "need_more" ? "Tell us a bit more" : "We couldn't do that"}</h3><p>${esc(r.message || "Please add a few more things about you and try again.")}</p></div>`; return; }
    renderDiscover(r);
  });
  async function renderDiscover(r) {
    const tierName = { explorer: "Fields to explore", focused: "Careers that fit you", curated: "Your curated list" }[r.tier.name];
    const out = $("#disc-results");
    out.innerHTML = `
      <div class="block-title"><h2>${tierName}</h2></div>
      ${r.summary ? `<p class="lede">${esc(r.summary)}</p>` : ""}
      <div class="fields">${r.fields.map((f, i) => `<div class="field-card"><span class="kicker">#${i + 1} field</span><b>${esc(f.vertical)}</b><small>e.g. ${esc(f.examples.join(", "))}</small></div>`).join("")}</div>
      <div class="dcards">${r.careers.map((c) => `
        <article class="dcard">
          <div class="dc-top"><h3>${esc(c.title)}</h3><span class="dc-cap">${esc(c.capability)}</span></div>
          <p class="dc-why">${esc(c.why || c.reasons.join(". "))}</p>
          <div class="dc-facts"><span>Median <b>${money(c.median)}</b></span><span>Growth <b>${c.growth_pct > 0 ? "+" : ""}${c.growth_pct}%</b></span><span>${esc(c.education)}</span></div>
          ${r.tier.name !== "explorer" ? `<div class="dc-more"><span>Classes: ${esc(c.hs_subjects.join(" · ") || "n/a")}</span>${c.majors.length ? `<span>Majors: ${esc(c.majors.join("; "))}</span>` : ""}</div>` : ""}
          <div class="dc-act"><a href="#" class="btn-ghost" data-drive="${esc(c.title)}">Test-drive →</a><button class="btn-save small" data-save="${c.id}" data-title="${esc(c.title)}">${isSaved(c.id) ? "♥ Saved" : "♡ Save"}</button></div>
          ${r.tier.name === "curated" ? `<div class="dc-schools" data-schools="${c.id}"></div>` : ""}
        </article>`).join("")}</div>
      <div class="callout-next"><b>Your next step:</b> ${esc(r.next_step)}</div>
      ${r.tier.need ? `<p class="note">Tell us ${r.tier.need} more thing${r.tier.need > 1 ? "s" : ""} above to unlock ${r.tier.name === "explorer" ? "more specific careers" : "majors and schools near you"}.</p>` : ""}
      <p class="note">Matched on O*NET interest profiles, knowledge areas and work context, plus BLS pay and growth. This run: ${r.totals.input_tokens + r.totals.output_tokens} tokens, $${r.totals.cost_usd.toFixed(4)}.</p>`;
    if (r.tier.name === "curated") {
      for (const c of r.careers.slice(0, 10)) {
        const q = new URLSearchParams({ career: c.id, state: state(), levels: "2,3", limit: "3" });
        api("/api/schools?" + q).then((s) => {
          const box = $(`[data-schools="${c.id}"]`);
          if (box && s.rows.length) box.innerHTML = `<b>Schools${state() ? " in " + esc($("#state").selectedOptions[0].text) : ""}:</b> ` + s.rows.map((x) => `${esc(x.school)} <small>(${esc(x.credential)}, ${money(x.earn_5yr || x.earn_1yr)})</small>`).join(" · ");
        });
      }
    }
  }

  /* ---------------- boot ---------------- */
  window.v2 = { show, onCareer };
  setGarage(garage());
  loadMeta().then(updateMeter);
  route();
})();
