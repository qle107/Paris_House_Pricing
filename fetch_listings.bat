@echo off
REM ============================================================
REM  Fetch REAL property listings from Bien'ici onto the map.
REM  Just double-click this file - no typing needed.
REM  It pulls ALL listings for ALL of PARIS (the 20 arrondissements),
REM  both for-sale AND for-rent, saves a dated snapshot, and opens the
REM  map. Then click any IRIS zone to see the listings inside it.
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
set REI_LISTINGS_TRANSACTION=both
REM  Caps set high so "full Paris" is not truncated. Bien'ici hard-caps any one
REM  search at ~2400 ads (100 pages), so PER_COMMUNE above that just means
REM  "take everything available per arrondissement"; LIMIT is the buy+rent total.
set REI_LISTINGS_LIMIT=60000
set REI_LISTINGS_PER_COMMUNE=3000
set REI_LISTINGS_RPS=1.0

echo.
echo Fetching ALL Bien'ici listings for Paris (20 arrondissements, sale + rent)...
echo This pulls every available ad and takes about 5-10 minutes - please wait.
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
