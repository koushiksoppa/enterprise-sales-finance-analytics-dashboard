# Installation Guide (Windows 11)

## 1. Prerequisites
- Windows 11
- [Python 3.11+](https://www.python.org/downloads/) (check "Add python.exe to PATH" during install)
- [Git](https://git-scm.com/download/win) and [GitHub Desktop](https://desktop.github.com/) (optional, for pushing to GitHub)
- [Power BI Desktop](https://www.microsoft.com/en-us/power-platform/products/power-bi/desktop) (free, Microsoft Store or direct download)
- [VS Code](https://code.visualstudio.com/) (recommended editor)
- SQL Server 2019+ or SQL Server Express, or Azure SQL Database (only needed if you want the SQL warehouse layer — the Power BI report also works directly off the CSVs without SQL Server)

## 2. Clone the repository
```powershell
git clone https://github.com/<your-username>/Enterprise-Sales-Finance-Analytics-Dashboard.git
cd Enterprise-Sales-Finance-Analytics-Dashboard
```

## 3. Set up the Python environment
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Run the data pipeline
```powershell
cd python
python generate_sample_data.py
python clean_data.py
python prepare_sql_csv.py
python build_kpis.py
python generate_insights.py
cd ..
```
This populates `data/raw/`, `data/processed/`, and `reports/`.

## 5. (Optional) Load the SQL Server data warehouse
1. Open SQL Server Management Studio (SSMS), connect to your instance.
2. Run `sql/01_schema.sql` to create the `SalesAnalyticsDW` database and tables.
3. Edit the `@DataPath` variable at the top of `sql/02_load_data.sql` to your
   local absolute path to `data\processed\`, then run it.
4. Run `sql/03_analysis_queries.sql` and `sql/04_views.sql` to explore the
   analytical queries and create the reporting views.

## 6. Build the Power BI report
Follow `powerbi/POWERBI_BUILD_GUIDE.md` step by step — it wires up the
Power Query M scripts, DAX measures, relationships, and all six dashboard
pages in Power BI Desktop and saves the final `.pbix`.

## 7. Push to GitHub
```powershell
git add .
git commit -m "Initial commit: Enterprise Sales & Finance Analytics Dashboard"
git remote add origin https://github.com/<your-username>/Enterprise-Sales-Finance-Analytics-Dashboard.git
git push -u origin main
```
If your `.pbix` exceeds GitHub's 100 MB limit, install [Git LFS](https://git-lfs.com/)
first (`git lfs install`) — `.gitattributes` in this repo already tracks
`*.pbix` and `*.xlsx` through LFS.

## Troubleshooting
| Issue | Fix |
|---|---|
| `python` not recognized | Reinstall Python and check "Add to PATH", or use `py` instead of `python` |
| `pip install` fails on a corporate network | Add `--trusted-host pypi.org --trusted-host files.pythonhosted.org` |
| `BULK INSERT` "Access denied" in SQL Server | Ensure the SQL Server service account has read access to the CSV folder, or use SSMS's Import Flat File wizard instead |
| Power BI can't find the CSVs | Double-check the `FolderPath` parameter value in Power Query — it must end with a trailing backslash |
