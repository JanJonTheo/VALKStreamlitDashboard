import streamlit as st
import pandas as pd
import json
import re
from api_client import get_json
from urllib.parse import quote

# =========================
# Colors & Mappings
# =========================
STATE_COLORS = {
    "War": "#e74c3c",
    "CivilWar": "#e74c3c",
    "Election": "#e67e22",
    "Elections": "#e67e22",
    "Expansion": "#3498db",
    "Boom": "#2980b9",
    "Bust": "#f1c40f",
    "CivilUnrest": "#f39c12",
    "Famine": "#8e44ad",
    "Outbreak": "#16a085",
    "Investment": "#27ae60",
    "PublicHoliday": "#9b59b6",
    "InfrastructureFailure": "#7f8c8d",
    "Drought": "#d35400",
    "Blight": "#8e44ad",
    "Bust2": "#f1c40f",  # falls API-Varianten existieren
    "PirateAttack": "#16a085",
    "Retreat": "#95a5a6",
    "None": "#181c22",
    "": "#181c22",
}

STATE_ICONS = {
    "War": "⚔️",
    "CivilWar": "⚔️",
    "Election": "🗳️",
    "Elections": "🗳️",
    "Expansion": "🡅",
    "Boom": "📈",
    "Bust": "📉",
    "CivilUnrest": "🔥",
    "Famine": "🍞❌",
    "Outbreak": "🧪",
    "Investment": "💰",
    "PublicHoliday": "🎉",
    "InfrastructureFailure": "🧱",
    "Drought": "🌵",
    "Blight": "🌿❌",
    "PirateAttack": "☠️",
    "Retreat": "⬇️",
    "None": "•",
    "": "•",
}

def _pretty_state_name(s: str) -> str:
    if not s:
        return ""
    # bekanntere Sonderfälle schöner schreiben
    specials = {
        "CivilWar": "Civil War",
        "PublicHoliday": "Public Holiday",
        "InfrastructureFailure": "Infrastructure Failure",
    }
    if s in specials:
        return specials[s]
    # CamelCase → "Camel Case"
    return re.sub(r"(?<!^)(?=[A-Z])", " ", s)

def _parse_states(cell) -> list[str]:
    if not cell:
        return []
    if isinstance(cell, list):
        items = cell
    else:
        items = [x.strip() for x in str(cell).split(",")]
    return [x for x in items if x and x != "None"]

# === Textformatierung (zeigt die Icons) ===
def fmt_state_text(val: str) -> str:
    if not val or val == "None":
        return ""
    return f"{STATE_ICONS.get(val, '•')} {_pretty_state_name(val)}"

def fmt_states_text(cell) -> str:
    states = _parse_states(cell)
    if not states:
        return ""
    return " · ".join(f"{STATE_ICONS.get(s, '•')} {_pretty_state_name(s)}" for s in states)

# === Hintergrund-Färbung ===
def style_state(val: str) -> str:
    if not val or val == "None":
        return ""
    c = STATE_COLORS.get(val, "#181c22")
    return f"background-color:{c}; color:#fff; font-weight:600;"

def style_states_cell(cell) -> str:
    states = _parse_states(cell)
    if not states:
        return ""
    # Ein State → normale Hintergrundfarbe
    if len(states) == 1:
        c = STATE_COLORS.get(states[0], "#181c22")
        return f"background-color:{c}; color:#fff; font-weight:600;"
    # Mehrere States → gleich breite Streifen (linear-gradient)
    n = len(states)
    stops = []
    for i, s in enumerate(states):
        start = int(i * 100 / n)
        end = int((i + 1) * 100 / n)
        color = STATE_COLORS.get(s, "#181c22")
        stops.append(f"{color} {start}% {end}%")
    gradient = ", ".join(stops)
    # Weißer Text + leichte Outline für Lesbarkeit
    return (
        f"background: linear-gradient(90deg, {gradient}); "
        f"color:#fff; font-weight:700; text-shadow: 0 1px 2px rgba(0,0,0,.35);"
    )

def fmt_pct(x: float) -> str:
    try:
        return f"{x:.2%}"
    except Exception:
        return ""

# Optional Override-Tabellen (falls bestimmte Keys hübscher heißen sollen)
GOV_OVERRIDES = {
    "$government_Corporate;": "Corporate",
    "$government_Dictatorship;": "Dictatorship",
    "$government_Feudal;": "Feudal",
    "$government_Patronage;": "Patronage",
    "$government_Democracy;": "Democracy",
    "$government_Communism;": "Communism",
    "$government_Confederacy;": "Confederacy",
    "$government_Cooperative;": "Cooperative",
    "$government_Anarchy;": "Anarchy",
    "$government_PrisonColony;": "Prison Colony",
}

SEC_OVERRIDES = {
    "$SYSTEM_SECURITY_low;": "Low",
    "$SYSTEM_SECURITY_medium;": "Medium",
    "$SYSTEM_SECURITY_high;": "High",
    "$SYSTEM_SECURITY_anarchy;": "Anarchy",
}

# Farbklassen für Chips (CSS Klassen -> Farben)
CHIP_COLORS = {
    "ok": "#064e3b",       # green
    "warn": "#5b3206",     # amber
    "info": "#0f2942",     # blue
    "pp": "#2b193e",       # violet
    "neut": "#27272a",     # gray
    "red": "#3b0d0d",      # red
    "vio": "#3a225f",      # alternative violet
    "sky": "#103048",      # alternative blue
}

