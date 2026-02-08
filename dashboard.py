import streamlit as st
import plotly.express as px
import pandas as pd
import analysis
import sys

# --- PAGE CONFIG ---
st.set_page_config(page_title="GPU Market Analyzer", layout="wide")
st.title("GPU Market Analysis Dashboard")

# --- LOAD DATA ---
@st.cache_data
def load_data():
    df = analysis.get_analyzed_df()
    
    # Load raw DB just to get the total count
    conn = analysis.sqlite3.connect("gpus.db")
    total_count = pd.read_sql_query("SELECT count(*) from gpus", conn).iloc[0,0]
    conn.close()
    
    return df, total_count

df, total_db_count = load_data()

# --- CONFIGURATION ---
TIER_ORDER = ["Low", "Low-Mid", "High-Mid", "High", "Ultra-High", "Ultra"] 

# --- TOP METRICS & ABOUT ---
with st.expander("About & Metrics", expanded=False):
    col1, col2 = st.columns(2)
    col1.metric("Total GPUs in DB", total_db_count)
    col2.metric("Analyzed GPUs", len(df))
    
    st.markdown("---")
    st.markdown("##### Methodology")
    st.caption("**Tiers:** K-Means clustering (5 tiers) based on relative performance.")
    st.caption("**FPS:** Estimated FPS using TechPowerUp relative scale against RTX 4060 Mobile (Most used GPU on Steam) benchmarks.")
    st.caption("**Active Price:** Prioritizes eBay average (recent sold), then Amazon, then MSRP.")

# --- MAIN TABS ---
tab_compare, tab_value, tab_scatter = st.tabs([
    "Head-to-Head", 
    "Best Value", 
    "Price vs Performance"
])

