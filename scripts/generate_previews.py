import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import subprocess
import json
import os

def get_bq_data():
    query = "SELECT * FROM traffic_analytics.v_dashboard_unified"
    # Try multiple bq locations if necessary
    bq_path = "bq.cmd"
    cmd = [bq_path, "query", "--use_legacy_sql=false", "--format=json", "--project_id=city-traffic-analytics", query]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print("Error fetching data:", result.stderr)
        return None
    return pd.DataFrame(json.loads(result.stdout))

def build_charts():
    df = get_bq_data()
    if df is None or df.empty:
        print("No data found to visualize.")
        return

    # Convert numeric columns
    numeric_cols = ['total_vehicles', 'avg_speed_kmh', 'congestion_score']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Set theme
    sns.set_theme(style="whitegrid")
    
    # Chart 1: Average Speed by Intersection
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x='intersection_id', y='avg_speed_kmh', hue='time_of_day')
    plt.title('Average Speed by Intersection and Time of Day')
    plt.ylabel('Speed (km/h)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('docs/charts_speed_by_intersection.png')
    print("Saved: docs/charts_speed_by_intersection.png")

    # Chart 2: Traffic Volume over Time
    plt.figure(figsize=(12, 6))
    df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
    daily_traffic = df.groupby('event_timestamp')['total_vehicles'].sum().reset_index()
    sns.lineplot(data=daily_traffic, x='event_timestamp', y='total_vehicles', marker='o')
    plt.title('Total Traffic Volume (Hourly)')
    plt.ylabel('Number of Vehicles')
    plt.tight_layout()
    plt.savefig('docs/charts_traffic_volume.png')
    print("Saved: docs/charts_traffic_volume.png")

    # Chart 3: Congestion Levels
    plt.figure(figsize=(8, 8))
    congestion_counts = df['congestion_level'].value_counts()
    plt.pie(congestion_counts, labels=congestion_counts.index, autopct='%1.1f%%', colors=sns.color_palette('viridis'))
    plt.title('Distribution of Congestion Levels')
    plt.tight_layout()
    plt.savefig('docs/charts_congestion_dist.png')
    print("Saved: docs/charts_congestion_dist.png")

if __name__ == "__main__":
    build_charts()
