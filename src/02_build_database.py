"""Step 2: clean all raw files, merge them into tidy tables, save them to
SQLite and CSV, and write the data-quality log.

Tables created (in data/processed, as CSV and inside macro_monitor.sqlite):
    macro          country-year-variable values (WEO, WDI, IDS)
    panel_wide     the same data with one column per variable
    growth_all     real GDP growth for all countries, two WEO editions
    trade          goods trade by partner (exports, imports CIF)
    migrant_stock  migrants from TJK/KGZ/UZB/KAZ by destination country
    gni_ppp        GNI per capita, PPP, all countries
    weo_historical past IMF forecasts (spring/fall editions since 1990)

The script stops with an error if a check finds something clearly wrong
(e.g. duplicate country-years, negative trade). Smaller issues are listed
in data_quality_log.md and do not stop the run.
"""

import datetime
import json
import sqlite3

import numpy as np
import pandas as pd

from common import (CORE_COUNTRIES, DATABASE_FILE, FIRST_ANALYSIS_YEAR,
                    LAST_ACTUAL_YEAR, MANUAL_DIR, PANEL_COUNTRIES,
                    PROCESSED_DIR, QUALITY_LOG_FILE, RAW_DIR,
                    WEO_VINTAGE_LABEL, dataframe_to_markdown, read_imf_sdmx)
from country_codes import M49_TO_ISO3, name_matches

# WEO indicators kept: code -> (variable name, unit)
WEO_VARIABLES = {
    "NGDP_RPCH": ("gdp_growth", "% change"),
    "PCPIPCH": ("inflation", "% change, period average"),
    "BCA_NGDPD": ("current_account", "% of GDP"),
    "GGXWDG_NGDP": ("government_debt", "% of GDP"),
    "NGDPD": ("gdp_usd", "US$"),
}

# World Bank WDI indicators kept: code -> (variable name, unit)
WDI_VARIABLES = {
    "BX.TRF.PWKR.CD.DT": ("remittances_usd", "US$"),
    "BX.TRF.PWKR.DT.GD.ZS": ("remittances_gdp", "% of GDP"),
    "PA.NUS.FCRF": ("exchange_rate", "local currency per US$"),
    "DT.DOD.DPPG.CD": ("ppg_external_debt_usd", "US$"),
}

# Trade flows kept: IMF code -> our name
TRADE_FLOWS = {"XG_FOB_USD": "exports", "MG_CIF_USD": "imports_cif"}
WORLD_CODE = "G001"            # IMF code for the world total
PLACEHOLDER_VALUES = [99999.0, 999999.0, 9999999.0]

# UN migrant stock file layout (checked in Stage 0)
UN_FILE = MANUAL_DIR / ("undesa_pd_2024_ims_stock_by_sex_destination_"
                        "and_origin.xlsx")
UN_HEADER_ROW = 10
UN_FIRST_YEAR_COLUMN = 7
UN_N_YEARS = 8
UN_ORIGINS = {762: "TJK", 417: "KGZ", 860: "UZB", 398: "KAZ"}
MAX_UNMAPPED_SHARE = 0.05      # stop if >5% of emigrants cannot be mapped

HISTORICAL_FILE = MANUAL_DIR / "weohistorical.xlsx"
HISTORICAL_SHEETS = ["ngdp_rpch", "pcpi_pch", "bca_gdp_bp6"]

# Plausible ranges (for years >= FIRST_ANALYSIS_YEAR). Values outside are
# flagged in the log, not removed.
PLAUSIBLE_RANGES = {
    "gdp_growth": (-30, 30),
    "inflation": (-10, 100),
    "current_account": (-50, 50),
    "government_debt": (0, 200),
    "remittances_gdp": (0, 80),
}
BIG_JUMP = 0.5                  # flag year-on-year changes above 50%
LEVEL_VARIABLES = ["remittances_usd", "gdp_usd", "ppg_external_debt_usd"]

