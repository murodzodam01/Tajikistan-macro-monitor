"""Shared settings and helper functions used by all project scripts.

Every numbered script imports from this file, so paths, country lists,
the IMF data reader and the chart style are defined in one place only.
"""

import json
import sqlite3
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")  # draw charts to files, without opening windows
import matplotlib.pyplot as plt  # noqa: E402  (must come after use())
from matplotlib.ticker import MaxNLocator  # noqa: E402

# ---------------------------------------------------------------------------
# Folders (relative to the project folder, so the project runs anywhere)
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
MANUAL_DIR = RAW_DIR / "manual"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
OUTPUT_DIR = PROJECT_DIR / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"
TABLE_DIR = OUTPUT_DIR / "tables"
DATABASE_FILE = PROCESSED_DIR / "macro_monitor.sqlite"
QUALITY_LOG_FILE = PROCESSED_DIR / "data_quality_log.md"

# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------

# Countries with the full set of series.
CORE_COUNTRIES = ["TJK", "KGZ", "UZB", "KAZ", "RUS", "CHN"]

# Countries in the panel regression (each has its own partner weights).
PANEL_COUNTRIES = ["TJK", "KGZ", "UZB", "KAZ"]

COUNTRY_NAMES = {
    "TJK": "Tajikistan",
    "KGZ": "Kyrgyz Republic",
    "UZB": "Uzbekistan",
    "KAZ": "Kazakhstan",
    "RUS": "Russia",
    "CHN": "China",
    "TUR": "Türkiye",
    "IRN": "Iran",
    "AFG": "Afghanistan",
}

# ---------------------------------------------------------------------------
# Fixed choices (stated before running any analysis)
# ---------------------------------------------------------------------------

# Live WEO edition, confirmed on the IMF Data Portal in Stage 0.
WEO_VINTAGE_LABEL = "WEO October 2026"

# Tajikistan's civil war ended in 1997, so the analysis sample starts
# in 1998. Data before 1998 are kept in the database but not analysed.
FIRST_ANALYSIS_YEAR = 1998

# Last year with outcome data in the October 2026 WEO. Note: it is still
# an IMF estimate, not final data. Later years are IMF projections.
LAST_ACTUAL_YEAR = 2025

# Newey-West (HAC) standard errors: number of lags.
HAC_LAGS = 1

# ---------------------------------------------------------------------------
# Reading IMF SDMX-JSON files
# ---------------------------------------------------------------------------


def label_of(value):
    """Return the code of an SDMX dimension value ('id' or 'value')."""
    if "id" in value:
        return str(value["id"])
    return str(value["value"])


def decode_attributes(definitions, positions):
    """Turn a list of attribute positions into {attribute name: value}.

    In SDMX-JSON an attribute is usually stored as a position in a list of
    allowed values. Some attributes (dates, for example) are stored as
    plain text instead.
    """
    decoded = {}
    for definition, position in zip(definitions, positions):
        name = definition["id"]
        allowed_values = definition.get("values")
        if position is None:
            decoded[name] = None
        elif allowed_values and isinstance(position, int):
            decoded[name] = label_of(allowed_values[position])
        else:
            decoded[name] = position
    return decoded


