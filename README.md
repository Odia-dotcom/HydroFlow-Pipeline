# HydroFlow-Pipeline
# 🌊 HydroFlow-Pipeline: A Simple, Smart Water Shortage Tracker for Africa

HydroFlow-Pipeline is an automated data tool that looks at real-time environmental data to track water scarcity and predict drought risks across Africa. 

Instead of showing static, pre-made charts, this app lets users type in **any African city or region**. The backend instantly finds the coordinates on a map, downloads live climate logs, and calculates a dynamic water shortage risk score.

🚀 **Live Dashboard Link:** [will insert Streamlit URL Here]  

---

## 🛠️ How It Works & The Tech Stack

This project is built using a clean, modern setup that runs entirely locally without needing expensive cloud servers:

*   **Finding Locations:** Python (`geopy`) takes whatever plain text the user types (like "Nairobi") and translates it into exact GPS latitude and longitude.
*   **Fetching Data:** Python (`requests`) calls the free, open-source Open-Meteo API to get rainfall and soil moisture data.
*   **The Smart Engine:** **DuckDB** acts as the local database. It is incredibly fast at processing numbers and runs inside a single local file on the computer—no server setup required.
*   **The Brain (SQL):** Clean SQL code calculates averages and risks inside the database.
*   **The Interface:** **Streamlit** and **Plotly** draw the webpage, drop-down menus, and interactive charts.
*   **🤖 AI Collaboration:** **Gemini** was leveraged as a pair-programmer to draft code templates, handle edge-case debugging (like API encoding issues), and optimize the SQL window functions.

--> INSERT GRAPH

---

## 📐 Organizing Data with the Medallion Architecture

To keep the project organized like a professional data platform, data travels through three strict steps inside DuckDB:

### 1. 🥉 The Bronze Layer (`bronze_water_data`)
It saves the raw weather data exactly as it arrives from the internet. We also attach a timestamp (`ingested_at`) so we always know exactly when the data was collected.

### 2. 🥈 The Silver Layer (`silver_water_data`)
This is the cleaning station. This step:
*   Fixes messy text and standardizes dates.
*   Rounds GPS coordinates so they look clean.
*   Fills in missing spaces automatically if a satellite or sensor skipped a reading.
*   Removes accidental duplicate rows so our stats stay accurate.

### 3. 🥇 The Gold Layer (Star Schema Analytics)
The clean data was split into a **Star Schema** and the final business math was run:
*   **`gold_dim_location`**: Stores unique location profiles using a secure ID code.
*   **`gold_dim_date`**: Breaks dates down into Year, Month, and Day for easy querying.
*   **`gold_fact_water_stress`**: Uses an advanced **SQL Window Function** to calculate a running 24-hour average of soil moisture. Then, it runs the custom risk matrix to output a simple **0% to 100% Shortage Probability Score** for the user.

---
## ⏱️ Performance Benchmarks (How Fast It Runs)

By using DuckDB instead of a heavy database server, the pipeline processes thousands of rows in milliseconds. Here is how long each step took according to the automated tracker:

*   **Step 1 (API Download):** ~4.1 seconds *(mostly waiting on your internet connection)*
*   **Step 2 (Bronze Load):** **0.015 seconds** ⚡
*   **Step 3 (Silver Cleaning):** **0.008 seconds** ⚡
*   **Step 4 (Gold Calculations):** **0.021 seconds** ⚡

---

## 🚀 How to Run It on Your Computer

### 1. Install the Tools
Clone this repository and download the required Python libraries using your terminal:
```bash
git clone https://github.com
cd HydroFlow-Pipeline
pip install -r requirements.txt
```
*(Your `requirements.txt` file should list: `requests`, `pandas`, `geopy`, `duckdb`, `streamlit`, `plotly`)*

### 2. Run the Pipeline Data Engine
Run the main orchestrator script to fetch the data and build your 3-layer database:
```bash
python pipeline_orchestrator.py
```

### 3. Open the Interactive Dashboard
Launch the web interface locally to see your graphs and play with the search box:
```bash
streamlit run app.py
```

---

## 💡 Important Takeaways

*   **Smart Automation:** The app handles typos and unexpected search queries safely without crashing.
*   **Lightweight Setup:** Using DuckDB facilitates completing complex data warehouse calculations inside a single, tiny database file.
*   **Separation of Work:** If the internet drops out, the API code handles it. If a calculation is wrong, the SQL code handles it. Keeping them separate makes the app much easier to maintain and update.
