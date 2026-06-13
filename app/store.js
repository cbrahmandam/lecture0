/* Digital History Taking — prototype data layer.
   Storage is intentionally provisional (localStorage) — the real backend,
   auth and FHIR server come later. Everything here is swappable.

   Responsibilities:
     - patient records keyed by mobile number
     - daily, IST-resetting, sequential token numbers ("first to save wins")
     - a stubbed spoken-language -> English translation
     - a stubbed possible-diagnosis suggester (gynaecology oriented)
     - FHIR R4 Patient / Encounter / Condition assembly
*/

const Store = (() => {
  const PATIENTS_KEY = "dht_patients_v1";
  const TOKEN_KEY = "dht_token_counter_v1";

  function read(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }
  function write(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  /* ---- IST date helpers (UTC + 5:30) ---- */
  function istNow() {
    const now = new Date();
    return new Date(now.getTime() + (5 * 60 + 30) * 60 * 1000);
  }
  function istDateKey() {
    const d = istNow();
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  /* ---- Patients ---- */
  function allPatients() {
    const map = read(PATIENTS_KEY, {});
    return Object.values(map);
  }
  function getByMobile(mobile) {
    const map = read(PATIENTS_KEY, {});
    return map[mobile] || null;
  }
  function savePatient(patient) {
    const map = read(PATIENTS_KEY, {});
    map[patient.mobile] = patient;
    write(PATIENTS_KEY, map);
    return patient;
  }

  function newPatientRecord({ mobile, name, address, aadhaar, age, city, language }) {
    return {
      id: "pat-" + mobile,
      mobile,
      name,
      address: address || "",
      aadhaar: aadhaar || "",
      age: age || "",
      city: city || "",
      language: language || "en",
      createdAt: new Date().toISOString(),
      visits: [],
    };
  }

  /* A visit = one terminal session that produced a token. */
  function addVisit(patient, { reason, transcript, transcriptLang, english, diagnosis, token, type }) {
    const visit = {
      visitId: "vis-" + Date.now(),
      date: new Date().toISOString(),
      istDate: istDateKey(),
      type: type || "new", // 'new' | 'followup' | 'new_issue'
      reason: reason || "",
      transcript: transcript || "",
      transcriptLang: transcriptLang || patient.language,
      english: english || "",
      diagnosis: diagnosis || "",
      token,
    };
    patient.visits = patient.visits || [];
    patient.visits.push(visit);
    savePatient(patient);
    return visit;
  }

  /* ---- Token: sequential, resets at 00:00 IST, first-to-save wins ----
     localStorage is single-origin so this models one terminal cleanly.
     With multiple terminals on shared storage the read-modify-write below
     is atomic per call, so the first writer takes the lower number. */
  function nextToken() {
    const today = istDateKey();
    let state = read(TOKEN_KEY, { date: today, counter: 0 });
    if (state.date !== today) {
      state = { date: today, counter: 0 };
    }
    state.counter += 1;
    write(TOKEN_KEY, state);
    return { number: state.counter, date: today };
  }
  function peekTokenState() {
    return read(TOKEN_KEY, { date: istDateKey(), counter: 0 });
  }

  /* ---- Stub translation (spoken language -> English) ----
     Phrase + word level. Good enough to demo the doctor's English panel;
     replaced by a real translation service later. */
  const PHRASES = {
    hi: [
      [/पेट\s*(में)?\s*दर्द/g, "pain in the abdomen"],
      [/पेडू\s*दर्द/g, "lower abdominal pain"],
      [/कमर\s*दर्द/g, "back pain"],
      [/सफ़ेद\s*पानी|सफेद\s*पानी/g, "white discharge"],
      [/खून\s*बह/g, "bleeding"],
      [/ज़्यादा\s*खून|अधिक\s*रक्तस्राव/g, "heavy bleeding"],
      [/माहवारी|पीरियड|मासिक/g, "menstrual period"],
      [/पीरियड\s*नहीं\s*आया|माहवारी\s*बंद/g, "missed period"],
      [/खुजली/g, "itching"],
      [/जलन/g, "burning sensation"],
      [/बुखार/g, "fever"],
      [/उल्टी/g, "vomiting"],
      [/जी\s*मिचला/g, "nausea"],
      [/गर्भ|प्रेगनेंट|पेट\s*से/g, "pregnancy"],
      [/कमजोरी|कमज़ोरी/g, "weakness"],
      [/चक्कर/g, "dizziness"],
      [/दर्द/g, "pain"],
      [/दिन/g, "days"],
      [/हफ्ता|हफ़्ता/g, "week"],
      [/महीना|महीने/g, "month(s)"],
      [/से\s*हो\s*रहा|से\s*है/g, "since"],
    ],
    te: [
      [/కడుపు\s*నొప్పి/g, "abdominal pain"],
      [/పొత్తి\s*కడుపు\s*నొప్పి/g, "lower abdominal pain"],
      [/నడుము\s*నొప్పి/g, "back pain"],
      [/తెల్ల\s*బట్ట|వైట్\s*డిశ్చార్జ్/g, "white discharge"],
      [/రక్తస్రావం|బ్లీడింగ్/g, "bleeding"],
      [/ఎక్కువ\s*రక్తస్రావం/g, "heavy bleeding"],
      [/నెలసరి|పీరియడ్|రుతుక్రమం/g, "menstrual period"],
      [/పీరియడ్\s*రాలేదు|నెలసరి\s*ఆగింది/g, "missed period"],
      [/దురద/g, "itching"],
      [/మంట/g, "burning sensation"],
      [/జ్వరం/g, "fever"],
      [/వాంతి/g, "vomiting"],
      [/వికారం/g, "nausea"],
      [/గర్భం|ప్రెగ్నెంట్/g, "pregnancy"],
      [/నీరసం|బలహీనత/g, "weakness"],
      [/తల\s*తిరగడం/g, "dizziness"],
      [/నొప్పి/g, "pain"],
      [/రోజులు/g, "days"],
      [/వారం/g, "week"],
      [/నెల|నెలలు/g, "month(s)"],
    ],
  };

  function translateToEnglish(text, lang) {
    if (!text) return "";
    if (lang === "en") return text;
    const rules = PHRASES[lang] || [];
    let out = text;
    const hits = [];
    rules.forEach(([re, en]) => {
      if (re.test(out)) hits.push(en);
      out = out.replace(re, " " + en + " ");
    });
    // Collapse leftover native script that wasn't matched into a readable note.
    const clean = out.replace(/\s+/g, " ").trim();
    const leftover = clean.replace(/[A-Za-z0-9 ,.()\-]/g, "").trim();
    let result = clean.replace(/[^A-Za-z0-9 ,.()\-]/g, "").replace(/\s+/g, " ").trim();
    if (!result && hits.length) result = hits.join(", ");
    if (leftover) {
      result += (result ? " " : "") + "[untranslated terms present — clinician to verify]";
    }
    return result || "[machine translation unavailable — please review original]";
  }

  /* ---- Stub possible-diagnosis suggester (gynaecology oriented) ----
     Keyword driven across en/translated text. Always editable by the doctor. */
  function suggestDiagnosis(englishText) {
    if (!englishText) return "";
    const s = englishText.toLowerCase();
    const dx = [];
    const has = (...ws) => ws.some((w) => s.includes(w));
    if (has("heavy bleeding", "heavy menstrual")) dx.push("Menorrhagia / abnormal uterine bleeding — evaluate");
    else if (has("bleeding") && has("between", "spotting")) dx.push("Intermenstrual bleeding — evaluate");
    else if (has("bleeding")) dx.push("Abnormal uterine bleeding — evaluate");
    if (has("missed period") || (has("pregnancy") && has("test"))) dx.push("? Pregnancy — confirm with test/USG");
    else if (has("pregnancy")) dx.push("Pregnancy-related — confirm gestation");
    if (has("white discharge", "discharge")) dx.push("Vaginal discharge — r/o vaginitis/cervicitis");
    if (has("itching", "burning") && has("discharge")) dx.push("Vulvovaginal candidiasis (suspected)");
    else if (has("itching")) dx.push("Vulval pruritus — examine");
    if (has("lower abdominal pain", "pelvic pain", "abdominal pain")) dx.push("Pelvic/abdominal pain — r/o PID, ovarian cyst");
    if (has("back pain")) dx.push("Low back pain — correlate clinically");
    if (has("fever") && has("pain", "discharge")) dx.push("? Pelvic inflammatory disease — assess");
    if (has("dizziness", "weakness") && has("bleeding")) dx.push("? Anaemia secondary to blood loss — check Hb");
    if (!dx.length) dx.push("Clinical correlation required — history non-specific");
    return dx.join("; ");
  }

  /* ---- FHIR R4 assembly ---- */
  function aadhaarSlot(aadhaar) {
    if (!aadhaar) return [];
    return [
      {
        system: "https://uidai.gov.in/aadhaar",
        value: aadhaar,
        type: { text: "Aadhaar" },
      },
    ];
  }

  function toFhirBundle(patient, visit) {
    const patUrn = "urn:uuid:" + patient.id;
    const encUrn = "urn:uuid:enc-" + (visit ? visit.visitId : "none");
    const conUrn = "urn:uuid:con-" + (visit ? visit.visitId : "none");

    const nameParts = (patient.name || "").trim().split(/\s+/);
    const family = nameParts.length > 1 ? nameParts.slice(-1)[0] : "";
    const given = nameParts.length > 1 ? nameParts.slice(0, -1) : [patient.name || ""];

    const patientResource = {
      resourceType: "Patient",
      id: patient.id,
      identifier: [
        { system: "https://hospital.example/mobile", value: patient.mobile },
        ...aadhaarSlot(patient.aadhaar),
      ],
      active: true,
      name: [{ use: "official", text: patient.name, family, given }],
      telecom: [{ system: "phone", value: patient.mobile, use: "mobile" }],
      gender: "female",
      address: patient.address
        ? [{ use: "home", text: patient.address, country: "IN" }]
        : undefined,
      extension: patient.age
        ? [{ url: "https://hospital.example/StructureDefinition/stated-age", valueString: String(patient.age) }]
        : undefined,
      communication: [
        {
          language: {
            coding: [
              {
                system: "urn:ietf:bcp:47",
                code: patient.language === "hi" ? "hi" : patient.language === "te" ? "te" : "en",
              },
            ],
          },
          preferred: true,
        },
      ],
    };

    const entries = [{ fullUrl: patUrn, resource: patientResource, request: { method: "PUT", url: "Patient/" + patient.id } }];

    if (visit) {
      const encounter = {
        resourceType: "Encounter",
        id: "enc-" + visit.visitId,
        status: "finished",
        class: { system: "http://terminology.hl7.org/CodeSystem/v3-ActCode", code: "AMB", display: "ambulatory" },
        type: [{ text: "Gynaecology — history taking" }],
        subject: { reference: "Patient/" + patient.id },
        period: { start: visit.date },
        identifier: [{ system: "https://hospital.example/token", value: String(visit.token) }],
      };
      const condition = {
        resourceType: "Condition",
        id: "con-" + visit.visitId,
        clinicalStatus: {
          coding: [{ system: "http://terminology.hl7.org/CodeSystem/condition-clinical", code: "active" }],
        },
        verificationStatus: {
          coding: [{ system: "http://terminology.hl7.org/CodeSystem/condition-ver-status", code: "provisional" }],
        },
        category: [
          {
            coding: [
              { system: "http://terminology.hl7.org/CodeSystem/condition-category", code: "encounter-diagnosis", display: "Encounter Diagnosis" },
            ],
          },
        ],
        code: { text: visit.diagnosis || "Undiagnosed — pending review" },
        subject: { reference: "Patient/" + patient.id },
        encounter: { reference: "Encounter/enc-" + visit.visitId },
        recordedDate: visit.date,
        note: [
          { text: "Verbatim (" + visit.transcriptLang + "): " + (visit.transcript || "") },
          { text: "English: " + (visit.english || "") },
        ],
      };
      entries.push({ fullUrl: encUrn, resource: encounter, request: { method: "PUT", url: "Encounter/enc-" + visit.visitId } });
      entries.push({ fullUrl: conUrn, resource: condition, request: { method: "PUT", url: "Condition/con-" + visit.visitId } });
    }

    return { resourceType: "Bundle", type: "transaction", timestamp: new Date().toISOString(), entry: entries };
  }

  /* ---- Demo seed so the doctor console isn't empty on first run ---- */
  function seedIfEmpty() {
    if (allPatients().length) return;
    const p1 = newPatientRecord({
      mobile: "9876543210", name: "Lakshmi Devi", address: "12-3-45, Charminar, Hyderabad, Telangana, 500002",
      aadhaar: "123412341234", age: "29", city: "Hyderabad", language: "te",
    });
    addVisit(p1, {
      reason: "new", type: "new",
      transcript: "నాకు రెండు వారాల నుండి కడుపు నొప్పి మరియు తెల్ల బట్ట ఉంది",
      transcriptLang: "te",
      english: "abdominal pain and white discharge since two weeks",
      diagnosis: suggestDiagnosis("abdominal pain and white discharge"),
      token: 1,
    });
    const p2 = newPatientRecord({
      mobile: "9123456780", name: "Ayesha Begum", address: "8-2-120, Banjara Hills, Hyderabad, Telangana, 500034",
      aadhaar: "432143214321", age: "34", city: "Hyderabad", language: "hi",
    });
    addVisit(p2, {
      reason: "new", type: "new",
      transcript: "मुझे एक महीने से ज़्यादा खून बह रहा है और कमजोरी है",
      transcriptLang: "hi",
      english: "heavy bleeding since one month and weakness",
      diagnosis: suggestDiagnosis("heavy bleeding since one month and weakness"),
      token: 2,
    });
    // bump the live counter so new saves continue from 3 for today
    write(TOKEN_KEY, { date: istDateKey(), counter: 2 });
  }

  return {
    istDateKey, allPatients, getByMobile, savePatient, newPatientRecord, addVisit,
    nextToken, peekTokenState, translateToEnglish, suggestDiagnosis, toFhirBundle, seedIfEmpty,
  };
})();
