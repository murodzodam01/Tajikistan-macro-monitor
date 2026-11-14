"""Step 5: stationarity tests and the three pre-stated regressions.

The specifications below were fixed BEFORE looking at any results
(see README). They are not changed after seeing the output.

    Spec 1  TJK growth = a + b1 * Russian growth + b2 * Chinese growth
    Spec 2  TJK growth = a + b1 * trade-weighted partner growth
                           + b2 * remittance-weighted partner growth
    Spec 3  Spec 2 for TJK, KGZ, UZB and KAZ together (panel), with
            country fixed effects

Sample: 1998-2025 (2025 is an IMF estimate). Annual data.
Standard errors: Newey-West (HAC) with 1 lag, no small-sample correction;
for the panel, Newey-West within each country ('hac-panel').
Results are associations, not causal effects.

The Newey-West standard errors of Spec 1 are also computed by hand with
numpy and compared with statsmodels, as a check on the library.
"""

import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import adfuller, kpss

from common import (COLORS, FIRST_ANALYSIS_YEAR, HAC_LAGS, LAST_ACTUAL_YEAR,
                    MUTED_TEXT, PANEL_COUNTRIES, read_table, save_figure,
                    save_table, set_chart_style)

ADF_MAX_LAGS = 2      # small annual sample: at most 2 lags, chosen by AIC

VARIABLE_LABELS = {
    "growth_RUS": "Russian growth",
    "growth_CHN": "Chinese growth",
    "trade_index": "Trade-weighted partner growth",
    "remit_index": "Remittance-weighted partner growth",
}


def build_country_data(growth, indices, country):
    """Growth, partner growth and indices for one country, 1998-2025."""
    own = growth[growth["country"] == country][["year", "growth"]]
    rus = growth[growth["country"] == "RUS"][["year", "growth"]]
    chn = growth[growth["country"] == "CHN"][["year", "growth"]]
    data = own.rename(columns={"growth": "growth_own"})
    data = data.merge(rus.rename(columns={"growth": "growth_RUS"}),
                      on="year")
    data = data.merge(chn.rename(columns={"growth": "growth_CHN"}),
                      on="year")
    country_indices = indices[indices["reporter"] == country][
        ["year", "trade_index", "remit_index"]]
    data = data.merge(country_indices, on="year", how="left")
    data = data[(data["year"] >= FIRST_ANALYSIS_YEAR)
                & (data["year"] <= LAST_ACTUAL_YEAR)]
    data["country"] = country
    return data.sort_values("year").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Stationarity
# ---------------------------------------------------------------------------

def stationarity_tests(data):
    """ADF (null: unit root) and KPSS (null: stationary) for each series."""
    series = {"growth_own": "Tajik growth"}
    series.update(VARIABLE_LABELS)
    rows = []
    for column, label in series.items():
        values = data[column].dropna().values
        adf_stat, adf_p, adf_lags, adf_n, _, _ = adfuller(
            values, maxlag=ADF_MAX_LAGS, regression="c", autolag="AIC",
            result_object=False)
        # KPSS p-values are only tabulated between 0.01 and 0.10; outside
        # that range statsmodels reports the bound and warns. We record it.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", InterpolationWarning)
            kpss_stat, kpss_p, kpss_lags, _ = kpss(values, regression="c",
                                                   nlags="auto")
        at_bound = any(issubclass(item.category, InterpolationWarning)
                       for item in caught)
        rows.append({"series": label,
                     "n": len(values),
                     "adf_stat": adf_stat, "adf_p": adf_p,
                     "adf_lags": adf_lags,
                     "kpss_stat": kpss_stat, "kpss_p": kpss_p,
                     "kpss_p_at_table_bound": at_bound})
    table = pd.DataFrame(rows)
    save_table(table, "table02_stationarity")
    print("Saved table: table02_stationarity")
    return table


# ---------------------------------------------------------------------------
# Regressions
# ---------------------------------------------------------------------------