# =========================================================
# TAB 1: HEAD-TO-HEAD COMPARATOR
# =========================================================
with tab_compare:
    st.subheader("Head-to-Head Comparison")
    
    # Toggle View
    is_mobile_view = st.toggle("Mobile / Compact View", value=True)
    
    sorted_names = df.sort_values("rel_performance", ascending=False)['name'].unique()
    
    compare_list = st.multiselect(
        "Select GPUs (1st is Baseline)", 
        options=sorted_names,
        default=sorted_names[:2] if len(sorted_names) >= 2 else sorted_names,
        max_selections=5
    )

    if compare_list:
        comp_df = df[df['name'].isin(compare_list)].set_index('name')
        comp_df = comp_df.reindex(compare_list)
        
        baseline_name = compare_list[0]
        baseline_row = comp_df.loc[baseline_name]

        # --- MOBILE / COMPACT CARD VIEW ---
        if is_mobile_view:
            st.caption(f"Baseline: **{baseline_name}**")
            
            for gpu_name in compare_list:
                row = comp_df.loc[gpu_name]
                
                # Render Ultra-Compact Card
                with st.container(border=True):
                    
                    # --- ROW 1: Header (Name vs Price) ---
                    # Use columns to align Price to the right
                    c_name, c_price = st.columns([0.65, 0.35])
                    
                    with c_name:
                        st.markdown(f"**{gpu_name}**")
                        st.caption(f"{row['tier']}")
                        
                    with c_price:
                        # Price Calculation & HTML Formatting for Right Alignment
                        price_val = row['active_price']
                        price_str = f"${price_val:.0f}"
                        
                        if gpu_name != baseline_name and baseline_row['active_price'] > 0:
                            diff = ((price_val - baseline_row['active_price']) / baseline_row['active_price']) * 100
                            # Price: Higher is Red (Bad), Lower is Green (Good)
                            color = "red" if diff > 0 else "green"
                            sign = "+" if diff > 0 else ""
                            # Using HTML for tight stacking and right alignment
                            st.markdown(
                                f"""<div style='text-align: right; line-height: 1.2;'>
                                <b>{price_str}</b><br>
                                <span style='color:{color}; font-size: 0.85em; font-weight: bold;'>{sign}{diff:.1f}%</span>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(f"<div style='text-align: right'><b>{price_str}</b></div>", unsafe_allow_html=True)

                    # --- ROW 2: Compact FPS Stats ---
                    # Helper to create colored Markdown segments
                    def get_fps_md(col_name, label):
                        val = row[col_name]
                        if gpu_name == baseline_name or baseline_row[col_name] == 0:
                            return f"**{label}:** {val:.0f}"
                        
                        base = baseline_row[col_name]
                        diff = ((val - base) / base) * 100
                        # FPS: Higher is Green (Good), Lower is Red (Bad)
                        color = "green" if diff > 0 else "red"
                        sign = "+" if diff > 0 else ""
                        # Streamlit Markdown Color Syntax: :color[text]
                        return f"**{label}:** {val:.0f} (:{color}[{sign}{diff:.0f}%])"

                    fps_1080 = get_fps_md("1080p Ultra", "1080p")
                    fps_1440 = get_fps_md("1440p Ultra", "1440p")
                    fps_4k = get_fps_md("4K Ultra", "4K")
                    
                    # Display all FPS in one line
                    st.markdown(f"{fps_1080} &nbsp;|&nbsp; {fps_1440} &nbsp;|&nbsp; {fps_4k}")

        # --- DESKTOP VIEW ---
        else:
            cols = st.columns(len(compare_list))
            for i, gpu_name in enumerate(compare_list):
                row = comp_df.loc[gpu_name]
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(f"#### {gpu_name}")
                        st.write(f"**Tier:** {row['tier']}")
                        
                        # Price Metric
                        p_delta = None
                        if i > 0 and baseline_row['active_price'] > 0:
                            diff = ((row['active_price'] - baseline_row['active_price'])/baseline_row['active_price'])*100
                            p_delta = f"{diff:.1f}%"
                        
                        st.metric("Price", f"${row['active_price']:.0f}", delta=p_delta, delta_color="inverse")
                        
                        st.divider()
                        
                        # FPS Metrics
                        def calc_delta(curr, base):
                            if base == 0: return None
                            return f"{((curr-base)/base)*100:.1f}%"

                        st.metric("1080p Ultra", f"{row['1080p Ultra']:.0f}", delta=None if i==0 else calc_delta(row['1080p Ultra'], baseline_row['1080p Ultra']))
                        st.metric("4K Ultra", f"{row['4K Ultra']:.0f}", delta=None if i==0 else calc_delta(row['4K Ultra'], baseline_row['4K Ultra']))

    else:
        st.info("Select GPUs above to compare.")

# =========================================================
# TAB 2: TARGET RESOLUTION & VALUE FINDER
# =========================================================
with tab_value:
    st.subheader("Find the Best Value for Your Target")

    c1, c2 = st.columns([1, 2])

    with c1:
        st.markdown("#### Define Your Goal")
        target_res = st.selectbox("Target Resolution", ["1080p", "1440p", "4K"])
        
        target_fps = st.number_input(
            "Target FPS (Minimum)", 
            min_value=10, 
            max_value=500, 
            value=60, 
            step=5
        )
        
        res_col_map = {
            "1080p": "1080p Ultra",
            "1440p": "1440p Ultra",
            "4K": "4K Ultra"
        }
        target_col = res_col_map[target_res]

    with c2:
        st.markdown(f"#### Top 5 Best Value Cards for {target_res} @ {target_fps}+ FPS")
        
        candidates = df[df[target_col] >= target_fps].copy()
        
        if not candidates.empty:
            candidates['Cost Per Frame'] = candidates['active_price'] / candidates[target_col]
            top_picks = candidates.sort_values("Cost Per Frame", ascending=True).head(5)
            
            display_cols = ['name', 'active_price', target_col, 'Cost Per Frame', 'tier']
            
            st.dataframe(
                top_picks[display_cols].style.format({
                    "active_price": "${:.0f}",
                    target_col: "{:.0f} FPS",
                    "Cost Per Frame": "${:.2f}"
                }),
                width="stretch",
                hide_index=True
            )
        else:
            st.error(f"No GPUs found that can hit {target_fps} FPS at {target_res}. Try lowering your target.")

# =========================================================
# TAB 3: MARKET SCATTER PLOT
# =========================================================
with tab_scatter:
    st.subheader("The Big Picture: Price vs. Performance")
    
    col_filter, col_search = st.columns(2)
    
    with col_filter:
        valid_tiers = [t for t in df['tier'].unique() if t]
        selected_tiers = st.multiselect(
            "Filter by Tier", 
            options=valid_tiers, 
            default=valid_tiers
        )

    with col_search:
        search_options = sorted(df['name'].unique().tolist())
        highlight_gpus = st.multiselect("🔍 Highlight Specific GPUs", options=search_options)

    # Apply Filter
    df_filtered = df[df['tier'].isin(selected_tiers)].copy()

    # --- PLOTTING ---
    if highlight_gpus:
        df_filtered['color_group'] = df_filtered['name'].apply(
            lambda x: "Selected" if x in highlight_gpus else "Others"
        )
        df_filtered = df_filtered.sort_values('color_group', ascending=True) 
        
        color_map = {"Selected": "#FF4B4B", "Others": "grey"}
        
        fig = px.scatter(
            df_filtered,
            x="active_price",
            y="rel_performance",
            color="color_group",
            color_discrete_map=color_map,
            size="rel_performance",
            hover_name="name",
            hover_data=["1080p Ultra", "4K Ultra", "active_price"],
            height=600,
            template="plotly_dark",
            opacity=0.8
        )
        fig.for_each_trace(
            lambda trace: trace.update(opacity=0.3) if trace.name == "Others" else trace.update(opacity=1.0, marker=dict(size=15, line=dict(width=2, color='white')))
        )
        fig.update_layout(showlegend=False)

    else:
        fig = px.scatter(
            df_filtered,
            x="active_price",
            y="rel_performance",
            color="tier",
            size="rel_performance",
            hover_name="name",
            hover_data=["1080p Ultra", "4K Ultra", "active_price"],
            height=600,
            template="plotly_dark",
            category_orders={"tier": TIER_ORDER}
        )

    fig.update_layout(
        title="Market Efficiency Frontier",
        xaxis_title="Price ($)",
        yaxis_title="Relative Performance (%)",
        legend_title_text="Performance Tier"
    )

    st.plotly_chart(fig, width="stretch")

    with st.expander("View Filtered Raw Data"):
        st.dataframe(df_filtered)