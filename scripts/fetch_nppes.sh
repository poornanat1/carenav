#!/usr/bin/env bash
# Download the real NPPES monthly file and extract ONLY NJ/NY provider rows, without
# ever landing the full ~11 GB CSV on disk (streams out of the zip and filters on the
# fly). Produces data_artifacts/nppes/npidata.csv (~90 MB) that the ingest auto-detects.
#
# Usage: scripts/fetch_nppes.sh
# Override the month/URL with NPPES_URL=... scripts/fetch_nppes.sh
#
# NOTE: CMS rotates the monthly filename. If the default URL 404s, find the current one
# at https://download.cms.gov/nppes/NPI_Files.html and pass it via NPPES_URL.
set -euo pipefail

OUT_DIR="${DATA_DIR:-./data_artifacts}/nppes"
ZIP="$OUT_DIR/nppes.zip"
OUT_CSV="$OUT_DIR/npidata.csv"
NPPES_URL="${NPPES_URL:-https://download.cms.gov/nppes/NPPES_Data_Dissemination_May_2026_V2.zip}"
STATES_REGEX="${NPPES_STATES_REGEX:-\"NJ\"|\"NY\"}"   # state column is quoted in the raw CSV
MAX_ROWS="${NPPES_MAX_ROWS:-80000}"                   # cap rows written (loader caps again)

mkdir -p "$OUT_DIR"

echo "Downloading NPPES (~1 GB) from $NPPES_URL ..."
curl -L --fail -o "$ZIP" "$NPPES_URL"

# Find the main data file name inside the zip (npidata_pfile_*.csv, excluding fileheader).
MAIN_CSV="$(unzip -l "$ZIP" | awk '/npidata_pfile_.*\.csv$/ && $0 !~ /fileheader/ {print $4}' | head -1)"
echo "Main file in zip: $MAIN_CSV"

echo "Streaming + filtering ($STATES_REGEX), capped at $MAX_ROWS rows -> $OUT_CSV ..."
# State Name is column 32 in the V.2 layout.
unzip -p "$ZIP" "$MAIN_CSV" \
  | awk -F',' -v re="$STATES_REGEX" -v max="$MAX_ROWS" \
      'NR==1 {print; next} $32 ~ re {print; c++} c>=max {exit}' \
  > "$OUT_CSV"

echo "Deleting zip to reclaim disk ..."
rm -f "$ZIP"

echo "Done: $(wc -l < "$OUT_CSV") rows in $OUT_CSV"
echo "Now run: make data   (or: make data-nppes)"
