import streamlit as st
import plotly.express as px
import pandas as pd
import analysis  # Importing your logic file

# --- PAGE CONFIG ---
st.set_page_config(page_title="GPU Market Analyzer", layout="wide")
st.title("GPU Market Analysis Dashboard")

# --- LOAD DATA ---
@st.cache_data
def load_data():
    # Get the cleaned data from your analysis script
    df = analysis.get_analyzed_df()
    
    # Load raw DB just to get the total count (including unpriced cards)
    conn = analysis.sqlite3.connect("gpus.db")
    total_count = pd.read_sql_query("SELECT count(*) from gpus", conn).iloc[0,0]
    conn.close()
    
    return df, total_count

df, total_db_count = load_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Global Filters")
valid_tiers = [t for t in df['tier'].unique() if t]
selected_tiers = st.sidebar.multiselect("Performance Tier", options=valid_tiers, default=valid_tiers)

# Filter Dataframe based on sidebar
global_mask = df['tier'].isin(selected_tiers)
df_filtered = df[global_mask]

# --- TOP METRICS ---
col1, col2 = st.columns(2)
col1.metric("Total GPUs in DB", total_db_count)
col2.metric("Total GPUs Priced & Analyzed", len(df))



st.markdown("---")

# =========================================================
# ABOUT THE DASHBOARD
# =========================================================
st.subheader("About This Dashboard")

st.markdown("##### How were the GPU tiers created?")
st.text("I used a simple K-Means clustering algorithm that sorts the GPUs into 5 tiers (Low, Low-Mid, High-Mid, High, Ultra-High) based on the relative performance. " \
"I went with 5 tiers to ensure there was the sorting was fairly spread out and not clumping too many in the same tier.")

st.markdown("##### How was the FPS calculated?")
st.text("I found the most used GPU according to the 11/25 Steam Hardware Survey (The RTX 4060 Mobile) and used the relative performance scale on the TechPowerUp website to estimate the performance of other GPUs. " \
"I found some benchmarks on YouTube for some Triple A titles and averaged them for each resolution. No eSports titles (CS2, Valorant, R6 Siege) were taken into consideration as they were extreme outliers in the data. ", width = "content")

st.markdown("##### What is active_price and how is it calculated?")
st.text("The 'active price' is calculated by simply preferring the average eBay price first and if that is not found then the average Amazon price and finally the MSRP. " \
"I chose eBay as the first preference since this is where cards are the most available for the best price. The eBay price is found by averaging the 10 most recent sales for Buy It Now price and Used condition." \
" This way, all broken parts and non GPU items are discarded and true market value can be found. This is the main price that is used for all price calculations in this dashboard.")


st.markdown("---")
# =========================================================
# SECTION 1: HEAD-TO-HEAD COMPARATOR
# =========================================================
st.subheader("Head-to-Head Comparison")

# Multi-select for comparing specific cards
compare_list = st.multiselect(
    "Select GPUs to Compare (Up to 5)", 
    options=df['name'].sort_values(),
    default=df.sort_values("rel_performance", ascending=False).head(3)['name'].tolist(), # Default to top 3
    max_selections=5
)

if compare_list:
    # Filter data for selected cards
    comp_df = df[df['name'].isin(compare_list)].set_index('name')
    
    # Create columns dynamically based on selection
    cols = st.columns(len(compare_list))
    
    for i, (name, row) in enumerate(comp_df.iterrows()):
        with cols[i]:
            st.info(f"### {name}")
            st.write(f"**Price:** ${row['active_price']:.0f}")
            st.write(f"**Tier:** {row['tier']}")
            st.write(f"**Driver Support:** {row['support']}")
            
            # FPS Metrics
            st.metric("1080p Ultra", f"{row['1080p Ultra']:.0f} FPS")
            st.metric("1440p Ultra", f"{row['1440p Ultra']:.0f} FPS")
            st.metric("4K Ultra", f"{row['4K Ultra']:.0f} FPS")
            
            # Value Metric
            st.write(f"**Cost per Frame:** ${row['Value 1080p']:.2f}")

else:
    st.info("Select GPUs above to see a comparison.")

st.markdown("---")

# =========================================================
# SECTION 2: TARGET RESOLUTION & VALUE FINDER
# =========================================================
st.subheader("Find the Best Value for Your Target")

c1, c2 = st.columns([1, 2])

with c1:
    st.markdown("#### Define Your Goal")
    target_res = st.selectbox("Target Resolution", ["1080p", "1440p", "4K"])
    target_fps = st.slider("Target FPS (Minimum)", 30, 120, 60)
    
    # Map selection to column name
    res_col_map = {
        "1080p": "1080p Ultra",
        "1440p": "1440p Ultra",
        "4K": "4K Ultra"
    }
    target_col = res_col_map[target_res]

with c2:
    st.markdown(f"#### Top 5 Best Value Cards for {target_res} @ {target_fps}+ FPS")
    
    # Logic: Filter for FPS target -> Sort by Cheapest Price
    # (Alternatively: Sort by Price per Frame, but usually users want the cheapest card that does the job)
    
    candidates = df[df[target_col] >= target_fps].copy()
    
    if not candidates.empty:
        # Calculate specific value for this resolution
        candidates['Cost Per Frame'] = candidates['active_price'] / candidates[target_col]
        
        # Sort by best value (Cost Per Frame)
        top_picks = candidates.sort_values("Cost Per Frame", ascending=True).head(5)
        
        # Formatting for display
        display_cols = ['name', 'active_price', target_col, 'Cost Per Frame', 'tier']
        
        st.dataframe(
            top_picks[display_cols].style.format({
                "active_price": "${:.0f}",
                target_col: "{:.0f} FPS",
                "Cost Per Frame": "${:.2f}"
            }),
            use_container_width=True
        )
    else:
        st.error(f"No GPUs found that can hit {target_fps} FPS at {target_res}. Try lowering your target.")

st.markdown("---")

# =========================================================
# SECTION 3: MARKET SCATTER PLOT
# =========================================================
st.subheader("The Big Picture: Price vs. Performance")

fig = px.scatter(
    df_filtered,
    x="active_price",
    y="rel_performance",
    color="tier",
    size="rel_performance",
    hover_name="name",
    hover_data=["1080p Ultra", "4K Ultra", "active_price"],
    title="Market Efficiency Frontier",
    labels={"active_price": "Price ($)", "rel_performance": "Relative Performance (%)"},
    height=600,
    template="plotly_dark"
)
st.plotly_chart(fig, use_container_width=True)

# Raw Data Expander
with st.expander("View Full Raw Data"):
    st.dataframe(df)