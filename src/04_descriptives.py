"""Step 4: descriptive charts and the summary statistics table.

Charts (saved to outputs/figures):
    fig01_growth_peers          real GDP growth, TJK and comparators
    fig02_trade_partners        Tajikistan's trade by partner (shares)
    fig03_remittances           remittances (% of GDP) and their sources
    fig04_debt_creditors        public external debt owed to China/Russia
    fig05_partner_indices       TJK growth vs partner growth indices
    fig06_ruble_shock           2014-15 ruble shock: TJK vs KGZ and UZB
    fig07_forecast_revisions    IMF growth forecasts, April vs October 2026

All charts are descriptive. None of them shows a causal effect.
"""

import matplotlib.pyplot as plt
import pandas as pd

from common import (COLORS, COUNTRY_NAMES, CORE_COUNTRIES,
                    FIRST_ANALYSIS_YEAR, LAST_ACTUAL_YEAR, MUTED_TEXT,
                    TEXT_COLOR, mark_shock_years, read_table, save_figure,
                    year_axis,
                    save_table, set_chart_style)

WEO_NOTE = "Source: IMF World Economic Outlook, October 2026."
TRADE_PARTNERS = ["RUS", "CHN", "KAZ", "UZB", "TUR", "IRN"]
SUMMARY_VARIABLES = {
    "gdp_growth": "Real GDP growth (%)",
    "inflation": "Inflation (%)",
    "current_account": "Current account (% of GDP)",
    "government_debt": "Government debt (% of GDP)",
    "remittances_gdp": "Remittances (% of GDP)",
}


def growth_series(growth_all, country, vintage="2026-10"):
    """Real GDP growth of one country from one WEO edition, by year."""
    rows = growth_all[(growth_all["country"] == country)
                      & (growth_all["vintage"] == vintage)]
    return rows.set_index("year")["growth"].sort_index()


def macro_series(macro, country, variable):
    """One variable for one country, indexed by year."""
    rows = macro[(macro["country"] == country)
                 & (macro["variable"] == variable)]
    return rows.set_index("year")["value"].sort_index()


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def chart_growth_peers(growth_all):
    """Small multiples: one panel per country, same y-axis."""
    figure, axes = plt.subplots(2, 3, figsize=(11, 6), sharex=True,
                                sharey=True)
    for axis, country in zip(axes.flat, CORE_COUNTRIES):
        series = growth_series(growth_all, country)
        series = series[series.index >= 1995]
        actual = series[series.index <= LAST_ACTUAL_YEAR]
        projected = series[series.index >= LAST_ACTUAL_YEAR]
        mark_shock_years(axis, 1995, 2031)
        axis.axhline(0, color=MUTED_TEXT, linewidth=0.8)
        axis.plot(actual.index, actual.values, color=COLORS[country])
        axis.plot(projected.index, projected.values, color=COLORS[country],
                  linestyle="--")
        axis.set_title(COUNTRY_NAMES[country])
        axis.set_xticks([2000, 2010, 2020, 2030])
    axes[0, 0].set_ylabel("Real GDP growth, %")
    axes[1, 0].set_ylabel("Real GDP growth, %")
    figure.suptitle("Real GDP growth, 1995-2031 (dashed: IMF projections "
                    "from 2025; shaded: shock years)", x=0.01, ha="left",
                    fontweight="bold")
    figure.tight_layout(rect=(0, 0.03, 1, 0.97))
    save_figure(figure, "fig01_growth_peers",
                WEO_NOTE + " 2025 is an IMF estimate.")


