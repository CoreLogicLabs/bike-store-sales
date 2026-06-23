"""
data_prep.py
============
Single source of truth for the Bike Store Sales analysis.

Every artifact in this project (Jupyter notebook, Streamlit app, README figures)
imports its numbers from here, so the headline KPIs are guaranteed to be identical
across deliverables.

Pipeline
--------
load_raw()      -> read the raw Kaggle CSV exactly as downloaded
audit()         -> data-quality report used by the notebook's "Data Forensics" section
clean()         -> drop injected duplicates, validate accounting identities
add_features()  -> engineer margin / discount / realized-price / calendar features
load_data()     -> convenience: raw -> clean -> features (the analysis-ready frame)
kpi_summary()   -> dict of executive KPIs computed on the clean frame

Design note on the time dimension
---------------------------------
Forensic checks (see `audit`) show the calendar is templated, not organic:
monthly row counts are identical for 2011==2012, 2013==2015 and 2014==2016, and
2014 & 2016 only contain January-July. Year-over-year *growth* is therefore an
artifact, not a business signal. We treat the data as a single cross-section
("book of business") and study seasonality only as a pooled month-of-year shape.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

# ----------------------------------------------------------------------------- #
# Paths
# ----------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "sales_data.csv"
CLEAN_CSV = PROJECT_ROOT / "data" / "sales_clean.csv"

MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Canonical ordering for the age buckets (data lives in 4 groups)
AGE_GROUP_ORDER = ["Youth (<25)", "Young Adults (25-34)", "Adults (35-64)", "Seniors (65+)"]


# ----------------------------------------------------------------------------- #
# Load
# ----------------------------------------------------------------------------- #
def load_raw(path: str | Path = RAW_CSV) -> pd.DataFrame:
    """Read the raw CSV exactly as downloaded from Kaggle (no transformations)."""
    return pd.read_csv(path)


# ----------------------------------------------------------------------------- #
# Audit  (powers the notebook's data-forensics narrative)
# ----------------------------------------------------------------------------- #
def audit(df: pd.DataFrame) -> dict:
    """Return a structured data-quality report on the *raw* frame.

    Nothing here mutates the data; it only measures it so the cleaning
    decisions downstream are evidence-based and reproducible.
    """
    d = df.copy()
    date = pd.to_datetime(d["Date"])

    # Accounting identities -------------------------------------------------- #
    id_rev = (d["Revenue"] == d["Cost"] + d["Profit"]).mean()
    id_cost = (d["Cost"] == d["Unit_Cost"] * d["Order_Quantity"]).mean()
    id_listprice = (d["Revenue"] == d["Unit_Price"] * d["Order_Quantity"]).mean()

    # Calendar redundancy ---------------------------------------------------- #
    cal_consistent = bool(
        (date.dt.day == d["Day"]).all()
        and (date.dt.year == d["Year"]).all()
        and (date.dt.strftime("%B") == d["Month"]).all()
    )

    # Templated-calendar fingerprint: monthly row-count vectors per year ----- #
    rc = (
        d.assign(_m=date.dt.month)
        .pivot_table(index="Year", columns="_m", values="Revenue", aggfunc="size", fill_value=0)
        .sort_index()
    )
    twins = {
        "2011_eq_2012": bool(rc.loc[2011].equals(rc.loc[2012])),
        "2013_eq_2015": bool(rc.loc[2013].equals(rc.loc[2015])),
        "2014_eq_2016": bool(rc.loc[2014].equals(rc.loc[2016])),
    }
    # Months actually populated per year (exposes the Jan-Jul truncation)
    months_per_year = {int(y): int((rc.loc[y] > 0).sum()) for y in rc.index}

    return {
        "n_rows": int(len(d)),
        "n_cols": int(d.shape[1]),
        "date_min": str(date.min().date()),
        "date_max": str(date.max().date()),
        "null_cells": int(d.isnull().sum().sum()),
        "exact_duplicate_rows": int(d.duplicated().sum()),
        "identity_revenue_eq_cost_plus_profit": round(float(id_rev), 4),
        "identity_cost_eq_unitcost_x_qty": round(float(id_cost), 4),
        "identity_revenue_eq_listprice_x_qty": round(float(id_listprice), 4),
        "calendar_columns_consistent": cal_consistent,
        "templated_year_twins": twins,
        "months_populated_per_year": months_per_year,
    }


# ----------------------------------------------------------------------------- #
# Clean
# ----------------------------------------------------------------------------- #
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the cleaning decisions justified by `audit`.

    1. Drop the exactly-1,000 byte-identical duplicate rows (an injected
       artifact: the count is suspiciously round and there is no order id that
       would make true repeat transactions distinguishable).
    2. Parse `Date` as the single source of truth for time.
    3. Normalise the "Seniors (64+)" label to "Seniors (65+)" so it matches the
       actual data (min age in that bucket is 65) and does not overlap the
       "Adults (35-64)" label cosmetically.
    """
    d = df.copy()
    d = d.drop_duplicates().reset_index(drop=True)
    d["Date"] = pd.to_datetime(d["Date"])
    d["Age_Group"] = d["Age_Group"].replace({"Seniors (64+)": "Seniors (65+)"})
    return d


