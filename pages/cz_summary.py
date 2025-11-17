import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from api_client import get_json
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


def format_us(num):
    """Format number in US style with thousands separator, e.g. 3985963 -> '3,985,963'."""
    try:
        return f"{int(num):,}"
    except Exception:
        return str(num)


def aggrid_fixed(df, height=300, key=None, col_widths=None, always_scroll=True):
    """Wrapper for AgGrid with optional column widths and dynamic height."""
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True, filter=True)

    # Right-align CBs (redeemed) column if present
    if df is not None and "CBs (redeemed)" in df.columns:
        gb.configure_column("CBs (redeemed)", cellStyle={"textAlign": "right"})

    # Fixed column widths
    if col_widths:
        for col, width in col_widths.items():
            gb.configure_column(col, width=width)

    grid_options = gb.build()

    # Dynamic height with upper bound, with or without scroll behaviour
    if df is not None and not df.empty:
        rows_height = 40 + 35 * len(df)
        if always_scroll:
            height = min(400, rows_height)
        else:
            height = min(600, rows_height)

    return AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.NO_UPDATE,
        height=height,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True,
        fit_columns_on_grid_load=False,
        key=key,
    )


def get_cb_by_cmdr(period, system_name):
    """Return dict {cmdr: total_combat_bonds} for given system/period from /summary/combat-bonds."""
    if not system_name:
        return {}

    url = f"summary/combat-bonds?period={period}&system_name={quote_plus(system_name)}"
    data = get_json(url) or []

    cb_by_cmdr = {}
    if isinstance(data, list):
        for item in data:
            cmdr_name = item.get("cmdr") or item.get("Cmdr")
            if not cmdr_name:
                continue
            value = item.get("combat_bonds", 0)
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = 0.0
            cb_by_cmdr[cmdr_name] = cb_by_cmdr.get(cmdr_name, 0.0) + value

    return cb_by_cmdr


def build_cmdr_distribution_from_df(filtered_df, cz_types, cb_by_cmdr):
    """Build Cmdr distribution for list endpoints (per CZ row) and merge with combat bonds."""
    if filtered_df is None or filtered_df.empty:
        cz_cmdrs = set()
    else:
        cz_cmdrs = set(filtered_df["cmdr"].unique())

    cb_cmdrs = set(cb_by_cmdr.keys())
    all_cmdrs = sorted(cz_cmdrs | cb_cmdrs)

    rows = []
    for cmdr in all_cmdrs:
        row = {"Cmdr": cmdr}
        for t in cz_types:
            if cmdr in cz_cmdrs:
                mask = (filtered_df["cmdr"] == cmdr) & (filtered_df["cz_type"].str.lower() == t.lower())
                value = filtered_df.loc[mask, "cz_count"].sum()
            else:
                value = 0
            row[t] = int(value)
        row["Total"] = int(sum(row[t] for t in cz_types))
        row["CBs"] = float(cb_by_cmdr.get(cmdr, 0.0))
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["Cmdr"] + cz_types + ["Total", "CBs"])

    dist_df = pd.DataFrame(rows)
    return dist_df[["Cmdr"] + cz_types + ["Total", "CBs"]]


def build_cmdr_distribution_from_summary(dist_list, cz_types, cb_by_cmdr):
    """Build Cmdr distribution for summary endpoints (already aggregated per cmdr)."""
    cz_by_cmdr = {}
    if isinstance(dist_list, list):
        for item in dist_list:
            cmdr_name = item.get("cmdr") or item.get("Cmdr")
            if not cmdr_name:
                continue
            low = int(item.get("low", 0))
            med = int(item.get("medium", 0))
            high = int(item.get("high", 0))
            total = int(item.get("total", low + med + high))
            cz_by_cmdr[cmdr_name] = {"Low": low, "Medium": med, "High": high, "Total": total}

    cz_cmdrs = set(cz_by_cmdr.keys())
    cb_cmdrs = set(cb_by_cmdr.keys())
    all_cmdrs = sorted(cz_cmdrs | cb_cmdrs)

    rows = []
    for cmdr in all_cmdrs:
        cz_row = cz_by_cmdr.get(cmdr, {})
        low = int(cz_row.get("Low", 0))
        med = int(cz_row.get("Medium", 0))
        high = int(cz_row.get("High", 0))
        total = int(cz_row.get("Total", low + med + high))
        cb = float(cb_by_cmdr.get(cmdr, 0.0))
        rows.append({
            "Cmdr": cmdr,
            "Low": low,
            "Medium": med,
            "High": high,
            "Total": total,
            "CBs": cb,
        })

    if not rows:
        return pd.DataFrame(columns=["Cmdr", "Low", "Medium", "High", "Total", "CBs"])

    return pd.DataFrame(rows)[["Cmdr", "Low", "Medium", "High", "Total", "CBs"]]


