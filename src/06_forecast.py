"""Step 6: forecast back-test, 2026-2030 baseline, scenarios, fan chart.

Back-test (target years 2005-2023 for one year ahead). From each forecast
origin v (autumn of year v) we forecast Tajik growth for v+1 ... v+5 with:
    naive      growth stays at its year-v value
    AR(1)      y_t = a + b * y_(t-1), estimated on 1998..v, iterated forward
    partner    Spec 2 (y_t = a + b1 * trade index + b2 * remittance index),
               estimated on 1998..v, fed with the IMF's OWN forecasts of
               partner growth from the autumn-v WEO (historical file), with
               partner weights of year v-1 (the last full year known then)
    IMF        the IMF autumn-v WEO forecast for Tajikistan
and compare with outcomes from the October 2026 WEO.

Honest limitations (also in the README):
  - Our models use year-v outcomes as revised by 2026; the IMF in autumn
    v only had preliminary data. This favours our models.
  - "Actual" values are themselves revised over time; 2025 is an estimate.
  - The historical forecasts file ends with autumn 2022, so one-year-ahead
    comparisons stop at target year 2023.

Baseline and scenarios: Spec 2 estimated on 1998-2025, partner growth
from the October 2026 WEO. Scenarios (fixed in advance):
    A  Russian growth 2 pp below the IMF baseline in 2026 and 2027
    B  Chinese growth 2 pp below the IMF baseline in 2026 and 2027
    C  Russia repeats its 2015 growth rate in 2026
The fan chart width comes from back-test errors (RMSE by horizon),
assuming roughly normal errors.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import (COLORS, FIRST_ANALYSIS_YEAR, LAST_ACTUAL_YEAR,
                    MUTED_TEXT, compute_partner_index, read_table,
                    save_figure, save_table, set_chart_style,
                    year_axis)

FIRST_ORIGIN = 2004          # first forecast origin (targets from 2005)
MAX_HORIZON = 5
FORECAST_YEARS = list(range(LAST_ACTUAL_YEAR + 1, LAST_ACTUAL_YEAR + 6))
SCENARIO_SHOCK = -2.0        # percentage points
Z_50 = 0.674                 # normal quantiles for 50% and 90% bands
Z_90 = 1.645
METHODS = ["naive", "AR(1)", "partner model", "IMF"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def fit_ar1(history, last_year):
    """AR(1) on years FIRST_ANALYSIS_YEAR..last_year. Returns (a, b)."""
    sample = history[(history.index >= FIRST_ANALYSIS_YEAR)
                     & (history.index <= last_year)]
    y = sample.values[1:]
    x = sm.add_constant(sample.values[:-1])
    params = sm.OLS(y, x).fit().params
    return params[0], params[1]


def fit_partner_model(data, last_year):
    """Spec 2 by OLS on FIRST_ANALYSIS_YEAR..last_year."""
    sample = data[(data["year"] >= FIRST_ANALYSIS_YEAR)
                  & (data["year"] <= last_year)].dropna()
    x = sm.add_constant(sample[["trade_index", "remit_index"]])
    return sm.OLS(sample["growth"], x).fit()


def predict_partner(model, trade_index, remit_index):
    """Forecast from the partner model for one year."""
    params = model.params
    return (params["const"] + params["trade_index"] * trade_index
            + params["remit_index"] * remit_index)


def vintage_indices(historical, trade_w, remit_w, origin, years):
    """Partner indices built from the IMF's forecasts in one WEO edition."""
    forecasts = historical[(historical["variable"] == "ngdp_rpch")
                           & (historical["season"] == "F")
                           & (historical["vintage_year"] == origin)]
    growth = forecasts.rename(columns={"country": "partner",
                                       "target_year": "year",
                                       "value": "growth"})
    known_trade = trade_w[trade_w["year"] <= origin - 1]
    known_remit = remit_w[remit_w["year"] <= origin - 1]
    trade_index = compute_partner_index(known_trade, growth, "TJK", years)
    remit_index = compute_partner_index(known_remit, growth, "TJK", years)
    if len(trade_index) == 0 or len(remit_index) == 0:
        return None
    both = trade_index[["year", "index"]].rename(
        columns={"index": "trade_index"}).merge(
        remit_index[["year", "index"]].rename(
            columns={"index": "remit_index"}), on="year")
    return both.set_index("year")


