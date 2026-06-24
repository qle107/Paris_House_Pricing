@echo off
REM ============================================================
REM  Fetch REAL property listings from Bien'ici onto the map.
REM  Just double-click this file - no typing needed.
REM  It pulls listings for ALL of PARIS (the 20 arrondissements),
REM  saves a dated snapshot, and opens the map. Then click any
REM  IRIS zone to see the listings inside it.
REM
REM  Want a different area? Edit REI_LISTINGS_SCOPE below:
REM     paris   = all 20 Paris arrondissements (default)
REM     all     = every covered commune in Ile-de-France (slow!)
REM  ...or pick exact communes instead, e.g.:
REM     set REI_LISTINGS_SCOPE=
REM     set REI_LISTINGS_LOCATIONS=saint-ouen-93400,montreuil-93100
REM ============================================================
cd /d "%~dp0"

set REI_LISTINGS_PROVIDER=bienici
set REI_LISTINGS_SCOPE=paris
set REI_LISTINGS_LIMIT=2000
set REI_LISTINGS_PER_COMMUNE=100
set REI_LISTINGS_RPS=0.5

echo.
echo Fetching Bien'ici listings for ALL of Paris (20 arrondissements)...
echo This can take a few minutes - please wait.
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py --with-listings --skip-ingest
) else (
  python main.py --with-listings --skip-ingest
)

echo.
echo Done - a dated snapshot is saved in data\listings_snapshots\.
echo The map should open; click any IRIS zone to see its listings. If already open, refresh.
pause