# Security -> Farbklasse
def chip_class_for_security(label: str) -> str:
    s = (label or "").strip().lower()
    if s == "high":
        return "ok"
    if s == "medium":
        return "info"
    if s in ("low", "anarchy"):
        return "warn" if s == "low" else "red"
    return "neut"

# Government -> Farbklasse (grob gruppiert)
def chip_class_for_government(label: str) -> str:
    g = (label or "").strip().lower()
    if g in ("corporate", "cooperative"):
        return "sky"
    if g in ("democracy", "confederacy"):
        return "info"
    if g in ("dictatorship", "anarchy", "prison colony"):
        return "red"
    if g in ("patronage", "feudal"):
        return "vio"
    if g in ("communism",):
        return "warn"
    return "neut"

# Helpers (formatting, parsing, options, resets)
def humanize_constant(val: str, kind: str) -> str:
    """Wandelt FDev-Keys ($government_X; / $SYSTEM_SECURITY_Y;) in Lesetext."""
    if not val:
        return "-"
    if kind == "gov":
        if val in GOV_OVERRIDES:
            return GOV_OVERRIDES[val]
    if kind == "sec":
        if val in SEC_OVERRIDES:
            return SEC_OVERRIDES[val]
    # generischer Fallback
    s = str(val).replace("$", "").replace(";", "")
    s = s.replace("government_", "").replace("SYSTEM_SECURITY_", "")
    s = s.replace("_", " ").title()
    return s or "-"

def color_state(val):
    color = STATE_COLORS.get(val, "#181c22")
    return f"background-color:{color};color:#fff;" if val and val != "None" else ""

def color_states_cell(cell):
    if not cell:
        return ""
    states = [s.strip() for s in cell.split(",") if s.strip()]
    if not states:
        return ""
    color = STATE_COLORS.get(states[0], "#181c22")
    return f"background-color:{color};color:#fff;"

def to_state_list(val):
    """'null'/None/JSON-String/Liste -> Liste reiner State-Namen"""
    if val in (None, "null", "None", ""):
        return []
    if isinstance(val, list):
        out = []
        for x in val:
            if isinstance(x, dict) and "State" in x:
                out.append(x["State"])
            elif isinstance(x, str):
                out.append(x)
        return out
    if isinstance(val, str):
        try:
            obj = json.loads(val)
            return to_state_list(obj)
        except Exception:
            return [s.strip() for s in val.split(",") if s.strip()]
    return []

def parse_json_str_list(val):
    """Für powerplays.power (JSON-String mit Stringliste)."""
    if not val:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            obj = json.loads(val)
            if isinstance(obj, list):
                return [str(x) for x in obj]
        except Exception:
            return [val]
    return [str(val)]

def build_stable_options(base_list, current_value, snapshot_value):
    base = list(dict.fromkeys([x for x in ([current_value, snapshot_value] + (base_list or [])) if x]))
    options = [""] + base
    idx = 0
    if current_value in options:
        idx = options.index(current_value)
    elif snapshot_value in options:
        idx = options.index(snapshot_value)
    return options, idx

RESET_WIDGET_KEYS = [
    "system_name_filter",
    "faction_filter",
    "controlling_faction_filter",
    "controlling_power_filter",
    "power_filter",
    "state_filter",
    "pending_state_filter",
    "recovering_state_filter",
    "has_conflict_filter",
    "controlling_faction_in_conflict_filter",
    "population_preset_filter",
    "population_min_filter",
    "population_max_filter",
    "powerplay_state_filter",
]

POP_PRESETS = {
    "All": (None, None),
    "1 – 100,000": (1, 100_000),
    "100,000 – 1,000,000": (100_000, 1_000_000),
    "1,000,000 – 100,000,000": (1_000_000, 100_000_000),
    "100,000,000 – 500,000,000": (100_000_000, 500_000_000),
    "500,000,000 – 1,000,000,000": (500_000_000, 1_000_000_000),
    "1,000,000,000+": (1_000_000_000, None),
    "Custom…": ("custom", "custom"),
}

def _fmt_us(n: int | None) -> str:
    if n is None:
        return "∞"
    return f"{n:,}"

def build_population_param(pop_min: int | None, pop_max: int | None) -> str | None:
    """
    Returns 'min-max' per API spec. Open upper bound -> 'min-'.
    Whole range -> None (do not include the parameter).
    """
    if pop_min is None and pop_max is None:
        return None
    if pop_min is None:
        pop_min = 0
    if pop_max is None:
        return f"{int(pop_min)}-"
    return f"{int(pop_min)}-{int(pop_max)}"

def _apply_reset_if_requested():
    """Wenn _do_reset gesetzt ist, alle Widget-Keys & Suche zurücksetzen.
       Muss VOR dem Rendern der Widgets aufgerufen werden!"""
    if st.session_state.get("_do_reset"):
        # Widget-Keys entfernen -> Widgets starten mit Default
        for k in RESET_WIDGET_KEYS:
            st.session_state.pop(k, None)

        # Suchzustand zurücksetzen
        st.session_state.run_search = False
        st.session_state.params_snapshot = {}
        st.session_state.system_name_snapshot = ""

        # Flag löschen
        st.session_state._do_reset = False

