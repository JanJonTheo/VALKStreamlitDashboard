import json
import re
import uuid
from urllib.parse import quote

import pandas as pd
import streamlit as st
from api_client import get_json
from streamlit_searchbox import st_searchbox

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

CHIP_COLORS = {
    "ok": "#064e3b",
    "warn": "#5b3206",
    "info": "#0f2942",
    "pp": "#2b193e",
    "neut": "#27272a",
    "red": "#3b0d0d",
    "vio": "#3a225f",
    "sky": "#103048",
}

# =========================
# Helper functions
# =========================
def _build_params_from_state():
    p = {}
    gs = st.session_state
    if gs.get("faction_filter"): p["faction"] = gs["faction_filter"]
    if gs.get("controlling_faction_filter"): p["controlling_faction"] = gs["controlling_faction_filter"]
    if gs.get("state_filter"): p["state"] = gs["state_filter"]
    if gs.get("pending_state_filter"): p["pending_state"] = gs["pending_state_filter"]
    if gs.get("recovering_state_filter"): p["recovering_state"] = gs["recovering_state_filter"]
    if gs.get("controlling_faction_in_conflict_filter", False): p["cf_in_conflict"] = "true"
    if gs.get("controlling_power_filter"): p["controlling_power"] = gs["controlling_power_filter"]
    if gs.get("power_filter"): p["power"] = gs["power_filter"]
    if gs.get("powerplay_state_filter"): p["powerplay_state"] = gs["powerplay_state_filter"]
    if gs.get("has_conflict_filter", False): p["has_conflict"] = "true"
    # Population (falls genutzt)
    if gs.get("population_preset_filter") == "Custom…":
        if gs.get("population_min_filter") is not None:
            p["population_min"] = gs["population_min_filter"]
        if not gs.get("population_no_upper_filter", False) and gs.get("population_max_filter") is not None:
            p["population_max"] = gs["population_max_filter"]
    return p

def _pretty_state_name(s: str) -> str:
    if not s:
        return ""
    specials = {
        "CivilWar": "Civil War",
        "PublicHoliday": "Public Holiday",
        "InfrastructureFailure": "Infrastructure Failure",
    }
    if s in specials:
        return specials[s]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", s)

def _parse_states(cell):
    """Accept:
       - list[str]                -> ["War", "Boom"]
       - list[dict]               -> [{"State":"War","Trend":0}, ...] (keys may be 'State' or 'state')
       - comma-separated string   -> "War,Boom"
       - None                     -> []
       Return list[str] of state names (no 'None')."""
    if not cell:
        return []
    if isinstance(cell, list):
        out = []
        for x in cell:
            if isinstance(x, str):
                s = x.strip()
            elif isinstance(x, dict):
                s = (x.get("state") or x.get("State") or "").strip()
            else:
                s = str(x).strip()
            if s and s != "None":
                out.append(s)
        return out
    # string fallback
    return [x for x in (y.strip() for y in str(cell).split(",")) if x and x != "None"]

def fmt_state_text(val: str) -> str:
    if not val or val == "None":
        return ""
    return f"{STATE_ICONS.get(val, '•')} {_pretty_state_name(val)}"

def fmt_states_text(cell) -> str:
    states = _parse_states(cell)
    if not states:
        return ""
    return " · ".join(f"{STATE_ICONS.get(s, '•')} {_pretty_state_name(s)}" for s in states)

def style_state(val: str) -> str:
    if not val or val == "None":
        return ""
    c = STATE_COLORS.get(val, "#181c22")
    return f"background-color:{c}; color:#fff; font-weight:600;"

def style_states_cell(cell) -> str:
    states = _parse_states(cell)
    if not states:
        return ""
    if len(states) == 1:
        c = STATE_COLORS.get(states[0], "#181c22")
        return f"background-color:{c}; color:#fff; font-weight:600;"
    n = len(states)
    stops = []
    for i, s in enumerate(states):
        start = int(i * 100 / n)
        end = int((i + 1) * 100 / n)
        color = STATE_COLORS.get(s, "#181c22")
        stops.append(f"{color} {start}% {end}%")
    gradient = ", ".join(stops)
    return (
        f"background: linear-gradient(90deg, {gradient}); "
        f"color:#fff; font-weight:700; text-shadow: 0 1px 2px rgba(0,0,0,.35);"
    )

def fmt_pct(x: float) -> str:
    try:
        return f"{x:.2%}"
    except Exception:
        return ""

def chip_class_for_security(label: str) -> str:
    s = (label or "").strip().lower()
    if s == "high":
        return "ok"
    if s == "medium":
        return "info"
    if s in ("low", "anarchy"):
        return "warn" if s == "low" else "red"
    return "neut"

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