# ---------------------------------------------------------------------------
# Back-test
# ---------------------------------------------------------------------------

def run_backtest(actual, data, historical, trade_w, remit_w):
    """All forecasts from every origin and horizon, with errors."""
    imf = historical[(historical["variable"] == "ngdp_rpch")
                     & (historical["season"] == "F")
                     & (historical["country"] == "TJK")]
    last_origin = int(historical["vintage_year"].max())
    rows = []
    for origin in range(FIRST_ORIGIN, last_origin + 1):
        targets = []
        for horizon in range(1, MAX_HORIZON + 1):
            if origin + horizon <= LAST_ACTUAL_YEAR:
                targets.append(origin + horizon)
        if not targets:
            continue
        a, b = fit_ar1(actual, origin)
        partner_model = fit_partner_model(data, origin)
        indices = vintage_indices(historical, trade_w, remit_w, origin,
                                  targets)
        ar_value = actual[origin]
        for target in targets:
            horizon = target - origin
            ar_value = a + b * ar_value          # iterate the AR(1)
            forecasts = {"naive": actual[origin], "AR(1)": ar_value}
            if indices is not None and target in indices.index:
                forecasts["partner model"] = predict_partner(
                    partner_model, indices.loc[target, "trade_index"],
                    indices.loc[target, "remit_index"])
            imf_value = imf[(imf["vintage_year"] == origin)
                            & (imf["target_year"] == target)]["value"]
            if len(imf_value) == 1:
                forecasts["IMF"] = imf_value.iloc[0]
            for method, value in forecasts.items():
                rows.append({"origin": origin, "target_year": target,
                             "horizon": horizon, "method": method,
                             "forecast": value,
                             "actual": actual.get(target)})
    table = pd.DataFrame(rows)
    table["error"] = table["forecast"] - table["actual"]
    return table


def accuracy(backtest):
    """MAE, RMSE and bias by method and horizon, on a common sample.

    Only target years where all four methods have a forecast are used,
    so the methods are compared on exactly the same years.
    """
    counts = backtest.groupby(["horizon", "target_year"])["method"].nunique()
    complete = counts[counts == len(METHODS)].reset_index()[
        ["horizon", "target_year"]]
    common = backtest.merge(complete, on=["horizon", "target_year"])
    rows = []
    for (horizon, method), group in common.groupby(["horizon", "method"]):
        errors = group["error"]
        rows.append({"horizon": horizon, "method": method,
                     "n": len(errors),
                     "first_target": group["target_year"].min(),
                     "last_target": group["target_year"].max(),
                     "mean_error": errors.mean(),
                     "mae": errors.abs().mean(),
                     "rmse": np.sqrt((errors ** 2).mean())})
    table = pd.DataFrame(rows)
    order = {method: rank for rank, method in enumerate(METHODS)}
    table["order"] = table["method"].map(order)
    table = table.sort_values(["horizon", "order"]).drop(columns="order")
    return table.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Baseline and scenarios
# ---------------------------------------------------------------------------

def scenario_growth(growth, name):
    """Partner growth table for one scenario (October 2026 WEO + shock)."""
    changed = growth.copy()
    if name == "A: Russia -2 pp (2026-27)":
        rows = (changed["partner"] == "RUS") & changed["year"].isin(
            [2026, 2027])
        changed.loc[rows, "growth"] = changed.loc[rows, "growth"] \
            + SCENARIO_SHOCK
    elif name == "B: China -2 pp (2026-27)":
        rows = (changed["partner"] == "CHN") & changed["year"].isin(
            [2026, 2027])
        changed.loc[rows, "growth"] = changed.loc[rows, "growth"] \
            + SCENARIO_SHOCK
    elif name == "C: Russia repeats 2015 (2026)":
        russia_2015 = changed.loc[(changed["partner"] == "RUS")
                                  & (changed["year"] == 2015), "growth"]
        rows = (changed["partner"] == "RUS") & (changed["year"] == 2026)
        changed.loc[rows, "growth"] = russia_2015.iloc[0]
    return changed


