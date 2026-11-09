#!/bin/bash
# Decompile Studio functions by address with Ghidra headless (no auto-analysis).
# usage: dc.sh OUTDIR 0xADDR [0xADDR...]   -> OUTDIR/<addr>.c
# First run imports the exe into ~/code/rs-re-ghidra (a few minutes).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$1; shift
EXE=${STUDIO_EXE:-$HOME/.local/share/rustudio/studio/RobloxStudioBeta.exe}
PROJ=${GHIDRA_PROJ:-$HOME/code/rs-re-ghidra}
GH=${GHIDRA_HOME:-$HOME/tools/ghidra_12.1.4_PUBLIC}
export JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/java-27-openjdk}
mkdir -p "$PROJ" "$OUT"
if [ -d "$PROJ/studio.rep" ]; then src=(-process "$(basename "$EXE")"); else src=(-import "$EXE"); fi
"$GH/support/analyzeHeadless" "$PROJ" studio "${src[@]}" -noanalysis -scriptPath "$HERE" \
  -postScript DecompileAt.java "$OUT" "$@" 2>&1 | grep -E "decompiled|ERROR|no function"