def humanize_constant(val: str, kind: str) -> str:
    if not val:
        return "-"
    if kind == "gov" and val in GOV_OVERRIDES:
        return GOV_OVERRIDES[val]
    if kind == "sec" and val in SEC_OVERRIDES:
        return SEC_OVERRIDES[val]
    s = str(val).replace("$", "").replace(";", "")
    s = s.replace("government_", "").replace("SYSTEM_SECURITY_", "")
    s = s.replace("_", " ").title()
    return s or "-"

def parse_json_str_list(val):
    if not val:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        try:
            obj = json.loads(val)
            if isinstance(obj, list):
                return [str(x) for x in obj]
        except Exception:
            return [val]
    return [str(val)]

def chip_css():
    return """
    <style>
      .valk-badges { display:flex; flex-wrap:wrap; gap:.5rem; margin:.35rem 0 .85rem 0; }
      .valk-badge { font-size:.85rem; line-height:1; padding:.45rem .6rem; border-radius:999px;
                    background:#1f2937; border:1px solid #374151; display:inline-flex; gap:.35rem;
                    align-items:center; white-space:nowrap; }
      .valk-badge .lbl { opacity:.75; }
      .valk-badge.ok{background:#064e3b;border-color:#064e3b;}
      .valk-badge.warn{background:#5b3206;border-color:#5b3206;}
      .valk-badge.info{background:#0f2942;border-color:#0f2942;}
      .valk-badge.pp{background:#2b193e;border-color:#2b193e;}
      .valk-badge.neut{background:#27272a;border-color:#27272a;}
      .valk-badge.red{background:#3b0d0d;border-color:#3b0d0d;}
      .valk-badge.vio{background:#3a225f;border-color:#3a225f;}
      .valk-badge.sky{background:#103048;border-color:#103048;}
    </style>
    """

def chip(label, value, klass="neut"):
    if value in (None, "", "-", "null"):
        return ""
    return f'<div class="valk-badge {klass}"><span class="lbl">{label}:</span><strong>{value}</strong></div>'

def _mark_dirty():
    # Wird durch Widgets via on_change gesetzt – triggert KEINE Suche
    # Wenn ein Search gerade "armed" ist, ignorieren wir Dirty-Events in diesem Run.
    if st.session_state.get("_lock_run_search", False):
        st.caption("🔒 DEBUG: dirty event ignored (armed search)")
        return

    st.session_state["_filters_dirty"] = True

    # Sobald ein Filter geändert wurde, alte Ergebnisse ausblenden
    if st.session_state.get("run_search", False):
        st.session_state["run_search"] = False
        #st.caption("🟡 DEBUG: filters marked dirty → run_search cleared")
    # kein st.rerun() nötig – Widgetänderung triggert ihn ohnehin

def render_grouped_header(sysinfo: dict, pp0: dict, conflicts_count: int = 0):
    allegiance = sysinfo.get("allegiance") or "-"
    government = humanize_constant(sysinfo.get("government"), "gov")
    security   = humanize_constant(sysinfo.get("security"), "sec")
    population = sysinfo.get("population")
    controlling = sysinfo.get("controlling_faction") or "-"
    controlling_power = sysinfo.get("controlling_power") or "-"

    powers_list = parse_json_str_list((pp0 or {}).get("power"))
    p_state     = (pp0 or {}).get("powerplay_state") or "-"
    ctrl_prog   = (pp0 or {}).get("control_progress")
    underm      = (pp0 or {}).get("undermining")
    reinf       = (pp0 or {}).get("reinforcement")

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

    css = chip_css()
    def row(title, items):
        row_html = ''.join([i for i in items if i])
        if not row_html:
            return ""
        return f'<div style="margin:.35rem 0 1rem 0;"><div style="font-size:.9rem;opacity:.85;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.06em;">{title}</div><div class="valk-badges">{row_html}</div></div>'
    html = css + row("System Info", sys_items) + row("Faction Info", faction_items) + row("Powerplay", pp_items)
    st.markdown(html, unsafe_allow_html=True)

def _fmt_us(n) -> str:
    if n is None:
        return "∞"
    return f"{n:,}"

# =========================
# Presets & state keys
# =========================
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

RESET_KEYS = [
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
    "run_search",
    "params_snapshot",
    "system_name_snapshot",
]

FILTER_KEYS = [
    # System NICHT im Snapshot, um System-only-Suche nicht zu stören
    # Population
    "population_preset_filter", "population_min_filter",
    "population_max_filter", "population_no_upper_filter",
    # Factions/States
    "faction_filter", "controlling_faction_filter", "state_filter",
    "pending_state_filter", "recovering_state_filter",
    "controlling_faction_in_conflict_filter",
    # Powerplay
    "controlling_power_filter", "power_filter", "powerplay_state_filter",
]

