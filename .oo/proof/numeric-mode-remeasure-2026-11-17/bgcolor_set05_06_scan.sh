#!/bin/bash
cd /mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript
/usr/bin/python .oo/proof/numeric-mode-remeasure-2026-11-17/scan_numeric_mode.py \
  --sets set05 set06 --match 'bgcolor' \
  --out .oo/proof/numeric-mode-remeasure-2026-11-17/scan_set05_06_bgcolor.json \
  > backscan.log 2>&1
echo "bgcolor scan exit=$?" >> status.txt