# CSS für kompaktere Filter-UI
def inject_aligned_rows_css(col_px: int = 260, chk_px: int = 180, gap_rem: float = .28):
    st.markdown(f"""
    <style>
      :root {{
        --valk-col: min({col_px}px, 20vw);
        --valk-chk: min({chk_px}px, 15vw);
        --valk-gap: {gap_rem}rem;
      }}

      /* dichter: Widgets & Labels */
      [data-testid="stExpander"] .streamlit-expanderContent [data-testid="stSelectbox"],
      [data-testid="stExpander"] .streamlit-expanderContent [data-testid="stNumberInput"],
      [data-testid="stExpander"] .streamlit-expanderContent [data-testid="stTextInput"] {{
        margin-bottom: .28rem !important;
      }}
      label {{ margin-bottom: .18rem !important; }}

      /* Responsive grid templates - stack on small screens */
      @media (max-width: 1200px) {{
        #sys-row + div[data-testid="stHorizontalBlock"],
        #fac-row + div[data-testid="stHorizontalBlock"],
        #pow-row + div[data-testid="stHorizontalBlock"] {{
          display: flex !important;
          flex-direction: column !important;
          gap: var(--valk-gap) !important;
        }}
        #sys-row + div[data-testid="stHorizontalBlock"] > div,
        #fac-row + div[data-testid="stHorizontalBlock"] > div,
        #pow-row + div[data-testid="stHorizontalBlock"] > div {{
          width: 100% !important;
          max-width: 400px !important;
        }}
      }}

      /* Wide screen grid layout */
      @media (min-width: 1201px) {{
        #sys-row + div[data-testid="stHorizontalBlock"],
        #fac-row + div[data-testid="stHorizontalBlock"],
        #pow-row + div[data-testid="stHorizontalBlock"] {{
          display: grid !important;
          grid-template-columns: repeat(3, 1fr) !important;
          gap: var(--valk-gap) !important;
          align-items: end !important;
        }}
      }}
    </style>
    """, unsafe_allow_html=True)

def inject_row_css(field_px: int = 260, checkbox_px: int = 160, gap_rem: float = .35):
    st.markdown(f"""
    <style>
      /* --- Kompaktere Widget-Abstände in Expandern --- */
      [data-testid="stExpander"] .streamlit-expanderContent 
        [data-testid="stSelectbox"],
      [data-testid="stExpander"] .streamlit-expanderContent 
        [data-testid="stMultiSelect"],
      [data-testid="stExpander"] .streamlit-expanderContent 
        [data-testid="stNumberInput"],
      [data-testid="stExpander"] .streamlit-expanderContent 
        [data-testid="stTextInput"],
      [data-testid="stExpander"] .streamlit-expanderContent 
        [data-testid="stDateInput"] {{
        margin-bottom: .35rem !important;
      }}
      [data-testid="stExpander"] .streamlit-expanderContent p {{
        margin: .25rem 0 !important;
      }}

      /* --- System-Reihe: System Name / Population / Has Conflict / Filler --- */
      #sys-row-start + div[data-testid="stHorizontalBlock"] {{
        display: grid !important;
        grid-template-columns: {field_px}px {field_px}px {checkbox_px}px 1fr !important;
        gap: {gap_rem}rem !important;
        align-items: end !important;
        justify-content: start !important;
      }}

      /* --- Faction-Reihe: 5 Selects + Checkbox + Filler --- */
      #fac-row-start + div[data-testid="stHorizontalBlock"] {{
        display: grid !important;
        grid-template-columns: repeat(5, {field_px}px) {checkbox_px}px 1fr !important;
        gap: {gap_rem}rem !important;
        align-items: end !important;
        justify-content: start !important;
      }}

      /* --- Power-Reihe: 3 Selects + Filler --- */
      #pow-row-start + div[data-testid="stHorizontalBlock"] {{
        display: grid !important;
        grid-template-columns: {field_px}px {field_px}px {field_px}px 1fr !important;
        gap: {gap_rem}rem !important;
        align-items: end !important;
        justify-content: start !important;
      }}
    </style>
    """, unsafe_allow_html=True)

def inject_sysrow_css(field_px: int = 260, checkbox_px: int = 160, gap_rem: float = .5):
    st.markdown(f"""
    <style>
      /* Wir targeten GENAU die Columns-Gruppe, die direkt auf den Marker folgt */
      #sys-row-start + div[data-testid="stHorizontalBlock"] {{
        display: grid !important;
        grid-template-columns: {field_px}px {field_px}px {checkbox_px}px 1fr !important;
        gap: {gap_rem}rem !important;
        align-items: end !important;   /* Checkbox unten bündig */
        justify-content: start !important;
      }}
    </style>
    """, unsafe_allow_html=True)