# =========================
# Data Access
# =========================
@st.cache_data(ttl=600, show_spinner=False)
def query_system_names(prefix: str, limit: int = 50) -> list[str]:
    if not prefix or len(prefix) < 3:
        return []
    try:
        data = get_json("lists/systems", params={"q": prefix, "limit": limit})
        if isinstance(data, list):
            return [s for s in data if isinstance(s, str)]
        if isinstance(data, dict) and isinstance(data.get("systems"), list):
            return [s for s in data["systems"] if isinstance(s, str)]
        return []
    except Exception:
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def get_list_from_api(endpoint, label="name"):
    try:
        data = get_json(endpoint)
        if isinstance(data, list):
            if all(isinstance(x, str) for x in data):
                return sorted(data)
            elif all(isinstance(x, dict) and label in x for x in data):
                return sorted([x[label] for x in data])
        return []
    except Exception:
        return []

def build_population_param(pop_min, pop_max) -> str | None:
    if pop_min is None and pop_max is None:
        return None
    if pop_min is None:
        pop_min = 0
    if pop_max is None:
        return f"{int(pop_min)}-"
    return f"{int(pop_min)}-{int(pop_max)}"

# =========================
# CMDR / Activities
# =========================
SUMMARY_ENDPOINTS = [
    ("Market Events",         "summary/market-events"),
    ("Missions Completed",    "summary/missions-completed"),
    ("Missions Failed",       "summary/missions-failed"),
    ("Bounty Vouchers",       "summary/bounty-vouchers"),
    ("Combat Bonds",          "summary/combat-bonds"),
    ("Exploration Sales",     "summary/exploration-sales"),
    ("Bounty Fines",          "summary/bounty-fines"),
    ("Influence by Faction",  "summary/influence-by-faction"),
    ("Influence EIC",         "summary/influence-eic"),
]

def fetch_cmdr_tab_data(system_name: str, period: str) -> dict:
    params = {"system_name": system_name, "period": period}
    out = {}
    for label, path in SUMMARY_ENDPOINTS:
        try:
            out[label] = get_json(path, params=params) or []
        except Exception as e:
            out[label] = {"error": str(e)}
    return out

def render_cmdr_tabs(system_name: str, period: str):
    with st.expander(f"👨‍🚀 CMDR Events — {system_name} [{period.upper()}]", expanded=True):
        data = fetch_cmdr_tab_data(system_name, period)
        labels = [label for label, _ in SUMMARY_ENDPOINTS]
        tabs = st.tabs(labels)
        for label, tab in zip(labels, tabs):
            with tab:
                d = data.get(label, [])
                if isinstance(d, dict) and d.get("error"):
                    st.error(d["error"])
                    continue
                df = pd.DataFrame(d)
                if df.empty:
                    st.info("No data.")
                else:
                    num_cols = list(df.select_dtypes(include=['number']).columns)
                    if num_cols:
                        df = df.sort_values(num_cols[0], ascending=False)
                    st.dataframe(df, use_container_width=True)

def _fmt_en_num(x):
    try:
        v = float(x)
        return f"{v:,.0f}" if abs(v - int(v)) < 1e-9 else f"{v:,.2f}"
    except Exception:
        return x

# ================================
# System Activities Table Renderer
# ================================
def fetch_system_activities(system_name: str, period: str):
    params = {"system": system_name, "period": period}  # ct|lt|tickid
    data = get_json("activities/system-summary", params=params) or []
    # Server kann einzelnes Objekt liefern → Liste herstellen
    if isinstance(data, dict):
        data = [data]
    # nur Sicherheitshalber: auf das angefragte System filtern
    if system_name:
        data = [r for r in data if (r.get("system") or "").lower() == system_name.lower()]
    return data

def render_system_activities_table(rows: list):
    if not rows:
        st.info("No data.")
        return

    rows = sorted(rows, key=lambda r: str(r.get("tickid", "")), reverse=True)
    r = rows[0]

    # System NICHT als Spalte, sondern als Index; KEINE Tick/tickid-Spalte mehr
    table_row = {
        "System": r.get("system", "-"),
        # INF
        "INF Pri": r.get("total_inf_primary", 0),
        "INF Sec": r.get("total_inf_secondary", 0),
        # TRADE (Buy / Sell)
        "Buy Items":  r.get("buy_items_total", 0),
        "Buy Value":  r.get("buy_value_total", 0),
        "Sell Items": r.get("sell_items_total", 0),
        "Sell Value": r.get("sell_value_total", 0),
        "Profit":     r.get("sell_profit_total", 0),
        # BM / BVs / Exploration / CBs / Fails
        "BM":     r.get("total_trade_bm", 0),
        "BVs":    r.get("total_bvs", 0),
        "Expl":   r.get("total_exploration", 0),
        "CBs":    r.get("total_cbs", 0),
        "Fails":  r.get("total_mission_fails", 0),
        # Murders / S&R
        "Murders (Ground)": r.get("total_murders_ground", 0),
        "Murders (Ship)":   r.get("total_murders_ship", 0),
        "S&R":              r.get("total_sandr", 0),
        # CZs Space/Ground
        "SpaceCZ L": r.get("cz_space_L", 0),
        "SpaceCZ M": r.get("cz_space_M", 0),
        "SpaceCZ H": r.get("cz_space_H", 0),
        "GroundCZ L": r.get("cz_ground_L", 0),
        "GroundCZ M": r.get("cz_ground_M", 0),
        "GroundCZ H": r.get("cz_ground_H", 0),
    }

    df = pd.DataFrame([table_row]).set_index("System")

    num_cols = list(df.columns)
    styled = (
        df.style
        .format({c: _fmt_en_num for c in num_cols})
        .set_properties(subset=num_cols, **{"text-align": "right", "min-width": "90px"})
        # ⬇️ NEU: Index-Spalte breiter machen
        .set_table_styles([
            {"selector": "th.row_heading", "props": "min-width:200px;"},
            {"selector": "th.row_heading.level0", "props": "min-width:200px;"},
        ])
    )
    st.table(styled)

