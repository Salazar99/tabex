#!/bin/bash
# Runs the similarity benchmark for the manual formulas: run_similarity.py on
# each pair, appending the results to results.txt.
#
# Each block writes the two inputs, appends the script's stdout, then a blank
# line for readability.
#
# The pairs:
#  1. F[0,2](x>0)         and G[0,2](x>0)
#  2. F[0,2](x>0)         and F[3,4](x>0)
#  3. F[0,2](z>0)         and F[0,2](x>0)
#  4. G[0,2](x>0)         and G[0,2](x>0 || y>0)
#  5. G[0,2](x>0)         and G[0,2](x>0 && y>0)
#  6. F[0,2](x>0)         and F[0,2](x>0 || y>0 || z>0 || w>0)
#  7. F[0,2](x>0)         and F[0,2](x>0 && y>0 && z>0 && w>0)
#  8. F[0,2](x>0 && y>0)  and F[0,2](x>0 || y>0)
#  9. F[0,2](x<5)         and F[0,2](x>0)
# 10. F[0,4](x>0)         and F[0,2](x>0)
#
# --via definition is the denotational path (the default): it needs no
# cargo/z3, unlike --via tableau.

cd "$(dirname "$0")" || exit 1
ROOT="../.."
RUN="python3 $ROOT/run_similarity.py --via definition"

rm -f results.txt

#1
IN1="F[0,2](x>0)"
IN2="G[0,2](x>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#2
IN1="F[0,2](x>0)"
IN2="F[3,4](x>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#3
IN1="F[0,2](z>0)"
IN2="F[0,2](x>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#4
IN1="G[0,2](x>0)"
IN2="G[0,2](x>0 || y>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#5
IN1="G[0,2](x>0)"
IN2="G[0,2](x>0 && y>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#6
IN1="F[0,2](x>0)"
IN2="F[0,2](x>0 || y>0 || z>0 || w>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#7
IN1="F[0,2](x>0)"
IN2="F[0,2](x>0 && y>0 && z>0 && w>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#8
IN1="F[0,2](x>0 && y>0)"
IN2="F[0,2](x>0 || y>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#9
IN1="F[0,2](x<5)"
IN2="F[0,2](x>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt

#10
IN1="F[0,4](x>0)"
IN2="F[0,2](x>0)"
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
$RUN "$IN1" "$IN2" >> results.txt
echo "" >> results.txt