def baseline_and_scenarios(data, growth, trade_w, remit_w, imf_now):
    """Partner-model forecasts for 2026-2030 under each scenario."""
    model = fit_partner_model(data, LAST_ACTUAL_YEAR)
    covariance = model.cov_params()
    names = ["Baseline", "A: Russia -2 pp (2026-27)",
             "B: China -2 pp (2026-27)", "C: Russia repeats 2015 (2026)"]
    rows = []
    baseline_indices = None
    for name in names:
        scenario = scenario_growth(growth, name)
        trade_index = compute_partner_index(trade_w, scenario, "TJK",
                                            FORECAST_YEARS)
        remit_index = compute_partner_index(remit_w, scenario, "TJK",
                                            FORECAST_YEARS)
        indices = trade_index[["year", "index"]].rename(
            columns={"index": "trade_index"}).merge(
            remit_index[["year", "index"]].rename(
                columns={"index": "remit_index"}), on="year")
        if name == "Baseline":
            baseline_indices = indices.set_index("year")
        for _, row in indices.iterrows():
            year = int(row["year"])
            forecast = predict_partner(model, row["trade_index"],
                                       row["remit_index"])
            # Uncertainty of the scenario EFFECT (difference from baseline)
            # coming from the estimated coefficients: d' V d.
            d_trade = row["trade_index"] - baseline_indices.loc[
                year, "trade_index"]
            d_remit = row["remit_index"] - baseline_indices.loc[
                year, "remit_index"]
            d = np.array([0.0, d_trade, d_remit])
            effect_se = float(np.sqrt(d @ covariance.values @ d))
            rows.append({"scenario": name, "year": year,
                         "trade_index": row["trade_index"],
                         "remit_index": row["remit_index"],
                         "forecast": forecast,
                         "effect_vs_baseline": None,
                         "effect_se": effect_se,
                         "imf_forecast": imf_now.get(year)})
    table = pd.DataFrame(rows)
    baseline = table[table["scenario"] == "Baseline"].set_index("year")[
        "forecast"]
    table["effect_vs_baseline"] = table["forecast"] - table["year"].map(
        baseline)
    return table, model


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def chart_backtest(backtest, accuracy_table):
    """One-year-ahead forecasts vs outcomes, and RMSE by method."""
    one_year = backtest[backtest["horizon"] == 1]
    figure, (left, right) = plt.subplots(
        1, 2, figsize=(11, 4.5), gridspec_kw={"width_ratios": [2, 1]})

    actual = one_year.drop_duplicates("target_year").set_index(
        "target_year")["actual"].sort_index()
    left.plot(actual.index, actual.values, color=COLORS["TJK"],
              label="Outcome (WEO Oct 2026)")
    for method, color, style in [("IMF", COLORS["IMF"], "--"),
                                 ("partner model", COLORS["RUS"], "-")]:
        rows = one_year[one_year["method"] == method].set_index(
            "target_year")["forecast"].sort_index()
        left.plot(rows.index, rows.values, color=color, linestyle=style,
                  linewidth=1.6, label=method + " (one year ahead)")
    left.set_ylabel("Tajik real GDP growth, %")
    left.set_title("One-year-ahead forecasts vs outcomes")
    year_axis(left)
    left.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=3,
                fontsize=8)

    h1 = accuracy_table[accuracy_table["horizon"] == 1]
    positions = list(range(len(h1)))
    right.barh(positions, h1["rmse"], color=COLORS["TJK"], height=0.55)
    for position, (_, row) in zip(positions, h1.iterrows()):
        right.text(row["rmse"] + 0.05, position,
                   str(round(row["rmse"], 2)), va="center", fontsize=8)
    right.set_yticks(positions)
    right.set_yticklabels(h1["method"])
    right.invert_yaxis()
    right.set_xlabel("RMSE, percentage points")
    n_years = int(h1["n"].iloc[0]) if len(h1) > 0 else 0
    right.set_title("Error, one year ahead (N=" + str(n_years) + ")")
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    save_figure(figure, "fig09_backtest",
                "Forecast origins: autumn of each year. IMF forecasts: IMF "
                "historical WEO forecasts file. Outcomes: WEO October 2026.")