# =================================
# Faction Activities Table Renderer
# =================================
def fetch_faction_activities(system_name: str, period: str):
    # period: ct|lt|tickid
    params = {"system": system_name, "period": period, "group": "faction"}
    data = get_json("activities/system-summary", params=params) or []
    if isinstance(data, dict):
        data = [data]
    # Nur Sicherheit: auf System filtern
    if system_name:
        data = [r for r in data if (r.get("system") or "").lower() == system_name.lower()]
    return data

def render_faction_activities_table(rows: list):
    """
    Erwartet Response-Liste aus /api/activities/system-summary?group=faction.
    Zeigt je Minor Faction eine Zeile
    """
    if not rows:
        st.info("No data.")
        return

    # Nur nach Faction sortieren (State entfällt)
    rows = sorted(rows, key=lambda r: str(r.get("faction", "")))

    # In DataFrame überführen – NUR gewünschte Spalten
    table = []
    for r in rows:
        table.append({
            "Faction": r.get("faction", "-"),
            # INF
            "INF Pri": r.get("total_inf_primary", 0),
            "INF Sec": r.get("total_inf_secondary", 0),
            # TRADE (Buy / Sell / Profit)
            "Buy Items":  r.get("buy_items_total", 0),
            "Buy Value":  r.get("buy_value_total", 0),
            "Sell Items": r.get("sell_items_total", 0),
            "Sell Value": r.get("sell_value_total", 0),
            "Profit":     r.get("sell_profit_total", 0),
            # BM / BVs / Exploration / CBs / Fails
            "BM":    r.get("total_trade_bm", 0),
            "BVs":   r.get("total_bvs", 0),
            "Expl":  r.get("total_exploration", 0),
            "CBs":   r.get("total_cbs", 0),
            "Fails": r.get("total_mission_fails", 0),
            # Murders / S&R
            "Murders (Ground)": r.get("total_murders_ground", 0),
            "Murders (Ship)":   r.get("total_murders_ship", 0),
            "S&R":              r.get("total_sandr", 0),
            # CZs
            "SpaceCZ L":  r.get("cz_space_L", 0),
            "SpaceCZ M":  r.get("cz_space_M", 0),
            "SpaceCZ H":  r.get("cz_space_H", 0),
            "GroundCZ L": r.get("cz_ground_L", 0),
            "GroundCZ M": r.get("cz_ground_M", 0),
            "GroundCZ H": r.get("cz_ground_H", 0),
        })

    df = pd.DataFrame(table).set_index("Faction")

    # Formatter (en-US) + rechtsbündige Zahlen
    def _fmt_en_num(x):
        try:
            v = float(x)
            return f"{v:,.0f}" if abs(v - int(v)) < 1e-9 else f"{v:,.2f}"
        except Exception:
            return "" if x is None else x

    num_cols = list(df.columns)
    styled = (
        df.style
        .format({c: _fmt_en_num for c in num_cols})
        .set_properties(subset=num_cols, **{"text-align": "right", "min-width": "80px"})
        # ⬇️ NEU: Index-Spalte breiter machen
        .set_table_styles([
            {"selector": "th.row_heading", "props": "min-width:200px;"},
            {"selector": "th.row_heading.level0", "props": "min-width:200px;"},
        ])
    )
    st.table(styled)

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

# =============================
# Minor Factions Table Renderer
# =============================
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

