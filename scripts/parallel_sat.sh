#!/bin/bash
set -euo pipefail

INPUT="$1"
shift
EXTRA_ARGS=("$@")

STLCC="../target/release/stlcc"

parallel --halt now,success=1 ::: \
  "$STLCC ${EXTRA_ARGS[*]} $INPUT" \
  "$STLCC --fol ${EXTRA_ARGS[*]} $INPUT"