def fit_time_series(data, regressors, name):
    """OLS with Newey-West standard errors for one country."""
    sample = data.dropna(subset=["growth_own"] + regressors)
    y = sample["growth_own"]
    x = sm.add_constant(sample[regressors])
    model = sm.OLS(y, x).fit(cov_type="HAC",
                             cov_kwds={"maxlags": HAC_LAGS})
    years = str(sample["year"].min()) + "-" + str(sample["year"].max())
    return model, sample, years, name


def fit_panel(panel, regressors, name):
    """Pooled OLS with country fixed effects, Newey-West within country."""
    sample = panel.dropna(subset=["growth_own"] + regressors)
    sample = sample.sort_values(["country", "year"]).reset_index(drop=True)
    dummies = pd.get_dummies(sample["country"], prefix="fe",
                             drop_first=True, dtype=float)
    x = sm.add_constant(pd.concat([sample[regressors], dummies], axis=1))
    y = sample["growth_own"]
    groups = pd.factorize(sample["country"])[0]
    model = sm.OLS(y, x).fit(cov_type="hac-panel",
                             cov_kwds={"groups": groups,
                                       "maxlags": HAC_LAGS})
    years = str(sample["year"].min()) + "-" + str(sample["year"].max())
    return model, sample, years, name


def newey_west_by_hand(x, residuals, lags):
    """Newey-West covariance matrix with Bartlett weights (numpy only).

    V = (X'X)^-1 S (X'X)^-1, with
    S = sum_t u_t^2 x_t x_t'
        + sum_{l=1..L} w_l * sum_t u_t u_{t-l} (x_t x_{t-l}' + x_{t-l} x_t')
    with Bartlett weights w_l = 1 - l / (L + 1).
    """
    x = np.asarray(x, dtype=float)
    u = np.asarray(residuals, dtype=float)
    xu = x * u[:, None]
    s_matrix = xu.T @ xu
    for lag in range(1, lags + 1):
        weight = 1 - lag / (lags + 1)
        gamma = xu[lag:].T @ xu[:-lag]
        s_matrix = s_matrix + weight * (gamma + gamma.T)
    xtx_inverse = np.linalg.inv(x.T @ x)
    return xtx_inverse @ s_matrix @ xtx_inverse


def check_newey_west(model, sample, regressors):
    """Compare hand-computed Newey-West standard errors with statsmodels."""
    x = sm.add_constant(sample[regressors])
    covariance = newey_west_by_hand(x, model.resid, HAC_LAGS)
    by_hand = np.sqrt(np.diag(covariance))
    difference = np.max(np.abs(by_hand - model.bse.values))
    print("Newey-West check (Spec 1): largest difference between hand "
          "calculation and statsmodels =", difference)
    assert difference < 1e-8, "Hand-computed Newey-West SEs do not match"
    table = pd.DataFrame({"term": model.bse.index,
                          "se_statsmodels": model.bse.values,
                          "se_by_hand": by_hand})
    save_table(table, "table04_newey_west_check", decimals=6)


def results_table(fits):
    """One row per coefficient, with model statistics on every row."""
    rows = []
    for model, sample, years, name in fits:
        intervals = model.conf_int()
        for term in model.params.index:
            if term.startswith("fe_"):
                continue        # country fixed effects are not reported
            rows.append({
                "specification": name,
                "term": VARIABLE_LABELS.get(term, term),
                "coefficient": model.params[term],
                "std_error": model.bse[term],
                "p_value": model.pvalues[term],
                "ci_low": intervals.loc[term, 0],
                "ci_high": intervals.loc[term, 1],
                "n": int(model.nobs),
                "years": years,
                "r_squared": model.rsquared,
                "se_type": model.cov_type + ", " + str(HAC_LAGS) + " lag",
            })
    return pd.DataFrame(rows)


