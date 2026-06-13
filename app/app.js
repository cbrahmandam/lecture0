/* Digital History Taking — patient terminal + doctor console (prototype).
   No framework, no build step. State lives in `state`; render() repaints #app. */

const state = {
  role: "home",          // 'home' | 'patient' | 'doctor'
  screen: "start",       // patient flow screens
  lang: "en",
  // working patient session
  mobile: "",
  patient: null,         // existing record if found
  draft: {},             // new-patient fields
  transcript: "",
  english: "",
  diagnosis: "",
  visitType: "new",      // 'new' | 'followup' | 'new_issue'
  lastVisit: null,
  lastToken: null,
  // doctor console
  doctorSearch: "",
  selectedMobile: null,
};

const root = document.getElementById("app");
const el = (html) => { const d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstChild; };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------- Speech: prompt read-aloud + recognition ---------- */
function speak(text, lang) {
  try {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = I18N[lang] ? I18N[lang].speechLang : "en-IN";
    u.rate = 0.95;
    window.speechSynthesis.speak(u);
  } catch (e) { /* non-fatal */ }
}

let recognition = null;
let recognizing = false;
function speechSupported() {
  return "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
}
function startRecognition(lang, onPartial, onFinal, onEnd) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { onEnd && onEnd(); return; }
  recognition = new SR();
  recognition.lang = I18N[lang] ? I18N[lang].speechLang : "en-IN";
  recognition.continuous = true;
  recognition.interimResults = true;
  let finalText = "";
  recognition.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText += r[0].transcript + " ";
      else interim += r[0].transcript;
    }
    onPartial && onPartial((finalText + interim).trim());
  };
  recognition.onerror = () => {};
  recognition.onend = () => { recognizing = false; onFinal && onFinal(finalText.trim()); onEnd && onEnd(); };
  recognizing = true;
  recognition.start();
}
function stopRecognition() {
  if (recognition && recognizing) { try { recognition.stop(); } catch (e) {} }
}

/* ---------- Helpers ---------- */
function go(screen) { state.screen = screen; render(); }
function tt(key, vars) { return t(state.lang, key, vars); }

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch (e) { return iso; }
}

/* ============================================================ */
/* RENDER                                                       */
/* ============================================================ */
function render() {
  root.innerHTML = "";
  root.appendChild(appbar());
  if (state.role === "doctor") root.appendChild(doctorView());
  else if (state.role === "patient") root.appendChild(patientView());
  else root.appendChild(homeView());
}

function appbar() {
  const node = el(`
    <div class="appbar">
      <div class="brand">
        <span class="dot"></span>
        <div>${esc(tt("appName"))}<small>${state.role === "doctor" ? "Doctor Console" : "Patient Terminal"}</small></div>
      </div>
      <div class="right" id="appbar-right"></div>
    </div>`);
  const right = node.querySelector("#appbar-right");
  if (state.role === "home") {
    const b = el(`<button class="btn ghost">${esc(tt("doctorConsole"))}</button>`);
    b.onclick = () => { state.role = "doctor"; render(); };
    right.appendChild(b);
  } else {
    const b = el(`<button class="btn subtle">⟵ Home</button>`);
    b.onclick = () => { resetSession(); state.role = "home"; state.selectedMobile = null; render(); };
    right.appendChild(b);
  }
  return node;
}

function resetSession() {
  state.screen = "start"; state.mobile = ""; state.patient = null; state.draft = {};
  state.transcript = ""; state.english = ""; state.diagnosis = ""; state.visitType = "new";
  state.lastVisit = null; state.lastToken = null;
}

/* ---------- HOME ---------- */
function homeView() {
  const wrap = el(`
    <div class="screen">
      <div class="card center">
        <h1>${esc(tt("appName"))}</h1>
        <p class="lead">${esc(tt("tagline"))}</p>
        <div class="spacer"></div>
        <button class="btn big" id="begin">▶  Touch to begin</button>
        <div class="spacer"></div>
        <button class="btn subtle" id="doc">${esc(tt("doctorConsole"))} →</button>
      </div>
    </div>`);
  wrap.querySelector("#begin").onclick = () => { state.role = "patient"; resetSession(); go("language"); };
  wrap.querySelector("#doc").onclick = () => { state.role = "doctor"; render(); };
  return wrap;
}

