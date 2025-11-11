#!/bin/bash
set -eu

INPUT=$1
shift

EXTRA_ARGS=("$@")
STLSAT="../target/release/stlsat"

parallel --tag --lb --halt now,success=1 -- \
  "$STLSAT ${EXTRA_ARGS[*]} $INPUT" \
  "$STLSAT --fol ${EXTRA_ARGS[*]} $INPUT"
