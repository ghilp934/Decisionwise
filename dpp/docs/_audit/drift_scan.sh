#!/bin/bash
# Drift Scan - Forbidden Tokens Detection
# Target: public/docs, docs/pilot, public/llms.txt, main.py

OUTPUT="docs/_audit/drift_inventory.txt"
SCAN_PATHS=(
    "public/docs"
    "docs/pilot"
    "public/llms.txt"
    "public/llms-full.txt"
    "apps/api/dpp_api/main.py"
)

echo "============================================" > "$OUTPUT"
echo "DRIFT INVENTORY - Forbidden Token Scan" >> "$OUTPUT"
echo "Date: $(date)" >> "$OUTPUT"
echo "Project: Decisionwise API Platform (Decisionproof)" >> "$OUTPUT"
echo "============================================" >> "$OUTPUT"
echo "" >> "$OUTPUT"

FORBIDDEN_TOKENS=(
    "X-API-Key"
    "dw_live_"
    "dw_test_"
    "sk_live_"
    "sk_test_"
    "workspace_id"
    "plan_id"
    "Decision Credits"
)

for TOKEN in "${FORBIDDEN_TOKENS[@]}"; do
    echo "## Scanning for: $TOKEN" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    
    FOUND=0
    for PATH in "${SCAN_PATHS[@]}"; do
        if [ -e "$PATH" ]; then
            RESULTS=$(grep -rn "$TOKEN" "$PATH" 2>/dev/null || true)
            if [ -n "$RESULTS" ]; then
                echo "### Found in: $PATH" >> "$OUTPUT"
                echo '```' >> "$OUTPUT"
                echo "$RESULTS" >> "$OUTPUT"
                echo '```' >> "$OUTPUT"
                echo "" >> "$OUTPUT"
                FOUND=1
            fi
        fi
    done
    
    if [ $FOUND -eq 0 ]; then
        echo "✓ No occurrences found" >> "$OUTPUT"
        echo "" >> "$OUTPUT"
    fi
done

echo "============================================" >> "$OUTPUT"
echo "SCAN COMPLETE" >> "$OUTPUT"
echo "============================================" >> "$OUTPUT"

cat "$OUTPUT"
