# =============================================================================
# Energy Poverty Explorer — Streamlit + Plotly
# =============================================================================
# This app lets you explore energy poverty indicators across Portuguese
# municipalities. You can:
#   - Pick a metric and a year using the controls on the left
#   - See a choropleth map colored by that metric for that year
#   - Click any municipality on the map to see its evolution over time
# =============================================================================

import json

import pandas as pd
import plotly.express as px
import streamlit as st

# =============================================================================
# SECTION 1: CONFIGURATION
# Change the paths below if you move the data files.
# =============================================================================

# Path to the dataset (parquet format)
DATA_PATH = "Data_treatment/energy_vs_income.parquet"

# Path to the GeoJSON file with municipality boundaries
# Portugal_Municipalities.geojson includes mainland + islands (308 features).
# We use properties.Concelho as the key to match municipalities.
GEOJSON_PATH = "geojsons/Portugal_Municipalities.geojson"

# These columns are geographic or structural — they should NOT appear in the
# metric selector because they don't represent measurable indicators.
NON_METRIC_COLUMNS = {"ano", "distrito", "concelho", "concelho_limpo"}

# Human-readable labels for each metric column.
# This makes the selector easier to understand.
METRIC_LABELS = {
    "energia_ativa_kwh":      "Total Energy Consumption (kWh)",
    "cpes":                   "Number of Households (CPEs)",
    "kwh_por_cpe":            "Energy per Household (kWh/CPE)",
    "Preco_Final":            "Electricity Price (EUR/kWh)",
    "annual_expenditure":     "Annual Energy Cost per Household (EUR)",
    "income":                 "Average Household Income (EUR)",
    "energy_expenditure_ratio": "Energy Expenditure Ratio — EER (%)",
    "energy_poverty":         "Energy Poverty Flag (1 = poor, 0 = not poor)",
}

# Streamlit page setup — must be the first Streamlit call in the script
st.set_page_config(
    page_title="Energy Poverty Explorer",
    layout="wide",
)

# =============================================================================
# SECTION 2: LOAD DATA
# We load the dataset once and cache it so the app stays fast.
# @st.cache_data tells Streamlit: "run this only the first time, then reuse"
# =============================================================================

@st.cache_data
def load_data():
    """Load the parquet dataset and the GeoJSON boundary file."""
    df = pd.read_parquet(DATA_PATH)

    # The GeoJSON stores municipality names in ALL CAPS (e.g. "AVEIRO").
    # The dataset uses title-case (e.g. "Aveiro").
    # We uppercase both text columns so they match when drawing the map.
    df["concelho"] = df["concelho"].str.upper()
    df["distrito"] = df["distrito"].str.upper()

    with open(GEOJSON_PATH) as f:
        geojson = json.load(f)

    return df, geojson


df, geojson = load_data()

# =============================================================================
# SECTION 3: PREPARE SELECTABLE METRIC COLUMNS
# We automatically find which columns are metrics by excluding structural ones.
# =============================================================================

# Keep only columns that are not in our exclusion list
metric_columns = [col for col in df.columns if col not in NON_METRIC_COLUMNS]

# Build a reverse lookup: label → column name (used to recover the column name
# after the user picks a human-readable label from the selectbox)
label_to_column = {METRIC_LABELS.get(col, col): col for col in metric_columns}

# List of human-readable labels to show in the selector
metric_labels_list = list(label_to_column.keys())

# Find the index of the default metric so the selectbox starts on it
default_metric_label = METRIC_LABELS.get("energy_expenditure_ratio", "energy_expenditure_ratio")
default_index = metric_labels_list.index(default_metric_label) if default_metric_label in metric_labels_list else 0

# Find the available years in the dataset (sorted from oldest to newest)
available_years = sorted(df["ano"].unique())

# =============================================================================
# SECTION 4: SESSION STATE INITIALIZATION
# Streamlit re-runs the whole script on every interaction. We use
# st.session_state to remember things between re-runs (like which municipality
# was clicked and what year was last selected).
# =============================================================================

if "selected_municipality" not in st.session_state:
    st.session_state.selected_municipality = None  # No municipality selected yet

if "last_year" not in st.session_state:
    st.session_state.last_year = available_years[0]  # Start at the earliest year

# =============================================================================
# SECTION 5: USER CONTROLS (title + metric selector + year slider)
# These appear at the top of the page.
# =============================================================================

st.title("Energy Poverty Explorer — Portugal")
st.caption("Select a metric and a year. Click a municipality on the map to see its trend.")

# Metric selector — the user picks which indicator to display on the map
selected_label = st.selectbox(
    "Select a metric to display on the map:",
    options=metric_labels_list,
    index=default_index,
)

# Convert the human-readable label back to the actual column name
selected_metric = label_to_column[selected_label]

# =============================================================================
# SECTION 6: TWO-COLUMN LAYOUT
# Left column: map + year slider
# Right column: small charts for the selected municipality (or district avg)
# =============================================================================

col_map, col_charts = st.columns([3, 2])

# =============================================================================
# SECTION 7: YEAR SLIDER (inside the left column)
# The slider lets the user pick which year to display on the map.
# =============================================================================

