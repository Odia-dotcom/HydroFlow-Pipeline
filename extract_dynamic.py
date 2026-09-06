import requests
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError
import time

# Initialize the geocoder
geolocator = Nominatim(user_agent="hydroflow_africa_pipeline_v2")

def get_coordinates_for_africa(location_name):
    """Converts plain text into Latitude/Longitude."""
    print(f" Geocoding location: '{location_name}'...")
    try:
        time.sleep(1) # Compliance rate-limiting
        location = geolocator.geocode(location_name, addressdetails=True, timeout=10)
        
        if not location:
            print(f" Location '{location_name}' not found.")
            return None
            
        address = location.raw.get("address", {})
        country = address.get("country", "")
        return {"city": location_name, "country": country, "lat": location.latitude, "lon": location.longitude}
    except GeopyError as e:
        print(f" Geocoding error for '{location_name}': {e}")
        return None

def extract_water_data(lat, lon):
    """Queries Open-Meteo using a manually constructed URL string to preserve literal commas."""
    # Data Engineering Best Practice: Build clean query string to avoid %2C encoding issues
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        f"&hourly=precipitation,soil_moisture_27_to_81cm"
        f"&past_days=14"
        f"&timezone=UTC"
    )
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.JSONDecodeError:
        print(f" JSON Decode Error. API Server returned text/HTML instead of JSON.")
        print(f" Server response excerpt: {response.text[:200]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f" Network/API connection error: {e}")
        return None

def transform_data(raw_json, meta):
    """Flattens API JSON into a clean DataFrame."""
    if not raw_json or "hourly" not in raw_json:
        return pd.DataFrame()
        
    hourly_data = raw_json["hourly"]
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(hourly_data["time"]),
        "precipitation_mm": hourly_data["precipitation"],
        "soil_moisture_m3": hourly_data["soil_moisture_27_to_81cm"]
    })
    
    df["search_query"] = meta["city"]
    df["resolved_country"] = meta["country"]
    df["latitude"] = meta["lat"]
    df["longitude"] = meta["lon"]
    
    df["soil_moisture_m3"] = df["soil_moisture_m3"].interpolate(method="linear")
    df["precipitation_mm"] = df["precipitation_mm"].fillna(0.0)
    return df

if __name__ == "__main__":
    AFRICA_TARGETS = ["Dodoma", "Dakar", "Bol, Chad", "Soweto"]
    all_data = []

    print("=" * 65)
    print(" Running Dynamic HydroFlow Africa Extraction Engine...\n")
    print("=" * 65)
    
    for target in AFRICA_TARGETS:
        meta = get_coordinates_for_africa(target)
        if meta:
            print(f" Found: {meta['city']} ({meta['lat']}, {meta['lon']})")
            raw_json = extract_water_data(meta["lat"], meta["lon"])
            clean_df = transform_data(raw_json, meta)
            
            if not clean_df.empty:
                all_data.append(clean_df)
                print(f" Processed {len(clean_df)} hourly logs successfully.\n")
                
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        final_df.to_csv("staging_africa_water.csv", index=False)
        print(f"\n Success! Staging file created: 'staging_africa_water.csv' ({len(final_df)} rows logged).")
    else:
        print(" Pipeline completed. No data records were generated.")
