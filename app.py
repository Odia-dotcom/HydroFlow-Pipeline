import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
from geopy.geocoders import Nominatim
import requests
import time

# Initialize Geocoder
geolocator = Nominatim(user_agent="hydroflow_live_user_app")

# 1. Page Configuration (Visual Layout)
st.set_page_config(
    page_title="Africa Water Shortage Monitoring Hub",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Live API Extraction & Transformation Helper
def fetch_live_metrics(lat, lon):
    """Queries Open-Meteo directly and prints live diagnostic errors if it fails."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        f"&hourly=precipitation,soil_moisture_27_to_81cm"
        f"&past_days=14"
        f"&timezone=UTC"
    )
    try:
        response = requests.get(url, timeout=10)
        
        # If the server responds with an error code (like 400 or 429), this shows it in the app
        if response.status_code != 200:
            st.sidebar.error(f"⚠️ API Server Error Code: {response.status_code}")
            st.sidebar.text_area("Server Response Details:", value=response.text[:300], height=100)
            return None
            
        return response.json()
    except Exception as e:
        st.sidebar.error(f"🔌 Network Connection Failed: {e}")
        return None

# 3. Main Dashboard Title & Header
st.title("🌍 Africa Water Shortage & Drought Risk Tracker")
st.markdown("""
**Welcome to the HydroFlow Platform.** 

This interactive hub monitors daily environmental conditions to track water scarcity and predict drought risks across key regions in Africa. 

By analyzing local rainfall trends and underground soil moisture levels, this system automatically calculates a **Shortage Probability Score**. This score helps communities, farmers, and decision-makers anticipate water stress and prepare before it turns into a critical shortage.Use the search box in the left sidebar to enter any city or region. 
""")

# 4. Sidebar Live Search Engine Controls
user_query = st.sidebar.text_input(
    label="🔍 Search any location", 
    value="Dodoma", 
    placeholder="Type any city or region in Africa...",
    help="Examples: Nairobi, Casablanca, Soweto, Timbuktu, Luanda"
)

if user_query:
    # Use a visual loading spinner while computing live API pipelines
    with st.spinner(f"Geocoding and running analytical risk models for '{user_query}'..."):
        try:
            # Step A: Live Geocoding via open-source map records
            location = geolocator.geocode(user_query, addressdetails=True, timeout=10)
            
            if location:
                lat, lon = location.latitude, location.longitude
                address = location.raw.get("address", {})
                country = address.get("country", "Unknown Country")
                
                # Step B: Live API Data Extraction
                raw_json = fetch_live_metrics(lat, lon)
                
                if raw_json and "hourly" in raw_json:
                    hourly_data = raw_json["hourly"]
                    
                    # Step C: Live Silver & Gold Transformation Layer Logic
                    df = pd.DataFrame({
                        "measurement_time": pd.to_datetime(hourly_data["time"]),
                        "precipitation_mm": [float(x) if x is not None else 0.0 for x in hourly_data["precipitation"]],
                        "soil_moisture_m3": hourly_data["soil_moisture_27_to_81cm"]
                    })
                    
                    # Handle null sensors via linear interpolation
                    df["soil_moisture_m3"] = df["soil_moisture_m3"].interpolate(method="linear")
                    
                    # Compute Gold 24h Rolling Average
                    df["rolling_24h_soil_moisture"] = df["soil_moisture_m3"].rolling(window=24, min_periods=1).mean()
                    
                    # Apply Dynamic Evaluation Matrix for Risk Score Calculation
                    def evaluate_scarcity_risk(row):
                        if row["soil_moisture_m3"] < 0.15 and row["precipitation_mm"] == 0:
                            return 95.0
                        elif row["soil_moisture_m3"] < 0.22 and row["precipitation_mm"] == 0:
                            return 65.0
                        elif row["soil_moisture_m3"] < 0.30:
                            return 35.0
                        else:
                            return 10.0
                            
                    df["shortage_probability_pct"] = df.apply(evaluate_scarcity_risk, axis=1)
                    
                    # Sort data to fetch the most recent metrics
                    region_data = df.sort_values(by="measurement_time", ascending=False)
                    latest_data = region_data.iloc[0]
                    
                    # ==========================================
                    #  UI RENDERING: Displaying Results
                    # ==========================================
                    st.subheader(f"📍 Current Status: {user_query.title()}, {country}")
                    
                    # KPI Columns
                    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
                    prob = latest_data['shortage_probability_pct']
                    status_tag = "🔴 Critical" if prob > 75 else "🟡 Warning" if prob > 40 else "🟢 Stable"
                    
                    with kpi_col1:
                        st.metric(
                            label="Shortage Probability (Next 14 Days)", 
                            value=f"{prob:.1f}%", 
                            delta=status_tag, 
                            delta_color="inverse"
                        )
                    with kpi_col2:
                        st.metric(
                            label="Current Soil Moisture", 
                            value=f"{latest_data['soil_moisture_m3']:.3f} m³/m³",
                            delta=f"24h Avg: {latest_data['rolling_24h_soil_moisture']:.3f}"
                        )
                    with kpi_col3:
                        st.metric(
                            label="Recent Recorded Precipitation", 
                            value=f"{latest_data['precipitation_mm']:.1f} mm"
                        )

                    st.markdown("---")

                    # Charts Section
                    st.subheader("🔮 Predictive Risk & Soil Moisture Trends")
                    chart_col1, chart_col2 = st.columns(2)
                    
                    with chart_col1:
                        st.markdown("**Soil Moisture Volatility vs 24h Moving Average**")
                        fig_moisture = px.line(
                            region_data, 
                            x="measurement_time", 
                            y=["soil_moisture_m3", "rolling_24h_soil_moisture"],
                            labels={"value": "Moisture (m³/m³)", "measurement_time": "Timeline"},
                            color_discrete_sequence=["#1f77b4", "#ff7f0e"]
                        )
                        st.plotly_chart(fig_moisture, use_container_width=True)
                        
                    with chart_col2:
                        st.markdown("**Calculated Dynamic Drought Probability Path**")
                        fig_risk = px.area(
                            region_data, 
                            x="measurement_time", 
                            y="shortage_probability_pct",
                            labels={"shortage_probability_pct": "Risk Score (%)", "measurement_time": "Timeline"},
                            color_discrete_sequence=["#d62728"]
                        )
                        fig_risk.update_yaxes(range=[0, 100])
                        st.plotly_chart(fig_risk, use_container_width=True)

                    st.markdown("---")
                    st.subheader("🛠️ Operational Metadata")
                    exp_col1, exp_col2 = st.columns(2)
                    with exp_col1:
                        st.markdown(f"**Geospatial Coordinates Lock:** Latitude: `{lat:.4f}` | Longitude: `{lon:.4f}`")
                    with exp_col2:
                        csv_data = region_data.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Export Clean Query Data (CSV)",
                            data=csv_data,
                            file_name=f"{user_query.lower()}_live_water_metrics.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                else:
                    st.sidebar.error("Could not fetch climate data for this location's coordinates.")
            else:
                st.sidebar.error(f"Could not find coordinates for '{user_query}'. Try checking the spelling or adding the country name.")
        except Exception as e:
            st.sidebar.error(f"Pipeline error: {e}")
