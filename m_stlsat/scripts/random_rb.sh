#!/bin/bash

# Lists of possible values for parameters
NUM_BOOL_VARS_LIST=(0)
NUM_REAL_VARS_LIST=(5)
MAX_REAL_CONSTRAINTS_LIST=(10)
MAX_HORIZON_LIST=(100 500 1000 5000 10000)
MAX_INTERVAL_LIST=(50 1000)
P_STOP_BASE_LIST=(0.05 0.1 0.15 0.2 0.25)
P_TEMPORAL_LIST=(0.33 0.5 0.75 0.95)
NUM_CONJUNCTIONS_LIST=(5 10)
NUM_FORMULAS_LIST=5

# Calculate total number of formulas
total_combinations=$(( ${#NUM_BOOL_VARS_LIST[@]} * ${#NUM_REAL_VARS_LIST[@]} * ${#MAX_REAL_CONSTRAINTS_LIST[@]} * ${#MAX_HORIZON_LIST[@]} * ${#MAX_INTERVAL_LIST[@]} * ${#P_STOP_BASE_LIST[@]} * ${#P_TEMPORAL_LIST[@]} * ${#NUM_CONJUNCTIONS_LIST[@]} ))
total_formulas=$(( total_combinations * NUM_FORMULAS_LIST ))
echo "Total formulas to generate: $total_formulas"

# Output folder based on timestamp or random
OUTPUT_FOLDER="../resources/random"

# Loop over all combinations
for b in "${NUM_BOOL_VARS_LIST[@]}"; do
    for r in "${NUM_REAL_VARS_LIST[@]}"; do
        for c in "${MAX_REAL_CONSTRAINTS_LIST[@]}"; do
            for l in "${MAX_HORIZON_LIST[@]}"; do
                for i in "${MAX_INTERVAL_LIST[@]}"; do
                    for ps in "${P_STOP_BASE_LIST[@]}"; do
                        for pt in "${P_TEMPORAL_LIST[@]}"; do
                            for j in "${NUM_CONJUNCTIONS_LIST[@]}"; do
                                # Escape floats for prefix
                                ps_escaped=$(echo $ps | tr '.' '_')
                                pt_escaped=$(echo $pt | tr '.' '_')
                                # Create prefix
                                prefix="b${b}_r${r}_c${c}_l${l}_i${i}_ps${ps_escaped}_pt${pt_escaped}_j${j}"
                                # Call the rb binary
                                ../target/debug/rb \
                                    -o "$OUTPUT_FOLDER" \
                                    -p "$prefix" \
                                    -n "$NUM_FORMULAS_LIST" \
                                    -j "$j" \
                                    -b "$b" \
                                    -r "$r" \
                                    -c "$c" \
                                    -l "$l" \
                                    --max-interval "$i" \
                                    --p-stop-base "$ps" \
                                    --p-temporal "$pt"
                            done
                        done
                    done
                done
            done
        done
    done
done