/* ---------- PATIENT FLOW ---------- */
function patientView() {
  switch (state.screen) {
    case "language": return screenLanguage();
    case "mobile": return screenMobile();
    case "existing_welcome": return screenExistingWelcome();
    case "new_name": return screenNewName();
    case "new_details": return screenNewDetails();
    case "describe": return screenDescribe();
    case "token": return screenToken();
    default: return screenLanguage();
  }
}

function backBtn(target) {
  const b = el(`<button class="btn ghost" style="flex:0 0 auto">${esc(tt("back"))}</button>`);
  b.onclick = () => go(target);
  return b;
}

function promptBubble(text) {
  const node = el(`<div class="prompt-bubble"><span class="speaker" title="Read aloud">🔊</span><div>${esc(text)}</div></div>`);
  node.querySelector(".speaker").onclick = () => speak(text, state.lang);
  return node;
}

function screenLanguage() {
  const wrap = el(`
    <div class="screen"><div class="card">
      <h2>${esc(tt("chooseLanguage"))} / Choose language</h2>
      <p class="hint">${esc(tt("languageHint"))}</p>
      <div class="tiles" id="tiles"></div>
    </div></div>`);
  const tiles = wrap.querySelector("#tiles");
  ["en", "hi", "te"].forEach((code) => {
    const tile = el(`<button class="tile"><div class="big-label">${esc(I18N[code].label)}</div><div class="sub">${esc(I18N[code].appName)}</div></button>`);
    tile.onclick = () => { state.lang = code; go("mobile"); speak(t(code, "enterMobile"), code); };
    tiles.appendChild(tile);
  });
  return wrap;
}

function screenMobile() {
  const wrap = el(`
    <div class="screen"><div class="card">
      ${promptBubbleHTML(tt("enterMobile"))}
      <label class="field">
        <input type="tel" id="mob" inputmode="numeric" maxlength="10" placeholder="${esc(tt("mobilePlaceholder"))}" value="${esc(state.mobile)}">
      </label>
      <div class="err" id="err"></div>
      <div class="btn-row" id="row"></div>
    </div></div>`);
  bindSpeaker(wrap, tt("enterMobile"));
  const row = wrap.querySelector("#row");
  row.appendChild(backBtn("language"));
  const next = el(`<button class="btn">${esc(tt("continue"))}</button>`);
  row.appendChild(next);
  const input = wrap.querySelector("#mob");
  input.oninput = () => { input.value = input.value.replace(/\D/g, "").slice(0, 10); };
  next.onclick = () => {
    const v = input.value.trim();
    if (!/^\d{10}$/.test(v)) { wrap.querySelector("#err").textContent = tt("mobileInvalid"); return; }
    state.mobile = v;
    const existing = Store.getByMobile(v);
    if (existing) {
      state.patient = existing;
      // honour patient's saved language but keep current selection for the session
      go("existing_welcome");
      speak(t(state.lang, "welcomeBack", { name: existing.name }), state.lang);
    } else {
      state.draft = { mobile: v };
      go("new_name");
      speak(t(state.lang, "enterName"), state.lang);
    }
  };
  setTimeout(() => input.focus(), 50);
  return wrap;
}

/* existing patient: follow-up vs new issue */
function screenExistingWelcome() {
  const p = state.patient;
  const wrap = el(`
    <div class="screen"><div class="card">
      ${promptBubbleHTML(tt("welcomeBack", { name: p.name }))}
      <div class="option-list" id="opts"></div>
      <div class="btn-row">${""}</div>
    </div></div>`);
  bindSpeaker(wrap, tt("welcomeBack", { name: p.name }));
  const opts = wrap.querySelector("#opts");
  const o1 = el(`<button class="option"><span class="num">1</span><span>${esc(tt("followUpReports"))}</span></button>`);
  const o2 = el(`<button class="option"><span class="num">2</span><span>${esc(tt("newIssue"))}</span></button>`);
  o1.onclick = () => { state.visitType = "followup"; go("describe"); speak(t(state.lang, "describeIssue"), state.lang); };
  o2.onclick = () => {
    // New issue: generate a token straightaway (no fresh description required by spec)
    state.visitType = "new_issue";
    finalizeSave(false);
  };
  opts.appendChild(o1); opts.appendChild(o2);
  const back = el(`<div class="btn-row"></div>`); back.appendChild(backBtn("mobile"));
  wrap.querySelector(".card").appendChild(back);
  return wrap;
}

