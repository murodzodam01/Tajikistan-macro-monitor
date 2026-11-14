"""Step 3: partner weights and partner growth indices.

For each panel country (TJK, KGZ, UZB, KAZ) this script builds:

1. Trade weights: partner p's share of the country's total goods trade
   (exports + imports CIF) in year t, using the IMF world total as the
   denominator.

2. Remittance weights: an estimate of the share of remittances coming
   from each destination country, rebuilt with the World Bank / KNOMAD
   method (Ratha and Shaw 2007) as documented by Huckstep and Clemens
   (CGD, October 2026):
       score_ij  = Y_i                        if Y_j <  Y_i
                 = Y_i + (Y_j - Y_i) ** 0.75  if Y_j >= Y_i
       weight_ij = score_ij * M_ij / sum over j of (score_ij * M_ij)
   where i is the origin (remittance-receiving) country, j a destination
   country, M_ij the UN migrant stock of people born in i living in j, and
   Y the GNI per capita in PPP terms. Migrant stocks are interpolated
   linearly between UN years and held at the 2024 level afterwards.
   These are MODEL ESTIMATES, not observed bilateral flows.

3. Two partner growth indices per country and year: the trade-weighted
   and the remittance-weighted average of partners' real GDP growth
   (IMF WEO October 2026, history and projections). Weights of year t-1
   are used for year t.
"""

import numpy as np
import pandas as pd

from common import (LAST_ACTUAL_YEAR, PANEL_COUNTRIES,
                    compute_partner_index, read_table, save_processed)

INCOME_EXPONENT = 0.75          # fixed by the KNOMAD method
INCOME_FALLBACK_YEARS = 2       # use income up to 2 years old if missing
FIRST_YEAR = 1993
LAST_YEAR = 2031                # last year of WEO projections


def trade_weights(trade):
    """Partner shares of total trade (exports + imports CIF)."""
    totals = (trade.groupby(["reporter", "partner", "year"])["value_usd"]
              .sum(min_count=1).reset_index())
    world = totals[totals["partner"] == "WLD"][["reporter", "year",
                                                "value_usd"]]
    world = world.rename(columns={"value_usd": "world_total"})
    partners = totals[totals["partner"] != "WLD"]
    partners = partners[partners["partner"] != partners["reporter"]]
    partners = partners.merge(world, on=["reporter", "year"], how="inner")
    partners["weight"] = partners["value_usd"] / partners["world_total"]
    partners = partners.dropna(subset=["weight"])
    partners = partners[partners["weight"] > 0]

    # Check: shares of identified partners should add up to about 1.
    sums = partners.groupby(["reporter", "year"])["weight"].sum()
    assert (sums < 1.10).all(), "Trade shares add up to more than 110%"
    return partners[["reporter", "partner", "year", "weight",
                     "value_usd"]]


def interpolate_stocks(migrants):
    """Annual migrant stocks: linear between UN years, flat after 2024."""
    mapped = migrants.dropna(subset=["destination"])
    mapped = mapped[mapped["destination"] != mapped["origin"]]
    wide = mapped.pivot_table(index=["origin", "destination"],
                              columns="year", values="stock",
                              aggfunc="sum")
    all_years = list(range(wide.columns.min(), LAST_ACTUAL_YEAR + 1))
    wide = wide.reindex(columns=all_years)
    wide = wide.interpolate(axis=1, limit_area="inside")
    wide = wide.ffill(axis=1)   # hold the 2024 value for 2025
    stocks = wide.stack().reset_index()
    stocks.columns = ["origin", "destination", "year", "stock"]
    return stocks


def income_table(gni):
    """GNI per capita (PPP) by country and year, gaps filled up to 2 years.

    Only past values are carried forward (never future ones), as in the
    KNOMAD method.
    """
    wide = gni.pivot_table(index="country", columns="year", values="value")
    all_years = list(range(wide.columns.min(), LAST_ACTUAL_YEAR + 1))
    wide = wide.reindex(columns=all_years)
    filled = wide.ffill(axis=1, limit=INCOME_FALLBACK_YEARS)
    income = filled.stack().reset_index()
    income.columns = ["country", "year", "income"]
    return income