def chart_trade_partners(trade_weights):
    """Stacked area of partner shares in Tajikistan's total goods trade."""
    tjk = trade_weights[(trade_weights["reporter"] == "TJK")
                        & (trade_weights["year"] >= 1995)
                        & (trade_weights["year"] <= LAST_ACTUAL_YEAR)]
    shares = tjk.pivot_table(index="year", columns="partner",
                             values="weight", aggfunc="sum").fillna(0)
    for partner in TRADE_PARTNERS:
        if partner not in shares.columns:
            shares[partner] = 0.0
    table = 100 * shares[TRADE_PARTNERS]
    table["Other"] = 100 - table.sum(axis=1)

    figure, axis = plt.subplots(figsize=(10, 5.5))
    labels = []
    for column in table.columns:
        labels.append(COUNTRY_NAMES.get(column, column))
    colors = []
    for column in table.columns:
        colors.append(COLORS[column])
    axis.stackplot(table.index, table.T.values, labels=labels,
                   colors=colors, edgecolor="#fcfcfb", linewidth=1.5)

    # Direct labels at the right edge, in the middle of each band.
    last_year = table.index.max()
    bottom = 0.0
    for column, label in zip(table.columns, labels):
        height = table.loc[last_year, column]
        if height >= 3:
            axis.text(last_year + 0.4, bottom + height / 2,
                      label + " " + str(round(height)) + "%",
                      va="center", fontsize=8, color=TEXT_COLOR)
        bottom += height
    axis.set_xlim(table.index.min(), last_year)
    axis.set_ylim(0, 100)
    axis.set_ylabel("Share of total goods trade, %")
    year_axis(axis)
    axis.set_title("Tajikistan's goods trade by partner "
                   "(exports + imports)")
    axis.legend(loc="upper left", bbox_to_anchor=(1.12, 1), fontsize=8)
    figure.tight_layout(rect=(0, 0.03, 1, 1))
    save_figure(figure, "fig02_trade_partners",
                "Source: IMF International Trade in Goods by partner "
                "(IMTS). 'Other' includes trade with unidentified partners.")


def chart_remittances(macro, remit_weights):
    """Two panels: remittances % of GDP; estimated sources for TJK."""
    figure, (left, right) = plt.subplots(1, 2, figsize=(11, 4.5))

    for country in ["TJK", "KGZ", "UZB"]:
        series = macro_series(macro, country, "remittances_gdp")
        series = series[(series.index >= 2000)
                        & (series.index <= LAST_ACTUAL_YEAR)]
        left.plot(series.index, series.values, color=COLORS[country],
                  label=COUNTRY_NAMES[country])
    left.set_ylabel("% of GDP")
    left.set_title("Personal remittances received")
    left.legend(loc="upper left")

    tjk = remit_weights[(remit_weights["reporter"] == "TJK")
                        & (remit_weights["year"] >= 2000)]
    shares = tjk.pivot_table(index="year", columns="partner",
                             values="weight", aggfunc="sum").fillna(0)
    parts = {}
    for partner in ["RUS", "KAZ"]:
        if partner in shares.columns:
            parts[partner] = 100 * shares[partner]
        else:
            parts[partner] = 0 * shares.iloc[:, 0]
    parts["Other"] = 100 - parts["RUS"] - parts["KAZ"]
    right.stackplot(shares.index, [parts["RUS"], parts["KAZ"],
                                   parts["Other"]],
                    labels=["Russia", "Kazakhstan", "Other"],
                    colors=[COLORS["RUS"], COLORS["KAZ"], COLORS["Other"]],
                    edgecolor="#fcfcfb", linewidth=1.5)
    right.set_ylim(0, 100)
    right.set_xlim(shares.index.min(), shares.index.max())
    right.set_ylabel("Estimated share of remittances, %")
    right.set_title("Tajikistan: estimated sources (model)")
    year_axis(left)
    year_axis(right)
    right.legend(loc="lower left")
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    save_figure(figure, "fig03_remittances",
                "Sources: World Bank WDI; UN DESA migrant stocks 2024; "
                "shares rebuilt with the World Bank/KNOMAD method "
                "(model estimates, not observed flows).")