with col_map:

    selected_year = st.slider(
        "Select a year:",
        min_value=available_years[0],
        max_value=available_years[-1],
        value=available_years[0],
        step=1,
    )

    # ----- RESET LOGIC -----
    # When the user moves the year slider, we reset the selected municipality.
    # This way the right panel shows district averages again (not stale data).
    if selected_year != st.session_state.last_year:
        st.session_state.selected_municipality = None
        st.session_state.last_year = selected_year

    # =========================================================================
    # SECTION 8: FILTER DATA FOR THE SELECTED YEAR
    # This is the core filter:
    #   "Give me all rows where the year column equals the selected year"
    # =========================================================================

    df_year = df[df["ano"] == selected_year].copy()

    # =========================================================================
    # SECTION 9: BUILD THE CHOROPLETH MAP
    # We color each municipality according to its value of the selected metric
    # for the selected year. The color scale resets for every year.
    # =========================================================================

    # Calculate the min and max values for this specific year and metric.
    # This ensures the color scale is always relative to the current year,
    # not the entire dataset.
    year_min = df_year[selected_metric].min()
    year_max = df_year[selected_metric].max()

    fig_map = px.choropleth_map(
        df_year,
        geojson=geojson,
        locations="concelho",                   # column in df that identifies each area
        featureidkey="properties.Concelho",     # matching key inside the GeoJSON
        color=selected_metric,                  # which column drives the color
        color_continuous_scale="Reds",          # white (low) → red (high)
        range_color=[year_min, year_max],       # recalculated per year
        map_style="carto-positron",             # clean, minimal background map
        center={"lat": 39.5, "lon": -8.0},     # center of Portugal
        zoom=5,
        opacity=0.75,
        hover_name="concelho",
        hover_data={selected_metric: True, "distrito": True, "concelho": False},
        labels={selected_metric: selected_label},
    )

    fig_map.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=520,
        coloraxis_colorbar=dict(title=selected_label, thickness=12),
    )

    # Render the map and capture click events.
    # on_select="rerun" means: when the user clicks, rerun the app with the
    # click information stored in the event object.
    map_event = st.plotly_chart(
        fig_map,
        use_container_width=True,
        on_select="rerun",
        key="main_map",
    )

    # =========================================================================
    # SECTION 10: DETECT CLICK — which municipality did the user click?
    # =========================================================================

    # Check if the click event has any selected points
    if map_event and map_event.selection and map_event.selection.points:
        clicked_location = map_event.selection.points[0].get("location")
        if clicked_location:
            st.session_state.selected_municipality = clicked_location

# =============================================================================
# SECTION 11: RIGHT PANEL — charts based on selection
# If a municipality was clicked: show line charts per metric for that place.
# If nothing was clicked: show bar charts with district-level averages.
# =============================================================================

with col_charts:

    selected_municipality = st.session_state.selected_municipality

    if selected_municipality:
        # ---- A MUNICIPALITY WAS CLICKED ----
        # Filter the full dataset to get all years for this municipality
        df_muni = df[df["concelho"] == selected_municipality].sort_values("ano")

        st.subheader(f"{selected_municipality}")
        st.caption("Evolution across all available years")

        # Show one small line chart per metric
        for col in metric_columns:
            label = METRIC_LABELS.get(col, col)

            fig_line = px.line(
                df_muni,
                x="ano",
                y=col,
                markers=True,
                labels={"ano": "Year", col: label},
                title=label,
            )
            fig_line.update_layout(
                height=180,
                margin={"r": 5, "t": 30, "l": 5, "b": 30},
                showlegend=False,
                title_font_size=12,
            )
            fig_line.update_xaxes(tickvals=available_years, tickfont_size=10)
            fig_line.update_yaxes(tickfont_size=10)

            st.plotly_chart(fig_line, use_container_width=True)

        # Button to clear the municipality selection
        if st.button("Clear selection (show district averages)"):
            st.session_state.selected_municipality = None
            st.rerun()

    else:
        # ---- NO MUNICIPALITY SELECTED ----
        # Show district-level averages for the selected year as bar charts.
        # This gives a good overview without overwhelming the user.

        st.subheader("District averages")
        st.caption(f"Average value per district — year {selected_year}")

        # Calculate the average of each metric grouped by district
        df_district = (
            df_year
            .groupby("distrito")[metric_columns]
            .mean()
            .reset_index()
            .sort_values(selected_metric, ascending=True)
        )

        # Show one small bar chart per metric
        for col in metric_columns:
            label = METRIC_LABELS.get(col, col)

            fig_bar = px.bar(
                df_district,
                x=col,
                y="distrito",
                orientation="h",
                labels={"distrito": "District", col: label},
                title=label,
                color=col,
                color_continuous_scale="Reds",
            )
            fig_bar.update_layout(
                height=220,
                margin={"r": 5, "t": 30, "l": 5, "b": 10},
                showlegend=False,
                coloraxis_showscale=False,
                title_font_size=12,
            )
            fig_bar.update_xaxes(tickfont_size=9)
            fig_bar.update_yaxes(tickfont_size=9)

            st.plotly_chart(fig_bar, use_container_width=True)