def remittance_weights(migrants, gni):
    """Rebuilt KNOMAD-style remittance shares by destination and year."""
    stocks = interpolate_stocks(migrants)
    income = income_table(gni)

    origin_income = income.rename(columns={"country": "origin",
                                           "income": "income_origin"})
    host_income = income.rename(columns={"country": "destination",
                                         "income": "income_host"})
    table = stocks.merge(origin_income, on=["origin", "year"], how="left")
    table = table.merge(host_income, on=["destination", "year"], how="left")

    # Income score. A host without income data gets the origin's income
    # (no bonus), as in the method. If the origin's own income is missing,
    # the score is set to 1, so weights follow migrant stocks only.
    score = table["income_origin"].copy()
    richer_host = table["income_host"] >= table["income_origin"]
    gap = table.loc[richer_host, "income_host"] - table.loc[
        richer_host, "income_origin"]
    score[richer_host] = (table.loc[richer_host, "income_origin"]
                          + gap ** INCOME_EXPONENT)
    stock_only = table["income_origin"].isna()
    score[stock_only] = 1.0
    table["score"] = score
    table["stock_only"] = stock_only

    table["raw_weight"] = table["score"] * table["stock"]
    totals = table.groupby(["origin", "year"])["raw_weight"].transform("sum")
    table["weight"] = table["raw_weight"] / totals
    table = table.dropna(subset=["weight"])
    table = table[table["weight"] > 0]

    sums = table.groupby(["origin", "year"])["weight"].sum()
    assert np.allclose(sums, 1.0), "Remittance weights do not sum to 1"
    return table.rename(columns={"origin": "reporter",
                                 "destination": "partner"})


def bilateral_remittances_usd(weights, macro):
    """Estimated remittances by sending country, in US$ (model estimate)."""
    totals = macro[macro["variable"] == "remittances_usd"][
        ["country", "year", "value"]]
    totals = totals.rename(columns={"country": "reporter",
                                    "value": "remittances_usd"})
    table = weights.merge(totals, on=["reporter", "year"], how="inner")
    table["estimated_usd"] = table["weight"] * table["remittances_usd"]
    return table[["reporter", "partner", "year", "weight",
                  "estimated_usd"]]


def build_indices(trade_w, remit_w, growth):
    """Trade- and remittance-weighted partner growth for each country."""
    years = list(range(FIRST_YEAR, LAST_YEAR + 1))
    frames = []
    for reporter in PANEL_COUNTRIES:
        t_weights = trade_w[trade_w["reporter"] == reporter]
        r_weights = remit_w[remit_w["reporter"] == reporter]
        trade_index = compute_partner_index(t_weights, growth, reporter,
                                            years)
        remit_index = compute_partner_index(r_weights, growth, reporter,
                                            years)
        trade_index = trade_index.rename(columns={
            "index": "trade_index", "coverage": "trade_coverage",
            "weight_year": "trade_weight_year"})
        remit_index = remit_index.rename(columns={
            "index": "remit_index", "coverage": "remit_coverage",
            "weight_year": "remit_weight_year"})
        both = trade_index.merge(remit_index, on=["reporter", "year"],
                                 how="outer")
        frames.append(both)
    indices = pd.concat(frames, ignore_index=True)
    indices["is_projection"] = indices["year"] > LAST_ACTUAL_YEAR
    return indices


def report_weights(trade_w, remit_w, indices):
    """Print a short summary so problems are visible in the console."""
    for reporter in PANEL_COUNTRIES:
        print()
        print(reporter)
        for year in [2000, 2010, 2020, LAST_ACTUAL_YEAR]:
            t_rows = trade_w[(trade_w["reporter"] == reporter)
                             & (trade_w["year"] == year)]
            r_rows = remit_w[(remit_w["reporter"] == reporter)
                             & (remit_w["year"] == year)]
            top_trade = t_rows.sort_values("weight", ascending=False).head(3)
            top_remit = r_rows.sort_values("weight", ascending=False).head(2)
            trade_text = ", ".join(
                top_trade["partner"] + " "
                + (100 * top_trade["weight"]).round(1).astype(str) + "%")
            remit_text = ", ".join(
                top_remit["partner"] + " "
                + (100 * top_remit["weight"]).round(1).astype(str) + "%")
            print("  ", year, "| top trade:", trade_text,
                  "| top remittance sources:", remit_text)
        low = indices[(indices["reporter"] == reporter)
                      & (indices["trade_coverage"] < 0.8)]
        if len(low) > 0:
            print("   WARNING: trade index coverage below 80% in years:",
                  list(low["year"]))


def main():
    trade = read_table("trade")
    migrants = read_table("migrant_stock")
    gni = read_table("gni_ppp")
    macro = read_table("macro")
    growth_all = read_table("growth_all")

    growth = growth_all[growth_all["vintage"] == "2026-10"]
    growth = growth.rename(columns={"country": "partner"})

    trade_w = trade_weights(trade)
    remit_w = remittance_weights(migrants, gni)
    remit_usd = bilateral_remittances_usd(remit_w, macro)
    indices = build_indices(trade_w, remit_w, growth)

    n_stock_only = int(remit_w["stock_only"].sum())
    print("Remittance weight rows without origin income (stock-only):",
          n_stock_only)
    report_weights(trade_w, remit_w, indices)

    print()
    save_processed(trade_w, "trade_weights")
    save_processed(remit_w, "remittance_weights")
    save_processed(remit_usd, "remittances_by_source")
    save_processed(indices, "partner_indices")


if __name__ == "__main__":
    main()