def chart_debt_creditors(macro):
    """Share of Tajikistan's public external debt owed to China/Russia."""
    total = macro_series(macro, "TJK", "ppg_external_debt_usd")
    figure, axis = plt.subplots(figsize=(9, 4.5))
    for creditor, variable in [("CHN", "debt_to_china_usd"),
                               ("RUS", "debt_to_russia_usd")]:
        owed = macro_series(macro, "TJK", variable)
        share = 100 * owed / total
        share = share.dropna()
        share = share[(share.index >= 1995)
                      & (share.index <= LAST_ACTUAL_YEAR)]
        axis.plot(share.index, share.values, color=COLORS[creditor],
                  label="Owed to " + COUNTRY_NAMES[creditor])
        if len(share) > 0:
            axis.text(share.index[-1] + 0.3, share.values[-1],
                      str(round(share.values[-1])) + "%", fontsize=8,
                      va="center", color=TEXT_COLOR)
    axis.set_ylabel("% of public external debt")
    axis.set_title("Tajikistan: public external debt by creditor")
    year_axis(axis)
    axis.legend(loc="upper left")
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    save_figure(figure, "fig04_debt_creditors",
                "Source: World Bank International Debt Statistics "
                "(bilateral PPG debt) and WDI (total PPG external debt).")


def chart_partner_indices(growth_all, indices):
    """Tajik growth against the two partner growth indices."""
    tjk_growth = growth_series(growth_all, "TJK")
    tjk = indices[indices["reporter"] == "TJK"].set_index("year")
    years = range(FIRST_ANALYSIS_YEAR, LAST_ACTUAL_YEAR + 1)
    figure, axis = plt.subplots(figsize=(10, 4.8))
    mark_shock_years(axis, FIRST_ANALYSIS_YEAR, LAST_ACTUAL_YEAR)
    axis.axhline(0, color=MUTED_TEXT, linewidth=0.8)
    axis.plot(list(years), tjk_growth.reindex(years).values,
              color=COLORS["TJK"], label="Tajikistan real GDP growth")
    axis.plot(list(years), tjk["remit_index"].reindex(years).values,
              color=COLORS["RUS"],
              label="Remittance-weighted partner growth")
    axis.plot(list(years), tjk["trade_index"].reindex(years).values,
              color=COLORS["CHN"], label="Trade-weighted partner growth")
    axis.set_ylabel("%")
    axis.set_title("Tajikistan's growth and its partners' growth")
    year_axis(axis)
    axis.legend(loc="lower left", fontsize=8)
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    save_figure(figure, "fig05_partner_indices",
                WEO_NOTE + " Weights: IMF IMTS trade; UN DESA migrant "
                "stocks (model). Shaded: 2009, 2015, 2020, 2022.")


def chart_ruble_shock(growth_all, macro):
    """Indexed real GDP and remittances, 2013 = 100, TJK vs KGZ and UZB."""
    countries = ["TJK", "KGZ", "UZB"]
    figure, (left, right) = plt.subplots(1, 2, figsize=(11, 4.5),
                                         sharey=False)
    for country in countries:
        growth = growth_series(growth_all, country)
        growth = growth[(growth.index >= 2012) & (growth.index <= 2018)]
        level = (1 + growth / 100).cumprod()
        level = 100 * level / level.loc[2013]
        left.plot(level.index, level.values, color=COLORS[country],
                  label=COUNTRY_NAMES[country], marker="o", markersize=4)

        remit = macro_series(macro, country, "remittances_usd")
        remit = remit[(remit.index >= 2011) & (remit.index <= 2018)]
        if 2013 in remit.index:
            right.plot(remit.index, 100 * remit / remit.loc[2013],
                       color=COLORS[country], label=COUNTRY_NAMES[country],
                       marker="o", markersize=4)
    for axis in [left, right]:
        axis.axvspan(2014.5, 2015.5, color="#999999", alpha=0.15,
                     linewidth=0)
        axis.axhline(100, color=MUTED_TEXT, linewidth=0.8)
        year_axis(axis)
    left.set_title("Real GDP (2013 = 100)")
    right.set_title("Remittances received, US$ (2013 = 100)")
    left.legend(loc="upper left")
    right.legend(loc="lower left")
    figure.suptitle("The 2014-15 ruble shock (descriptive comparison, "
                    "not a causal estimate)", x=0.01, ha="left",
                    fontweight="bold")
    figure.tight_layout(rect=(0, 0.05, 1, 0.94))
    save_figure(figure, "fig06_ruble_shock",
                WEO_NOTE + " World Bank WDI. Shaded: 2015.")


