#!/usr/bin/env bash
# Optionally generate REAL Synthea data. The pipeline works without this (it falls back
# to a deterministic synthetic dataset), but this produces richer FHIR/CSV output and is
# the on-ramp to the GCP Healthcare API story (docs/14-gcp-mapping.md).
#
# Usage: scripts/run_synthea.sh [population]
# Requires: Java (java -version). Output CSVs land in $SYNTHEA_OUTPUT_DIR.
set -euo pipefail

POP="${1:-${SYNTHEA_POPULATION:-200}}"
OUT_DIR="${SYNTHEA_OUTPUT_DIR:-./data_artifacts/synthea/csv}"
WORK="./data_artifacts/synthea"
JAR="$WORK/synthea-with-dependencies.jar"
JAR_URL="https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"

mkdir -p "$WORK" "$OUT_DIR"

if [ ! -f "$JAR" ]; then
  echo "Downloading Synthea jar..."
  curl -L -o "$JAR" "$JAR_URL"
fi

echo "Generating $POP synthetic patients (CSV + FHIR)..."
java -jar "$JAR" \
  -p "$POP" \
  --exporter.csv.export=true \
  --exporter.fhir.export=true \
  --exporter.baseDirectory "$WORK/output" \
  "New Jersey"

# Synthea writes CSVs under output/csv — copy to the configured dir.
cp -f "$WORK/output/csv/"*.csv "$OUT_DIR/" 2>/dev/null || true
echo "Done. CSVs in $OUT_DIR — now run: make data"
