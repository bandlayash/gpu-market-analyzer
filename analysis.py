import sqlite3
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

# --- CONFIGURATION ---
ANCHOR_FPS_1080P = 64
ANCHOR_FPS_1440P = 51
ANCHOR_FPS_4K = 44.2

DB_PATH = "gpus.db"

def get_raw_data():
    """Simple fetch from DB using a local connection"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT name, launch_prices, amazon_new_avg, ebay_used_avg, rel_performance, tier, driver_support
        FROM gpus
        WHERE rel_performance IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def update_gpu_tiers():
    """
    Calculates K-Means clustering and saves 'tier' to the database.
    Run this function manually or via main block to update tiers.
    """
    conn = sqlite3.connect(DB_PATH)
    
    # Get Data
    df = pd.read_sql_query("SELECT name, rel_performance FROM gpus WHERE rel_performance IS NOT NULL", conn)
    
    if df.empty:
        print("No performance data found! Run the benchmark scraper first.")
        conn.close()
        return

    # Run K-Means
    X = df[['rel_performance']]
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    df['cluster'] = kmeans.fit_predict(X)

    # Sort clusters
    cluster_means = df.groupby('cluster')['rel_performance'].mean().sort_values()
    tier_names = ['Low', 'Low-Mid','High-Mid', 'High', 'Ultra-High']
    label_map = {old_label: new_name for old_label, new_name in zip(cluster_means.index, tier_names)}
    df['tier'] = df['cluster'].map(label_map)

    # Save back to SQLite
    print("-" * 30)
    print("Classifying GPUs...")
    
    try:
        conn.execute("ALTER TABLE gpus ADD COLUMN tier TEXT")
    except sqlite3.OperationalError:
        pass 

    # Update rows
    count = 0
    for index, row in df.iterrows():
        conn.execute("UPDATE gpus SET tier = ? WHERE name = ?", (row['tier'], row['name']))
        count += 1
        
    conn.commit()
    conn.close()
    print(f"Updated {count} GPUs with new tiers.")


def get_analyzed_df():
    """
    Returns the fully processed dataframe for the Dashboard.
    """
    df = get_raw_data()
    if 'driver_support' in df.columns:
        df['support'] = df['driver_support'].fillna("Unknown")
        df = df.drop(columns=['driver_support'])
    else:
        df['support'] = "N/A"

    # Price Strategy: Prefer eBay -> Amazon -> MSRP
    # Create a clean 'active_price' column
    # Ensure columns are numeric before math
    df['ebay_used_avg'] = pd.to_numeric(df['ebay_used_avg'], errors='coerce')
    df['new_avg'] = pd.to_numeric(df['new_avg'], errors='coerce')
    df['launch_prices'] = pd.to_numeric(df['launch_prices'], errors='coerce')

    df['active_price'] = df['ebay_used_avg'].fillna(df['new_avg']).fillna(df['launch_prices'])
    
    # Remove invalid rows (Free or Broken data)
    df = df[df['active_price'] > 50] 

    # Calculate Estimated FPS
    ratio = df['rel_performance'] / 100.0
    
    df['1080p Ultra'] = ratio * ANCHOR_FPS_1080P
    df['1440p Ultra'] = ratio * ANCHOR_FPS_1440P
    df['4K Ultra'] = ratio * ANCHOR_FPS_4K

    # Calculate "Value" (Cost per Frame)
    df['Value 1080p'] = df['active_price'] / df['1080p Ultra']
    df['Value 1440p'] = df['active_price'] / df['1440p Ultra']
    df['Value 4K'] = df['active_price'] / df['4K Ultra']

    
    
    return df

# Only run the update if this file is executed directly
if __name__ == "__main__":
    update_gpu_tiers()