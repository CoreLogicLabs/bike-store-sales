"""
Global Bike Retailer — Profitability & Customer Analytics
Interactive Streamlit dashboard.

Runs on the exact same `src/data_prep.py` pipeline as the notebook, so every
number here is consistent with the notebook and README. Sidebar filters
recompute all KPIs and charts on the *filtered* slice.

Launch:  streamlit run app/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# --- make src importable ----------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import data_prep as dp          # noqa: E402
import viz                      # noqa: E402

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ISO-3 codes for the 6 markets (robust choropleth mapping)
ISO3 = {
    "United States": "USA", "Australia": "AUS", "Canada": "CAN",
    "United Kingdom": "GBR", "Germany": "DEU", "France": "FRA",
}

# ============================================================================ #
# Page config & light styling
# ============================================================================ #
st.set_page_config(
    page_title="Bike Retailer Analytics",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 2rem;}
      [data-testid="stMetricValue"] {font-size: 1.5rem;}
      h1, h2, h3 {color: #22333B;}
    </style>
    """,
    unsafe_allow_html=True,
)

PLOTLY_TEMPLATE = "plotly_white"
CAT_MAP = viz.CATEGORY_COLORS


@st.cache_data(show_spinner="Loading & cleaning data…")
def get_data() -> pd.DataFrame:
    return dp.load_data()


df_all = get_data()

# ============================================================================ #
# Sidebar filters
# ============================================================================ #
st.sidebar.title("🚲 Bike Retailer Analytics")
st.sidebar.caption("Profitability & Customer Analytics")

countries = sorted(df_all["Country"].unique())
categories = ["Bikes", "Accessories", "Clothing"]
genders = sorted(df_all["Customer_Gender"].unique())
age_groups = [a for a in dp.AGE_GROUP_ORDER if a in df_all["Age_Group"].unique()]

sel_country = st.sidebar.multiselect("Country", countries, default=countries)
sel_cat = st.sidebar.multiselect("Product category", categories, default=categories)
sel_gender = st.sidebar.multiselect("Gender", genders, default=genders)
sel_age = st.sidebar.multiselect("Age group", age_groups, default=age_groups)

mask = (
    df_all["Country"].isin(sel_country)
    & df_all["Product_Category"].isin(sel_cat)
    & df_all["Customer_Gender"].isin(sel_gender)
    & df_all["Age_Group"].isin(sel_age)
)
df = df_all[mask].copy()

st.sidebar.markdown("---")
st.sidebar.metric("Rows in view", f"{len(df):,}", f"{len(df)/len(df_all):.0%} of dataset")
st.sidebar.caption(
    "Data: synthetic AdventureWorks-lineage extract (113k rows, 2011–2016). "
    "Time is templated → no YoY trends; see the **Data Quality** tab."
)

if df.empty:
    st.warning("No rows match the current filters. Widen your selection in the sidebar.")
    st.stop()

# ============================================================================ #
# Header + KPI cards
# ============================================================================ #
st.title("Global Bike Retailer — Profitability & Customer Analytics")
st.markdown(
    "**Revenue and profit don't come from the same place.** Bikes drive revenue; "
    "accessories drive margin. Use the sidebar to slice the book of business."
)

k = dp.kpi_summary(df)
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Revenue", viz.money_compact(k["total_revenue"]))
c2.metric("Profit", viz.money_compact(k["total_profit"]))
c3.metric("Gross margin", viz.pct(k["gross_margin_pct"]))
c4.metric("Orders", viz.num_compact(k["n_orders"]))
c5.metric("Avg order value", viz.money(k["avg_order_value"], 0))
c6.metric("Avg discount", viz.pct(k["avg_discount_pct"]))

st.markdown("")

tab_prof, tab_cust, tab_geo, tab_price, tab_season, tab_quality = st.tabs(
    ["📊 Profitability", "👥 Customers", "🌍 Geography",
     "💸 Pricing & Discount", "📅 Seasonality", "🔎 Data Quality"]
)