def chart_fan(actual, scenarios, accuracy_table):
    """2026-2030 baseline with error bands, scenarios and the IMF path."""
    partner_rmse = accuracy_table[accuracy_table["method"]
                                  == "partner model"].set_index(
        "horizon")["rmse"]
    baseline = scenarios[scenarios["scenario"] == "Baseline"].set_index(
        "year")
    widths = []
    for year in baseline.index:
        horizon = year - LAST_ACTUAL_YEAR
        available = partner_rmse[partner_rmse.index <= horizon]
        widths.append(available.iloc[-1] if len(available) > 0
                      else np.nan)
    widths = np.array(widths)

    figure, axis = plt.subplots(figsize=(10, 5))
    history = actual[(actual.index >= 2010)
                     & (actual.index <= LAST_ACTUAL_YEAR)]
    years = [LAST_ACTUAL_YEAR] + list(baseline.index)
    center = [history.iloc[-1]] + list(baseline["forecast"])
    band_90 = [0.0] + list(Z_90 * widths)
    band_50 = [0.0] + list(Z_50 * widths)
    axis.fill_between(years, np.array(center) - np.array(band_90),
                      np.array(center) + np.array(band_90),
                      color=COLORS["TJK"], alpha=0.12, linewidth=0,
                      label="90% band (back-test errors)")
    axis.fill_between(years, np.array(center) - np.array(band_50),
                      np.array(center) + np.array(band_50),
                      color=COLORS["TJK"], alpha=0.25, linewidth=0,
                      label="50% band")
    axis.plot(history.index, history.values, color=COLORS["TJK"],
              label="Outcome")
    axis.plot(years, center, color=COLORS["TJK"], linestyle="--",
              label="Partner model baseline")
    axis.plot(baseline.index, baseline["imf_forecast"], color=COLORS["IMF"],
              linestyle=":", linewidth=2, label="IMF WEO Oct 2026")
    styles = {"A: Russia -2 pp (2026-27)": (COLORS["RUS"], "-"),
              "B: China -2 pp (2026-27)": (COLORS["CHN"], "-"),
              "C: Russia repeats 2015 (2026)": (COLORS["RUS"], "-.")}
    for name, (color, style) in styles.items():
        rows = scenarios[scenarios["scenario"] == name]
        axis.plot(rows["year"], rows["forecast"], color=color,
                  linestyle=style, linewidth=1.5, label=name)
    axis.axvline(LAST_ACTUAL_YEAR + 0.5, color=MUTED_TEXT, linewidth=0.8)
    axis.set_ylabel("Tajik real GDP growth, %")
    axis.set_title("Tajikistan: growth outlook 2026-2030 (partner model)")
    year_axis(axis)
    axis.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    save_figure(figure, "fig10_fan_chart",
                "Partner model = Spec 2 estimated 1998-2025, fed with IMF "
                "October 2026 partner forecasts. 2025 is an IMF estimate.")


def main():
    set_chart_style()
    growth_all = read_table("growth_all")
    growth = growth_all[growth_all["vintage"] == "2026-10"].rename(
        columns={"country": "partner"})
    historical = read_table("weo_historical")
    trade_w = read_table("trade_weights")
    remit_w = read_table("remittance_weights")
    indices = read_table("partner_indices")
    trade_w = trade_w[trade_w["reporter"] == "TJK"]
    remit_w = remit_w[remit_w["reporter"] == "TJK"]

    tjk_growth = growth[growth["partner"] == "TJK"].set_index("year")[
        "growth"].sort_index()
    actual = tjk_growth[tjk_growth.index <= LAST_ACTUAL_YEAR]
    imf_now = tjk_growth[tjk_growth.index > LAST_ACTUAL_YEAR]

    data = indices[indices["reporter"] == "TJK"][
        ["year", "trade_index", "remit_index"]]
    data = data.merge(actual.rename("growth").reset_index(), on="year")

    backtest = run_backtest(actual, data, historical, trade_w, remit_w)
    accuracy_table = accuracy(backtest)
    save_table(backtest, "table05_backtest_forecasts")
    save_table(accuracy_table, "table06_forecast_accuracy")
    print(accuracy_table.round(2).to_string(index=False))

    scenarios, model = baseline_and_scenarios(data, growth, trade_w,
                                              remit_w, imf_now)
    save_table(scenarios, "table07_baseline_scenarios")
    print(scenarios[["scenario", "year", "forecast", "effect_vs_baseline",
                     "effect_se", "imf_forecast"]].round(2).to_string(
                         index=False))

    chart_backtest(backtest, accuracy_table)
    chart_fan(actual, scenarios, accuracy_table)


if __name__ == "__main__":
    main()
