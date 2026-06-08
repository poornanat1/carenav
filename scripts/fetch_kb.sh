#!/usr/bin/env bash
# Refresh the KB corpus from upstream public sources (OPTIONAL).
#
# The committed Markdown files in carenav/rag/corpus/ are the source of truth and make
# `make data` build the vector store fully offline on a fresh clone. This script only
# documents where the real content comes from and pulls raw upstream copies into
# data_artifacts/kb_raw/ for manual review when you want to re-curate. It does NOT
# overwrite the committed corpus — keeping the build deterministic is the point.
#
# Usage: scripts/fetch_kb.sh
set -euo pipefail

OUT_DIR="${DATA_DIR:-./data_artifacts}/kb_raw"
mkdir -p "$OUT_DIR/consumer_health" "$OUT_DIR/drug_label" "$OUT_DIR/sbc"

echo "Fetching raw upstream KB sources into $OUT_DIR (for review; corpus stays committed) ..."

# --- consumer health: MedlinePlus / CDC ---
curl -sL "https://medlineplus.gov/diabetestype2.html" \
  -o "$OUT_DIR/consumer_health/type-2-diabetes.html" || echo "  (medlineplus diabetes fetch failed)"
curl -sL "https://www.cdc.gov/high-blood-pressure/about/index.html" \
  -o "$OUT_DIR/consumer_health/high-blood-pressure.html" || echo "  (cdc bp fetch failed)"

# --- drug labels: openFDA (structured JSON) ---
curl -sL "https://api.fda.gov/drug/label.json?search=openfda.generic_name:metformin&limit=1" \
  -o "$OUT_DIR/drug_label/metformin.json" || echo "  (openfda metformin fetch failed)"
curl -sL "https://api.fda.gov/drug/label.json?search=openfda.generic_name:lisinopril&limit=1" \
  -o "$OUT_DIR/drug_label/lisinopril.json" || echo "  (openfda lisinopril fetch failed)"

# --- SBC: CMS template ---
echo "  SBC docs are synthetic examples on the CMS SBC template:"
echo "    https://www.cms.gov/marketplace/resources/regulations-guidance/summary-benefits-coverage"

cat <<'EOF'

Done. Raw sources are under data_artifacts/kb_raw/ for review.
To update the corpus: condense a raw source into a heading-structured Markdown file
under carenav/rag/corpus/<source_type>/, keep the frontmatter fields, then re-run:
    make data-kb
EOF
