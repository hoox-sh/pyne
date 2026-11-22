#!/bin/bash
cd /mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript
PROOF=.oo/proof/numeric-mode-remeasure-2026-11-17
PYNE=$(which pyne)
echo "pyne=$PYNE version=$($PYNE --version) started=$(date -Is)" >> "$PROOF/status.txt"
for MODE in parse interpret compile auto; do
  echo "mode=$MODE start=$(date -Is)" >> "$PROOF/status.txt"
  "$PYNE" corpus run set05 set06 --workers 4 --rich --mode "$MODE" \
    --out "$PROOF/corpus-$MODE.csv" \
    > "$PROOF/corpus-$MODE.log" 2>&1
  rc=$?
  echo "mode=$MODE exit=$rc end=$(date -Is)" >> "$PROOF/status.txt"
done
echo "corpus all modes done $(date -Is)" >> "$PROOF/status.txt"