# The data-quality log is built as a list of Markdown lines.
LOG = []


def log(text=""):
    """Add a line to the data-quality log and print it."""
    LOG.append(text)
    print(text)


# ---------------------------------------------------------------------------
# Readers, one per source
# ---------------------------------------------------------------------------

def read_weo_core():
    """WEO October 2026: selected indicators for the core countries."""
    frames = []
    update_dates = {}
    for country in CORE_COUNTRIES:
        path = RAW_DIR / "imf_weo" / ("weo_live_" + country + ".json")
        table = read_imf_sdmx(path)
        update_dates[country] = sorted(
            table["COUNTRY_UPDATE_DATE"].dropna().unique())
        table = table[table["INDICATOR"].isin(WEO_VARIABLES)].copy()
        found = set(table["INDICATOR"])
        missing = set(WEO_VARIABLES) - found
        assert not missing, (country + ": WEO indicators missing: "
                             + ", ".join(sorted(missing)))
        names = {}
        units = {}
        for code, (name, unit) in WEO_VARIABLES.items():
            names[code] = name
            units[code] = unit
        table["variable"] = table["INDICATOR"].map(names)
        table["unit"] = table["INDICATOR"].map(units)
        table["country"] = table["COUNTRY"]
        frames.append(table[["country", "year", "variable", "value",
                             "unit"]])
    macro = pd.concat(frames, ignore_index=True)
    macro["source"] = "IMF " + WEO_VINTAGE_LABEL
    return macro, update_dates


def check_weo_vintage(update_dates):
    """Stop if the WEO files are not the autumn 2026 edition."""
    log("## WEO edition")
    log("Expected: " + WEO_VINTAGE_LABEL + ". COUNTRY_UPDATE_DATE by country:")
    for country, dates in update_dates.items():
        log("- " + country + ": " + ", ".join(dates))
        for text in dates:
            date = datetime.datetime.strptime(text, "%m/%d/%Y")
            assert date.year == 2026 and date.month >= 7, (
                country + ": WEO update date " + text + " is not from the "
                "autumn 2026 round. The live WEO may have changed edition; "
                "check before continuing.")
    log()


def read_weo_growth_all():
    """Real GDP growth for all countries, October 2026 and April 2026."""
    files = {"2026-10": "weo_live_all_countries_ngdp_rpch.json",
             "2026-04": "weo_2026apr_all_countries_ngdp_rpch.json"}
    frames = []
    for vintage, file_name in files.items():
        table = read_imf_sdmx(RAW_DIR / "imf_weo" / file_name)
        # Keep countries only: 3-letter codes (aggregates look like G001).
        is_country = table["COUNTRY"].str.fullmatch("[A-Z]{3}")
        table = table[is_country]
        frames.append(pd.DataFrame({"country": table["COUNTRY"],
                                    "year": table["year"],
                                    "vintage": vintage,
                                    "growth": table["value"]}))
    growth = pd.concat(frames, ignore_index=True)
    growth = growth.dropna(subset=["growth"])
    return growth