def finalize_cmdr_distribution(df, cz_types):
    """Prepare Cmdr distribution for display: rename CBs column and format values."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Cmdr"] + cz_types + ["Total", "CBs (redeemed)"])

    df = df.copy()
    if "CBs" in df.columns:
        df = df.rename(columns={"CBs": "CBs (redeemed)"})
        df["CBs (redeemed)"] = df["CBs (redeemed)"].map(format_us)
    else:
        df["CBs (redeemed)"] = "0"

    return df


def main():
    st.title("Conflict Zone Summary")

    period_labels = {
        "cd": "Current Day (today)",
        "ld": "Last Day (yesterday)",
        "cw": "Current Week",
        "lw": "Last Week",
        "cm": "Current Month",
        "lm": "Last Month",
        "2m": "Last 2 Months",
        "y": "Current Year",
        "ct": "Current Tick",
        "lt": "Last Tick",
        "all": "Complete History"
    }

    def on_period_change():
        st.session_state['period_changed'] = True

    # Session state init
    if "selected_label" not in st.session_state:
        st.session_state["selected_label"] = list(period_labels.values())[0]
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = 0
    if "spacecz_system" not in st.session_state:
        st.session_state["spacecz_system"] = None
    if "groundcz_system" not in st.session_state:
        st.session_state["groundcz_system"] = None

    selected_label = st.selectbox(
        "Select Period:",
        list(period_labels.values()),
        index=list(period_labels.values()).index(st.session_state["selected_label"]),
        key="selected_label",
        on_change=on_period_change
    )
    selected_period = [k for k, v in period_labels.items() if v == selected_label][0]

    tab1, tab2 = st.tabs(["🚀 Space CZ", "🔫 Ground CZ"])

    # SPACE CZ TAB
    with tab1:
        st.subheader("🚀 Space CZ Summary")
        st.session_state["active_tab"] = 0

        data = get_json(f"syntheticcz-summary?period={selected_period}")
        if not data or (isinstance(data, list) and not data):
            st.info("No Space CZ data found for selected filters.")
        else:
            cz_types = ["Low", "Medium", "High"]

            if isinstance(data, list):
                df = pd.DataFrame(data)
                if df.empty:
                    st.info("No Space CZ data found for selected filters.")
                else:
                    systems = sorted(df["starsystem"].unique())
                    system_key = f"spacecz_system_{selected_period}"
                    if st.session_state.get(system_key) not in systems:
                        st.session_state[system_key] = systems[0]
                    selected_system = st.selectbox(
                        "Select Starsystem:",
                        systems,
                        key=system_key
                    )
                    filtered_df = df[df["starsystem"] == selected_system]

                    st.markdown(f"**{selected_system} - Space CZ Summary**")

                    # CZ counts by type (only Low/Medium/High)
                    cz_counts = {}
                    for t in cz_types:
                        mask = filtered_df["cz_type"].str.lower() == t.lower()
                        cz_counts[t] = int(filtered_df.loc[mask, "cz_count"].sum())
                    total_cz = sum(cz_counts.values())
                    st.markdown(f"Total: {total_cz} CZs")

                    # Combat bonds summary for this system/period
                    cb_by_cmdr = get_cb_by_cmdr(selected_period, selected_system)
                    total_cb = sum(cb_by_cmdr.values())
                    st.markdown(f"Total CBs (redeemed): {format_us(total_cb)} Cr.")

                    cz_df = pd.DataFrame([{"Type": t, "Count": cz_counts[t]} for t in cz_types])
                    aggrid_fixed(
                        cz_df,
                        height=150,
                        key=f"{selected_system}_{selected_period}_space_cz",
                        col_widths={"Type": 100, "Count": 80}
                    )

                    # Cmdr Distribution + CBs per Cmdr
                    dist_df_raw = build_cmdr_distribution_from_df(filtered_df, cz_types, cb_by_cmdr)
                    dist_df_display = finalize_cmdr_distribution(dist_df_raw, cz_types)

                    st.markdown("Cmdr Distribution:")
                    aggrid_fixed(
                        dist_df_display,
                        key=f"{selected_system}_{selected_period}_space_cmdr",
                        col_widths={
                            "Cmdr": 180,
                            "Low": 80,
                            "Medium": 80,
                            "High": 80,
                            "Total": 80,
                            "CBs (redeemed)": 130,
                        },
                        always_scroll=True,
                    )
            else:
                summary = data.get("summary", {})
                if not summary:
                    st.info("No Space CZ summary available.")
                else:
                    cz_types = ["Low", "Medium", "High"]
                    system_name = summary.get("system") or summary.get("starsystem") or summary.get("name") or "Unknown System"
                    st.markdown(f"**{system_name} - Space CZ Summary**")

                    cz_counts = {t: int(summary.get(t.lower(), 0)) for t in cz_types}
                    total_cz = sum(cz_counts.values())
                    st.markdown(f"Total: {total_cz} CZs")

                    cb_by_cmdr = get_cb_by_cmdr(selected_period, system_name)
                    total_cb = sum(cb_by_cmdr.values())
                    st.markdown(f"Total CBs (redeemed): {format_us(total_cb)} Cr.")

                    cz_df = pd.DataFrame([{"Type": t, "Count": cz_counts[t]} for t in cz_types])
                    aggrid_fixed(
                        cz_df,
                        height=150,
                        key=f"single_space_cz_{selected_period}",
                        col_widths={"Type": 100, "Count": 80}
                    )

                    dist_list = data.get("cmdr_distribution", [])
                    if dist_list:
                        dist_df_raw = build_cmdr_distribution_from_summary(dist_list, cz_types, cb_by_cmdr)
                        dist_df_display = finalize_cmdr_distribution(dist_df_raw, cz_types)

                        st.markdown("Cmdr Distribution:")
                        aggrid_fixed(
                            dist_df_display,
                            key=f"single_space_cmdr_{selected_period}",
                            col_widths={
                                "Cmdr": 180,
                                "Low": 80,
                                "Medium": 80,
                                "High": 80,
                                "Total": 80,
                                "CBs (redeemed)": 130,
                            },
                            always_scroll=True,
                        )
                    else:
                        st.info("No Cmdr distribution data available.")

    # GROUND CZ TAB
    with tab2:
        st.subheader("🔫 Ground CZ Summary")
        st.session_state["active_tab"] = 1

        data = get_json(f"syntheticgroundcz-summary?period={selected_period}")
        if not data or (isinstance(data, list) and not data):
            st.info("No Ground CZ data found for selected filters.")
        else:
            cz_types = ["Low", "Medium", "High"]

            if isinstance(data, list):
                df = pd.DataFrame(data)
                if df.empty:
                    st.info("No Ground CZ data found for selected filters.")
                else:
                    systems = sorted(df["starsystem"].unique())
                    system_key = f"groundcz_system_{selected_period}"
                    if st.session_state.get(system_key) not in systems:
                        st.session_state[system_key] = systems[0]
                    selected_system = st.selectbox(
                        "Select Starsystem:",
                        systems,
                        key=system_key
                    )
                    filtered_df = df[df["starsystem"] == selected_system]

                    st.markdown(f"**{selected_system} - Ground CZ Summary**")

                    # CZ counts by type (only Low/Medium/High)
                    cz_counts = {}
                    for t in cz_types:
                        mask = filtered_df["cz_type"].str.lower() == t.lower()
                        cz_counts[t] = int(filtered_df.loc[mask, "cz_count"].sum())
                    total_cz = sum(cz_counts.values())
                    st.markdown(f"Total: {total_cz} CZs")

                    # Combat bonds summary
                    cb_by_cmdr = get_cb_by_cmdr(selected_period, selected_system)
                    total_cb = sum(cb_by_cmdr.values())
                    st.markdown(f"Total CBs (redeemed): {format_us(total_cb)} Cr.")

                    cz_df = pd.DataFrame([{"Type": t, "Count": cz_counts[t]} for t in cz_types])
                    aggrid_fixed(
                        cz_df,
                        height=150,
                        key=f"{selected_system}_{selected_period}_ground_cz",
                        col_widths={"Type": 100, "Count": 80}
                    )

                    # Settlements
                    if "settlement" in filtered_df.columns:
                        settlements = filtered_df.groupby("settlement")["cz_count"].sum().reset_index()
                        settlements = settlements.rename(columns={"cz_count": "CZs", "settlement": "Settlement"})
                        st.markdown("Settlements:")
                        aggrid_fixed(
                            settlements,
                            key=f"{selected_system}_{selected_period}_ground_settlements",
                            col_widths={"Settlement": 320, "CZs": 100},
                            always_scroll=True,
                        )

                    # Cmdr Distribution + CBs
                    dist_df_raw = build_cmdr_distribution_from_df(filtered_df, cz_types, cb_by_cmdr)
                    dist_df_display = finalize_cmdr_distribution(dist_df_raw, cz_types)

                    st.markdown("Cmdr Distribution:")
                    aggrid_fixed(
                        dist_df_display,
                        key=f"{selected_system}_{selected_period}_ground_cmdr",
                        col_widths={
                            "Cmdr": 200,
                            "Low": 100,
                            "Medium": 100,
                            "High": 100,
                            "Total": 100,
                            "CBs (redeemed)": 150,
                        },
                        always_scroll=True,
                    )
            else:
                summary = data.get("summary", {})
                if not summary:
                    st.info("No Ground CZ summary available.")
                else:
                    system_name = summary.get("system") or summary.get("starsystem") or summary.get("name") or "Unknown System"
                    st.markdown(f"**{system_name} - Ground CZ Summary**")

                    cz_counts = {t: int(summary.get(t.lower(), 0)) for t in cz_types}
                    total_cz = sum(cz_counts.values())
                    st.markdown(f"Total: {total_cz} CZs")

                    cb_by_cmdr = get_cb_by_cmdr(selected_period, system_name)
                    total_cb = sum(cb_by_cmdr.values())
                    st.markdown(f"Total CBs (redeemed): {format_us(total_cb)} Cr.")

                    cz_df = pd.DataFrame([{"Type": t, "Count": cz_counts[t]} for t in cz_types])
                    aggrid_fixed(
                        cz_df,
                        height=150,
                        key=f"single_ground_cz_{selected_period}",
                        col_widths={"Type": 100, "Count": 80}
                    )

                    settlements = data.get("settlements", [])
                    if settlements:
                        set_df = pd.DataFrame(settlements)
                        set_df = set_df.rename(columns={"settlement": "Settlement", "czs": "CZs"})
                        set_df = set_df[["Settlement", "CZs"]]
                        st.markdown("Settlements:")
                        aggrid_fixed(
                            set_df,
                            key=f"single_ground_settlements_{selected_period}",
                            col_widths={"Settlement": 320, "CZs": 100},
                            always_scroll=True,
                        )
                    else:
                        st.info("No settlement data available.")

                    dist_list = data.get("cmdr_distribution", [])
                    if dist_list:
                        dist_df_raw = build_cmdr_distribution_from_summary(dist_list, cz_types, cb_by_cmdr)
                        dist_df_display = finalize_cmdr_distribution(dist_df_raw, cz_types)

                        st.markdown("Cmdr Distribution:")
                        aggrid_fixed(
                            dist_df_display,
                            key=f"single_ground_cmdr_{selected_period}",
                            col_widths={
                                "Cmdr": 200,
                                "Low": 100,
                                "Medium": 100,
                                "High": 100,
                                "Total": 100,
                                "CBs (redeemed)": 150,
                            },
                            always_scroll=True,
                        )
                    else:
                        st.info("No Cmdr distribution data available.")


if __name__ == "__main__":
    main()
