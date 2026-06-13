# Digital History Taking — Prototype

A touch-first terminal that lets a patient give their medical history **in their own
language** (English, Hindi, Telugu — including Hyderabadi/Telangana/Andhra usage),
records it **verbatim**, translates it to **English**, and prepares a
**FHIR R4** patient record for the doctor. Built as a clickable prototype —
**storage and auth are deliberately deferred** (see *Decisions pending*).

> Status: UI prototype. No backend, no real auth, no cloud STT/translation yet.

## Run it

No build step, no dependencies. Just serve the `app/` folder:

```bash
cd app
python3 -m http.server 8000
# open http://localhost:8000  (use Chrome for voice input)
```

Or open `app/index.html` directly (voice works best when served over http/https in Chrome).

## Install on a phone/tablet (PWA — works offline)

The app is a **Progressive Web App**: it installs to the home screen and runs
**fully offline** with **local storage**, so no app store or APK build is needed.

1. Serve `app/` over **HTTPS** (any static host — GitHub Pages, Netlify, an
   internal server). A service worker requires `https://` (or `localhost`).
2. Open the URL in **Chrome on Android** (or Safari on iOS).
3. Chrome shows **"Add to Home screen" / Install**; tap it. iOS: Share → *Add to Home Screen*.
4. Launch it from the home screen — it opens full-screen, no browser chrome, and
   keeps working with no network. Patient data persists in the device's local storage.

Files that make it installable: `manifest.webmanifest`, `sw.js` (offline cache),
`icon-192.png` / `icon-512.png` (regenerate with `node make-icons.js`).

> Want a real `.apk`? This installable PWA can be wrapped into one later with
> [PWABuilder](https://www.pwabuilder.com/) or Bubblewrap (TWA) — both consume the
> manifest above. A direct APK build wasn't possible in this hosted environment
> because its network policy blocks Google's Android SDK servers.

## What's built

### Patient terminal (persona: Patient)
1. **Touch to begin** on the "Terminal".
2. **Choose language** — English / Hindi / Telugu. Every following screen and every
   spoken prompt switches to that language.
3. **Mobile number** — prompt is read aloud. 10-digit validation.
   - **Existing patient** → *"Hi {name}, how are you? Welcome back. What did you come for today?"*
     - **1. Follow up with reports** → describe the issue (voice) → token.
     - **2. New issue** → token straight away.
   - **New patient** → Name → greeting → Address + PIN + **Aadhaar (validated as 12 digits)**
     → describe issue (voice + live transcript) → token.
4. **Voice capture** — browser speech recognition in the chosen language (`hi-IN`,
   `te-IN`, `en-IN`), live transcript, editable. Falls back to typing if unsupported.
5. **Save & token** — sequential **token number**, **resets at 00:00 IST**,
   **first-to-save wins** (atomic read-modify-write on the counter).

### Doctor console (persona: Doctor)
- **Queue list** of patients with **token numbers**; tap a name to open the record.
- Record shows the **5 field sets**:
  1. Patient **Name & Age**
  2. Patient **City**
  3. **History — spoken language (verbatim)**
  4. **History — English** (translated)
  5. **Possible diagnosis** (keyword suggester, gynaecology-oriented, editable later)
- **Visit history sorted by date** (newest first) for returning patients.
- **FHIR R4 Bundle** preview (Patient + Encounter + Condition) per visit.

### Theme & device
- White + light-blue palette, large touch targets, responsive up to ~15".
- Devanagari/Telugu web fonts requested via system font stack.

## How the pieces map

| File | Responsibility |
|------|----------------|
| `app/index.html` | Shell; loads the three scripts |
| `app/i18n.js` | UI strings + spoken-prompt text for en/hi/te |
| `app/store.js` | Patients, IST token counter, **stub translation**, **stub diagnosis**, **FHIR R4** assembly, demo seed |
| `app/app.js` | View state machine: home → patient flow / doctor console; voice capture |
| `app/styles.css` | White & light-blue theme, tablet-first |

## Stubs that become real services later
- **Speech-to-text**: currently the browser Web Speech API. Swap for a server-side
  STT tuned for Hyderabadi Hindi / Telangana–Andhra Telugu.
- **Translation** (`Store.translateToEnglish`): phrase/keyword rules today → real MT.
- **Diagnosis** (`Store.suggestDiagnosis`): keyword heuristics → clinical model; always
  clinician-confirmed.

## Decisions pending (by design)
- **Storage**: prototype uses `localStorage`. Real DB + FHIR server TBD.
- **Auth**: none yet — doctor console is open in the prototype.
- **Multi-terminal tokens**: modeled atomically here; needs a shared transactional
  counter (e.g. DB sequence) in production so "first to save wins" holds across terminals.
- **Gender**: FHIR Patient currently defaults to `female` (gynaecology context) — make
  this captured/configurable.