def read_trade():
    """IMF IMTS goods trade by partner for the panel countries."""
    frames = []
    for reporter in PANEL_COUNTRIES:
        path = RAW_DIR / "imf_imts" / ("imts_" + reporter + ".json")
        table = read_imf_sdmx(path)
        table = table[table["INDICATOR"].isin(TRADE_FLOWS)].copy()
        table["flow"] = table["INDICATOR"].map(TRADE_FLOWS)
        table["reporter"] = reporter
        table["partner"] = table["COUNTERPART_COUNTRY"]
        table.loc[table["partner"] == WORLD_CODE, "partner"] = "WLD"
        if "STATUS" not in table.columns:
            table["STATUS"] = None
        frames.append(table[["reporter", "partner", "year", "flow", "value",
                             "STATUS"]])
    trade = pd.concat(frames, ignore_index=True)
    trade = trade.rename(columns={"value": "value_usd", "STATUS": "status"})

    # Keep real countries (3 letters) and the world total; drop regions.
    keep = trade["partner"].str.fullmatch("[A-Z]{3}")
    n_dropped = int((~keep).sum())
    trade = trade[keep].copy()

    log("## Trade by partner (IMF IMTS)")
    log("- Observations dropped because the partner is a region or group: "
        + str(n_dropped))

    # Placeholder values such as 99,999 are set to missing (Stage 0).
    is_placeholder = trade["value_usd"].abs().isin(PLACEHOLDER_VALUES)
    log("- Placeholder values (99,999 / 999,999 / 9,999,999) set to "
        "missing: " + str(int(is_placeholder.sum())))
    if is_placeholder.any():
        examples = trade[is_placeholder].head(10)
        log("  Examples: " + "; ".join(
            examples["reporter"] + "-" + examples["partner"] + " "
            + examples["year"].astype(str) + " " + examples["flow"]))
    trade.loc[is_placeholder, "value_usd"] = np.nan

    n_estimated = int((trade["status"] == "e").sum())
    log("- Observations flagged as estimated by the IMF (status 'e'): "
        + str(n_estimated))
    assert (trade["value_usd"].dropna() >= 0).all(), "Negative trade values"
    return trade


def read_wdi_core():
    """World Bank WDI indicators for the core countries."""
    frames = []
    for code, (variable, unit) in WDI_VARIABLES.items():
        path = RAW_DIR / "wb_wdi" / (code + ".json")
        frames.append(read_wdi_file(path, variable, unit))
    return pd.concat(frames, ignore_index=True)


def read_wdi_file(path, variable, unit):
    """Read one World Bank WDI JSON file into a long table."""
    with open(path, encoding="utf-8") as file:
        content = json.load(file)
    rows = []
    for item in content[1]:
        rows.append({"country": item["countryiso3code"],
                     "year": int(item["date"]),
                     "variable": variable,
                     "value": item["value"],
                     "unit": unit})
    table = pd.DataFrame(rows)
    table["value"] = pd.to_numeric(table["value"], errors="coerce")
    table["source"] = "World Bank WDI"
    return table


def read_gni_ppp():
    """GNI per capita, PPP, for all countries (aggregates included)."""
    path = RAW_DIR / "wb_wdi" / "NY.GNP.PCAP.PP.CD_all_countries.json"
    table = read_wdi_file(path, "gni_ppp", "current international $")
    table = table.dropna(subset=["value"])
    table = table[table["country"].str.fullmatch("[A-Z]{3}")]
    return table[["country", "year", "value"]]


def read_ids_debt():
    """Tajikistan's public debt owed to China and Russia (World Bank IDS)."""
    creditors = {"china": "debt_to_china_usd", "russia": "debt_to_russia_usd"}
    rows = []
    for name, variable in creditors.items():
        path = RAW_DIR / "wb_ids" / ("tjk_bilateral_ppg_debt_" + name
                                     + ".json")
        with open(path, encoding="utf-8") as file:
            content = json.load(file)
        for item in content["source"]["data"]:
            year = None
            for concept in item["variable"]:
                if concept["concept"] == "Time":
                    year = int(str(concept["id"]).replace("YR", ""))
            rows.append({"country": "TJK", "year": year,
                         "variable": variable, "value": item["value"],
                         "unit": "US$"})
    table = pd.DataFrame(rows)
    table["value"] = pd.to_numeric(table["value"], errors="coerce")
    table["source"] = "World Bank IDS"
    return table