def joint_tests(fits):
    """Wald test that both partner coefficients are zero (robust SEs).

    Added after the first run as a diagnostic: in Spec 2 the two indices
    move together, so each coefficient alone can look insignificant even
    if the two are jointly related to Tajik growth. The specifications
    themselves are unchanged.
    """
    rows = []
    for model, sample, years, name in fits:
        terms = []
        for term in model.params.index:
            if term != "const" and not term.startswith("fe_"):
                terms.append(term)
        hypothesis = ", ".join(term + " = 0" for term in terms)
        test = model.wald_test(hypothesis, use_f=False, scalar=True)
        rows.append({"specification": name,
                     "hypothesis": hypothesis,
                     "chi2": float(test.statistic),
                     "df": len(terms),
                     "p_value": float(test.pvalue),
                     "n": int(model.nobs)})
    table = pd.DataFrame(rows)
    save_table(table, "table08_joint_tests")
    print("Saved table: table08_joint_tests")
    return table


def index_correlations(data):
    """How strongly the regressors move together (Tajik sample)."""
    columns = ["growth_RUS", "growth_CHN", "trade_index", "remit_index"]
    matrix = data[columns].corr().round(3)
    labels = []
    for column in columns:
        labels.append(VARIABLE_LABELS[column])
    matrix.index = labels
    matrix.columns = labels
    table = matrix.reset_index().rename(columns={"index": "variable"})
    save_table(table, "table09_regressor_correlations")
    print("Saved table: table09_regressor_correlations")


def coefficient_plot(results):
    """Point estimates with 95% intervals, one row per coefficient."""
    table = results[results["term"] != "const"].reset_index(drop=True)
    figure, axis = plt.subplots(figsize=(9, 4.5))
    positions = list(range(len(table)))
    axis.axvline(0, color=MUTED_TEXT, linewidth=0.8)
    for position, (_, row) in zip(positions, table.iterrows()):
        axis.plot([row["ci_low"], row["ci_high"]], [position, position],
                  color=COLORS["TJK"], linewidth=2)
        axis.scatter([row["coefficient"]], [position], s=50,
                     color=COLORS["TJK"], edgecolor="#fcfcfb", zorder=3)
    labels = []
    for _, row in table.iterrows():
        labels.append(row["specification"] + ": " + row["term"]
                      + "  (N=" + str(row["n"]) + ")")
    axis.set_yticks(positions)
    axis.set_yticklabels(labels, fontsize=8)
    axis.invert_yaxis()
    axis.set_xlabel("Change in Tajik growth (pp) per 1 pp of partner "
                    "growth, with 95% interval")
    axis.set_title("Regression coefficients (associations, not causal "
                   "effects)")
    figure.tight_layout(rect=(0, 0.06, 1, 1))
    save_figure(figure, "fig08_regression_coefficients",
                "Newey-West standard errors, 1 lag. Spec 3: panel of TJK, "
                "KGZ, UZB, KAZ with country fixed effects.")


def main():
    set_chart_style()
    growth_all = read_table("growth_all")
    growth = growth_all[growth_all["vintage"] == "2026-10"]
    indices = read_table("partner_indices")

    tjk = build_country_data(growth, indices, "TJK")
    panel = pd.concat([build_country_data(growth, indices, country)
                       for country in PANEL_COUNTRIES], ignore_index=True)
    print("TJK sample:", tjk["year"].min(), "-", tjk["year"].max(),
          "| rows:", len(tjk))

    stationarity_tests(tjk)

    spec1_vars = ["growth_RUS", "growth_CHN"]
    spec2_vars = ["trade_index", "remit_index"]
    fit1 = fit_time_series(tjk, spec1_vars, "Spec 1")
    fit2 = fit_time_series(tjk, spec2_vars, "Spec 2")
    fit3 = fit_panel(panel, spec2_vars, "Spec 3 (panel)")
    check_newey_west(fit1[0], fit1[1], spec1_vars)

    for model, sample, years, name in [fit1, fit2, fit3]:
        print()
        print(name, "| N =", int(model.nobs), "| years", years)
        print(model.summary().tables[1])

    results = results_table([fit1, fit2, fit3])
    save_table(results, "table03_regressions")
    print("Saved table: table03_regressions")
    print(joint_tests([fit1, fit2, fit3]).round(3).to_string(index=False))
    index_correlations(tjk)
    coefficient_plot(results)


if __name__ == "__main__":
    main()