# ----------------------------------------------------------------------------- #
# Feature engineering
# ----------------------------------------------------------------------------- #
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer the analytical features used across the project."""
    d = df.copy()

    # Profitability
    d["Profit_Margin"] = d["Profit"] / d["Revenue"]

    # Price realization / discounting:
    # Unit_Price behaves like a list (catalog) price; Revenue is what was booked.
    # Revenue is always <= list value, so the gap is an *implied discount*.
    d["List_Revenue"] = d["Unit_Price"] * d["Order_Quantity"]
    d["Discount_Amount"] = d["List_Revenue"] - d["Revenue"]
    d["Discount_Pct"] = d["Discount_Amount"] / d["List_Revenue"]
    d["Realized_Unit_Price"] = d["Revenue"] / d["Order_Quantity"]

    # Calendar features (Date is the source of truth)
    d["Month_Num"] = d["Date"].dt.month
    d["Month_Name"] = d["Date"].dt.strftime("%B")
    d["Weekday"] = d["Date"].dt.day_name()
    d["Quarter"] = d["Date"].dt.quarter

    # Ordered categoricals for clean plotting
    d["Month_Name"] = pd.Categorical(d["Month_Name"], categories=MONTH_ORDER, ordered=True)
    age_cats = [c for c in AGE_GROUP_ORDER if c in d["Age_Group"].unique()]
    d["Age_Group"] = pd.Categorical(d["Age_Group"], categories=age_cats, ordered=True)

    return d


def load_data(path: str | Path = RAW_CSV, save_clean: bool = False) -> pd.DataFrame:
    """raw -> clean -> features. The analysis-ready frame used everywhere."""
    d = add_features(clean(load_raw(path)))
    if save_clean:
        CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(CLEAN_CSV, index=False)
    return d


# ----------------------------------------------------------------------------- #
# KPI summary
# ----------------------------------------------------------------------------- #
def kpi_summary(df: pd.DataFrame) -> dict:
    """Executive KPIs computed on the analysis-ready frame."""
    revenue = float(df["Revenue"].sum())
    profit = float(df["Profit"].sum())
    cost = float(df["Cost"].sum())
    units = int(df["Order_Quantity"].sum())
    orders = int(len(df))
    return {
        "total_revenue": revenue,
        "total_profit": profit,
        "total_cost": cost,
        "gross_margin_pct": profit / revenue * 100,
        "n_orders": orders,
        "units_sold": units,
        "avg_order_value": revenue / orders,
        "avg_order_profit": profit / orders,
        "avg_units_per_order": units / orders,
        "avg_discount_pct": float(df["Discount_Pct"].mean()) * 100,
        "discount_dollars": float(df["Discount_Amount"].sum()),
        "n_countries": int(df["Country"].nunique()),
        "n_products": int(df["Product"].nunique()),
        "loss_making_orders": int((df["Profit"] < 0).sum()),
    }


def category_economics(df: pd.DataFrame) -> pd.DataFrame:
    """Volume-vs-margin table by product category (the analytical backbone)."""
    g = df.groupby("Product_Category", observed=True).agg(
        Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum"),
        Orders=("Revenue", "size"),
        Units=("Order_Quantity", "sum"),
    )
    g["Margin_%"] = g["Profit"] / g["Revenue"] * 100
    g["Revenue_Share_%"] = g["Revenue"] / g["Revenue"].sum() * 100
    g["Profit_Share_%"] = g["Profit"] / g["Profit"].sum() * 100
    g["Avg_Order_Value"] = g["Revenue"] / g["Orders"]
    return g.sort_values("Revenue", ascending=False)


if __name__ == "__main__":
    raw = load_raw()
    print("AUDIT (raw):")
    for k, v in audit(raw).items():
        print(f"  {k}: {v}")

    data = load_data(save_clean=True)
    print(f"\nClean frame: {data.shape[0]:,} rows x {data.shape[1]} cols")
    print(f"Saved -> {CLEAN_CSV}")

    print("\nKPI SUMMARY:")
    for k, v in kpi_summary(data).items():
        print(f"  {k}: {v:,.2f}" if isinstance(v, float) else f"  {k}: {v:,}")

    print("\nCATEGORY ECONOMICS:")
    print(category_economics(data).round(1))