def read_migrant_stocks():
    """UN DESA migrant stocks: emigrants of our 4 countries by destination."""
    table = pd.read_excel(UN_FILE, sheet_name="Table 1",
                          header=UN_HEADER_ROW)
    year_columns = list(table.columns[UN_FIRST_YEAR_COLUMN:
                                      UN_FIRST_YEAR_COLUMN + UN_N_YEARS])
    years = [int(str(column).split(".")[0]) for column in year_columns]
    assert years == [1990, 1995, 2000, 2005, 2010, 2015, 2020, 2024], (
        "Unexpected year columns in the UN file: " + str(year_columns))

    table = table.rename(columns={
        table.columns[1]: "destination_name",
        table.columns[3]: "data_type",
        table.columns[4]: "destination_m49",
        table.columns[5]: "origin_name",
        table.columns[6]: "origin_m49",
    })
    # Destination is a country when 'Data type' is filled in.
    table = table[table["data_type"].notna()]
    table = table[table["origin_m49"].isin(UN_ORIGINS)].copy()

    # Check the origin names (e.g. code 762 must say Tajikistan).
    for code in UN_ORIGINS:
        names = table.loc[table["origin_m49"] == code, "origin_name"]
        for name in names.unique():
            assert name_matches(code, name), (
                "Origin code " + str(code) + " has name " + str(name))

    long = table.melt(id_vars=["origin_m49", "destination_m49",
                               "destination_name"],
                      value_vars=year_columns, var_name="year_column",
                      value_name="stock")
    column_to_year = dict(zip(year_columns, years))
    long["year"] = long["year_column"].map(column_to_year)
    long["stock"] = pd.to_numeric(long["stock"], errors="coerce")
    long["origin"] = long["origin_m49"].map(UN_ORIGINS)
    long["destination_m49"] = long["destination_m49"].astype(int)

    # Map destination codes to ISO3, checking each name.
    iso3_codes = []
    for _, row in long.iterrows():
        code = row["destination_m49"]
        if code in M49_TO_ISO3:
            assert name_matches(code, row["destination_name"]), (
                "Code " + str(code) + " is '" + str(row["destination_name"])
                + "', not what country_codes.py expects. Fix the table.")
            iso3_codes.append(M49_TO_ISO3[code][0])
        else:
            iso3_codes.append(None)
    long["destination"] = iso3_codes
    assert (long["stock"].dropna() >= 0).all(), "Negative migrant stocks"
    return long[["origin", "destination", "destination_m49",
                 "destination_name", "year", "stock"]]


def check_unmapped_destinations(migrants):
    """Report (and limit) migrants living in countries we cannot map."""
    log("## Migrant stocks (UN DESA 2024)")
    unmapped = migrants[migrants["destination"].isna()]
    for origin in PANEL_COUNTRIES:
        rows = migrants[migrants["origin"] == origin]
        for year in sorted(rows["year"].unique()):
            in_year = rows[rows["year"] == year]
            total = in_year["stock"].sum()
            lost = in_year.loc[in_year["destination"].isna(), "stock"].sum()
            share = lost / total if total > 0 else 0.0
            if share > 0.01:
                log("- " + origin + " " + str(year) + ": "
                    + str(round(100 * share, 1)) + "% of emigrants live in "
                    "countries not in country_codes.py")
            assert share <= MAX_UNMAPPED_SHARE, (
                origin + " " + str(year) + ": more than 5% of emigrants in "
                "unmapped countries. Add them to country_codes.py.")
    top_unmapped = (unmapped.groupby("destination_name")["stock"].sum()
                    .sort_values(ascending=False).head(10))
    if len(top_unmapped) > 0:
        log("- Largest unmapped destinations (all origins, all years): "
            + "; ".join(top_unmapped.index.astype(str)))
    log("- Unmapped destinations are dropped from the remittance weights "
        "and the remaining weights are rescaled.")
    log()