function screenNewName() {
  const wrap = el(`
    <div class="screen"><div class="card">
      ${promptBubbleHTML(tt("enterName"))}
      <label class="field"><input type="text" id="name" placeholder="${esc(tt("namePlaceholder"))}" value="${esc(state.draft.name || "")}"></label>
      <div class="err" id="err"></div>
      <div class="btn-row" id="row"></div>
    </div></div>`);
  bindSpeaker(wrap, tt("enterName"));
  const row = wrap.querySelector("#row");
  row.appendChild(backBtn("mobile"));
  const next = el(`<button class="btn">${esc(tt("next"))}</button>`);
  row.appendChild(next);
  const input = wrap.querySelector("#name");
  next.onclick = () => {
    const v = input.value.trim();
    if (!v) { wrap.querySelector("#err").textContent = "—"; return; }
    state.draft.name = v;
    go("new_details");
    speak(t(state.lang, "greetName", { name: v }) + ". " + t(state.lang, "enterAddress"), state.lang);
  };
  setTimeout(() => input.focus(), 50);
  return wrap;
}

function screenNewDetails() {
  const name = state.draft.name || "";
  const wrap = el(`
    <div class="screen"><div class="card">
      <h2>${esc(tt("greetName", { name }))}</h2>
      ${promptBubbleHTML(tt("enterAddress"))}
      <label class="field"><span class="lbl">${esc(tt("addressPlaceholder"))}</span>
        <textarea id="addr" placeholder="${esc(tt("addressPlaceholder"))}">${esc(state.draft.address || "")}</textarea></label>
      <label class="field"><span class="lbl">${esc(tt("aadhaarPlaceholder"))}</span>
        <input type="tel" id="aadhaar" inputmode="numeric" maxlength="12" placeholder="${esc(tt("aadhaarPlaceholder"))}" value="${esc(state.draft.aadhaar || "")}"></label>
      <div class="row-2 split">
        <label class="field"><span class="lbl">${esc(tt("ageOptional"))}</span>
          <input type="number" id="age" min="0" max="120" placeholder="${esc(tt("age"))}" value="${esc(state.draft.age || "")}"></label>
        <label class="field"><span class="lbl">${esc(tt("cityOptional"))}</span>
          <input type="text" id="city" placeholder="${esc(tt("cityOptional"))}" value="${esc(state.draft.city || "")}"></label>
      </div>
      <div class="err" id="err"></div>
      <div class="btn-row" id="row"></div>
    </div></div>`);
  bindSpeaker(wrap, tt("enterAddress"));
  const aad = wrap.querySelector("#aadhaar");
  aad.oninput = () => { aad.value = aad.value.replace(/\D/g, "").slice(0, 12); };
  const row = wrap.querySelector("#row");
  row.appendChild(backBtn("new_name"));
  const next = el(`<button class="btn">${esc(tt("next"))}</button>`);
  row.appendChild(next);
  next.onclick = () => {
    const aadhaar = aad.value.trim();
    if (!/^\d{12}$/.test(aadhaar)) { wrap.querySelector("#err").textContent = tt("aadhaarInvalid"); return; }
    state.draft.address = wrap.querySelector("#addr").value.trim();
    state.draft.aadhaar = aadhaar;
    state.draft.age = wrap.querySelector("#age").value.trim();
    state.draft.city = wrap.querySelector("#city").value.trim();
    go("describe");
    speak(t(state.lang, "describeIssue"), state.lang);
  };
  return wrap;
}

function screenDescribe() {
  const supported = speechSupported();
  const wrap = el(`
    <div class="screen"><div class="card">
      ${promptBubbleHTML(tt("describeIssue"))}
      <p class="hint">${esc(supported ? tt("describeHint") : tt("micUnsupported"))}</p>
      <div class="mic-wrap" ${supported ? "" : 'style="display:none"'}>
        <button class="mic" id="mic">🎙️</button>
        <div class="mic-status" id="status"></div>
      </div>
      <label class="field"><span class="lbl">${esc(tt("transcript"))}</span>
        <textarea id="trans" placeholder="${esc(tt("transcriptPlaceholder"))}">${esc(state.transcript)}</textarea></label>
      <div class="btn-row" id="row"></div>
    </div></div>`);
  bindSpeaker(wrap, tt("describeIssue"));
  const trans = wrap.querySelector("#trans");
  trans.oninput = () => { state.transcript = trans.value; };
  const status = wrap.querySelector("#status");
  const mic = wrap.querySelector("#mic");
  if (mic) {
    mic.onclick = () => {
      if (recognizing) { stopRecognition(); return; }
      mic.classList.add("recording"); mic.textContent = "⏹️";
      status.textContent = tt("listening");
      startRecognition(state.lang,
        (partial) => { trans.value = partial; state.transcript = partial; },
        (final) => { if (final) { state.transcript = final; trans.value = final; } },
        () => { mic.classList.remove("recording"); mic.textContent = "🎙️"; status.textContent = ""; }
      );
    };
  }
  const row = wrap.querySelector("#row");
  row.appendChild(backBtn(state.visitType === "followup" ? "existing_welcome" : "new_details"));
  const save = el(`<button class="btn">${esc(tt("saveAndToken"))}</button>`);
  row.appendChild(save);
  save.onclick = () => {
    stopRecognition();
    state.transcript = trans.value.trim();
    finalizeSave(true);
  };
  return wrap;
}