def chart_forecast_revisions(growth_all):
    """IMF growth forecasts for 2026 and 2027: April vs October 2026."""
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    positions = list(range(len(CORE_COUNTRIES)))
    for axis, year in zip(axes, [2026, 2027]):
        for position, country in zip(positions, CORE_COUNTRIES):
            april = growth_series(growth_all, country, "2026-04").get(year)
            october = growth_series(growth_all, country, "2026-10").get(year)
            axis.plot([april, october], [position, position],
                      color="#b5b4ae", linewidth=2, zorder=1)
            axis.scatter([april], [position], s=60, facecolor="#fcfcfb",
                         edgecolor=MUTED_TEXT, linewidth=1.5, zorder=2,
                         label="April 2026" if position == 0 else None)
            axis.scatter([october], [position], s=60, color=COLORS["TJK"],
                         edgecolor="#fcfcfb", linewidth=1.5, zorder=3,
                         label="October 2026" if position == 0 else None)
        axis.set_xlabel("Projected real GDP growth, %")
        axis.set_title("Forecast for " + str(year))
    labels = []
    for country in CORE_COUNTRIES:
        labels.append(COUNTRY_NAMES[country])
    axes[0].set_yticks(positions)
    axes[0].set_yticklabels(labels)
    # The y-axis is shared, so flip it once only (Tajikistan on top).
    axes[0].invert_yaxis()
    handles, legend_labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, legend_labels, loc="upper right", ncol=2,
                  fontsize=8, bbox_to_anchor=(1, 1.02))
    figure.tight_layout(rect=(0, 0.05, 1, 0.95))
    save_figure(figure, "fig07_forecast_revisions",
                "Source: IMF WEO April 2026 and October 2026 editions.")


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def summary_statistics(macro):
    """Mean, standard deviation, min, max and N, 1998-2025."""
    rows = []
    sample = macro[(macro["year"] >= FIRST_ANALYSIS_YEAR)
                   & (macro["year"] <= LAST_ACTUAL_YEAR)]
    for variable, label in SUMMARY_VARIABLES.items():
        for country in CORE_COUNTRIES:
            values = sample[(sample["country"] == country)
                            & (sample["variable"] == variable)]["value"]
            values = values.dropna()
            if len(values) == 0:
                continue
            rows.append({"variable": label,
                         "country": country,
                         "n": len(values),
                         "mean": values.mean(),
                         "sd": values.std(),
                         "min": values.min(),
                         "max": values.max()})
    table = pd.DataFrame(rows)
    save_table(table, "table01_summary_statistics", decimals=2)
    print("Saved table: table01_summary_statistics")


def main():
    set_chart_style()
    growth_all = read_table("growth_all")
    macro = read_table("macro")
    trade_weights = read_table("trade_weights")
    remit_weights = read_table("remittance_weights")
    indices = read_table("partner_indices")

    chart_growth_peers(growth_all)
    chart_trade_partners(trade_weights)
    chart_remittances(macro, remit_weights)
    chart_debt_creditors(macro)
    chart_partner_indices(growth_all, indices)
    chart_ruble_shock(growth_all, macro)
    chart_forecast_revisions(growth_all)
    summary_statistics(macro)


if __name__ == "__main__":
    main()