def read_weo_historical():
    """IMF historical WEO forecasts file, reshaped to a long table."""
    frames = []
    for sheet in HISTORICAL_SHEETS:
        table = pd.read_excel(HISTORICAL_FILE, sheet_name=sheet)
        vintage_columns = [column for column in table.columns
                           if str(column).endswith(sheet)
                           and str(column)[0] in "SF"]
        long = table.melt(id_vars=["ISOAlpha_3Code", "year"],
                          value_vars=vintage_columns,
                          var_name="column", value_name="raw_value")
        long = long.rename(columns={"ISOAlpha_3Code": "country",
                                    "year": "target_year"})
        long = long.dropna(subset=["country"])     # aggregates have no ISO3
        long["season"] = long["column"].str[0]      # S = spring, F = fall
        long["vintage_year"] = long["column"].str[1:5].astype(int)
        long["variable"] = sheet
        # Missing values are stored as "." in this file.
        long["value"] = pd.to_numeric(long["raw_value"], errors="coerce")
        n_text = int((long["value"].isna() & long["raw_value"].notna()
                      & (long["raw_value"].astype(str) != ".")).sum())
        assert n_text == 0, sheet + ": unexpected text values in the file"
        frames.append(long[["country", "target_year", "variable", "season",
                            "vintage_year", "value"]].dropna(
                                subset=["value"]))
    historical = pd.concat(frames, ignore_index=True)

    log("## Historical WEO forecasts file")
    last_vintage = historical["vintage_year"].max()
    log("- Last edition in the file: " + str(last_vintage) + " (S = April, "
        "F = September/October).")
    tjk_fall = historical[(historical["country"] == "TJK")
                          & (historical["variable"] == "ngdp_rpch")
                          & (historical["season"] == "F")]
    log("- Fall editions with a Tajikistan growth forecast: "
        + str(tjk_fall["vintage_year"].min()) + " to "
        + str(tjk_fall["vintage_year"].max()))
    log()
    return historical


# ---------------------------------------------------------------------------
# Checks on the combined macro table
# ---------------------------------------------------------------------------

def check_macro(macro):
    """Duplicates, coverage, ranges and big jumps. Writes to the log."""
    duplicates = macro.duplicated(subset=["country", "year", "variable"])
    assert not duplicates.any(), (
        "Duplicate country-year-variable rows: "
        + str(macro[duplicates].head()))

    log("## Coverage by variable and country (non-missing values)")
    coverage_rows = []
    for (variable, country), group in macro.groupby(["variable", "country"]):
        group = group.dropna(subset=["value"]).sort_values("year")
        if len(group) == 0:
            coverage_rows.append([variable, country, "", "", 0, "", "", ""])
            continue
        first, last = group["year"].min(), group["year"].max()
        expected = set(range(first, last + 1))
        gaps = sorted(expected - set(group["year"]))
        coverage_rows.append([variable, country, first, last, len(group),
                              ", ".join(str(year) for year in gaps),
                              round(group["value"].min(), 2),
                              round(group["value"].max(), 2)])
    coverage = pd.DataFrame(coverage_rows, columns=[
        "variable", "country", "first", "last", "n", "gaps", "min", "max"])
    log(dataframe_to_markdown(coverage))

    log("## Values outside plausible ranges (from " + str(FIRST_ANALYSIS_YEAR)
        + "; flagged, not removed)")
    n_flags = 0
    for variable, (low, high) in PLAUSIBLE_RANGES.items():
        rows = macro[(macro["variable"] == variable)
                     & (macro["year"] >= FIRST_ANALYSIS_YEAR)]
        outside = rows[(rows["value"] < low) | (rows["value"] > high)]
        for _, row in outside.iterrows():
            log("- " + row["country"] + " " + str(row["year"]) + " "
                + variable + " = " + str(round(row["value"], 2)))
            n_flags += 1
    if n_flags == 0:
        log("- None.")
    log()

    log("## Year-on-year changes above 50% in US$ level series (flagged)")
    n_jumps = 0
    for variable in LEVEL_VARIABLES:
        for country in macro["country"].unique():
            series = (macro[(macro["variable"] == variable)
                            & (macro["country"] == country)]
                      .dropna(subset=["value"]).sort_values("year"))
            series = series[series["year"] >= FIRST_ANALYSIS_YEAR]
            change = series["value"].pct_change(fill_method=None)
            big = series[change.abs() > BIG_JUMP]
            for _, row in big.iterrows():
                previous = series.loc[series["year"] == row["year"] - 1,
                                      "value"]
                if len(previous) == 0:
                    continue
                pct = 100 * (row["value"] / previous.iloc[0] - 1)
                log("- " + country + " " + variable + " "
                    + str(row["year"]) + ": " + str(round(pct)) + "%")
                n_jumps += 1
    if n_jumps == 0:
        log("- None.")
    log()

    # Hard checks: values that cannot be negative.
    for variable in ["remittances_usd", "exchange_rate", "gdp_usd",
                     "ppg_external_debt_usd"]:
        values = macro.loc[macro["variable"] == variable, "value"].dropna()
        assert (values >= 0).all(), variable + " has negative values"


