import base64
import hashlib
import json
import re
from html import escape

import requests
import streamlit as st


st.set_page_config(page_title="Listing Tool (DE)", layout="wide")

st.markdown(
    """
<style>
/* Generate (new) */
div.stButton > button[kind="primary"]{
  background:#ef4444 !important;
  border:1px solid #ef4444 !important;
  color:#ffffff !important;
  font-weight:700 !important;
}
div.stButton > button[kind="primary"]:hover{
  background:#dc2626 !important;
  border-color:#dc2626 !important;
}

/* Apply updates */
.apply-update div.stButton > button{
  background:#6ec6ff !important;
  border:1px solid #6ec6ff !important;
  color:#0b2742 !important;
  font-weight:700 !important;
}
.apply-update div.stButton > button:hover{
  background:#5bb8f5 !important;
  border-color:#5bb8f5 !important;
  color:#0b2742 !important;
}
.apply-update div.stButton > button[disabled]{
  background:#6ec6ff !important;
  border:1px solid #6ec6ff !important;
  color:#0b2742 !important;
  opacity:1 !important;
}
</style>
""",
    unsafe_allow_html=True,
)


def safe_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


OPENROUTER_API_KEY = safe_secret("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Models wie im bisherigen Tool
OPENROUTER_MODEL_VISION = safe_secret("OPENROUTER_MODEL_VISION", "google/gemini-3-flash-preview").strip()
OPENROUTER_MODEL_TEXT = safe_secret("OPENROUTER_MODEL_TEXT", "openai/gpt-5-chat").strip()

TEMPERATURE = 0
TIMEOUT_SEC = 90

SYSTEM_PROMPT_DE = """
Du erstellst professionelle deutsche Schmuck-Listings für Marktplätze.

Ausgabeformat MUSS exakt sein:

[DE]
TITLE: <eine Zeile>
DESCRIPTION:
<ein oder mehrere Absätze>

Regeln:
- Gib NUR den [DE]-Block aus.
- Titel SEO-stark und klickstark formulieren.
- Titel darf maximal 80 Zeichen haben.
- Übernimm KEINE Marken-, Hersteller-, Shop- oder Modellnamen aus dem Input.
- Nutze Informationen aus SOURCE, IMAGE NOTES, VARIANTS NOTE und UPDATE NOTES als Faktenbasis.
- Keine Emojis, keine Zusatzkommentare.
""".strip()

QUALITY_CHECK_SYSTEM_PROMPT = """
Du bist ein strenger QA-Prüfer für deutsche Schmuck-Listings.

Wichtig:
- Du darfst KEINEN Titel und KEINE Beschreibung umschreiben.
- Du gibst NUR einen Prüfbericht aus.
- Alle Prüfregeln sind gleich wichtig. Keine Priorisierung.
- Prüfe vollständig gegen SOURCE, IMAGE NOTES, VARIANTS NOTE und UPDATE NOTES.

Prüfpunkte:
- Faktenwidersprüche
- Fehlende relevante Fakten aus den Eingaben
- Titel länger als 80 Zeichen
- Übernommene Marken-/Hersteller-/Shop-/Modellnamen
- Unklare, unprofessionelle oder nicht SEO-taugliche Formulierungen

Ausgabeformat:
- Wenn Probleme gefunden werden: pro Zeile genau
  "- Problem: <kurz> | Stelle: <Titel/Beschreibung> | Grund: <faktischer Grund>"
- Wenn keine Probleme gefunden werden: genau
  "Keine Auffälligkeiten gefunden."
""".strip()

VISION_SYSTEM_PROMPT = """
Extrahiere nur klar sichtbare, lesbare Fakten aus dem Bild.

Regeln:
- Nicht raten oder interpretieren.
- Erfasse alle sichtbaren Material-, Metall-, Maß-, Gewichts-, Farb- und Designangaben.
- Erfasse sichtbaren Text auf dem Bild möglichst exakt.
- Erfasse erkennbare Varianten (z. B. unterschiedliche Farben/Materialien/Größen).
- Rückgabe als faktische Bullet-List.
""".strip()




EBAY_TEMPLATE = r"""
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Playfair+Display:ital,wght@0,400;0,500;1,400&family=Lato:wght@300;400&display=swap" rel="stylesheet">
<style>
  body, div, h1, h2, h3, p, ul, li, span, img, label, input { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Lato', sans-serif; background-color: #ffffff; color: #262626; line-height: 1.8; -webkit-font-smoothing: antialiased; font-weight: 300; }
  .luxe-container { max-width: 1000px; margin: 0 auto; background: #ffffff; padding: 20px; }
  .luxe-top-bar { text-align: center; border-bottom: 1px solid #fafafa; padding: 40px 0 30px; margin-bottom: 40px; }
  .luxe-brand-logo { font-family: 'Cinzel', serif; font-size: 32px; letter-spacing: 5px; color: #171717; text-transform: uppercase; margin-bottom: 5px; display: block; }
  .luxe-brand-tagline { font-family: 'Playfair Display', serif; font-style: italic; font-size: 12px; color: #a3a3a3; }
  .luxe-title-section { text-align: center; margin-bottom: 50px; }
  .luxe-vertical-line { width: 1px; height: 50px; background-color: #e8d3a3; margin: 0 auto 30px; }
  .luxe-title { font-family: 'Playfair Display', serif; font-size: 38px; color: #171717; margin-bottom: 20px; font-weight: 500; line-height: 1.3; }
  .luxe-subtitle { font-size: 13px; color: #737373; text-transform: uppercase; letter-spacing: 2px; }
  .luxe-grid { display: flex; flex-wrap: wrap; gap: 50px; margin-bottom: 80px; align-items: flex-start; }
  .luxe-col-left { flex: 1 1 500px; }
  .luxe-col-right { flex: 1 1 350px; }
  .luxe-col-full { flex: 1 1 100%; max-width: 800px; margin: 0 auto; }
  .luxe-main-image-wrapper { position: relative; background-color: #fafafa; margin-bottom: 20px; border: 1px solid #f0f0f0; display: flex; align-items: center; justify-content: center; height: 550px; overflow: hidden; }
  .luxe-main-img { max-width: 95%; max-height: 95%; object-fit: contain; mix-blend-mode: multiply; }
  .luxe-thumbs { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 5px; }
  .luxe-thumb { width: 80px; height: 80px; object-fit: cover; border: 1px solid #e5e5e5; opacity: 0.7; }
  .luxe-price-block { margin-bottom: 40px; }
  .luxe-price { font-family: 'Playfair Display', serif; font-size: 42px; color: #171717; display: block; line-height: 1; margin-bottom: 10px; }
  .luxe-desc { font-size: 15px; color: #525252; margin-bottom: 40px; text-align: justify; font-weight: 300; }
  .luxe-specs-title { font-family: 'Cinzel', serif; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #171717; border-bottom: 1px solid #f5f5f5; padding-bottom: 10px; margin-bottom: 20px; }
  .luxe-spec-item { display: flex; align-items: flex-start; font-size: 14px; color: #525252; margin-bottom: 12px; }
  .luxe-spec-icon { color: #d4d4d4; margin-right: 15px; font-size: 16px; }
  .luxe-promo-section { margin-bottom: 80px; border: 1px solid #f5f5f5; background: #fafafa; }
  .luxe-promo-img { width: 100%; height: 300px; object-fit: cover; display: block; }
  .luxe-promo-content { padding: 40px; text-align: center; }
  .luxe-promo-title { font-family: 'Cinzel', serif; font-size: 18px; letter-spacing: 4px; text-transform: uppercase; margin-bottom: 15px; color: #171717; }
  .luxe-promo-desc { font-size: 14px; color: #737373; max-width: 600px; margin: 0 auto; line-height: 1.6; }
  .luxe-tabs-section { border-top: 1px solid #f5f5f5; padding-top: 60px; margin-top: 60px; text-align: center; position: relative; }
  .luxe-tab-input { display: none; }
  .luxe-tab-header { margin-bottom: 40px; }
  .luxe-tab-title {
    display: inline-block;
    margin: 0 20px;
    font-family: 'Cinzel', serif;
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #a3a3a3;
    border-bottom: 1px solid transparent;
    padding-bottom: 5px;
    cursor: pointer;
    transition: all 0.3s ease;
  }
  .luxe-tab-content {
    display: none;
    max-width: 700px;
    margin: 0 auto;
    font-size: 14px;
    color: #737373;
    min-height: 100px;
  }
  #luxe-tab-1:checked ~ .luxe-tab-header label[for="luxe-tab-1"],
  #luxe-tab-2:checked ~ .luxe-tab-header label[for="luxe-tab-2"],
  #luxe-tab-3:checked ~ .luxe-tab-header label[for="luxe-tab-3"] {
    color: #171717;
    border-bottom: 1px solid #171717;
  }
  #luxe-tab-1:checked ~ .luxe-tab-content-1,
  #luxe-tab-2:checked ~ .luxe-tab-content-2,
  #luxe-tab-3:checked ~ .luxe-tab-content-3 {
    display: block;
  }
  .luxe-footer { margin-top: 80px; padding-top: 40px; border-top: 1px solid #f5f5f5; text-align: center; }
  .luxe-copyright { font-size: 10px; color: #e5e5e5; letter-spacing: 2px; text-transform: uppercase; }
  @media (max-width: 768px) {
    .luxe-main-image-wrapper { height: auto; max-height: none; min-height: 300px; }
    .luxe-title { font-size: 28px; }
    .luxe-grid { flex-direction: column; gap: 30px; }
    .luxe-col-left, .luxe-col-right { flex: 1 1 100%; width: 100%; }
    .luxe-tab-title { display: block; margin: 0 0 15px; border-bottom: none !important; }
  }
</style>

<div class="luxe-container">
  <div class="luxe-top-bar"><span class="luxe-brand-logo">Juwelique</span><span class="luxe-brand-tagline">Fine &amp; Contemporary Jewelry</span></div>
  <div class="luxe-title-section"><div class="luxe-vertical-line"></div><h1 class="luxe-title">{{TITLE}}</h1></div>
  <div class="luxe-grid">
    <div class="luxe-col-full">
      <div class="luxe-price-block"><span class="luxe-price"></span></div>
      <div class="luxe-desc">{{DESCRIPTION}}</div>
      <div class="luxe-specs">
        <h3 class="luxe-specs-title">Details &amp; Material</h3>
      </div>
    </div>
  </div>
  <div class="luxe-tabs-section">
    <input type="radio" name="luxe-tabs" id="luxe-tab-1" class="luxe-tab-input" checked="">
    <input type="radio" name="luxe-tabs" id="luxe-tab-2" class="luxe-tab-input">
    <input type="radio" name="luxe-tabs" id="luxe-tab-3" class="luxe-tab-input">
    <div class="luxe-tab-header">
      <label for="luxe-tab-1" class="luxe-tab-title">Details</label>
      <label for="luxe-tab-2" class="luxe-tab-title">Versand</label>
      <label for="luxe-tab-3" class="luxe-tab-title">Rückgabe</label>
    </div>
    <div class="luxe-tab-content luxe-tab-content-1">
      Modern icons, precision set — refined brilliance defines contemporary fine and fashion jewelry, crafted for everyday grandeur.
    </div>
    <div class="luxe-tab-content luxe-tab-content-2">
      Kostenloser &amp; Versicherter Versand.
    </div>
    <div class="luxe-tab-content luxe-tab-content-3">
      30 Tage Rückgaberecht
    </div>
  </div>
  <div class="luxe-footer"><p class="luxe-copyright">© 2026 Juwelique</p></div>
</div>
"""


def build_ebay_template(title: str, description: str) -> str:
    safe_title = escape((title or '').strip())
    safe_desc = escape((description or '').strip())
    safe_desc = safe_desc.replace("\n\n", "<br><br>").replace("\n", "<br>")
    return EBAY_TEMPLATE.replace("{{TITLE}}", safe_title).replace("{{DESCRIPTION}}", safe_desc)


def clear_all():
    keys_to_clear = [
        "source_text",
        "variants_note",
        "image_notes",
        "image_notes_hash",
        "update_notes",
        "out_de_title",
        "out_de_desc",
        "draft_raw",
        "image_upload",
        "quality_report",
    ]

    for key in keys_to_clear:
        st.session_state[key] = ""

    current_uploader_key = st.session_state.get("uploader_key", 0)
    st.session_state.pop(f"image_upload_{current_uploader_key}", None)
    st.session_state["uploader_key"] = current_uploader_key + 1


def call_openrouter(messages: list[dict], model_name: str) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("Missing OPENROUTER_API_KEY in Streamlit secrets.")

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": TEMPERATURE,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Listing Tool (DE)",
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=TIMEOUT_SEC)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def clean_text(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_block(text: str, tag: str = "DE") -> dict:
    cleaned = clean_text(text)
    match = re.search(rf"\[{tag}\]\s*(.*?)(?=\n\[[A-Z]{{2}}\]|\Z)", cleaned, flags=re.S)
    block = match.group(1).strip() if match else ""

    title_match = re.search(r"(?m)^\s*TITLE:\s*(.+)\s*$", block)
    desc_match = re.search(r"(?s)DESCRIPTION:\s*(.+)\s*$", block)

    return {
        "raw": cleaned,
        "title": title_match.group(1).strip() if title_match else "",
        "desc": desc_match.group(1).strip() if desc_match else "",
        "has_block": bool(block),
    }


def de_title_ok(title: str) -> bool:
    return len((title or "").strip()) <= 80


def render_copy_button(label: str, text: str, key: str):
    button_id = f"copy-btn-{key}"
    payload = json.dumps(text or "")
    button_label = json.dumps(label)
    html_content = f"""
        <div style=\"display: inline-block; margin-right: 8px;\">
          <button id=\"{button_id}\" style=\"padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;background:#f8fafc;cursor:pointer;font-size:0.9rem;\">
            {label}
          </button>
          <script>
            (() => {{
              const btn = document.getElementById('{button_id}');
              if (!btn) return;
              const original = {button_label};
              const text = {payload};
              const copy = async () => {{
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                  return navigator.clipboard.writeText(text);
                }}
                const el = document.createElement('textarea');
                el.value = text;
                el.setAttribute('readonly', '');
                el.style.position = 'fixed';
                el.style.opacity = '0';
                document.body.appendChild(el);
                el.select();
                document.execCommand('copy');
                document.body.removeChild(el);
              }};
              btn.addEventListener('click', async () => {{
                btn.disabled = true;
                let ok = true;
                try {{
                  await copy();
                }} catch (err) {{
                  ok = false;
                  console.error(err);
                }}
                btn.innerText = ok ? '✓' : '⚠';
                setTimeout(() => {{
                  btn.innerText = original;
                  btn.disabled = false;
                }}, 1000);
              }});
            }})();
          </script>
        </div>
        """
    st.components.v1.html(html_content, height=42)


def normalize_image_notes(raw: str) -> str:
    lines = [
        re.sub(r"\s+", " ", line.strip("-*• ").strip())
        for line in (raw or "").splitlines()
        if line.strip()
    ]
    bullets = [f"- {line}" for line in lines if line]
    return "\n".join(bullets).strip()


def build_initial_user_prompt(source: str, update_notes: str, variants_note: str, image_notes: str) -> str:
    return f"""
SOURCE:
{(source or '').strip()}

IMAGE NOTES (aus Bildern extrahiert; verbindliche Fakten):
{(image_notes or '').strip() or '(keine)'}

VARIANTS NOTE:
{(variants_note or '').strip() or '(keine)'}

UPDATE NOTES:
{(update_notes or '').strip() or '(keine)'}

Aufgabe:
- Erstelle ein neues deutsches Schmuck-Listing.
- Berücksichtige Bildinformationen und sichtbaren Bildtext vollständig als Fakten.
""".strip()


def build_update_user_prompt(source: str, current_draft_raw: str, update_notes: str, variants_note: str, image_notes: str) -> str:
    return f"""
SOURCE:
{(source or '').strip()}

IMAGE NOTES (aus Bildern extrahiert; verbindliche Fakten):
{(image_notes or '').strip() or '(keine)'}

VARIANTS NOTE:
{(variants_note or '').strip() or '(keine)'}

CURRENT DRAFT (beibehalten, nur minimal ändern):
{(current_draft_raw or '').strip()}

UPDATE NOTES:
{(update_notes or '').strip() or '(keine)'}

Aufgabe:
- Aktualisiere den CURRENT DRAFT minimal anhand der UPDATE NOTES.
- Berücksichtige Bildinformationen und sichtbaren Bildtext vollständig als Fakten.
""".strip()


def build_quality_check_user_prompt(source: str, title: str, description: str, update_notes: str, variants_note: str, image_notes: str) -> str:
    return f"""
SOURCE:
{(source or '').strip()}

IMAGE NOTES (aus Bildern extrahiert; verbindliche Fakten):
{(image_notes or '').strip() or '(keine)'}

VARIANTS NOTE:
{(variants_note or '').strip() or '(keine)'}

UPDATE NOTES:
{(update_notes or '').strip() or '(keine)'}

ZU PRÜFENDER TITEL (DE):
{(title or '').strip()}

ZU PRÜFENDE BESCHREIBUNG (DE):
{(description or '').strip()}

Aufgabe:
- Prüfe den Titel und die Beschreibung vollständig.
- Erzeuge ausschließlich einen Prüfbericht gemäß vorgegebenem Format.
- Schreibe den Listing-Text nicht um und schlage keine Neuformulierung als Volltext vor.
""".strip()


st.title("Listing Tool (DE)")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input")

    st.button("Clear", use_container_width=True, on_click=clear_all)

    source = st.text_area(
        "SOURCE (paste raw product data)",
        height=360,
        key="source_text",
        placeholder="Paste your product raw data here...",
    )

    st.text_input(
        "Variants notice, etc.",
        key="variants_note",
        placeholder="variants, etc.",
    )

    uploader_key = st.session_state.get("uploader_key", 0)
    uploaded_images = st.file_uploader(
        "Image upload (jpg/png/webp)",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"image_upload_{uploader_key}",
        accept_multiple_files=True,
    )
    st.caption("Images are analyzed for product facts and variants.")

    if uploaded_images:
        image_hashes = []
        valid_images = []
        for idx, image in enumerate(uploaded_images, start=1):
            if not hasattr(image, "getvalue"):
                continue
            image_bytes = image.getvalue()
            image_hashes.append(hashlib.sha256(image_bytes).hexdigest())
            valid_images.append((idx, image, image_bytes))

        combined_hash = hashlib.sha256("".join(image_hashes).encode("utf-8")).hexdigest()

        if st.session_state.get("image_notes_hash") != combined_hash:
            if not OPENROUTER_API_KEY:
                st.warning("Missing OPENROUTER_API_KEY. Cannot analyze images.")
            else:
                raw_image_notes: list[str] = []
                with st.spinner("Analyzing image(s)..."):
                    for _, image, image_bytes in valid_images:
                        data_url = f"data:{image.type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
                        messages = [
                            {"role": "system", "content": VISION_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Extrahiere alle lesbaren Schmuck-Fakten inkl. sichtbarer Schrift und Varianten.",
                                    },
                                    {"type": "image_url", "image_url": {"url": data_url}},
                                ],
                            },
                        ]
                        raw_notes = call_openrouter(messages, OPENROUTER_MODEL_VISION)
                        raw_image_notes.append(raw_notes)

                combined_notes = normalize_image_notes("\n".join(raw_image_notes))
                st.session_state["image_notes"] = combined_notes
                st.session_state["image_notes_hash"] = combined_hash

    btn_generate = st.button("Generate (new)", type="primary", use_container_width=True)

    if btn_generate:
        if not source.strip():
            st.warning("Paste SOURCE first.")
        else:
            with st.spinner("Generating DE listing..."):
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT_DE},
                    {
                        "role": "user",
                        "content": build_initial_user_prompt(
                            source,
                            st.session_state.get("update_notes", ""),
                            st.session_state.get("variants_note", ""),
                            st.session_state.get("image_notes", ""),
                        ),
                    },
                ]
                raw_de = call_openrouter(messages, OPENROUTER_MODEL_TEXT)

            parsed_de = parse_block(raw_de, "DE")

            if parsed_de["has_block"] and not de_title_ok(parsed_de["title"]):
                with st.spinner("DE title too long → tightening..."):
                    fix_msg = (
                        "Kürze NUR den DE TITLE auf maximal 80 Zeichen. "
                        "Bedeutung/Fakten beibehalten. Rest unverändert. "
                        "Gib erneut das gleiche [DE]-Format aus."
                    )
                    messages.append({"role": "assistant", "content": clean_text(raw_de)})
                    messages.append({"role": "user", "content": fix_msg})
                    raw_de = call_openrouter(messages, OPENROUTER_MODEL_TEXT)
                    parsed_de = parse_block(raw_de, "DE")

            st.session_state["draft_raw"] = parsed_de["raw"]
            st.session_state["out_de_title"] = parsed_de["title"]
            st.session_state["out_de_desc"] = parsed_de["desc"]
            st.rerun()

    with st.form("update_form"):
        update_notes = st.text_area(
            "UPDATE NOTES (facts you want to apply / mandatory)",
            height=140,
            key="update_notes",
            placeholder="Facts only...",
        )

        st.markdown('<div class="apply-update">', unsafe_allow_html=True)
        btn_update = st.form_submit_button(
            "Apply updates (keep draft)",
            use_container_width=True,
            disabled=not st.session_state.get("draft_raw"),
        )
        st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.subheader("Output")

    if btn_update:
        if not st.session_state.get("draft_raw"):
            st.warning("No draft yet. Click Generate first.")
            st.stop()
        if not source.strip():
            st.warning("Paste SOURCE first (same product).")
        else:
            with st.spinner("Applying updates..."):
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT_DE},
                    {
                        "role": "user",
                        "content": build_update_user_prompt(
                            source,
                            st.session_state["draft_raw"],
                            update_notes,
                            st.session_state.get("variants_note", ""),
                            st.session_state.get("image_notes", ""),
                        ),
                    },
                ]
                raw_de = call_openrouter(messages, OPENROUTER_MODEL_TEXT)

            parsed_de = parse_block(raw_de, "DE")

            if parsed_de["has_block"] and not de_title_ok(parsed_de["title"]):
                with st.spinner("DE title too long → tightening..."):
                    fix_msg = (
                        "Kürze NUR den DE TITLE auf maximal 80 Zeichen. "
                        "Bedeutung/Fakten beibehalten. Rest unverändert. "
                        "Gib erneut das gleiche [DE]-Format aus."
                    )
                    messages.append({"role": "assistant", "content": clean_text(raw_de)})
                    messages.append({"role": "user", "content": fix_msg})
                    raw_de = call_openrouter(messages, OPENROUTER_MODEL_TEXT)
                    parsed_de = parse_block(raw_de, "DE")

            st.session_state["draft_raw"] = parsed_de["raw"]
            st.session_state["out_de_title"] = parsed_de["title"]
            st.session_state["out_de_desc"] = parsed_de["desc"]

    st.text_input("Title (DE) — must be ≤ 80 chars", key="out_de_title")
    st.caption(f"DE title length: {len(st.session_state.get('out_de_title', ''))} / 80")
    st.text_area("Description (DE)", height=220, key="out_de_desc")

    btn_quality_check = st.button(
        "Run quality check",
        use_container_width=True,
        disabled=not (st.session_state.get("out_de_title") or st.session_state.get("out_de_desc")),
    )

    if btn_quality_check:
        if not source.strip():
            st.warning("Paste SOURCE first.")
        else:
            with st.spinner("Running quality check..."):
                check_messages = [
                    {"role": "system", "content": QUALITY_CHECK_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_quality_check_user_prompt(
                            source,
                            st.session_state.get("out_de_title", ""),
                            st.session_state.get("out_de_desc", ""),
                            st.session_state.get("update_notes", ""),
                            st.session_state.get("variants_note", ""),
                            st.session_state.get("image_notes", ""),
                        ),
                    },
                ]
                quality_report = call_openrouter(check_messages, OPENROUTER_MODEL_TEXT)
            st.session_state["quality_report"] = clean_text(quality_report)

    st.text_area(
        "Quality check (read-only)",
        value=st.session_state.get("quality_report", ""),
        height=140,
        disabled=True,
    )

    de_title_val = st.session_state.get("out_de_title", "")
    de_desc_val = st.session_state.get("out_de_desc", "")
    combined_de = f"{de_title_val}\n\n{de_desc_val}"
    ebay_html = build_ebay_template(de_title_val, de_desc_val)

    col_copy_left, col_copy_mid, col_copy_right, col_copy_template = st.columns([1, 1, 1, 1.2])
    with col_copy_left:
        render_copy_button("Copy DE Title", de_title_val, key="copy_de_title")
    with col_copy_mid:
        render_copy_button("Copy Both (DE)", combined_de, key="copy_de_both")
    with col_copy_right:
        render_copy_button("Copy DE Description", de_desc_val, key="copy_de_desc")
    with col_copy_template:
        render_copy_button("Copy eBay Template (DE)", ebay_html, key="copy_de_ebay_template")

    st.divider()
    st.caption("Draft memory (what the model will update next):")
    st.text_area("Current draft (raw)", value=st.session_state.get("draft_raw", ""), height=160)
