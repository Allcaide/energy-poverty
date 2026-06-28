# Miro AI prompt — Energy Poverty Explorer architecture diagram

Paste the prompt below into Miro's AI diagram generator ("Create diagram with AI").
It describes the whole project: data sources, ingestion pipeline, storage, the
Streamlit app and the local AI assistant, plus the Docker setup.

---

## PROMPT (copy from here)

Create a clean, left-to-right architecture / data-flow diagram for a data science
project called "Energy Poverty Explorer — Portugal". Organize it into 5 labeled
horizontal zones (swimlanes), connected by arrows. Use a different color per zone,
rounded boxes, and small format tags (API / CSV / Parquet / Excel) on the source boxes.

ZONE 1 — DATA SOURCES (different formats, this is important):
- "INE API" — household income per municipality 2015–2021, fetched live over a REST/JSON API (tag: API · JSON).
- "ERSE — energy_household.csv" — domestic electricity consumption (kWh per CPE) by municipality and year (tag: CSV).
- "DGEG — energy_prices.parquet" — average electricity price €/kWh, band DC (tag: Parquet).
- "SCE energy certificates — 17 CSV files" — EstatisticasSCE 2015–2023 yearly + 2024/2025 quarterly, UTF-16 encoded (tag: CSV ×17).
- "idade_mediana_por_municipio.xlsx" — median age per municipality, static 2023 (tag: Excel).
Group these five boxes inside Zone 1.

ZONE 2 — INGESTION & TRANSFORMATION PIPELINE (one Jupyter notebook: data_ingestion.ipynb, using pandas + numpy):
Show these processing steps as a vertical chain of boxes:
1. "Fetch income via INE API (2015–2021)".
2. "Forecast income 2022–2026" — weighted growth model: 50% pre-COVID CAGR + 10% inflation + 10% GDP growth + 15% min wage + 15% average wage (macro values from PORDATA / Banco de Portugal).
3. "Load consumption CSV" and "Load prices Parquet (avg per year)".
4. "Annual expenditure = kWh per CPE × €/kWh".
5. "Load + concat 17 SCE certificate CSVs → keep residential & existing buildings → share of bad classes D/E/F = energy efficiency index".
6. "Load median age Excel".
7. "Normalize municipality names" (strip accents, lowercase) so all datasets can be joined.
8. "MERGE everything on municipality + year".
9. "Compute EER = annual expenditure / income × 100" and "energy_poverty flag = EER > 5%", plus "age-weighted EER".
Make it clear all sources flow INTO this pipeline and converge at the MERGE step.

ZONE 3 — STORAGE / OUTPUT:
- "energy_vs_income.parquet" — the single clean final dataset (1116 rows: one row per municipality per year 2022–2025; columns: income, annual_expenditure, energy_expenditure_ratio, energy_poverty, median_age, age_weighted_eer, energy_eff_index).
- "Portugal_Municipalities.geojson" — municipality map boundaries.
Arrow from the pipeline MERGE step to the Parquet file.

ZONE 4 — APPLICATION (Streamlit app: energy_app.py):
- "Streamlit web app" reads the Parquet + GeoJSON.
- Sub-boxes for its features: "Choropleth map (Plotly)", "Metric selector + year slider", "Click municipality → time-series charts", "District averages + Top 10 table".
- A separate sub-system "AI Assistant (ai_chat.py)" shown as a 4-step loop:
  (a) user asks a question in plain language,
  (b) "Local Ollama model turns question into SQL (or returns NO_QUERY if off-topic)",
  (c) "DuckDB runs the SQL on the dataset",
  (d) "Ollama explains the result in natural language".
- Show "ai_feedback.md" as an editable file feeding examples/rules into the AI model.
- Note that the model runs locally (e.g. qwen2.5:3b) — nothing leaves the machine.
Arrow from Zone 3 Parquet into both the Streamlit charts and the DuckDB query box.

ZONE 5 — INFRASTRUCTURE (Docker, wrap as a dashed container around Zone 4):
- Two containers managed by docker-compose: "app container (Streamlit, port 8502→8501)" and "ollama container (port 11434, models in a named volume)".
- Arrow labeled "http://ollama:11434" from the app container to the ollama container.

STYLE: modern, readable, arrows showing direction of data flow left-to-right
(sources → pipeline → storage → app), the AI assistant as a small clockwise loop,
format tags on the sources, one accent color per zone, and a title at the top:
"Energy Poverty Explorer — Data Pipeline & App Architecture".