/* Create/locate patient, translate, suggest dx, take a token, persist. */
function finalizeSave(withDescription) {
  let patient = state.patient;
  if (!patient) {
    patient = Store.newPatientRecord({ ...state.draft, language: state.lang });
    Store.savePatient(patient);
    state.patient = patient;
  }
  let english = "", diagnosis = "", transcript = "";
  if (withDescription) {
    transcript = state.transcript;
    english = Store.translateToEnglish(transcript, state.lang);
    diagnosis = Store.suggestDiagnosis(english);
  }
  const tok = Store.nextToken();           // sequential, IST-resetting, first-to-save wins
  const visit = Store.addVisit(patient, {
    type: state.visitType,
    transcript, transcriptLang: state.lang,
    english, diagnosis,
    token: tok.number,
    reason: state.visitType,
  });
  state.lastVisit = visit;
  state.lastToken = tok;
  state.english = english; state.diagnosis = diagnosis;
  go("token");
}

function screenToken() {
  const tok = state.lastToken;
  const name = (state.patient && state.patient.name) || state.draft.name || "";
  const wrap = el(`
    <div class="screen"><div class="card token-card">
      <div class="token-badge">${esc(tt("tokenDate"))} · ${esc(tok.date)}</div>
      <p class="lead" style="margin-bottom:0">${esc(tt("thankYou", { name }))}</p>
      <div class="hint">${esc(tt("tokenTitle"))}</div>
      <div class="token-number">${esc(String(tok.number).padStart(2, "0"))}</div>
      <p class="lead">${esc(tt("tokenNote"))}</p>
      <div class="btn-row"><button class="btn big" id="done">${esc(tt("done"))}</button></div>
    </div></div>`);
  speak(tt("tokenTitle") + " " + tok.number + ". " + tt("tokenNote"), state.lang);
  wrap.querySelector("#done").onclick = () => { resetSession(); state.role = "home"; render(); };
  return wrap;
}

/* small helpers to keep markup tidy */
function promptBubbleHTML(text) {
  return `<div class="prompt-bubble"><span class="speaker" data-say="${esc(text)}" title="Read aloud">🔊</span><div>${esc(text)}</div></div>`;
}
function bindSpeaker(wrap, text) {
  const s = wrap.querySelector(".speaker");
  if (s) s.onclick = () => speak(s.getAttribute("data-say") || text, state.lang);
}

/* ============================================================ */
/* DOCTOR CONSOLE                                               */
/* ============================================================ */
function doctorView() {
  if (state.selectedMobile) return doctorRecord();
  return doctorList();
}

