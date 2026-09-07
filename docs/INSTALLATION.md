# Installation Guide (Windows)

## 1. Prerequisites

- Windows 10 or 11
- [Python 3.11+](https://www.python.org/downloads/) (tick "Add python.exe to PATH" during install)
- [Git](https://git-scm.com/download/win) — optional, for cloning and pushing
- [Power BI Desktop](https://www.microsoft.com/en-us/power-platform/products/power-bi/desktop) (free) — only needed to build the `.pbix`
- [VS Code](https://code.visualstudio.com/) — recommended editor
- SQL Server 2019+, SQL Server Express, or Azure SQL — only needed for the
  warehouse layer. The Power BI report also runs directly off the CSVs.

## 2. Clone the repository

```powershell
git clone https://github.com/koushiksoppa/enterprise-sales-finance-analytics-dashboard.git
cd enterprise-sales-finance-analytics-dashboard
```

## 3. Set up the Python environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Only pandas, numpy and openpyxl are required. The insights report and the
dashboard previews are generated with the standard library plus pandas — no
plotting or templating dependency.

## 4. Run the data pipeline

```powershell
python python\generate_sample_data.py
python python\clean_data.py
python python\prepare_sql_csv.py
python python\build_kpis.py
python python\generate_insights.py
python python\build_dashboard_previews.py
```

Run them in that order; each stage reads the previous stage's output. This
populates `data/raw/`, `data/processed/`, `reports/` and `screenshots/`.

Then open `reports/executive_insights.html` in a browser and the SVGs in
`screenshots/` to check the run.

## 5. (Optional) Load the SQL Server data warehouse

1. Open SQL Server Management Studio (SSMS) and connect to your instance.
2. Run `sql/01_schema.sql` to create the `SalesAnalyticsDW` database and tables.
3. Edit the `@DataPath` variable at the top of `sql/02_load_data.sql` to your
   local absolute path to `data\processed\` (keep the trailing backslash), then
   run it. `python\prepare_sql_csv.py` must have been run first — the load
   reads `DimInventory_ForSql.csv` and `FactSales_ForSql.csv`.
4. Run `sql/04_views.sql` to create the reporting views, then
   `sql/03_analysis_queries.sql` to explore the analytical queries.

The query results should match the corresponding files in `reports/`. If they
do not, that is a defect worth chasing rather than rounding away.

## 6. Build the Power BI report

Follow `powerbi/POWERBI_BUILD_GUIDE.md` step by step. It wires up the Power
Query M scripts, the theme, the DAX measures, the relationships, and all six
dashboard pages, with the position and field list of every visual. Import
`powerbi/theme.json` first so no colour needs to be chosen by hand.

## 7. Push to GitHub

```powershell
git add .
git commit -m "Update analytics pipeline and dashboard"
git push
```

If your `.pbix` exceeds GitHub's 100 MB limit, install
[Git LFS](https://git-lfs.com/) first (`git lfs install`) — `.gitattributes`
already tracks `*.pbix` and `*.xlsx` through LFS.

## Troubleshooting

| Issue | Fix |
|---|---|
| `python` not recognized | Reinstall Python with "Add to PATH" ticked, or use `py` instead of `python` |
| `pip install` fails on a corporate network | Add `--trusted-host pypi.org --trusted-host files.pythonhosted.org` |
| `build_kpis.py` raises `FileNotFoundError` | Run `clean_data.py` first — it writes the files in `data/processed/` that this stage reads |
| `BULK INSERT` "Access denied" | Give the SQL Server service account read access to the CSV folder, or use SSMS's Import Flat File wizard |
| `BULK INSERT` fails converting the last column, or text columns come back with a trailing character | The CSVs use CRLF line endings. `ROWTERMINATOR` must be `0x0d0a`, not `'\n'` — the shipped script already does this; check you have not reverted it |
| Power Query error converting `is_weekend` | Run `prepare_sql_csv.py`, which writes `is_weekend` as 1/0. The DimDate query converts 1/0 to a logical value |
| Power Query drops `margin_pct` from DimProduct | The `Columns=` count in `Csv.Document` must match the file — DimProduct has 6 columns |
| Power BI can't find the CSVs | Check the `FolderPath` parameter value in Power Query — it must end with a trailing backslash |
| Date axis sorts Apr, Aug, Dec | Set `DimDate[Month-Year]` to sort by `Month-Year Sort` (Column tools → Sort by column) |