# ============================================================================ #
# TAB 1 — Profitability
# ============================================================================ #
with tab_prof:
    econ = dp.category_economics(df)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Revenue vs profit by category")
        e = econ.reset_index()
        fig = go.Figure()
        fig.add_bar(x=e["Product_Category"], y=e["Revenue"], name="Revenue",
                    marker_color=[CAT_MAP[c] for c in e["Product_Category"]],
                    text=[viz.money_compact(v) for v in e["Revenue"]], textposition="outside")
        fig.add_bar(x=e["Product_Category"], y=e["Profit"], name="Profit",
                    marker_color=[CAT_MAP[c] for c in e["Product_Category"]],
                    marker_pattern_shape="/", opacity=0.55,
                    text=[viz.money_compact(v) for v in e["Profit"]], textposition="outside")
        fig.update_layout(template=PLOTLY_TEMPLATE, barmode="group", height=420,
                          yaxis_title="USD", legend_title="", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.subheader("Margin % by category")
        e = econ.reset_index()
        fig = px.bar(e, x="Product_Category", y="Margin_%",
                     color="Product_Category", color_discrete_map=CAT_MAP,
                     text=e["Margin_%"].round(1).astype(str) + "%")
        fig.update_traces(textposition="outside")
        fig.update_layout(template=PLOTLY_TEMPLATE, height=420, showlegend=False,
                          yaxis_title="Gross margin %", xaxis_title="", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Volume vs margin by sub-category  ·  bubble = revenue")
    sub = (df.groupby(["Product_Category", "Sub_Category"], observed=True)
             .agg(Revenue=("Revenue", "sum"), Profit=("Profit", "sum"),
                  Orders=("Revenue", "size")).reset_index())
    sub["Margin_%"] = sub["Profit"] / sub["Revenue"] * 100
    sub["Avg_Order_Value"] = sub["Revenue"] / sub["Orders"]
    fig = px.scatter(sub, x="Avg_Order_Value", y="Margin_%", size="Revenue",
                     color="Product_Category", color_discrete_map=CAT_MAP,
                     hover_name="Sub_Category", log_x=True, size_max=60,
                     labels={"Avg_Order_Value": "Average order value (USD, log)",
                             "Margin_%": "Gross margin %"})
    fig.update_layout(template=PLOTLY_TEMPLATE, height=480, legend_title="Category")
    st.plotly_chart(fig, width="stretch")

    with st.expander("Category economics table"):
        st.dataframe(
            econ.style.format({
                "Revenue": "${:,.0f}", "Profit": "${:,.0f}", "Margin_%": "{:.1f}%",
                "Revenue_Share_%": "{:.1f}%", "Profit_Share_%": "{:.1f}%",
                "Avg_Order_Value": "${:,.0f}", "Orders": "{:,.0f}", "Units": "{:,.0f}",
            }),
            width="stretch",
        )

    st.subheader("Profit concentration — top 15 products")
    top = (df.groupby(["Product_Category", "Product"])
             .agg(Profit=("Profit", "sum"), Revenue=("Revenue", "sum"))
             .sort_values("Profit", ascending=False).head(15).reset_index())
    fig = px.bar(top[::-1], x="Profit", y="Product", orientation="h",
                 color="Product_Category", color_discrete_map=CAT_MAP,
                 hover_data={"Revenue": ":,.0f"})
    fig.update_layout(template=PLOTLY_TEMPLATE, height=520, legend_title="Category",
                      xaxis_title="Profit (USD)", yaxis_title="")
    st.plotly_chart(fig, width="stretch")

# ============================================================================ #
# TAB 2 — Customers
# ============================================================================ #
with tab_cust:
    st.info("No customer id exists in this dataset → demographics are **transaction-level** "
            "(attributes of purchases). RFM / CLV / cohort analysis is not possible.", icon="ℹ️")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Revenue & margin by age group")
        ag = (df.groupby("Age_Group", observed=True)
                .agg(Revenue=("Revenue", "sum"), Profit=("Profit", "sum")).reset_index())
        ag["Margin_%"] = ag["Profit"] / ag["Revenue"] * 100
        fig = go.Figure()
        fig.add_bar(x=ag["Age_Group"].astype(str), y=ag["Revenue"],
                    marker_color=viz.ACCENT, name="Revenue",
                    text=[viz.money_compact(v) for v in ag["Revenue"]], textposition="outside")
        fig.add_scatter(x=ag["Age_Group"].astype(str), y=ag["Margin_%"], yaxis="y2",
                        mode="lines+markers", name="Margin %", line=dict(color=viz.ACCENT_2, width=3))
        fig.update_layout(template=PLOTLY_TEMPLATE, height=430,
                          yaxis_title="Revenue (USD)",
                          yaxis2=dict(title="Margin %", overlaying="y", side="right",
                                      range=[0, 70], showgrid=False),
                          legend=dict(orientation="h"), margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.subheader("Category mix by gender")
        gd = (df.groupby(["Customer_Gender", "Product_Category"], observed=True)["Revenue"]
                .sum().reset_index())
        tot = gd.groupby("Customer_Gender")["Revenue"].transform("sum")
        gd["Share_%"] = gd["Revenue"] / tot * 100
        fig = px.bar(gd, x="Customer_Gender", y="Share_%", color="Product_Category",
                     color_discrete_map=CAT_MAP, text=gd["Share_%"].round(0).astype(int).astype(str) + "%")
        fig.update_layout(template=PLOTLY_TEMPLATE, height=430, barmode="stack",
                          yaxis_title="% of gender's revenue", xaxis_title="", legend_title="Category",
                          margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Customer age distribution by category")
    fig = px.histogram(df, x="Customer_Age", color="Product_Category", nbins=40,
                       color_discrete_map=CAT_MAP, opacity=0.8)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=400, barmode="overlay",
                      xaxis_title="Customer age", yaxis_title="Orders", legend_title="Category")
    st.plotly_chart(fig, width="stretch")

# ============================================================================ #
# TAB 3 — Geography
# ============================================================================ #
with tab_geo:
    ctry = (df.groupby("Country")
              .agg(Revenue=("Revenue", "sum"), Profit=("Profit", "sum"),
                   Orders=("Revenue", "size")).reset_index())
    ctry["Margin_%"] = ctry["Profit"] / ctry["Revenue"] * 100
    ctry["ISO3"] = ctry["Country"].map(ISO3)

    metric = st.radio("Colour the map by", ["Revenue", "Margin_%"], horizontal=True)
    fig = px.choropleth(ctry, locations="ISO3", locationmode="ISO-3",
                        color=metric, color_continuous_scale="Blues", hover_name="Country",
                        hover_data={"ISO3": False, "Revenue": ":,.0f", "Margin_%": ":.1f"})
    fig.update_layout(template=PLOTLY_TEMPLATE, height=460,
                      geo=dict(showframe=False, projection_type="natural earth"),
                      margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Revenue by country")
        cc = ctry.sort_values("Revenue")
        fig = px.bar(cc, x="Revenue", y="Country", orientation="h",
                     text=[viz.money_compact(v) for v in cc["Revenue"]])
        fig.update_traces(marker_color=viz.ACCENT, textposition="outside")
        fig.update_layout(template=PLOTLY_TEMPLATE, height=380, xaxis_title="Revenue (USD)",
                          yaxis_title="", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
    with col2:
        st.subheader("Margin % by country")
        cc = ctry.sort_values("Margin_%")
        fig = px.bar(cc, x="Margin_%", y="Country", orientation="h",
                     text=cc["Margin_%"].round(1).astype(str) + "%")
        fig.update_traces(marker_color=viz.ACCENT_2, textposition="outside")
        fig.update_layout(template=PLOTLY_TEMPLATE, height=380, xaxis_title="Gross margin %",
                          yaxis_title="", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Top 15 states / regions by revenue")
    st_df = (df.groupby(["Country", "State"])["Revenue"].sum()
               .sort_values(ascending=False).head(15).reset_index())
    st_df["Label"] = st_df["State"] + " (" + st_df["Country"] + ")"
    fig = px.bar(st_df[::-1], x="Revenue", y="Label", orientation="h")
    fig.update_traces(marker_color=viz.ACCENT)
    fig.update_layout(template=PLOTLY_TEMPLATE, height=480, xaxis_title="Revenue (USD)",
                      yaxis_title="", margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")

# ============================================================================ #
# TAB 4 — Pricing & Discount
# ============================================================================ #
with tab_price:
    st.markdown(
        "`Unit_Price` is a **list price**; booked `Revenue` is always ≤ list value. "
        "The gap is an **implied discount**. Question: are we cutting price hardest on "
        "the products we can least afford to?"
    )
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Distribution of implied discount")
        fig = px.histogram(df, x=df["Discount_Pct"] * 100, nbins=40)
        fig.update_traces(marker_color=viz.ACCENT)
        fig.add_vline(x=df["Discount_Pct"].mean() * 100, line_color=viz.ACCENT_2,
                      annotation_text=f"mean {df['Discount_Pct'].mean()*100:.1f}%")
        fig.update_layout(template=PLOTLY_TEMPLATE, height=420,
                          xaxis_title="Discount vs list (%)", yaxis_title="Orders", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
    with col2:
        st.subheader("Discount depth vs margin")
        sd = (df.groupby(["Product_Category", "Sub_Category"], observed=True)
                .agg(Discount=("Discount_Pct", "mean"), Margin=("Profit_Margin", "mean"),
                     Revenue=("Revenue", "sum")).reset_index())
        sd["Discount"] *= 100
        sd["Margin"] *= 100
        fig = px.scatter(sd, x="Discount", y="Margin", size="Revenue",
                         color="Product_Category", color_discrete_map=CAT_MAP,
                         hover_name="Sub_Category", size_max=55,
                         labels={"Discount": "Avg discount vs list (%)", "Margin": "Avg gross margin (%)"})
        fig.update_layout(template=PLOTLY_TEMPLATE, height=420, legend_title="Category")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Average discount by category")
    dc = (df.groupby("Product_Category")["Discount_Pct"].mean() * 100).reset_index()
    fig = px.bar(dc, x="Product_Category", y="Discount_Pct", color="Product_Category",
                 color_discrete_map=CAT_MAP, text=dc["Discount_Pct"].round(2).astype(str) + "%")
    fig.update_traces(textposition="outside")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=380, showlegend=False,
                      yaxis_title="Avg discount vs list (%)", xaxis_title="", margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")

# ============================================================================ #
# TAB 5 — Seasonality
# ============================================================================ #
with tab_season:
    st.warning(
        "The calendar is **templated** and 2014/2016 truncate at July → no year-over-year "
        "trends. Below is a **month-of-year shape** averaged across only the years each month "
        "is populated (truncation-bias corrected). Treat as indicative.",
        icon="⚠️",
    )
    my = df.groupby(["Year", "Month_Num"])["Revenue"].sum().reset_index()
    season = my.groupby("Month_Num")["Revenue"].mean().reindex(range(1, 13))
    s = pd.DataFrame({"Month": MONTH_ABBR, "Revenue": season.values})
    fig = px.area(s, x="Month", y="Revenue", markers=True)
    fig.update_traces(line_color=viz.ACCENT, fillcolor="rgba(46,134,171,0.12)")
    fig.update_layout(template=PLOTLY_TEMPLATE, height=420,
                      yaxis_title="Avg revenue per populated year (USD)", margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Category mix by month (% of month revenue)")
    mc = (df.groupby(["Month_Num", "Product_Category"], observed=True)["Revenue"]
            .sum().unstack().reindex(range(1, 13)))
    mc_share = mc.div(mc.sum(axis=1), axis=0) * 100
    mc_share.index = MONTH_ABBR
    fig = px.imshow(mc_share, text_auto=".0f", color_continuous_scale="Blues",
                    aspect="auto", labels=dict(color="% of month"))
    fig.update_layout(template=PLOTLY_TEMPLATE, height=420, xaxis_title="", yaxis_title="",
                      margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")

# ============================================================================ #
# TAB 6 — Data Quality (forensics)
# ============================================================================ #
with tab_quality:
    st.subheader("Why this dataset's time axis can't be trusted")
    st.markdown(
        "A forensic audit of the **raw** file (full dataset, ignores sidebar filters) shows the "
        "calendar is synthetically templated. This is documented openly rather than hidden."
    )
    raw = dp.load_raw()
    report = dp.audit(raw)

    rc = (raw.assign(_m=pd.to_datetime(raw["Date"]).dt.month)
             .pivot_table(index="Year", columns="_m", values="Revenue",
                          aggfunc="size", fill_value=0).sort_index())
    rc.columns = [MONTH_ABBR[m - 1] for m in rc.columns]
    fig = px.imshow(rc, text_auto="d", color_continuous_scale="Reds", aspect="auto",
                    labels=dict(color="orders", x="", y="Year"))
    fig.update_layout(template=PLOTLY_TEMPLATE, height=380, margin=dict(t=10),
                      title="Orders by year × month — note: 2014 & 2016 stop in July; "
                            "2013≡2015, 2014≡2016, 2011≡2012")
    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Accounting identities (raw data)**")
        st.markdown(
            f"- `Revenue = Cost + Profit` → **{report['identity_revenue_eq_cost_plus_profit']:.0%}** of rows ✅\n"
            f"- `Cost = Unit_Cost × Qty` → **{report['identity_cost_eq_unitcost_x_qty']:.0%}** of rows ✅\n"
            f"- `Revenue = Unit_Price × Qty` → **{report['identity_revenue_eq_listprice_x_qty']:.1%}** "
            "(the rest is the implied discount)"
        )
    with col2:
        st.markdown("**Cleaning actions**")
        st.markdown(
            f"- Dropped **{report['exact_duplicate_rows']:,}** exact duplicate rows (injected artifact)\n"
            "- `Date` kept as single source of truth\n"
            "- Relabelled `Seniors (64+)` → `Seniors (65+)`\n"
            "- Scoped out YoY trends (templated calendar)"
        )

    st.markdown("**Twin-year fingerprint** (identical monthly order-count vectors):")
    st.json(report["templated_year_twins"])
    st.caption("Real businesses do not produce byte-identical monthly volumes two years apart.")

# ============================================================================ #
# Footer
# ============================================================================ #
st.markdown("---")
st.caption(
    "Built with Streamlit · all figures computed from `src/data_prep.py` (identical to the "
    "notebook & README) · synthetic dataset, findings demonstrate method, not real trading results."
)