def render_minor_factions_table(factions: list) -> None:
    """
    Tabellendarstellung der Minor Factions – identisch zur Systemseite.
    Erwartet die rohe Liste aus dem API-Response unter entry['factions'].
    """
    if not factions:
        st.info("No minor factions found.")
        return

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
        for f in factions if isinstance(f, dict)
    ])

    if df.empty:
        st.info("No minor factions found.")
        return

    df = df.sort_values(by="Influence", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "#"

    styled = (
        df.style
          .applymap(style_state, subset=["State"])
          .applymap(style_states_cell, subset=["Active States"])
          .applymap(style_states_cell, subset=["Pending"])
          .applymap(style_states_cell, subset=["Recovering"])
          .format({
              "Influence": fmt_pct,
              "State": fmt_state_text,
              "Active States": fmt_states_text,
              "Pending": fmt_states_text,
              "Recovering": fmt_states_text,
          })
          .set_properties(subset=["Influence"], **{"text-align": "right", "min-width": "90px", "max-width": "90px"})
          .set_properties(subset=["Name"], **{"min-width": "200px", "max-width": "200px"})
          .set_properties(subset=["Allegiance"], **{"min-width": "100px", "max-width": "100px"})
          .set_properties(subset=["Government"], **{"min-width": "120px", "max-width": "120px"})
          .set_properties(subset=["State"], **{"text-align": "center", "min-width": "140px", "max-width": "160px"})
          .set_properties(subset=["Active States", "Pending", "Recovering"], **{"min-width": "180px", "max-width": "220px"})
    )
    st.table(styled)

# =========================
# Page
# =========================
def render():
    st.title("System Information")
    st.text("Shows system summary and minor factions. Filter by API parameters.")

    factions = get_list_from_api("lists/factions")
    controlling_factions = get_list_from_api("lists/controlling-factions")
    controlling_powers = get_list_from_api("lists/controlling-powers")
    powers = controlling_powers

    # Init session
    st.session_state.setdefault("run_search", False)
    st.session_state.setdefault("params_snapshot", {})
    st.session_state.setdefault("system_name_snapshot", "")
    st.session_state.setdefault("_filters_dirty", False)
    st.session_state.setdefault("_lock_run_search", False)

    # (do not auto-unlock here; unlock after results are rendered)
    # st.caption(
    #     f"🧩 DEBUG init: run_search={st.session_state.get('run_search', False)}, "
    #     f"dirty={st.session_state.get('_filters_dirty', False)}, "
    #     f"lock={st.session_state.get('_lock_run_search', False)}"
    # )

    # Sticky rehydration of filters from snapshot
    if st.session_state.get("_rehydrate_pending", False):
        snap = st.session_state.get("_filters_snapshot")
        if isinstance(snap, dict):
            for k, v in snap.items():
                st.session_state[k] = v
        st.session_state["_rehydrate_pending"] = False

    # --- Full reset before any widget is instantiated ---
    if st.session_state.get("_do_full_reset", False):
        WIDGET_KEYS = [
            # searchbox
            "system_name_filter",
            # population widgets
            "population_preset_filter", "population_min_filter", "population_max_filter",
            "population_no_upper_filter", "has_conflict_filter",
            # faction/state widgets
            "faction_filter", "controlling_faction_filter", "state_filter",
            "pending_state_filter", "recovering_state_filter",
            "controlling_faction_in_conflict_filter",
            # power/powerplay widgets
            "controlling_power_filter", "power_filter", "powerplay_state_filter",
        ]
        PROGRAM_KEYS = [
            "run_search", "params_snapshot", "system_name_snapshot",
        ]

        for k in WIDGET_KEYS + PROGRAM_KEYS:
            st.session_state.pop(k, None)

        # remount empty searchbox
        st.session_state["_system_combo_uid"] = uuid.uuid4().hex[:8]

        # done – clear flag
        st.session_state.pop("_do_full_reset", None)
        # kein st.rerun() nötig – wir sind noch vor der Widget-Instanziierung

    # --- System searchbox (strings only), OUTSIDE any form ---
    if "_system_combo_uid" not in st.session_state:
        st.session_state["_system_combo_uid"] = uuid.uuid4().hex[:8]
    searchbox_key = f"system_combo_{st.session_state['_system_combo_uid']}"

    st.write("**System**")
    current_sel = st.session_state.get("system_name_filter", "")

    def _search_fn(q: str):
        return query_system_names(q, limit=50)

    try:
        sel = st_searchbox(
            search_function=_search_fn,
            default=current_sel or None,
            key=searchbox_key,
            placeholder="Search system (≥3 characters)…",
        )
    except Exception:
        # Duplicate key (rare on first run) -> rotate key and clean rerun
        st.session_state["_system_combo_uid"] = uuid.uuid4().hex[:8]
        st.rerun()

    if sel:
        prev = st.session_state.get("system_name_filter", "")
        st.session_state["system_name_filter"] = sel
        #st.caption(f"🎯 DEBUG selection: **{st.session_state.get('system_name_filter', '–')}**")
        # Mark dirty ONLY if changed and not in armed search
        if sel != prev and not st.session_state.get("_lock_run_search", False):
            st.session_state["_filters_dirty"] = True
            if st.session_state.get("run_search", False):
                st.session_state["run_search"] = False
                #st.caption("🟡 DEBUG: selection changed → run_search cleared")
    else:
        # KEIN neuer Pick via Searchbox in diesem Run
        prev_sys = st.session_state.get("system_name_snapshot", "")
        # Nur wenn zuvor mit System gesucht wurde UND das Feld tatsächlich geleert ist:
        if st.session_state.get("run_search") and prev_sys and not st.session_state.get("system_name_filter"):
            st.session_state["run_search"] = False
            st.session_state["system_name_snapshot"] = ""
            st.rerun()
    # WICHTIG: system_name_filter NICHT pauschal leeren – sonst blockiert System-only-Suche

    st.caption(f"Current selection: **{st.session_state.get('system_name_filter','–')}**")

    # --- Filters (live widgets) ---
    c1, c2, _ = st.columns(3)
    with c1:
        pop_opts = list(POP_PRESETS.keys())
        if "population_preset_filter" in st.session_state:
            pop_preset = st.selectbox("Population", pop_opts,
                                      key="population_preset_filter",
                                      on_change=_mark_dirty)
        else:
            pop_preset = st.selectbox("Population", pop_opts,
                                      index=0,
                                      key="population_preset_filter",
                                      on_change=_mark_dirty)
    with c2:
        if "has_conflict_filter" in st.session_state:
            st.checkbox("Has Conflict", key="has_conflict_filter", on_change=_mark_dirty)
        else:
            st.checkbox("Has Conflict", value=False, key="has_conflict_filter", on_change=_mark_dirty)

    pop_min, pop_max = POP_PRESETS[pop_preset]
    if pop_min == "custom" and pop_max == "custom":
        cx1, cx2 = st.columns(2)
        with cx1:
            pop_min = st.number_input("Min (incl.)", min_value=0, step=1, format="%d",
                                      key="population_min_filter", on_change=_mark_dirty)
        with cx2:
            # Obergrenze optional: nur Eingabefeld zeigen, wenn keine "No upper limit"
            if "population_no_upper_filter" in st.session_state:
                no_upper = st.checkbox("No upper limit",
                                       key="population_no_upper_filter",
                                       on_change=_mark_dirty)
            else:
                no_upper = st.checkbox("No upper limit", value=False,
                                       key="population_no_upper_filter",
                                       on_change=_mark_dirty)
            if not no_upper:
                pop_max = st.number_input("Max (incl.)", min_value=0, step=1, format="%d",
                                          key="population_max_filter", on_change=_mark_dirty)
            else:
                # Stellen wir sicher, dass kein alter Max-Wert hängen bleibt
                st.session_state["population_max_filter"] = None

    if pop_min is None and pop_max is None:
        st.caption("Active range: **All**")
    elif pop_max is None:
        st.caption(f"Active range: **{_fmt_us(pop_min)}+**")
    else:
        st.caption(f"Active range: **{_fmt_us(pop_min)} – {_fmt_us(pop_max)}**")

    st.divider()

    f1c1, f1c2, f1c3 = st.columns(3)
    with f1c1:
        cur = st.session_state.get("faction_filter", "")
        opts = [""] + sorted(set(factions + ([cur] if cur else [])))
        if "faction_filter" in st.session_state:
            st.selectbox("Faction", opts, key="faction_filter", on_change=_mark_dirty)
        else:
            st.selectbox("Faction", opts,
                         index=opts.index(cur) if cur in opts else 0,
                         key="faction_filter", on_change=_mark_dirty)
    with f1c2:
        cur = st.session_state.get("controlling_faction_filter", "")
        opts = [""] + sorted(set(controlling_factions + ([cur] if cur else [])))
        if "controlling_faction_filter" in st.session_state:
            st.selectbox("Controlling Faction", opts,
                         key="controlling_faction_filter", on_change=_mark_dirty)
        else:
            st.selectbox("Controlling Faction", opts,
                         index=opts.index(cur) if cur in opts else 0,
                         key="controlling_faction_filter", on_change=_mark_dirty)
    with f1c3:
        st.selectbox("State", [""] + list(STATE_COLORS.keys()),
                     key="state_filter", on_change=_mark_dirty)

    f2c1, f2c2, f2c3 = st.columns(3)
    with f2c1:
        st.selectbox("Pending State", [""] + list(STATE_COLORS.keys()),
                     key="pending_state_filter", on_change=_mark_dirty)
    with f2c2:
        st.selectbox("Recovering State", [""] + list(STATE_COLORS.keys()),
                     key="recovering_state_filter", on_change=_mark_dirty)
    with f2c3:
        if "controlling_faction_in_conflict_filter" in st.session_state:
            st.checkbox("Controlling Faction in conflict",
                        help="Only systems where the chosen Controlling Faction is in conflict.",
                        key="controlling_faction_in_conflict_filter",
                        on_change=_mark_dirty)
        else:
            st.checkbox("Controlling Faction in conflict", value=False,
                        help="Only systems where the chosen Controlling Faction is in conflict.",
                        key="controlling_faction_in_conflict_filter",
                        on_change=_mark_dirty)

    st.divider()

    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        cur = st.session_state.get("controlling_power_filter", "")
        opts = [""] + sorted(set(controlling_powers + ([cur] if cur else [])))
        if "controlling_power_filter" in st.session_state:
            st.selectbox("Controlling Power", opts,
                         key="controlling_power_filter", on_change=_mark_dirty)
        else:
            st.selectbox("Controlling Power", opts,
                         index=opts.index(cur) if cur in opts else 0,
                         key="controlling_power_filter", on_change=_mark_dirty)
    with pc2:
        cur = st.session_state.get("power_filter", "")
        opts = [""] + sorted(set(powers + ([cur] if cur else [])))
        # Warnung vermeiden + dirty markieren
        if "power_filter" in st.session_state:
            st.selectbox("Power", opts, key="power_filter", on_change=_mark_dirty)
        else:
            st.selectbox("Power", opts,
                         index=opts.index(cur) if cur in opts else 0,
                         key="power_filter", on_change=_mark_dirty)
    with pc3:
        st.selectbox("Powerplay State",
                     ["", "Unoccupied", "Fortified", "Exploited", "Stronghold"],
                     key="powerplay_state_filter", on_change=_mark_dirty)

    # --- Buttons OUTSIDE (side-by-side) ---
    bc1, bc2 = st.columns([1, 1])
    search_clicked = bc1.button("Search")
    reset_clicked  = bc2.button("Reset")

    # Alle aktuellen UI-Filter in einer Momentaufnahme sammeln
    current_filters = {k: st.session_state.get(k) for k in FILTER_KEYS}

    # Build params snapshot from live widget values
    params = {}
    if st.session_state.get("faction_filter"): params["faction"] = st.session_state["faction_filter"]
    if st.session_state.get("controlling_faction_filter"): params["controlling_faction"] = st.session_state["controlling_faction_filter"]
    if st.session_state.get("controlling_power_filter"): params["controlling_power"] = st.session_state["controlling_power_filter"]
    if st.session_state.get("power_filter"): params["power"] = st.session_state["power_filter"]
    if st.session_state.get("powerplay_state_filter"): params["powerplay_state"] = st.session_state["powerplay_state_filter"]
    if st.session_state.get("state_filter"): params["state"] = st.session_state["state_filter"]
    if st.session_state.get("pending_state_filter"): params["pending_state"] = st.session_state["pending_state_filter"]
    if st.session_state.get("recovering_state_filter"): params["recovering_state"] = st.session_state["recovering_state_filter"]
    if st.session_state.get("has_conflict_filter"): params["has_conflict"] = "true"
    if st.session_state.get("controlling_faction_in_conflict_filter"): params["cf_in_conflict"] = "true"

    pop_param = build_population_param(
        st.session_state.get("population_min_filter") if pop_min == "custom" and pop_max == "custom" else pop_min,
        st.session_state.get("population_max_filter") if pop_min == "custom" and pop_max == "custom" else pop_max,
    )
    if pop_param: params["population"] = pop_param

    if reset_clicked:
        for k in RESET_KEYS:
            st.session_state.pop(k, None)
        st.session_state.pop("_filters_dirty", None)
        # Rehydrate-Mechanik leeren
        st.session_state.pop("_filters_snapshot", None)
        st.session_state.pop("_rehydrate_pending", None)
        # Rehydrate-Mechanik leeren
        st.session_state.pop("_filters_snapshot", None)
        st.session_state.pop("_rehydrate_pending", None)
        st.session_state.pop("_filters_dirty", None)

        # --- WICHTIG: Searchbox komplett "remounten", damit Auswahl wirklich verschwindet
        try:
            st.session_state.pop(searchbox_key, None)  # internen Wert der Searchbox löschen
        except Exception:
            pass
        st.session_state["_system_combo_uid"] = uuid.uuid4().hex[:8]  # neuen Key erzwingen
        st.session_state["system_name_filter"] = ""  # sicherheitshalber
        st.session_state["system_name_snapshot"] = ""  # und Snapshot leeren

        st.rerun()

    if search_clicked:

        # Alle aktuellen Filter sammeln (nutze deine FILTER_KEYS-Liste)
        current_filters = {k: st.session_state.get(k) for k in FILTER_KEYS}

        # Parameter aus aktuellem State bauen (falls noch nicht gemacht)
        params = _build_params_from_state()  # deine Helper-Funktion; sonst wie bisher params zusammenbauen

        # Für den unmittelbar folgenden Rerun "suche scharf schalten" und Dirty-Events ignorieren
        st.session_state["_lock_run_search"] = True

        st.session_state["_filters_dirty"] = False
        st.session_state["system_name_snapshot"] = (st.session_state.get("system_name_filter") or "").strip()
        st.session_state["params_snapshot"] = params
        st.session_state["run_search"] = True

        # DEBUG: Armed + Snapshot anzeigen
        # st.caption(
        #     "🔒 DEBUG armed: "
        #     f"system='{st.session_state.get('system_name_snapshot', '')}', "
        #     f"params={st.session_state.get('params_snapshot', {})}"
        # )
        st.rerun()

    # Results block
    if not st.session_state.get("run_search", False):
        if st.session_state.get("_filters_dirty"):
            st.info("Filter geändert. Klicke **Search**, um neue Ergebnisse zu laden.")
        else:
            st.info("Set filters and click **Search** to load data.")
        return

    system_name = st.session_state.get("system_name_snapshot", "")
    params = st.session_state.get("params_snapshot", {})
    # Wir sind im "armed" Suchlauf angekommen → Lock jetzt lösen
    st.session_state["_lock_run_search"] = False
    # DEBUG: Unlocked + finaler Call-Kontext
    # st.caption(
    #     f"🔓 DEBUG unlocked: render results with "
    #     f"system='{system_name or '∅'}', params={params or {} }"
    # )

    if system_name:
        st.markdown(f"Results for System: **{system_name}** with Filters: `{params}`")
    else:
        st.markdown(f"Results for **filter-only** search (no system) with Filters: `{params}`")

    # — Optionales Debug (zum schnellen Prüfen des Endpunkts):
    # st.caption(f"DEBUG CALL → endpoint={'system-summary/'+system_name if system_name else 'system-summary'}  params={params}")

    try:
        if system_name:
            # single-system summary
            path = f"system-summary/{quote(system_name, safe='')}"
            data = get_json(path, params=params)
        else:
            # multi-system summary based on filters only
            data = get_json("system-summary", params=params)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    if isinstance(data, dict):
        data = [data]
    if not data:
        st.warning("No systems found.")
        return

    for entry in data:
        sysinfo = entry.get("system_info", {}) or {}
        sys_name = sysinfo.get("system_name", "Unknown")
        st.subheader(sys_name)

        # Header chips
        pp_list = entry.get("powerplays") or []
        pp0 = pp_list[0] if pp_list else {}
        conflicts = entry.get("conflicts", []) or []
        render_grouped_header(sysinfo, pp0, len(conflicts))

        # Action buttons (per system)
        b1, b2, b3, b4, b5, b6 = st.columns(6)
        c_cmdr_ct = b1.button("CMDR Events (CT)", key=f"cmdr_ct_{sys_name}")
        c_cmdr_lt = b2.button("CMDR Events (LT)", key=f"cmdr_lt_{sys_name}")
        c_sys_ct  = b3.button("System Activities (CT)", key=f"sys_ct_{sys_name}")
        c_sys_lt  = b4.button("System Activities (LT)", key=f"sys_lt_{sys_name}")
        c_fac_ct  = b5.button("Faction Activities (CT)", key=f"fac_ct_{sys_name}")
        c_fac_lt  = b6.button("Faction Activities (LT)", key=f"fac_lt_{sys_name}")

        # st.caption(
        #     f"🖲️ DEBUG clicks: "
        #     f"cmdr_ct={c_cmdr_ct}, cmdr_lt={c_cmdr_lt}, "
        #     f"sys_ct={c_sys_ct}, sys_lt={c_sys_lt}, "
        #     f"fac_ct={c_fac_ct}, fac_lt={c_fac_lt}"
        # )

        if c_cmdr_ct:
            #st.caption(f"📊 DEBUG → render_cmdr_tabs(system='{sys_name}', period='ct')")
            render_cmdr_tabs(sys_name, "ct")

        if c_cmdr_lt:
            #st.caption(f"📊 DEBUG → render_cmdr_tabs(system='{sys_name}', period='lt')")
            render_cmdr_tabs(sys_name, "lt")

        if c_sys_ct or c_sys_lt:
            period = "ct" if c_sys_ct else "lt"
            #st.caption(f"🛰️ DEBUG → fetch_system_activities(system='{sys_name}', period='{period}')")
            rows = fetch_system_activities(sys_name, period)
            with st.expander(f"🛰️ System Activities — {sys_name} [{period.upper()}]", expanded=True):
                #st.caption(f"🛰️ DEBUG rows={len(rows)}")
                render_system_activities_table(rows)

        if c_fac_ct or c_fac_lt:
            period = "ct" if c_fac_ct else "lt"
           # st.caption(f"🏳️ DEBUG → fetch_faction_activities(system='{sys_name}', period='{period}')")
            rows = fetch_faction_activities(sys_name, period)
            with st.expander(f"🏳️ Faction Activities — {sys_name} [{period.upper()}]", expanded=True):
                #st.caption(f"🏳️ DEBUG rows={len(rows)}")
                render_faction_activities_table(rows)

        # Minor Factions
        minor_factions = entry.get("factions") or entry.get("minor_factions") or []
        with st.expander("📊 Minor Factions", expanded=False):
            render_minor_factions_table(minor_factions)

        # Conflicts
        with st.expander("⚔️ Conflicts", expanded=False):
            render_conflicts_table(conflicts)

        st.markdown("---")

# Streamlit Page Entry
render()
