#!/bin/bash
# This script is used to run the similarity benchmark for the manual formulas. It will run the run_similarity.py script for each pair of formulas and save the results in a file called similarity_results.txt.
# For the manual formulas, we will use the following pairs of formulas:
#1. F[0,2](x>0) and G[0,2](x>0)
#2. F[0,2](x>0) and F[3,4](x>0)
#3. F[0,2](z>0) and F[0,2](x>0)
#4. F[0,2](x>0) and F[0,2](x>0 || y>0)
#5. F[0,2](x>0) and F[0,2](x>0 && y>0)
export TABEX_ROOT=~/tabex
rm -rf results.txt

#1
# INPUTS
IN1="F[0,2](x>0)"
IN2="G[0,2](x>0)"

# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt

#2
# INPUTS
IN1="F[0,2](x>0)"
IN2="F[3,4](x>0)"
# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt

#3
# INPUTS
IN1="F[0,2](z>0)"
IN2="F[0,2](x>0)"

# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt

#4
# INPUTS
IN1="G[0,2](x>0)"
IN2="G[0,2](x>0 || y>0)"

# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt

#5
# INPUTS
IN1="G[0,2](x>0)"
IN2="G[0,2](x>0 && y>0)"

# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt

# INPUTS
IN1="F[0,2](x>0 && y>0)"
IN2="F[0,2](x>0 || y>0)"

# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt

#5
# INPUTS
IN1="F[0,2](x<5)"
IN2="F[0,2](x>0)"

# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt

#6
# INPUTS
IN1="F[0,4](x>0)"
IN2="F[0,2](x>0)"

# 1. Scrive gli input nel file tra virgolette
echo "Formula1: $IN1 Formula2: $IN2" >> results.txt
# 2. Esegue il file Python e appende lo standard output (stdout)
python3 ../../run_similarity.py "$IN1" "$IN2" >> results.txt
# 3. Aggiunge una riga vuota per leggibilità (opzionale)
echo "" >> results.txt