def check_trade_totals(trade):
    """Compare the sum over partner countries with the world total."""
    log("## Trade: sum over partner countries vs world total")
    wide = trade.pivot_table(index=["reporter", "year", "flow"],
                             columns="partner", values="value_usd",
                             aggfunc="sum")
    partners = [column for column in wide.columns if column != "WLD"]
    partner_sum = wide[partners].sum(axis=1)
    ratio = partner_sum / wide["WLD"]
    years = ratio.index.get_level_values("year")
    ratio = ratio[years >= FIRST_ANALYSIS_YEAR]
    flagged = ratio[(ratio < 0.95) | (ratio > 1.05)]
    if len(flagged) == 0:
        log("- From " + str(FIRST_ANALYSIS_YEAR) + ", partner sums are "
            "within 5% of the world total in every year.")
    for (reporter, year, flow), value in flagged.items():
        log("- " + reporter + " " + str(year) + " " + flow
            + ": partners sum to " + str(round(100 * value, 1))
            + "% of the world total")
    log("- Weights use the world total as denominator, so trade with "
        "unidentified partners lowers the coverage of the partner index "
        "instead of being spread over known partners.")
    log()


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def make_wide_panel(macro):
    """One row per country-year, one column per variable."""
    wide = macro.pivot_table(index=["country", "year"], columns="variable",
                             values="value", aggfunc="first")
    wide = wide.reset_index()
    wide["is_projection"] = wide["year"] > LAST_ACTUAL_YEAR
    return wide


def save_all(tables):
    """Save every table as CSV and into one SQLite database."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_FILE.exists():
        DATABASE_FILE.unlink()
    connection = sqlite3.connect(DATABASE_FILE)
    for name, table in tables.items():
        table.to_csv(PROCESSED_DIR / (name + ".csv"), index=False)
        table.to_sql(name, connection, index=False)
        print("Saved table:", name, "(" + str(len(table)) + " rows)")
    connection.close()


def main():
    LOG.clear()
    log("# Data-quality log")
    log("Created: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    log()

    weo, update_dates = read_weo_core()
    check_weo_vintage(update_dates)
    growth_all = read_weo_growth_all()
    trade = read_trade()
    check_trade_totals(trade)
    wdi = read_wdi_core()
    ids = read_ids_debt()
    gni = read_gni_ppp()
    migrants = read_migrant_stocks()
    check_unmapped_destinations(migrants)
    historical = read_weo_historical()

    macro = pd.concat([weo, wdi, ids], ignore_index=True)
    macro = macro.dropna(subset=["value"])
    check_macro(macro)

    tables = {
        "macro": macro,
        "panel_wide": make_wide_panel(macro),
        "growth_all": growth_all,
        "trade": trade,
        "migrant_stock": migrants,
        "gni_ppp": gni,
        "weo_historical": historical,
    }
    save_all(tables)

    with open(QUALITY_LOG_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(LOG) + "\n")
    print("Data-quality log:", QUALITY_LOG_FILE)


if __name__ == "__main__":
    main()