def read_imf_sdmx(path):
    """Read an IMF SDMX-JSON data file into a long table.

    Returns one row per observation with one column per dimension
    (e.g. COUNTRY, INDICATOR), plus 'year', 'value' and the series and
    observation attributes.

    Note: the IMF does not list time periods in order, so each
    observation's position is mapped to its year explicitly.
    """
    with open(path, encoding="utf-8") as file:
        content = json.load(file)
    data = content["data"]
    structure = data["structures"][0]
    series_dimensions = structure["dimensions"]["series"]
    time_values = structure["dimensions"]["observation"][0]["values"]
    series_attributes = structure["attributes"].get("series", [])
    observation_attributes = structure["attributes"].get("observation", [])
    all_series = data["dataSets"][0]["series"]

    rows = []
    for series_key, one_series in all_series.items():
        # Turn the key, e.g. "0:56:0", into dimension codes.
        codes = {}
        positions = series_key.split(":")
        for dimension, position in zip(series_dimensions, positions):
            codes[dimension["id"]] = label_of(
                dimension["values"][int(position)])

        series_info = decode_attributes(series_attributes,
                                        one_series.get("attributes", []))

        for time_position, observation in one_series["observations"].items():
            row = dict(codes)
            row.update(series_info)
            row["year"] = int(label_of(time_values[int(time_position)]))
            row["value"] = observation[0]
            row.update(decode_attributes(observation_attributes,
                                         observation[1:]))
            rows.append(row)

    table = pd.DataFrame(rows)
    table["value"] = pd.to_numeric(table["value"], errors="coerce")
    return table


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def save_processed(table, name):
    """Save a processed table as CSV and into the SQLite database."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(PROCESSED_DIR / (name + ".csv"), index=False)
    connection = sqlite3.connect(DATABASE_FILE)
    table.to_sql(name, connection, index=False, if_exists="replace")
    connection.close()
    print("Saved table:", name, "(" + str(len(table)) + " rows)")


def read_table(name):
    """Read one table from the processed CSV files."""
    path = PROCESSED_DIR / (name + ".csv")
    assert path.exists(), "Missing processed file: " + str(path)
    return pd.read_csv(path)


def save_table(table, name, folder=TABLE_DIR, decimals=3):
    """Save an output table as CSV and as Markdown (for the README/note)."""
    folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(folder / (name + ".csv"), index=False)
    rounded = table.round(decimals)
    with open(folder / (name + ".md"), "w", encoding="utf-8") as file:
        file.write(dataframe_to_markdown(rounded))


def dataframe_to_markdown(table):
    """Write a small table as Markdown text (no extra library needed)."""
    columns = [str(column) for column in table.columns]
    lines = ["| " + " | ".join(columns) + " |",
             "|" + "|".join(["---"] * len(columns)) + "|"]
    for _, row in table.iterrows():
        cells = []
        for value in row:
            if pd.isna(value):
                cells.append("")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Partner growth index
# ---------------------------------------------------------------------------


def compute_partner_index(weights, growth, reporter, years):
    """Weighted average of partners' growth, for one reporting country.

    weights: table with columns partner, year, weight (for this reporter)
    growth:  table with columns partner, year, growth
    years:   target years to compute

    For target year t the weights of year t-1 are used (or the last year
    with weights, for forecast years). Partners without a growth value are
    left out and the remaining weights rescaled; 'coverage' reports the
    share of the total weight that had growth data.
    """
    last_weight_year = weights["year"].max()
    first_weight_year = weights["year"].min()
    rows = []
    for year in years:
        weight_year = min(year - 1, last_weight_year)
        if weight_year < first_weight_year:
            continue
        year_weights = weights[weights["year"] == weight_year]
        year_growth = growth[growth["year"] == year]
        merged = year_weights[["partner", "weight"]].merge(
            year_growth[["partner", "growth"]], on="partner", how="left")
        total_weight = merged["weight"].sum()
        has_growth = merged["growth"].notna()
        used_weight = merged.loc[has_growth, "weight"].sum()
        if total_weight <= 0 or used_weight <= 0:
            continue
        weighted_sum = (merged.loc[has_growth, "weight"]
                        * merged.loc[has_growth, "growth"]).sum()
        rows.append({"reporter": reporter, "year": year,
                     "index": weighted_sum / used_weight,
                     "coverage": used_weight / total_weight,
                     "weight_year": weight_year})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Chart style
# ---------------------------------------------------------------------------

# One colour per country, the same in every chart. These are the eight
# hues of a colour-blind-checked palette; the stacked trade chart order
# (RUS, CHN, KAZ, UZB, TUR, IRN) was validated for colour-blind separation.
COLORS = {
    "TJK": "#2a78d6",   # blue: the focus country
    "RUS": "#eb6834",   # orange
    "CHN": "#1baf7a",   # aqua
    "KAZ": "#eda100",   # yellow
    "KGZ": "#e87ba4",   # magenta
    "UZB": "#008300",   # green
    "TUR": "#6250d6",   # violet
    "IRN": "#e34948",   # red
    "Other": "#bfbfbf",  # neutral grey
    "IMF": "#52514e",   # dark grey for IMF forecasts
}
TEXT_COLOR = "#0b0b0b"
MUTED_TEXT = "#52514e"

# Years with large shocks, marked on time-series charts.
SHOCK_YEARS = {2009: "Global crisis", 2015: "Ruble shock",
               2020: "COVID-19", 2022: "Sanctions on Russia"}


def set_chart_style():
    """Apply one simple, consistent style to all charts."""
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelcolor": MUTED_TEXT,
        "axes.edgecolor": "#b5b4ae",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#e4e3df",
        "grid.linewidth": 0.6,
        "xtick.color": MUTED_TEXT,
        "ytick.color": MUTED_TEXT,
        "lines.linewidth": 2.0,
        "legend.frameon": False,
    })


def save_figure(figure, name, source_note):
    """Add a source note under the chart and save it as PNG."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    figure.text(0.01, 0.005, source_note, fontsize=7, color="#555555",
                ha="left", va="bottom")
    figure.savefig(FIGURE_DIR / (name + ".png"), bbox_inches="tight")
    plt.close(figure)
    print("Saved figure:", name + ".png")


def year_axis(axis):
    """Show whole years only on the x-axis (no '2012.5' ticks)."""
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))


def mark_shock_years(axis, first_year, last_year):
    """Shade shock years on a time-series chart."""
    for year in SHOCK_YEARS:
        if first_year <= year <= last_year:
            axis.axvspan(year - 0.5, year + 0.5, color="#999999",
                         alpha=0.15, linewidth=0)
