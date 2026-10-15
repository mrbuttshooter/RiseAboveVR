#!/usr/bin/env bash
# Usage: gen.sh <name> <round> <prompt-file>
# Asks Gemini 3.8 Flash (High, max effort) for a Blender script, safety-checks it, builds + renders it.
set -u
cd "$(dirname "$0")"
NAME="$1"; ROUND="$2"; PROMPT_FILE="$3"
AGY="/c/Users/User/AppData/Local/Microsoft/WinGet/Packages/Google.AntigravityCLI_Microsoft.Winget.Source_8wekyb3d8bbwe/agy.exe"
BLENDER="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
mkdir -p scripts out logs
RAW="scripts/${NAME}_r${ROUND}.raw.txt"
PY="scripts/${NAME}_r${ROUND}.py"
OUT="E:/Unity_project/_gen3d/out/${NAME}_r${ROUND}.fbx"

"$AGY" --model "Gemini 3.8 Flash (High)" --print-timeout 900s -p "$(cat "$PROMPT_FILE")" > "$RAW" 2> "logs/${NAME}_r${ROUND}.agy.txt"
# Keep only the code (drop markdown fences / chatter before the first import).
python - "$RAW" "$PY" <<'EOF'
import sys, re
t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r"```(?:python)?\n(.*?)```", t, re.S)
if m: t = m.group(1)
i = t.find("import ")
if i > 0: t = t[i:]
open(sys.argv[2], "w", encoding="utf-8").write(t)
EOF
LINES=$(wc -l < "$PY")
if [ "$LINES" -lt 30 ]; then echo "GEN-FAIL: only $LINES lines"; head -20 "$RAW"; tail -5 "logs/${NAME}_r${ROUND}.agy.txt"; exit 1; fi
# Safety: AI-written code must not touch the network, run programs or delete files.
if grep -nE "subprocess|import socket|from socket|urllib|import requests|http\.client|shutil|os\.remove|os\.unlink|rmtree|os\.system|popen|exec\(|eval\(|__import__|ctypes|winreg" "$PY"; then echo "UNSAFE: refusing to run"; exit 2; fi
"$BLENDER" -b --factory-startup -P "$PY" -- "$OUT" > "logs/${NAME}_r${ROUND}.blender.txt" 2>&1
echo "script: $LINES lines"
grep -E "^TRIS|Error|Traceback|line [0-9]+, in" "logs/${NAME}_r${ROUND}.blender.txt" | head -8
ls -la "out/${NAME}_r${ROUND}".* 2>/dev/null