def inject_compact_filter_css(width_px: int = 260):
    # Globale Regeln, kein Scoping – sonst greift es in Streamlit nicht zuverlässig
    st.markdown(f"""
    <style>
      :root {{
        --valk-filter-width: min({width_px}px, 90vw);
        --valk-filter-width-mobile: min(300px, 95vw);
      }}

      /* ---------- kompakter Expander ---------- */
      [data-testid="stExpander"] details > summary {{
        padding: .35rem .5rem !important;
        font-size: .95rem !important;
      }}
      [data-testid="stExpander"] .streamlit-expanderContent {{
        padding: .35rem .25rem .25rem .25rem !important;
      }}

      /* ---------- Responsive Widget-Breiten ---------- */
      @media (max-width: 768px) {{
        :root {{
          --valk-filter-width: var(--valk-filter-width-mobile);
        }}
        
        /* Auf kleinen Bildschirmen: volle Breite nutzen */
        [data-testid="stSelectbox"],
        [data-testid="stMultiSelect"],
        [data-testid="stNumberInput"],
        [data-testid="stTextInput"],
        [data-testid="stDateInput"] {{
          width: 100% !important;
        }}
        
        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div,
        [data-testid="stNumberInput"] > div,
        [data-testid="stTextInput"] > div,
        [data-testid="stDateInput"] > div {{
          width: 100% !important;
          max-width: 100% !important;
          min-width: auto !important;
        }}
      }}

      @media (min-width: 769px) {{
        /* Desktop: feste Breiten beibehalten */
        [data-testid="stSelectbox"],
        [data-testid="stMultiSelect"],
        [data-testid="stNumberInput"],
        [data-testid="stTextInput"],
        [data-testid="stDateInput"] {{
          display: inline-block !important;
          flex: 0 0 auto !important;
        }}

        /* 1) Erste Wrapper-Ebene (Streamlit um das Widget) */
        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div,
        [data-testid="stNumberInput"] > div,
        [data-testid="stTextInput"] > div,
        [data-testid="stDateInput"] > div {{
          width: var(--valk-filter-width) !important;
          max-width: var(--valk-filter-width) !important;
          min-width: var(--valk-filter-width) !important;
        }}

        /* 2) Nächste Ebene im Select */
        [data-testid="stSelectbox"] > div > div,
        [data-testid="stMultiSelect"] > div > div {{
          width: var(--valk-filter-width) !important;
          max-width: var(--valk-filter-width) !important;
          min-width: var(--valk-filter-width) !important;
        }}

        /* 3) BaseWeb/React-Select Container selbst */
        [data-testid="stSelectbox"] div[data-baseweb="select"],
        [data-testid="stMultiSelect"] div[data-baseweb="select"],
        [data-testid="stSelectbox"] div[role="combobox"],
        [data-testid="stMultiSelect"] div[role="combobox"] {{
          width: var(--valk-filter-width) !important;
          max-width: var(--valk-filter-width) !important;
          min-width: var(--valk-filter-width) !important;
        }}

        /* 4) Inputs direkt */
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input {{
          width: var(--valk-filter-width) !important;
          max-width: var(--valk-filter-width) !important;
          min-width: var(--valk-filter-width) !important;
        }}
      }}

      /* Labels enger (mehr vertikale Dichte) */
      label {{ margin-bottom: .2rem !important; }}

      /* kompakte Button-Reihe - responsive */
      .btn-row > div {{ 
        display: flex !important; 
        gap: .5rem !important; 
        align-items: center !important; 
        flex-wrap: wrap !important;
      }}
      
      @media (max-width: 480px) {{
        .btn-row > div {{
          flex-direction: column !important;
          align-items: stretch !important;
        }}
      }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# Chip UI
# =========================
def chip_css():
    return f"""
    <style>
      .valk-badges {{ display:flex; flex-wrap:wrap; gap:.5rem; margin:.35rem 0 .85rem 0; }}
      .valk-badge {{ font-size:.85rem; line-height:1; padding:.45rem .6rem; border-radius:999px;
                     background:#1f2937; border:1px solid #374151; display:inline-flex; gap:.35rem;
                     align-items:center; white-space:nowrap; }}
      .valk-badge .lbl {{ opacity:.75; }}
      {"".join([f".valk-badge.{k}{{background:{v};border-color:{v};}}" for k,v in CHIP_COLORS.items()])}
    </style>
    """

def chip(label, value, klass="neut"):
    if value in (None, "", "-", "null"):
        return ""
    return f'<div class="valk-badge {klass}"><span class="lbl">{label}:</span><strong>{value}</strong></div>'

def render_grouped_header(sysinfo: dict, pp0: dict, conflicts_count: int = 0):
    allegiance = sysinfo.get("allegiance") or "-"
    government_raw = sysinfo.get("government")
    security_raw = sysinfo.get("security")
    population = sysinfo.get("population")

    government = humanize_constant(government_raw, "gov")
    security   = humanize_constant(security_raw, "sec")

    controlling = sysinfo.get("controlling_faction") or "-"
    controlling_power = sysinfo.get("controlling_power") or "-"

    # PowerPlay (erste Zeile, optional)
    powers_list = parse_json_str_list(pp0.get("power"))
    p_state     = pp0.get("powerplay_state") or "-"
    ctrl_prog   = pp0.get("control_progress")
    underm      = pp0.get("undermining")
    reinf       = pp0.get("reinforcement")

    # ---- Gruppen zusammenstellen ----
    sys_items = [
        chip("Security", security, chip_class_for_security(security)),
        chip("Population", f"{int(population):,}".replace(",", ".")) if isinstance(population, int) else "",
        chip("Conflicts", str(int(conflicts_count)), "warn" if conflicts_count else "neut"),
    ]

    faction_items = [
        chip("Controlling Faction", controlling, "ok"),
        chip("Allegiance", allegiance, "info"),
        chip("Government", government, chip_class_for_government(government)),
    ]

    pp_items = [
        chip("Controlling Power", controlling_power, "pp" if controlling_power != "-" else "neut"),
        chip("Powers (nearby)", ", ".join(powers_list), "pp") if powers_list else "",
        chip("PowerPlay", p_state, "pp") if p_state and p_state != "-" else "",
        chip("Ctrl-Progress", f"{float(ctrl_prog):.1%}", "pp") if isinstance(ctrl_prog, (int, float)) else "",
        chip("Undermining", f"{int(underm):,}".replace(",", "."), "warn" if (isinstance(underm, (int, float)) and underm > 0) else "neut") if isinstance(underm, (int, float)) else "",
        chip("Reinforcement", f"{int(reinf):,}".replace(",", "."), "ok" if (isinstance(reinf, (int, float)) and reinf > 0) else "neut") if isinstance(reinf, (int, float)) else "",
    ]

    # ---- CSS + HTML (Gruppenüberschriften + Chips) ----
    css = chip_css() + """
    <style>
      .valk-group { margin:.35rem 0 1rem 0; }
      .valk-title { font-size:.9rem; opacity:.85; margin-bottom:.35rem; 
                    text-transform:uppercase; letter-spacing:.06em; }
    </style>
    """
    def row(title, items):
        row_html = ''.join([i for i in items if i])
        if not row_html:
            return ""
        return f'<div class="valk-group"><div class="valk-title">{title}</div><div class="valk-badges">{row_html}</div></div>'

    html = css + row("System Info", sys_items) + row("Faction Info", faction_items) + row("Powerplay", pp_items)
    st.markdown(html, unsafe_allow_html=True)

def render_header_chips(sysinfo: dict, pp0: dict, conflict_count: int = 0):
    allegiance = sysinfo.get("allegiance") or "-"
    government_raw = sysinfo.get("government")
    security_raw = sysinfo.get("security")
    population = sysinfo.get("population")

    government = humanize_constant(government_raw, "gov")
    security = humanize_constant(security_raw, "sec")

    controlling = sysinfo.get("controlling_faction") or "-"
    controlling_power = sysinfo.get("controlling_power") or "-"

    powers_list = parse_json_str_list(pp0.get("power"))
    p_state = pp0.get("powerplay_state") or "-"
    ctrl_prog = pp0.get("control_progress")
    underm = pp0.get("undermining")
    reinf = pp0.get("reinforcement")

    items = [
        chip("Controlling Faction", controlling, "ok"),
        chip("Controlling Power", controlling_power, "pp" if controlling_power != "-" else "neut"),
        chip("Allegiance", allegiance, "info"),
        chip("Government", government, chip_class_for_government(government)),
        chip("Security", security, chip_class_for_security(security)),
        chip("Population", f"{int(population):,}".replace(",", ".")) if isinstance(population, int) else "",
    ]
    if powers_list:
        items.append(chip("Powers (nearby)", ", ".join(powers_list), "pp"))
    if p_state and p_state != "-":
        items.append(chip("PowerPlay", p_state, "pp"))
    if isinstance(ctrl_prog, (int, float)):
        items.append(chip("Ctrl-Progress", f"{ctrl_prog:.1%}", "pp"))
    if isinstance(underm, (int, float)) and underm >= 0:
        items.append(chip("Undermining", f"{int(underm):,}".replace(",", "."), "warn" if underm else "neut"))
    if isinstance(reinf, (int, float)) and reinf >= 0:
        items.append(chip("Reinforcement", f"{int(reinf):,}".replace(",", "."), "ok" if reinf else "neut"))
    if conflict_count > 0:
        items.append(chip("Conflicts", str(conflict_count), "red"))

    html = chip_css() + '<div class="valk-badges">' + "".join([i for i in items if i]) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ============================
# Conflicts-Mapping & Renderer
# ============================
CONFLICT_TYPE_LABELS = {
    "war": "⚔️ War",
    "civilwar": "🏛 Civil War",
    "election": "🗳 Election",
}
CONFLICT_TYPE_COLORS = {
    "War": "#c0392b",        # rot
    "Civil War": "#e67e22",  # orange
    "Election": "#3498db",   # blau
}
CONFLICT_STATUS_COLORS = {
    "active": "#065f46",     # grün
    "pending": "#92400e",    # amber
    "ended": "#374151",      # grau (fallback)
}

LEAD_GREEN = "#065f46"      # führt
TRAIL_RED  = "#7f1d1d"      # verliert
TIE_YELLOW = "#a16207"      # unentschieden
CELL_TEXT  = "#ffffff"

def _conflict_row_style(row: pd.Series) -> pd.Series:
    """Gibt pro Spalte CSS-Styles zurück (Pandas Styler row-wise)."""
    styles = {}

    # Type einfärben
    tlabel = row.get("Type", "")
    tcolor = CONFLICT_TYPE_COLORS.get(tlabel, "#374151")
    styles["Type"] = f"background-color:{tcolor};color:{CELL_TEXT};"

    # Status einfärben
    status = str(row.get("Status", "") or "").lower()
    scolor = CONFLICT_STATUS_COLORS.get(status, "#374151")
    styles["Status"] = f"background-color:{scolor};color:{CELL_TEXT};"

    # Leader/Loser markieren (Won D1 / Won D2)
    d1 = int(row.get("Won D1") or 0)
    d2 = int(row.get("Won D2") or 0)

    if d1 == 0 and d2 == 0:
        # Noch keine gewerteten Tage -> KEINE farbliche Markierung der Fraktionen
        pass
    elif d1 > d2:
        styles["Faction 1"] = f"background-color:{LEAD_GREEN};color:{CELL_TEXT};"
        styles["Faction 2"] = f"background-color:{TRAIL_RED};color:{CELL_TEXT};"
    elif d2 > d1:
        styles["Faction 2"] = f"background-color:{LEAD_GREEN};color:{CELL_TEXT};"
        styles["Faction 1"] = f"background-color:{TRAIL_RED};color:{CELL_TEXT};"
    else:
        # Unentschieden (aber mind. einer > 0)
        styles["Faction 1"] = f"background-color:{TIE_YELLOW};color:{CELL_TEXT};"
        styles["Faction 2"] = f"background-color:{TIE_YELLOW};color:{CELL_TEXT};"

    # Stakes etwas dezenter
    styles["Stake 1"] = "opacity:.9;"
    styles["Stake 2"] = "opacity:.9;"

    return pd.Series(styles)

def render_conflicts_table(conflicts: list):
    """Baut die stylische Conflicts-Tabelle und rendert sie."""
    if not conflicts:
        return

    rows = []
    for c in conflicts:
        # Label-Mapping für type
        raw_type = (c.get("war_type") or "").lower()
        type_label = CONFLICT_TYPE_LABELS.get(raw_type, raw_type.title() if raw_type else "-")
        rows.append({
            "Type": type_label,
            "Status": c.get("status") or "-",
            "Faction 1": c.get("faction1") or "-",
            "Stake 1": c.get("stake1") or "-",
            "Faction 2": c.get("faction2") or "-",
            "Stake 2": c.get("stake2") or "-",
            "Won D1": c.get("won_days1") or 0,
            "Won D2": c.get("won_days2") or 0,
        })

    df = pd.DataFrame(rows)

    # hübsche Breiten & Ausrichtung
    styled = (
        df.style
          .apply(_conflict_row_style, axis=1)
          .set_properties(subset=["Type"], **{"min-width": "110px", "max-width": "140px", "text-align": "center"})
          .set_properties(subset=["Status"], **{"min-width": "90px", "max-width": "110px", "text-align": "center"})
          .set_properties(subset=["Faction 1", "Faction 2"], **{"min-width": "220px"})
          .set_properties(subset=["Stake 1", "Stake 2"], **{"min-width": "200px", "max-width": "320px"})
          .set_properties(subset=["Won D1", "Won D2"], **{"min-width": "80px", "text-align": "center"})
    )
    st.table(styled)

# ============================
# Page Render, Filter & Search
# ============================
def handle_too_many_systems_response(resp) -> bool:
    """Erkennt die API-Antwort bei zu vielen Treffern und rendert eine Nutzerinfo.
       Gibt True zurück, wenn die Antwort bereits verarbeitet wurde (früher return)."""
    if isinstance(resp, dict) and resp.get("error") and isinstance(resp.get("systems"), list):
        count = resp.get("count", 0)
        limit_hint = 100  # aktuell gesetztes Server-Limit
        st.error("Zu viele Systeme gefunden. Bitte schränke die Filter weiter ein.")
        st.caption(f"Gefundene Systeme: {count} (Limit: {limit_hint})")

        # Kleine Hilfestellung
        with st.expander("Vorschläge für Filter-Verfeinerung", expanded=True):
            st.write(
                "- **System Name** (präziser, mindestens 3 Zeichen)\n"
                "- **Controlling Faction / Power** ergänzen\n"
                "- **State / Pending / Recovering** festlegen\n"
                "- **Has Conflict** aktivieren, wenn relevant"
            )

        # Trefferliste anzeigen (st.table)
        systems = resp.get("systems", [])
        if systems:
            st.subheader("Trefferliste (Auszug)")
            st.table(pd.DataFrame({"System": systems}))

        return True
    return False

def get_list_from_api(endpoint, label="name"):
    try:
        data = get_json(endpoint)
        if isinstance(data, list):
            # Falls die API eine Liste von Strings liefert
            if all(isinstance(x, str) for x in data):
                return sorted(data)
            # Falls die API eine Liste von Dicts liefert
            elif all(isinstance(x, dict) and label in x for x in data):
                return sorted([x[label] for x in data])
        return []
    except Exception:
        return []

def render():
    st.title("System Information")
    st.text("Shows system summary and minor factions. Filter by API parameters.")

    # Dropdown-Listen laden (können leer/flackernd sein)
    system_names = get_list_from_api("lists/systems")
    factions = get_list_from_api("lists/factions")
    controlling_factions = get_list_from_api("lists/controlling-factions")
    controlling_powers = get_list_from_api("lists/controlling-powers")
    powers = controlling_powers  # gleiche Liste wie controlling_power

    # STATE-Init (oben in render(), vor dem UI)
    if "run_search" not in st.session_state:
        st.session_state.run_search = False
    if "params_snapshot" not in st.session_state:
        st.session_state.params_snapshot = {}
    if "system_name_snapshot" not in st.session_state:
        st.session_state.system_name_snapshot = ""

    # Reset ggf. anwenden, BEVOR Widgets gerendert werden
    _apply_reset_if_requested()

    # CSS für kompakte Filter-UI
    inject_compact_filter_css(width_px=260)  # fixe Breite pro Control
    inject_aligned_rows_css(col_px=260, chk_px=180, gap_rem=.26)

    # FILTER als FORM – löst keine Suche aus, bis "Search" geklickt wird
    with st.form("system_filters"):
        # --- aktuelle Werte/Snapshots wie gehabt ---
        current_sel = st.session_state.get("system_name_filter", "")
        last_snapshot = st.session_state.get("system_name_snapshot", "")
        snap = st.session_state.get("params_snapshot", {})

        base = list(dict.fromkeys([x for x in ([current_sel, last_snapshot] + (system_names or [])) if x]))
        system_name_options = [""] + base

        sel_index = 0
        if current_sel and current_sel in system_name_options:
            sel_index = system_name_options.index(current_sel)
        elif last_snapshot and last_snapshot in system_name_options:
            sel_index = system_name_options.index(last_snapshot)

        # =========================
        # System (Expander)
        # =========================
        with st.expander("System", expanded=True):
            # Marker für das gemeinsame Grid (ID ändern!)
            st.markdown('<span id="sys-row"></span>', unsafe_allow_html=True)

            # Responsive columns: 3 on desktop, 1 on mobile
            sys_c1, sys_c2, sys_c3 = st.columns(3)

            with sys_c1:
                system_name = st.selectbox(
                    "System Name",
                    system_name_options,
                    index=sel_index,
                    key="system_name_filter"
                )
            with sys_c2:
                population_preset = st.selectbox(
                    "Population",
                    list(POP_PRESETS.keys()),
                    index=0,
                    key="population_preset_filter",
                )
            with sys_c3:
                has_conflict = st.checkbox("Has Conflict", value=False, key="has_conflict_filter")

            # Ableiten min/max + evtl. Custom
            pop_min, pop_max = POP_PRESETS[population_preset]
            if pop_min == "custom" and pop_max == "custom":
                cx1, cx2 = st.columns(2)
                with cx1:
                    pop_min = st.number_input("Min (incl.)", min_value=0, step=1, format="%d",
                                              key="population_min_filter")
                with cx2:
                    no_upper = st.checkbox("No upper limit", value=False)
                    if no_upper:
                        pop_max = None
                    else:
                        pop_max = st.number_input("Max (incl.)", min_value=0, step=1, format="%d",
                                                  key="population_max_filter")

            # Statuszeile
            if pop_min is None and pop_max is None:
                st.caption("Active range: **All**")
            elif pop_max is None:
                st.caption(f"Active range: **{_fmt_us(pop_min)}+**")
            else:
                st.caption(f"Active range: **{_fmt_us(pop_min)} – {_fmt_us(pop_max)}**")

        # =========================
        # Faction (Expander)
        # =========================
        with st.expander("Faction", expanded=False):
            st.markdown('<span id="fac-row"></span>', unsafe_allow_html=True)
            # First row: 3 main filters
            fac_c1, fac_c2, fac_c3 = st.columns(3)
            # Second row: 2 more filters + checkbox
            fac_c4, fac_c5, fac_c6 = st.columns(3)

            with fac_c1:
                cur = st.session_state.get("faction_filter", "")
                snap_val = snap.get("faction", "")
                opts, idx = build_stable_options(factions, cur, snap_val)
                faction = st.selectbox("Faction", opts, index=idx, key="faction_filter")

            with fac_c2:
                cur = st.session_state.get("controlling_faction_filter", "")
                snap_val = snap.get("controlling_faction", "")
                opts, idx = build_stable_options(controlling_factions, cur, snap_val)
                controlling_faction = st.selectbox("Controlling Faction", opts, index=idx,
                                                   key="controlling_faction_filter")

            with fac_c3:
                state = st.selectbox("State", [""] + list(STATE_COLORS.keys()), key="state_filter")

            with fac_c4:
                pending_state = st.selectbox("Pending State", [""] + list(STATE_COLORS.keys()),
                                             key="pending_state_filter")

            with fac_c5:
                recovering_state = st.selectbox("Recovering State", [""] + list(STATE_COLORS.keys()),
                                                key="recovering_state_filter")

            with fac_c6:
                controlling_faction_in_conflict = st.checkbox(
                    "Controlling Faction in conflict",
                    value=False,
                    help="Only systems where the chosen Controlling Faction is in conflict.",
                    key="controlling_faction_in_conflict_filter"
                )

        # =========================
        # Power (Expander)
        # =========================
        with st.expander("Power", expanded=False):
            st.markdown('<span id="pow-row"></span>', unsafe_allow_html=True)
            pow_c1, pow_c2, pow_c3 = st.columns(3)

            with pow_c1:
                cur = st.session_state.get("controlling_power_filter", "")
                snap_val = snap.get("controlling_power", "")
                opts, idx = build_stable_options(controlling_powers, cur, snap_val)
                controlling_power = st.selectbox("Controlling Power", opts, index=idx, key="controlling_power_filter")
            with pow_c2:
                cur = st.session_state.get("power_filter", "")
                snap_val = snap.get("power", "")
                opts, idx = build_stable_options(powers, cur, snap_val)
                power = st.selectbox("Power", opts, index=idx, key="power_filter")
            with pow_c3:
                powerplay_state = st.selectbox(
                    "Powerplay State",
                    [""] + ["Unoccupied", "Fortified", "Exploited", "Stronghold"],
                    key="powerplay_state_filter"
                )

        # =========================
        # Parameter zusammenstellen
        # =========================
        params = {}
        if faction: params["faction"] = faction
        if controlling_faction: params["controlling_faction"] = controlling_faction
        if controlling_power: params["controlling_power"] = controlling_power
        if power: params["power"] = power
        if powerplay_state: params["powerplay_state"] = powerplay_state
        if state: params["state"] = state
        if pending_state: params["pending_state"] = pending_state
        if recovering_state: params["recovering_state"] = recovering_state
        if has_conflict: params["has_conflict"] = "true"
        if controlling_faction_in_conflict: params["cf_in_conflict"] = "true"

        pop_param = build_population_param(pop_min, pop_max)
        if pop_param: params["population"] = pop_param

        # Buttons kompakt nebeneinander
        st.markdown('<div class="btn-row">', unsafe_allow_html=True)
        bcol1, bcol2 = st.columns([1, 1])
        with bcol1:
            submitted = st.form_submit_button("Search")
        with bcol2:
            # Hinweis: Reset-Button bleibt außerhalb der Form funktionsgleich – hier nur Dummy-Info
            st.caption("Use **Reset** below to clear all filters.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Validierungen/Submit Handling wie gehabt
        if submitted:
            if controlling_faction_in_conflict and not controlling_faction:
                st.error('Bitte wähle eine **Controlling Faction**, wenn du "Controlling Faction in conflict" aktivierst.')
            elif (pop_min is not None and pop_max is not None) and (pop_min > pop_max):
                st.error("Population range is invalid: Min must not be greater than Max.")
            else:
                st.session_state.system_name_snapshot = st.session_state.get("system_name_filter", "")
                st.session_state.params_snapshot = params
                st.session_state.run_search = True
                st.rerun()

    # Reset-Button: Nur Flag setzen und rerun -> Keys werden oben zurückgesetzt
    if st.button("Reset"):
        st.session_state._do_reset = True
        st.rerun()

    # Gate: Ohne Search-Klick nichts laden
    if not st.session_state.run_search:
        st.info("Setze Filter und klicke **Search**, um Daten zu laden.")
        return

    # Snapshots für die Suche
    system_name = st.session_state.system_name_snapshot
    params = st.session_state.params_snapshot

    # <<< NEU: jetzt erst leeren Suchfall abfangen >>>
    if not system_name and not {k: v for k, v in params.items() if v not in ("", None)}:
        st.warning("Bitte gib einen Systemnamen oder mindestens einen Filter an.")
        return
    st.markdown(f"Results for System: **{system_name or '*'}'** with Filters: `{params}`")

    # --- Daten holen (nur /system-summary; 400-Body sicher auswerten) ---
    try:
        path = f"system-summary/{quote(system_name, safe='')}" if system_name else "system-summary"
        data = get_json(path, params=params)

    except Exception as e:
        # Versuche, den JSON-Body der 4xx-Antwort auszulesen
        resp_json = None
        try:
            resp = getattr(e, "response", None)
            if resp is not None:
                resp_json = resp.json()
        except Exception:
            resp_json = None

        # Spezialfall „zu viele Systeme“ hübsch rendern + abbrechen
        if resp_json and handle_too_many_systems_response(resp_json):
            return

        # Kein Spezialfall → normaler Fehler
        st.error(f"Error loading data: {e}")
        return

    if isinstance(data, dict) and not ("error" in data and len(data) <= 3):
        data = [data]
    if not data:
        st.warning("No systems found.")
        return

    for entry in data:
        sysinfo = entry.get("system_info", {}) or {}
        sys_name = sysinfo.get("system_name", "Unknown")

        st.subheader(sys_name)

        # Powerplay (erste Zeile)
        pp_list = entry.get("powerplays") or []
        pp0 = pp_list[0] if pp_list else {}

        # Anzahl der Conflicts bestimmen
        conflicts = entry.get("conflicts", []) or []
        conflict_count = len(conflicts)

        # Header-Chips (inkl. Government/Security Mapping und Conflict-Chip)
        #render_header_chips(sysinfo, pp0, conflict_count)
        render_grouped_header(sysinfo, pp0, conflict_count)

        # Minor Factions
        factions = entry.get("factions", []) or []
        with st.expander("👥 Minor Factions", expanded=False):
            if not factions:
                st.info("No minor factions found.")
            else:
                df = pd.DataFrame([
                    {
                        "Name": f.get("name", ""),
                        "Allegiance": f.get("allegiance", ""),
                        "Government": humanize_constant(f.get("government", ""), "gov") if f.get("government") else "",
                        "State": "" if (f.get("state") in (None, "", "None")) else f.get("state"),
                        "Influence": f.get("influence", 0.0),
                        "Active States": ", ".join(to_state_list(f.get("active_states"))),
                        "Pending": ", ".join(to_state_list(f.get("pending_states"))),
                        "Recovering": ", ".join(to_state_list(f.get("recovering_states"))),
                    }
                    for f in factions
                ])

                df = df.sort_values(by="Influence", ascending=False).reset_index(drop=True)
                df.index = df.index + 1
                df.index.name = "#"

                styled = (
                    df.style
                    .map(style_state, subset=["State"])
                    .map(style_states_cell, subset=["Active States"])
                    .map(style_states_cell, subset=["Pending"])
                    .map(style_states_cell, subset=["Recovering"])
                    .format({
                        "Influence": fmt_pct,
                        "State": fmt_state_text,
                        "Active States": fmt_states_text,
                        "Pending": fmt_states_text,
                        "Recovering": fmt_states_text,
                    })
                    .set_properties(subset=["Influence"], **{
                        "text-align": "right",
                        "min-width": "90px", "max-width": "90px",
                    })
                    .set_properties(subset=["Name"], **{
                        "min-width": "200px", "max-width": "200px",
                    })
                    .set_properties(subset=["Allegiance"], **{
                        "min-width": "100px", "max-width": "100px",
                    })
                    .set_properties(subset=["Government"], **{
                        "min-width": "120px", "max-width": "120px",
                    })
                    .set_properties(subset=["State"], **{
                        "text-align": "center",
                        "min-width": "140px", "max-width": "160px",
                    })
                    .set_properties(subset=["Active States", "Pending", "Recovering"], **{
                        "min-width": "180px", "max-width": "220px",
                    })
                )
                st.table(styled)

        # --- Conflicts ---
        conflicts = entry.get("conflicts", []) or []
        with st.expander("⚔️ Conflicts", expanded=False):
            if conflicts:
                render_conflicts_table(conflicts)
            else:
                st.info("No conflicts found.")

        st.markdown("---")
