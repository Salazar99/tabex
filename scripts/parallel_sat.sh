#!/bin/bash
set -euo pipefail

INPUT="$1"
shift
EXTRA_ARGS=("$@")

parallel --halt now,success=1 ::: \
  "target/release/stlcc ${EXTRA_ARGS[*]} $INPUT" \
  "target/release/stlcc --fol ${EXTRA_ARGS[*]} $INPUT"