function doctorList() {
  const patients = Store.allPatients();
  // newest visit first; each row shows latest token
  const rows = patients
    .map((p) => {
      const last = (p.visits && p.visits.length) ? p.visits[p.visits.length - 1] : null;
      return { p, last };
    })
    .filter(({ p }) => {
      const q = state.doctorSearch.toLowerCase();
      return !q || (p.name && p.name.toLowerCase().includes(q)) || (p.mobile && p.mobile.includes(q));
    })
    .sort((a, b) => {
      const ta = a.last ? a.last.token : 0, tb = b.last ? b.last.token : 0;
      return ta - tb; // by token ascending (queue order)
    });

  const wrap = el(`
    <div class="doctor-wrap">
      <div class="doctor-header">
        <h1>Patients — Today's Queue</h1>
        <label class="search field" style="margin:0">
          <input type="text" id="search" placeholder="Search name or mobile" value="${esc(state.doctorSearch)}">
        </label>
      </div>
      <div class="patient-list" id="list"></div>
    </div>`);
  wrap.querySelector("#search").oninput = (e) => { state.doctorSearch = e.target.value; render(); };
  const list = wrap.querySelector("#list");
  if (!rows.length) {
    list.appendChild(el(`<div class="empty">No patient records yet. Patients who save at the terminal will appear here.</div>`));
  }
  rows.forEach(({ p, last }) => {
    const isReturning = (p.visits || []).length > 1;
    const tnum = last ? String(last.token).padStart(2, "0") : "—";
    const city = p.city || "—";
    const tagHtml = isReturning ? `<span class="tag ret">${esc(t(state.lang, "returningTag"))}</span>` : `<span class="tag new">${esc(t(state.lang, "newPatientTag"))}</span>`;
    const row = el(`
      <div class="patient-row">
        <div class="token-chip"><div class="tnum">${esc(tnum)}</div><div class="tlbl">Token</div></div>
        <div class="patient-meta">
          <div class="pname">${esc(p.name)} ${tagHtml}</div>
          <div class="psub">${esc(p.age ? "Age " + p.age + " · " : "")}${esc(city)} · ${esc(p.mobile)} · ${(p.visits||[]).length} visit(s)</div>
        </div>
        <div class="chev">›</div>
      </div>`);
    row.onclick = () => { state.selectedMobile = p.mobile; render(); };
    list.appendChild(row);
  });
  return wrap;
}

function fieldSet(n, title, bodyHtml) {
  return `<div class="field-set"><div class="fs-head"><span class="n">${n}</span>${esc(title)}</div><div class="fs-body">${bodyHtml}</div></div>`;
}

/* Render the stored FHIR R4 record as a plain, readable record card —
   pulls the items (name, age, address, token, diagnosis…) out of the
   Patient / Encounter / Condition resources. No JSON on screen. */
function fhirReadable(bundle) {
  const resources = (bundle.entry || []).map((e) => e.resource);
  const pat = resources.find((r) => r.resourceType === "Patient");
  const enc = resources.find((r) => r.resourceType === "Encounter");
  const con = resources.find((r) => r.resourceType === "Condition");
  if (!pat) return `<span class="hint">No record.</span>`;

  const ids = pat.identifier || [];
  const mobile = (ids.find((i) => (i.system || "").includes("mobile")) || {}).value || "—";
  const aadhaar = (ids.find((i) => i.type && i.type.text === "Aadhaar") || {}).value || "—";
  const fullName = (pat.name && pat.name[0] && pat.name[0].text) || "—";
  const ageExt = (pat.extension || []).find((e) => (e.url || "").includes("stated-age"));
  const age = ageExt ? ageExt.valueString : "—";
  const gender = pat.gender ? pat.gender.charAt(0).toUpperCase() + pat.gender.slice(1) : "—";
  const address = (pat.address && pat.address[0] && pat.address[0].text) || "—";
  const langCode = pat.communication && pat.communication[0] && pat.communication[0].language.coding[0].code;
  const langName = I18N[langCode] ? I18N[langCode].label : (langCode || "—");

  const patRows = [
    ["Full name", fullName], ["Age", age], ["Gender", gender],
    ["Mobile", mobile], ["Aadhaar", aadhaar], ["Address", address],
    ["Preferred language", langName],
  ];
  let encRows = [];
  if (enc) {
    const token = (enc.identifier && enc.identifier[0] && enc.identifier[0].value) || "—";
    const type = (enc.type && enc.type[0] && enc.type[0].text) || "—";
    const when = enc.period && enc.period.start ? formatDate(enc.period.start) : "—";
    encRows = [["Visit type", type], ["Token", token], ["Status", enc.status || "—"], ["Date", when]];
  }
  let conRows = [];
  if (con) {
    const dx = (con.code && con.code.text) || "—";
    const ver = con.verificationStatus && con.verificationStatus.coding[0] && con.verificationStatus.coding[0].code;
    conRows = [["Possible diagnosis", dx], ["Status", ver || "—"]];
  }
  const rowHtml = (list) => list.map(([k, v]) => `<div class="rec-row"><div class="rk">${esc(k)}</div><div class="rv">${esc(v)}</div></div>`).join("");

  return `
    <div class="rec-sub">Patient details</div>${rowHtml(patRows)}
    ${enc ? `<div class="rec-sub">This visit</div>${rowHtml(encRows)}` : ""}
    ${con ? `<div class="rec-sub">Provisional diagnosis</div>${rowHtml(conRows)}` : ""}
    <div class="hint" style="margin-top:12px">Saved as a FHIR R4 record (Patient · Encounter · Condition).</div>`;
}

