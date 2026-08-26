for f in *.dot; do
    echo "Processing $f"
    echo "Results for $f:\n" >> "result.paths"
    python3 ../parse_graph.py "$f" >> "result.paths"
done