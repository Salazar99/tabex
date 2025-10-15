#!/bin/bash

# Directory containing benchmark files
BENCHMARKS_DIR="../resources/benchmarks"
STLCC="../target/release/stlcc"

# Check if benchmarks directory exists
if [ ! -d "$BENCHMARKS_DIR" ]; then
    echo "Error: Benchmarks directory not found at $BENCHMARKS_DIR"
    exit 1
fi

# Check if stlcc binary exists
if [ ! -f "$STLCC" ]; then
    echo "Error: stlcc binary not found at $STLCC"
    exit 1
fi

echo "Running benchmarks..."
echo "===================="

# Iterate through all files in benchmarks directory
for benchmark in "$BENCHMARKS_DIR"/*; do
    if [ -f "$benchmark" ]; then
        filename=$(basename "$benchmark")
        echo "Benchmarking: $filename"
        
        "$STLCC" "$@" "$benchmark"
        
        echo "--------------------"
    fi
done

echo "Benchmarks completed."