function doctorRecord() {
  const p = Store.getByMobile(state.selectedMobile);
  if (!p) { state.selectedMobile = null; return doctorList(); }
  const visits = (p.visits || []).slice().sort((a, b) => new Date(b.date) - new Date(a.date)); // newest first
  const latest = visits[0];
  const langName = I18N[latest ? latest.transcriptLang : p.language] ? I18N[latest ? latest.transcriptLang : p.language].label : "—";

  // 5 field sets driven by the most recent visit
  const set1 = `<div class="kv"><div><div class="k">Name</div><div class="v">${esc(p.name)}</div></div><div><div class="k">Age</div><div class="v">${esc(p.age || "—")}</div></div></div>`;
  const set2 = `<div class="kv"><div><div class="k">City</div><div class="v">${esc(p.city || "—")}</div></div></div>`;
  const set3 = latest && latest.transcript
    ? `<div class="k" style="margin-bottom:6px">Spoken (${esc(langName)})</div><div class="verbatim">${esc(latest.transcript)}</div>`
    : `<span class="hint">No spoken history for the latest visit (token only).</span>`;
  const set4 = latest && latest.english
    ? `<div class="verbatim">${esc(latest.english)}</div>`
    : `<span class="hint">—</span>`;
  const set5 = latest && latest.diagnosis
    ? `<div class="dx">${esc(latest.diagnosis)}</div><div class="hint">Suggested by keyword model — confirm clinically.</div>`
    : `<span class="hint">—</span>`;

  const wrap = el(`
    <div class="doctor-wrap">
      <div class="doctor-header">
        <button class="btn ghost" id="back">⟵ Back to queue</button>
        <div style="text-align:right">
          <div class="pname" style="font-size:22px;font-weight:700;color:var(--blue-900)">${esc(p.name)}</div>
          <div class="psub" style="color:var(--muted)">Token ${latest ? esc(String(latest.token).padStart(2,"0")) : "—"} · ${esc(p.mobile)}</div>
        </div>
      </div>
      <div class="record">
        ${fieldSet(1, "Patient — Name & Age", set1)}
        ${fieldSet(2, "Patient — City", set2)}
        ${fieldSet(3, "History — spoken language (verbatim)", set3)}
        ${fieldSet(4, "History — English", set4)}
        ${fieldSet(5, "Possible diagnosis", set5)}
      </div>

      <h2 style="margin-top:26px">Visit history</h2>
      <div class="field-set"><div class="fs-body" id="visits"></div></div>

      <h2 style="margin-top:26px">Patient record</h2>
      <div class="field-set"><div class="fs-body" id="fhir"></div></div>
    </div>`);

  wrap.querySelector("#back").onclick = () => { state.selectedMobile = null; render(); };

  const vbox = wrap.querySelector("#visits");
  if (!visits.length) vbox.appendChild(el(`<span class="hint">No visits recorded.</span>`));
  visits.forEach((v) => {
    const typeLabel = v.type === "followup" ? "Follow-up with reports" : v.type === "new_issue" ? "New issue (token only)" : "New visit";
    const block = el(`
      <div class="visit">
        <div class="vdate">${esc(formatDate(v.date))} · Token ${esc(String(v.token).padStart(2,"0"))} · ${esc(typeLabel)}</div>
        ${v.transcript ? `<div class="k">Spoken</div><div class="verbatim" style="margin-bottom:8px">${esc(v.transcript)}</div>` : ""}
        ${v.english ? `<div class="k">English</div><div style="margin-bottom:8px">${esc(v.english)}</div>` : ""}
        ${v.diagnosis ? `<div class="k">Possible diagnosis</div><div class="dx">${esc(v.diagnosis)}</div>` : ""}
        ${!v.transcript && !v.english ? `<span class="hint">Token generated without a new description.</span>` : ""}
      </div>`);
    vbox.appendChild(block);
  });

  const bundle = Store.toFhirBundle(p, latest || null);
  wrap.querySelector("#fhir").innerHTML = fhirReadable(bundle);
  return wrap;
}

/* ---------- boot ---------- */
Store.seedIfEmpty();
render();
