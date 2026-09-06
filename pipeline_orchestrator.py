import time
from datetime import datetime
import subprocess
import duckdb
import os

DB_FILE = "africa_water_data_lake.db"
CSV_FILE = "staging_africa_water.csv"

def log_step(step_name, status="STARTING", duration=None):
    """Utility to print highly visible, framed pipeline step banners."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if status == "STARTING":
        print("\n" + "=" * 65)
        print(f" [{timestamp}] RUNNING: {step_name.upper()}")
        
    elif status == "SUCCESS":
        print("=" * 65)
        print(f" SUCCESS: Completed in {duration:.4f} seconds.")
        
    elif status == "FAILED":
        print("!" * 65)
        print(f" CRITICAL FAILURE AT STEP: {step_name.upper()}")
        print("!" * 65 + "\n")


def run_orchestrator():
    print("=============================================")
    print(" HYDROFLOW-PIPELINE AUTOMATED ORCHESTRATOR")
    print(f" Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=============================================\n")
    
    pipeline_start_time = time.time()

    # ------------------------------------------------------------------
    # STEP 1: Dynamic API Extraction (Ingestion)
    # ------------------------------------------------------------------
    log_step("STEP 1: API Extraction & Geocoding (Ingestion Engine)")
    step_start = time.time()
    
    try:
        # Executes your extraction script as a subprocess
        result = subprocess.run(["python", "extract_dynamic.py"], capture_output=True, text=True, check=True)
        step_duration = time.time() - step_start
        log_step("STEP 1: API Extraction & Geocoding (Ingestion Engine)", "SUCCESS", step_duration)
    except subprocess.CalledProcessError as e:
        log_step("STEP 1: API Extraction & Geocoding (Ingestion Engine)", "FAILED")
        print(f"Error Details:\n{e.stderr}")
        return

    # Connect to DuckDB to orchestrate the internal Medallion transformations
    conn = duckdb.connect(DB_FILE)

    # ------------------------------------------------------------------
    # STEP 2: Bronze Layer Loading
    # ------------------------------------------------------------------
    log_step("STEP 2: Ingesting Raw Staging CSV to BRONZE Layer")
    step_start = time.time()
    
    try:
        conn.execute(f"""
            CREATE OR REPLACE TABLE bronze_water_data AS
            SELECT *, current_timestamp AS ingested_at
            FROM read_csv_auto('{CSV_FILE}');
        """)
        step_duration = time.time() - step_start
        log_step("STEP 2: Ingesting Raw Staging CSV to BRONZE Layer", "SUCCESS", step_duration)
    except Exception as e:
        log_step("STEP 2: Ingesting Raw Staging CSV to BRONZE Layer", "FAILED")
        print(f"SQL Error: {e}")
        conn.close()
        return

    # ------------------------------------------------------------------
    # STEP 3: Silver Layer Cleaning & Validation
    # ------------------------------------------------------------------
    log_step("STEP 3: Cleaning, Normalizing & Casting to SILVER Layer")
    step_start = time.time()
    
    try:
        conn.execute("""
            CREATE OR REPLACE TABLE silver_water_data AS
            SELECT DISTINCT
                TRIM(search_query) AS location_name,
                TRIM(resolved_country) AS country,
                CAST(timestamp AS TIMESTAMP) AS measurement_time,
                CAST(timestamp AS DATE) AS measurement_date,
                ROUND(latitude, 4) AS latitude,
                ROUND(longitude, 4) AS longitude,
                COALESCE(CAST(precipitation_mm AS DOUBLE), 0.0) AS precipitation_mm,
                COALESCE(CAST(soil_moisture_m3 AS DOUBLE), 0.0) AS soil_moisture_m3,
                ingested_at,
                current_timestamp AS processed_at
            FROM bronze_water_data
            WHERE search_query IS NOT NULL AND timestamp IS NOT NULL;
        """)
        step_duration = time.time() - step_start
        log_step("STEP 3: Cleaning, Normalizing & Casting to SILVER Layer", "SUCCESS", step_duration)
    except Exception as e:
        log_step("STEP 3: Cleaning, Normalizing & Casting to SILVER Layer", "FAILED")
        print(f"SQL Error: {e}")
        conn.close()
        return

    # ------------------------------------------------------------------
    # STEP 4: Gold Layer Star Schema Modeling
    # ------------------------------------------------------------------
    log_step("STEP 4: Compiling Analytics Metrics & Risk Models into GOLD Layer")
    step_start = time.time()
    
    try:
        # Gold: Dimensions
        conn.execute("""
            CREATE OR REPLACE TABLE gold_dim_location AS
            SELECT DISTINCT md5(location_name || '_' || latitude || '_' || longitude) AS location_key,
            location_name, country, latitude, longitude FROM silver_water_data;
        """)
        conn.execute("""
            CREATE OR REPLACE TABLE gold_dim_date AS
            SELECT DISTINCT measurement_date AS date_key,
            EXTRACT(year FROM measurement_date) AS year,
            EXTRACT(month FROM measurement_date) AS month,
            EXTRACT(day FROM measurement_date) AS day FROM silver_water_data;
        """)
        
        # Gold: Fact Table with Business Logic Matrix
        conn.execute("""
            CREATE OR REPLACE TABLE gold_fact_water_stress AS
            SELECT 
                md5(location_name || '_' || latitude || '_' || longitude) AS location_key,
                measurement_date AS date_key,
                measurement_time,
                precipitation_mm,
                soil_moisture_m3,
                AVG(soil_moisture_m3) OVER (
                    PARTITION BY location_name ORDER BY measurement_time ROWS BETWEEN 24 PRECEDING AND CURRENT ROW
                ) AS rolling_24h_soil_moisture,
                CASE 
                    WHEN soil_moisture_m3 < 0.15 AND precipitation_mm = 0 THEN 95.0
                    WHEN soil_moisture_m3 < 0.22 AND precipitation_mm = 0 THEN 65.0
                    WHEN soil_moisture_m3 < 0.30 THEN 35.0
                    ELSE 10.0
                END AS shortage_probability_pct
            FROM silver_water_data;
        """)
        step_duration = time.time() - step_start
        log_step("STEP 4: Compiling Analytics Metrics & Risk Models into GOLD Layer", "SUCCESS", step_duration)
    except Exception as e:
        log_step("STEP 4: Compiling Analytics Metrics & Risk Models into GOLD Layer", "FAILED")
        print(f"SQL Error: {e}")
        conn.close()
        return

    # Close DuckDB Data Lake handle safely
    conn.close()

    # ------------------------------------------------------------------
    # PIPELINE CLOSURE
    # ------------------------------------------------------------------
    total_pipeline_duration = time.time() - pipeline_start_time
    print("==================================================================")
    print(f" HYDROFLOW-PIPELINE RUN COMPLETED SUCCESSFULLY!")
    print(f" Total Execution Runtime: {total_pipeline_duration:.2f} seconds")
    print("==================================================================")

if __name__ == "__main__":
    run_orchestrator()
