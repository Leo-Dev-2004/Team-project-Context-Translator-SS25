#!/usr/bin/env bash
set -euo pipefail

# Render a Mermaid diagram into one canonical SVG and one canonical PNG in the
# `diagrams/` folder. Also archive timestamped copies into `diagrams/.bin`.
# Usage: ./scripts/render-diagram.sh [--non-interactive] <input-mermaid> [output-base]

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIAGRAMS_DIR="$ROOT_DIR/diagrams"
BIN_DIR="$DIAGRAMS_DIR/.bin"
mkdir -p "$BIN_DIR"

NON_INTERACTIVE=0
if [[ "${1:-}" == "--non-interactive" ]]; then
  NON_INTERACTIVE=1
  shift
fi

INPUT=${1:-$DIAGRAMS_DIR/architecture.mermaid}
OUT_BASE=${2:-$(basename "$INPUT" | sed -E 's/\.(mmd|mermaid|md)$//')-architecture}

CANONICAL_SVG="$DIAGRAMS_DIR/${OUT_BASE}.svg"
CANONICAL_PNG="$DIAGRAMS_DIR/${OUT_BASE}.png"

echo "[render-diagram] input=$INPUT out_base=$OUT_BASE"

if [[ ! -f "$INPUT" ]]; then
  echo "[render-diagram] ERROR: input file not found: $INPUT" >&2
  exit 3
fi

# Work against a temporary copy so we never modify the source
TMP_SRC="$(mktemp --suffix .mmd)"
cp -f "$INPUT" "$TMP_SRC"

# Render SVG robustly with retries
MERMAID_CLI=( npx -y @mermaid-js/mermaid-cli -i "$TMP_SRC" -o )
MAX_ATTEMPTS=3
ATTEMPT=1
BACKOFF=2
SVG_TMP=""
while (( ATTEMPT <= MAX_ATTEMPTS )); do
  echo "[render-diagram] mermaid attempt $ATTEMPT/$MAX_ATTEMPTS"
  SVG_TMP="$(mktemp --suffix .svg)"
  # mermaid-cli wants the output path as the last arg
  if ( "${MERMAID_CLI[@]}" "$SVG_TMP" ) 2> /dev/null; then
    echo "[render-diagram] mermaid-cli succeeded"
    break
  else
    echo "[render-diagram] mermaid-cli failed on attempt $ATTEMPT"
    rm -f "$SVG_TMP" || true
    if (( ATTEMPT == MAX_ATTEMPTS )); then
      echo "[render-diagram] reached max attempts, aborting" >&2
      rm -f "$TMP_SRC" || true
      exit 6
    fi
    sleep $BACKOFF
    BACKOFF=$(( BACKOFF * 2 ))
    ATTEMPT=$(( ATTEMPT + 1 ))
  fi
done

if [[ ! -f "$SVG_TMP" || ! -s "$SVG_TMP" ]]; then
  echo "[render-diagram] ERROR: SVG missing or empty" >&2
  rm -f "$TMP_SRC" || true
  exit 7
fi

if ! grep -q "<svg" "$SVG_TMP"; then
  echo "[render-diagram] ERROR: generated SVG does not contain <svg tag" >&2
  rm -f "$TMP_SRC" "$SVG_TMP" || true
  exit 8
fi

echo "[render-diagram] SVG generated (temp): $SVG_TMP"

# Attempt PNG generation: prefer mermaid-cli if it supports direct PNG (rare), otherwise rsvg-convert, then ImageMagick flatten
MERMAID_PNG_DPI="${MERMAID_PNG_DPI:-300}"
PNG_TMP=""
PNG_OUT=""

echo "[render-diagram] PNG DPI set to $MERMAID_PNG_DPI"

# Try rsvg-convert if available
if command -v rsvg-convert >/dev/null 2>&1; then
  echo "[render-diagram] Converting SVG -> PNG with rsvg-convert"
  PNG_TMP="$(mktemp --suffix .png)"
  if rsvg-convert -o "$PNG_TMP" "$SVG_TMP"; then
    echo "[render-diagram] rsvg-convert created temporary PNG: $PNG_TMP"
    # Flatten with ImageMagick if available
    if command -v convert >/dev/null 2>&1; then
      echo "[render-diagram] Flattening PNG with ImageMagick (density $MERMAID_PNG_DPI)"
      if convert -density "$MERMAID_PNG_DPI" "$PNG_TMP" -background white -alpha remove -alpha off "$CANONICAL_PNG"; then
        PNG_OUT="$CANONICAL_PNG"
        rm -f "$PNG_TMP" || true
        echo "[render-diagram] Flattened PNG written: $PNG_OUT"
      else
        echo "[render-diagram] ImageMagick flatten failed; keeping tmp PNG: $PNG_TMP" >&2
        PNG_OUT="$PNG_TMP"
      fi
    else
      PNG_OUT="$PNG_TMP"
      echo "[render-diagram] ImageMagick not found; keeping rsvg-convert output at $PNG_TMP (may have transparency)"
    fi
  else
    echo "[render-diagram] rsvg-convert failed" >&2
    rm -f "$PNG_TMP" || true
    PNG_TMP=""
  fi
elif command -v convert >/dev/null 2>&1; then
  echo "[render-diagram] Using ImageMagick convert to produce PNG"
  if convert -density "$MERMAID_PNG_DPI" "$SVG_TMP" -background white -alpha remove -alpha off "$CANONICAL_PNG"; then
    PNG_OUT="$CANONICAL_PNG"
    echo "[render-diagram] ImageMagick convert created PNG: $PNG_OUT"
  else
    echo "[render-diagram] ImageMagick convert failed" >&2
  fi
else
  echo "[render-diagram] No PNG converter available; PNG will not be created" >&2
fi

# Atomically place canonical SVG into diagrams/
mv -f "$SVG_TMP" "$CANONICAL_SVG"
echo "[render-diagram] Canonical SVG written: $CANONICAL_SVG"

# If PNG_TMP was used and not moved, move/copy to canonical PNG location
if [[ -n "$PNG_OUT" && -f "$PNG_OUT" && "$PNG_OUT" != "$CANONICAL_PNG" ]]; then
  # PNG_OUT is a tmp file; move it to canonical location
  mv -f "$PNG_OUT" "$CANONICAL_PNG"
  echo "[render-diagram] Canonical PNG written: $CANONICAL_PNG"
fi

# Archive timestamped copies (copy, don't move) for traceability
TS=$(date +%s)
cp -f "$TMP_SRC" "$BIN_DIR/${OUT_BASE}-source-$TS.mmd" || true
if [[ -f "$CANONICAL_SVG" ]]; then
  cp -f "$CANONICAL_SVG" "$BIN_DIR/${OUT_BASE}-$TS.svg" || true
fi
if [[ -f "$CANONICAL_PNG" ]]; then
  cp -f "$CANONICAL_PNG" "$BIN_DIR/${OUT_BASE}-$TS.png" || true
fi

rm -f "$TMP_SRC" || true

echo "[render-diagram] Done. Canonical files:"
echo "  SVG: $CANONICAL_SVG"
if [[ -f "$CANONICAL_PNG" ]]; then
  echo "  PNG: $CANONICAL_PNG"
else
  echo "  PNG: (not generated)"
fi
echo "[render-diagram] Archived copies in: $BIN_DIR"

exit 0
#!/usr/bin/env bash
set -euo pipefail

# Robust mermaid render script for this repository
# Usage: ./scripts/render-diagram.sh [--non-interactive] <input-mermaid> [output-base]
# Produces: diagrams/.bin/<output-base>.svg and .png (if converter available)

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIAGRAMS_DIR="$ROOT_DIR/diagrams"
BIN_DIR="$DIAGRAMS_DIR/.bin"
mkdir -p "$BIN_DIR"

NON_INTERACTIVE=0
if [[ "${1:-}" == "--non-interactive" ]]; then
  NON_INTERACTIVE=1
  shift
fi

INPUT=${1:-$DIAGRAMS_DIR/architecture.mermaid}
OUT_BASE=${2:-$(basename "$INPUT" | sed -E 's/\.(mmd|mermaid|md)$//')-architecture}
SVG_OUT="$DIAGRAMS_DIR/${OUT_BASE}.svg"
PNG_OUT="$DIAGRAMS_DIR/${OUT_BASE}.png"
MD_OUT="$DIAGRAMS_DIR/${OUT_BASE}-todiagram.md"

echo "[render-diagram] input=$INPUT out_base=$OUT_BASE"

if [[ ! -f "$INPUT" ]]; then
  echo "[render-diagram] ERROR: input file not found: $INPUT" >&2
  exit 3
fi

# Best-effort ToDiagram publish
if [[ -n "${TODIAGRAM_API_KEY-}" ]]; then
  echo "[render-diagram] TODIAGRAM_API_KEY detected — publishing best-effort"
  # Prefer the helper script scripts/create_todiagram.js if present
  if [[ -x "$(dirname "$0")/create_todiagram.js" || -f "$(dirname "$0")/create_todiagram.js" ]]; then
    echo "[render-diagram] Using scripts/create_todiagram.js for ToDiagram publish"
    node "$(dirname "$0")/create_todiagram.js" || echo "[render-diagram] create_todiagram.js failed; continuing"
  else
    # Fallback: inline Node publish (original behavior)
    node -e "
const fs=require('fs'); const https=require('https'); const src=fs.readFileSync(process.argv[1],'utf8');
const data={ title: require('path').basename(process.argv[1]), content: src };
const opt={ method:'POST', headers:{ 'Content-Type':'application/json', 'Authorization':'Bearer '+process.env.TODIAGRAM_API_KEY } };
const req=https.request('https://todiagram.com/api/document', opt, res=>{ let b=''; res.on('data',c=>b+=c); res.on('end',()=>{ try{ const j=JSON.parse(b); if(j.url){ console.log('ToDiagram URL:', j.url); fs.writeFileSync(process.argv[2],'# ToDiagram link\n\n'+j.url); } else console.error('todiagram returned unexpected payload'); } catch(e){ console.error('todiagram publish parse error', e.message); }}); }); req.on('error',e=>console.error('todiagram request error', e.message)); req.write(JSON.stringify(data)); req.end(); " "$INPUT" "$MD_OUT" || echo "[render-diagram] ToDiagram publish failed; continuing"
  fi
fi

# Render SVG with retries
MERMAID_CMD=( npx -y @mermaid-js/mermaid-cli -i "$INPUT" -o "$SVG_OUT" )
max_attempts=3
attempt=1
backoff=2
tmp_err=""
while (( attempt <= max_attempts )); do
  echo "[render-diagram] mermaid attempt $attempt/$max_attempts"
  tmp_err="$(mktemp --suffix .log)"
  if ( "${MERMAID_CMD[@]}" ) 2> "$tmp_err"; then
    echo "[render-diagram] mermaid-cli succeeded"
    rm -f "$tmp_err" || true
    break
  else
    echo "[render-diagram] mermaid-cli failed on attempt $attempt"
    if (( attempt == max_attempts )); then
      echo "[render-diagram] reached max attempts, saving logs to $BIN_DIR" >&2
      cp -f "$tmp_err" "$BIN_DIR/mermaid-stderr-$(date +%s).log" || true
      mv -f "$INPUT" "$BIN_DIR/mermaid-source-$(date +%s).mmd" || true
      cat "$tmp_err" >&2 || true
      exit 6
    fi
    sleep $backoff
    backoff=$(( backoff * 2 ))
    attempt=$(( attempt + 1 ))
  fi
done

if [[ ! -f "$SVG_OUT" || ! -s "$SVG_OUT" ]]; then
  echo "[render-diagram] ERROR: SVG missing or empty: $SVG_OUT" >&2
  exit 7
fi

if ! grep -q "<svg" "$SVG_OUT"; then
  echo "[render-diagram] ERROR: SVG does not contain <svg tag" >&2
  cp -f "$SVG_OUT" "$BIN_DIR/$(basename "$SVG_OUT").suspect" || true
  exit 8
fi

echo "[render-diagram] SVG generated: $SVG_OUT"

# Generate PNG: prefer mermaid-cli direct PNG (Puppeteer-backed) to ensure fonts/text render correctly.
# Fallback: rsvg-convert then ImageMagick flattening to force white background.
# Configure PNG output DPI (density) for higher-resolution rasterization. Can be overridden via env var MERMAID_PNG_DPI.
MERMAID_PNG_DPI="${MERMAID_PNG_DPI:-300}"
echo "[render-diagram] PNG DPI set to $MERMAID_PNG_DPI"
PNG_OUT_TMP=""
PNG_OUT=""
MERMAID_PNG="$DIAGRAMS_DIR/${OUT_BASE}.png"
echo "[render-diagram] Attempting to generate PNG using mermaid-cli (preferred)"
# Try mermaid-cli direct PNG output to ensure accurate text rendering (if supported)
if npx -y @mermaid-js/mermaid-cli -i "$INPUT" -o "$PNG_OUT" --width 2000 --scale 2 2>/dev/null; then
  if [[ -f "$MERMAID_PNG" ]]; then
    PNG_OUT="$MERMAID_PNG"
    echo "[render-diagram] mermaid-cli produced PNG: $PNG_OUT"
  else
    echo "[render-diagram] mermaid-cli reported success but PNG not found; continuing to fallbacks"
    PNG_OUT=""
  fi
else
  echo "[render-diagram] mermaid-cli did not produce PNG (continuing to fallbacks)"
fi

if [[ -z "$PNG_OUT" ]]; then
  # Try rsvg-convert to produce a PNG (may preserve transparency)
  if command -v rsvg-convert >/dev/null 2>&1; then
    echo "[render-diagram] Converting SVG -> PNG with rsvg-convert"
    PNG_OUT_TMP="$(mktemp --suffix .png)"
    if rsvg-convert -o "$PNG_OUT_TMP" "$SVG_OUT"; then
      echo "[render-diagram] rsvg-convert created temporary PNG: $PNG_OUT_TMP"
      # If ImageMagick is available, flatten with density to improve resolution and remove transparency
      if command -v convert >/dev/null 2>&1; then
        echo "[render-diagram] Flattening and rasterizing temporary PNG with density $MERMAID_PNG_DPI"
        if convert -density "$MERMAID_PNG_DPI" "$PNG_OUT_TMP" -background white -alpha remove -alpha off "$MERMAID_PNG"; then
          PNG_OUT="$MERMAID_PNG"
          rm -f "$PNG_OUT_TMP" || true
          echo "[render-diagram] Flattened PNG written: $PNG_OUT"
        else
          echo "[render-diagram] ImageMagick flattening failed; keeping temporary PNG at $PNG_OUT_TMP" >&2
          PNG_OUT="$PNG_OUT_TMP"
        fi
      else
        PNG_OUT="$PNG_OUT_TMP"
        echo "[render-diagram] ImageMagick not found; keeping rsvg-convert output at $PNG_OUT_TMP (may have transparency)"
      fi
    else
      echo "[render-diagram] rsvg-convert failed" >&2
      rm -f "$PNG_OUT_TMP" || true
      PNG_OUT_TMP=""
      PNG_OUT=""
    fi
  fi
fi

if [[ -z "$PNG_OUT" ]]; then
  if command -v convert >/dev/null 2>&1; then
    # As a last resort, try ImageMagick convert from the SVG directly and flatten to white
    echo "[render-diagram] Flattening temporary PNG to white background with ImageMagick convert"
    if convert -background white -alpha remove -alpha off "$SVG_OUT" "$MERMAID_PNG"; then
      PNG_OUT="$MERMAID_PNG"
      echo "[render-diagram] ImageMagick convert created PNG: $PNG_OUT"
    else
      echo "[render-diagram] ImageMagick convert failed" >&2
      PNG_OUT=""
    fi
  fi
fi

# If rsvg-convert produced a PNG and ImageMagick is available, flatten it to white background for consistency
if [[ -n "$PNG_OUT_TMP" && -n "$PNG_OUT" && "$PNG_OUT" != "$PNG_OUT_TMP" && -f "$PNG_OUT_TMP" ]]; then
  if command -v convert >/dev/null 2>&1; then
    echo "[render-diagram] Flattening temporary PNG to white background (density $MERMAID_PNG_DPI)"
    if convert -density "$MERMAID_PNG_DPI" "$PNG_OUT_TMP" -background white -alpha remove -alpha off "$PNG_OUT"; then
      rm -f "$PNG_OUT_TMP" || true
      echo "[render-diagram] Flattened PNG written: $PNG_OUT"
    else
      echo "[render-diagram] Failed to flatten PNG; keeping temporary PNG at $PNG_OUT_TMP" >&2
      PNG_OUT="$PNG_OUT_TMP"
    fi
  fi
fi

if [[ -n "$PNG_OUT" && -f "$PNG_OUT" ]]; then
  png_size=$(stat --printf=%s "$PNG_OUT")
  if (( png_size < 512 )); then
    echo "[render-diagram] WARNING: generated PNG size small ($png_size bytes)"
  else
    echo "[render-diagram] PNG ready: $PNG_OUT ($png_size bytes)"
  fi
else
  echo "[render-diagram] PNG generation skipped or failed; no PNG available" >&2
fi

# Archive artifacts (SVG, PNG, mermaid source copy)
ts=$(date +%s)
mkdir -p "$BIN_DIR"
mv -f "$INPUT" "$BIN_DIR/${OUT_BASE}-source-$ts.mmd" || true
if [[ -f "$SVG_OUT" ]]; then
  # Move the canonical SVG into the archive (.bin) instead of copying it
  mv -f "$SVG_OUT" "$BIN_DIR/${OUT_BASE}-$ts.svg" || true
  SVG_ARCHIVE="$BIN_DIR/${OUT_BASE}-$ts.svg"
fi
if [[ -n "$PNG_OUT" && -f "$PNG_OUT" ]]; then
  # Keep the PNG in diagrams/ (user preference) but also archive a timestamped copy
  cp -f "$PNG_OUT" "$BIN_DIR/${OUT_BASE}-$ts.png" || true
fi

echo "[render-diagram] Done. Artifacts in $BIN_DIR"
if [[ -n "${SVG_ARCHIVE:-}" ]]; then
  echo "[render-diagram] SVG archived: $SVG_ARCHIVE"
else
  echo "[render-diagram] SVG: $SVG_OUT"
fi
if [[ -n "$PNG_OUT" ]]; then
  echo "[render-diagram] PNG: $PNG_OUT"
fi

exit 0
#!/usr/bin/env bash
set -euo pipefail

# Render script for mermaid diagrams.
# Behavior:
# 1) If TODIAGRAM_API_KEY is set, attempt to publish to ToDiagram (best-effort) and write a markdown with link.
# 2) Always render an SVG locally using @mermaid-js/mermaid-cli with absolute paths.
# 3) Produce descriptive filenames based on the source mermaid filename.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIAGRAMS_DIR="$ROOT_DIR/diagrams"
OUT_DIR="$DIAGRAMS_DIR/.bin"
mkdir -p "$OUT_DIR"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <path-to-mermaid-file> [output-name-base]"
  exit 2
fi

MERMAID_SRC="$1"
if [ ! -f "$MERMAID_SRC" ]; then
  echo "Mermaid source not found: $MERMAID_SRC"
  exit 3
fi

SRC_BASENAME="$(basename "$MERMAID_SRC" .mermaid)"
OUT_BASE="${2:-$SRC_BASENAME-architecture}"
SVG_OUT="$OUT_DIR/${OUT_BASE}.svg"
MD_OUT="$DIAGRAMS_DIR/${OUT_BASE}.md"

echo "Rendering mermaid source: $MERMAID_SRC"
echo "SVG output: $SVG_OUT"

# Try ToDiagram publish if API key present (best-effort)
if [ -n "${TODIAGRAM_API_KEY-}" ]; then
  echo "TODIAGRAM_API_KEY detected — attempting ToDiagram publish (best-effort)"
  node -e "
const fs=require('fs');
const path=require('path');
const https=require('https');
const src=fs.readFileSync(process.argv[1],'utf8');
const payload={ title: path.basename(process.argv[1]), content: src };
const options={ method:'POST', headers:{ 'Content-Type':'application/json', 'Authorization':'Bearer '+process.env.TODIAGRAM_API_KEY } };
const req=https.request('https://todiagram.com/api/document', options, res=>{ let body=''; res.on('data',c=>body+=c); res.on('end',()=>{ try{ const j=JSON.parse(body); if(j && j.url){ console.log('ToDiagram URL:', j.url); fs.writeFileSync(process.argv[2],'# ToDiagram link\n\n'+j.url); } else console.error('ToDiagram returned unexpected payload'); } catch(e){ console.error('ToDiagram publish failed:', e.message); } }); });
req.on('error', e=>{ console.error('ToDiagram request error:', e.message); });
req.write(JSON.stringify(payload)); req.end();
" "$MERMAID_SRC" "$MD_OUT" || echo "ToDiagram publish failed; continuing to local render"
fi

# Local render with mermaid-cli (deterministic). Retry on transient failures.
MERMAID_CLI="npx -y @mermaid-js/mermaid-cli"
RETRIES=2
DELAY=2
COUNT=0
while true; do
  set +e
  $MERMAID_CLI -i "$MERMAID_SRC" -o "$SVG_OUT"
  RC=$?
  set -e
  if [ $RC -eq 0 ]; then
    echo "Rendered SVG successfully: $SVG_OUT"
    break
  fi
  if [ $COUNT -ge $RETRIES ]; then
    echo "mermaid-cli failed after $((COUNT+1)) attempts (rc=$RC)." >&2
    exit $RC
  fi
  COUNT=$((COUNT+1))
  echo "Render failed (rc=$RC), retrying in $DELAY s..." >&2
  sleep $DELAY
  DELAY=$((DELAY*2))
done

# Validate output
if [ ! -s "$SVG_OUT" ]; then
  echo "SVG output missing or empty: $SVG_OUT" >&2
  exit 4
fi

echo "SVG created: $SVG_OUT"
echo "Also wrote (optional) ToDiagram markdown: $MD_OUT"

exit 0
#!/usr/bin/env bash
#!/usr/bin/env bash
set -euo pipefail

# Robust mermaid render helper for the repo.
# - Supports non-interactive CI runs
# - Allows overriding mermaid-cli command (MERMAID_CLI_CMD)
# - Captures renderer stderr for debugging
# - Validates output contains <svg
# Usage:
#   ./scripts/render-diagram.sh [--non-interactive] <input-file> [output-file]

NON_INTERACTIVE=0
if [[ "${1:-}" == "--non-interactive" ]]; then
  NON_INTERACTIVE=1
  shift
fi

INPUT=${1:-diagrams/architecture.mermaid}
OUTPUT=${2:-}

if [[ -z "$OUTPUT" ]]; then
  base=$(basename "$INPUT")
  dir=$(dirname "$INPUT")
  name="${base%.*}"
  OUTPUT="$dir/$name.svg"
fi

# Canonical absolute paths
real_input="$(realpath --canonicalize-missing "$INPUT")"
real_output="$(realpath --canonicalize-missing "$OUTPUT")"

# Temp files and cleanup
tmp_mermaid=""
tmp_errlog=""
cleanup() {
  if [[ -n "$tmp_mermaid" && -f "$tmp_mermaid" ]]; then
    rm -f "$tmp_mermaid"
  fi
  if [[ -n "$tmp_errlog" && -f "$tmp_errlog" ]]; then
    rm -f "$tmp_errlog"
  fi
}
trap cleanup EXIT

echo "[render-diagram] input=$real_input output=$real_output"

infer_existing_source() {
  for f in "$PWD/diagrams/architecture.mermaid" "$PWD/diagrams/architecture.mmd" "$PWD/diagrams/architecture.md"; do
    if [[ -f "$f" ]]; then
      echo "$f"
      return 0
    fi
  done
  return 1
}

if [[ $NON_INTERACTIVE -eq 0 && -t 0 ]]; then
  default_src=$(infer_existing_source || true)
  echo "[render-diagram] interactive mode detected. To run non-interactively use --non-interactive"
  read -r -p "Press Enter to continue (or Ctrl-C to cancel)..." || true
  if [[ -n "$default_src" ]]; then
    real_input="$default_src"
  fi
else
  # non-interactive: prefer detected source if it exists
  default_src=$(infer_existing_source || true)
  if [[ -n "$default_src" ]]; then
    real_input="$default_src"
  fi
fi

if [[ ! -f "$real_input" ]]; then
  output_dir_guess=$(dirname "$real_output")
  bin_candidate="$output_dir_guess/.bin/$(basename "$INPUT")"
  if [[ -f "$bin_candidate" ]]; then
    echo "[render-diagram] input not found at $real_input; using archived copy $bin_candidate"
    real_input="$(realpath "$bin_candidate")"
  else
    echo "[render-diagram] ERROR: input file not found: $real_input" >&2
    exit 3
  fi
fi

case "$real_input" in
  *.md|*.markdown)
    extracted_mermaid=$(mktemp --suffix .mermaid)
    echo "[render-diagram] extracting mermaid block from markdown to $extracted_mermaid"
    awk '/```mermaid/{flag=1;next}/```/{flag=0}flag' "$real_input" > "$extracted_mermaid"
    if [[ ! -s "$extracted_mermaid" ]]; then
      echo "[render-diagram] ERROR: no mermaid block found in $real_input" >&2
      exit 4
    fi
    source_mermaid="$extracted_mermaid"
    ;;
  *.mmd|*.mermaid)
    source_mermaid="$real_input"
    ;;
  *)
    echo "[render-diagram] Unsupported input type: $real_input" >&2
    exit 5
    ;;
esac

# Work from a temp copy so we never edit the canonical source
tmp_mermaid="$(mktemp --suffix .mermaid)"
cp -f "$source_mermaid" "$tmp_mermaid"
MERMAID="$tmp_mermaid"

# Render a Mermaid diagram robustly according to the repository runbook.

# Choose mermaid cli command. Allow override to avoid network installs in CI.
if [[ -n "${MERMAID_CLI_CMD:-}" ]]; then
  MERMAID_CMD=( $MERMAID_CLI_CMD -i "$MERMAID" -o "$real_output" )
else
  MERMAID_CMD=( npx -y @mermaid-js/mermaid-cli -i "$MERMAID" -o "$real_output" )
fi

# Attempt render with retries. Capture stderr on final failure for debugging.
max_attempts=3
attempt=1
backoff=2
while (( attempt <= max_attempts )); do
  echo "[render-diagram] attempt $attempt/$max_attempts"
  tmp_errlog="$(mktemp --suffix .log)"
  if ( "${MERMAID_CMD[@]}" ) 2> "$tmp_errlog"; then
    echo "[render-diagram] mermaid-cli succeeded"
    rm -f "$tmp_errlog" || true
    break
  else
    echo "[render-diagram] mermaid-cli failed on attempt $attempt"
    if (( attempt == max_attempts )); then
      echo "[render-diagram] reached max attempts, saving error log to .bin for inspection"
      # ensure bin dir exists and copy logs
      output_dir=$(dirname "$real_output")
      bin_dir="$output_dir/.bin"
      mkdir -p "$bin_dir"
      cp -f "$tmp_errlog" "$bin_dir/mermaid-stderr-$(date +%s).log" || true
      cp -f "$MERMAID" "$bin_dir/mermaid-source-$(date +%s).mmd" || true
      echo "[render-diagram] ERROR: mermaid-cli failed. See $bin_dir for logs and sanitized source" >&2
      cat "$tmp_errlog" >&2 || true
      exit 6
    fi
    sleep $backoff
    backoff=$(( backoff * 2 ))
    attempt=$(( attempt + 1 ))
  fi
done

# Quick sanity check on SVG content: ensure it contains <svg
if [[ ! -f "$real_output" ]]; then
  echo "[render-diagram] ERROR: output not created: $real_output" >&2
  exit 7
fi
if ! grep -q "<svg" "$real_output"; then
  echo "[render-diagram] ERROR: output created but does not contain <svg tag (render likely failed)" >&2
  # store suspect output
  output_dir=$(dirname "$real_output")
  bin_dir="$output_dir/.bin"
  mkdir -p "$bin_dir"
  cp -f "$real_output" "$bin_dir/$(basename "$real_output").suspect" || true
  exit 8
fi

# Verify non-trivial size (but accept small diagrams)
size=$(stat --printf=%s "$real_output")
if (( size < 512 )); then
  echo "[render-diagram] WARNING: output size small ($size bytes) but contains <svg>"
fi

# Attempt deterministic SVG -> PNG conversion (optional, but enabled)
PNG_OUT="${real_output%.*}.png"
if command -v rsvg-convert >/dev/null 2>&1; then
  echo "[render-diagram] Converting SVG -> PNG using rsvg-convert"
  if ! rsvg-convert -o "$PNG_OUT" "$real_output"; then
    echo "[render-diagram] rsvg-convert failed to produce PNG" >&2
    PNG_OUT=""
  fi
elif command -v convert >/dev/null 2>&1; then
  echo "[render-diagram] Converting SVG -> PNG using ImageMagick convert"
  if ! convert "$real_output" "$PNG_OUT"; then
    echo "[render-diagram] ImageMagick convert failed to produce PNG" >&2
    PNG_OUT=""
  fi
else
  echo "[render-diagram] No SVG->PNG converter (rsvg-convert or convert) found; skipping PNG generation"
  PNG_OUT=""
fi

if [[ -n "$PNG_OUT" && -f "$PNG_OUT" ]]; then
  png_size=$(stat --printf=%s "$PNG_OUT")
  if (( png_size < 512 )); then
    echo "[render-diagram] WARNING: generated PNG size small ($png_size bytes)"
  else
    echo "[render-diagram] PNG created: $PNG_OUT ($png_size bytes)"
  fi
fi

echo "[render-diagram] SUCCESS: $real_output ($size bytes)"

# Post-render: move non-PNG files (except canonical input) into .bin for archival
output_dir=$(dirname "$real_output")
bin_dir="$output_dir/.bin"
mkdir -p "$bin_dir"
shopt -s dotglob
for f in "$output_dir"/*; do
  if [[ "$f" == "$bin_dir" ]]; then
    continue
  fi
  if [[ -f "$f" && "$f" == *.png ]]; then
    continue
  fi
  if [[ -e "$f" && "$(realpath "$f")" == "$(realpath --canonicalize-missing "$INPUT")" ]]; then
    # preserve canonical input
    continue
  fi
  if [[ -e "$f" && "$f" != "$real_output" ]]; then
    mv -f "$f" "$bin_dir" || true
  fi
done
shopt -u dotglob

echo "[render-diagram] cleanup complete; artifacts saved in $bin_dir"

exit 0
# Usage:
#   ./scripts/render-diagram.sh <input-file> [output-file]
# If input is a markdown file containing a fenced ```mermaid block, the script
# will extract it to a temporary file before rendering.

INPUT=${1:-diagrams/architecture.mermaid}
OUTPUT=${2:-}

if [[ -z "$OUTPUT" ]]; then
  base=$(basename "$INPUT")
  dir=$(dirname "$INPUT")
  name="${base%.*}"
  OUTPUT="$dir/$name.svg"
fi

#!/usr/bin/env bash
set -euo pipefail

# Render a Mermaid diagram robustly according to the repository runbook.
# Usage:
#   ./scripts/render-diagram.sh <input-file> [output-file]
# If input is a markdown file containing a fenced ```mermaid block, the script
# will extract it to a temporary file before rendering.

INPUT=${1:-diagrams/architecture.mermaid}
OUTPUT=${2:-}

if [[ -z "$OUTPUT" ]]; then
  base=$(basename "$INPUT")
  dir=$(dirname "$INPUT")
  name="${base%.*}"
  OUTPUT="$dir/$name.svg"
fi

real_input="$(realpath --canonicalize-missing "$INPUT")"
real_output="$(realpath --canonicalize-missing "$OUTPUT")"

tmp_mermaid=""
cleanup() {
  if [[ -n "$tmp_mermaid" && -f "$tmp_mermaid" ]]; then
    rm -f "$tmp_mermaid"
  fi
}
trap cleanup EXIT

echo "[render-diagram] input=$real_input output=$real_output"

# --- Interactive prompt / inference support
# If run in an interactive terminal, ask the user a short set of questions
# (processes, connections, queues, styling, output format). If the user
# accepts defaults (presses Enter) the script will use existing mermaid sources.

infer_existing_source() {
  # prefer .mermaid, then .mmd, then .md
  for f in "$PWD/diagrams/architecture.mermaid" "$PWD/diagrams/architecture.mmd" "$PWD/diagrams/architecture.md"; do
    if [[ -f "$f" ]]; then
      echo "$f"
      return 0
    fi
  done
  return 1
}

extract_node_labels() {
  local src="$1"
  # crude extraction of labels that look like ID[Label] or ID[Label text]
  if [[ -f "$src" ]]; then
    grep -oP "\w+\[([^]]+)\]" "$src" | sed -E 's/\w+\[//;s/\]$//' | sed 's/^ *//;s/ *$//' | uniq
  fi
}

if [[ -t 0 ]]; then
  # interactive; compute defaults
  default_src=$(infer_existing_source || true)
  default_out="$PWD/diagrams/architecture.svg"
  echo "[render-diagram] interactive mode detected. I'll ask 6 quick questions; press Enter to accept defaults."

  # Q1: processes
  echo
  echo "1) Processes to show (comma-separated). Default: use existing source"
  if [[ -n "$default_src" ]]; then
    echo "   detected source: $default_src"
    echo "   detected nodes:"
    extract_node_labels "$default_src" | sed -n '1,20p' || true
  fi
  read -r -p "   Processes (or leave blank to use existing): " answer_processes

  #!/usr/bin/env bash
  set -euo pipefail

  # Render a Mermaid diagram robustly according to the repository runbook.
  # Usage:
  #   ./scripts/render-diagram.sh <input-file> [output-file]
  # If input is a markdown file containing a fenced ```mermaid block, the script
  # will extract it to a temporary file before rendering.

  INPUT=${1:-diagrams/architecture.mermaid}
  OUTPUT=${2:-}

  if [[ -z "$OUTPUT" ]]; then
    base=$(basename "$INPUT")
    dir=$(dirname "$INPUT")
    name="${base%.*}"
    OUTPUT="$dir/$name.svg"
  fi

  real_input="$(realpath --canonicalize-missing "$INPUT")"
  real_output="$(realpath --canonicalize-missing "$OUTPUT")"

  tmp_mermaid=""
  cleanup() {
    if [[ -n "$tmp_mermaid" && -f "$tmp_mermaid" ]]; then
      rm -f "$tmp_mermaid"
    fi
  }
  trap cleanup EXIT

  echo "[render-diagram] input=$real_input output=$real_output"
          echo "  ${part}" >> "$gen_file"
        fi
      done
    fi
    # add queue node
    if [[ -n "$answer_queues" ]]; then
      qid="AI_Queues"
      echo "  ${qid}[\"${answer_queues}\"]" >> "$gen_file"
    fi
    # extra notes (as a note node)
    if [[ -n "$answer_extra" ]]; then
      echo "  Note[\"${answer_extra}\"]" >> "$gen_file"
    fi

    echo "[render-diagram] generated mermaid source at $gen_file"
    # use generated file as the source
    real_input="$gen_file"
  else
    # no custom input provided — use existing source
    if [[ -n "$default_src" ]]; then
      real_input="$default_src"
    fi
  fi
fi

# If input is a markdown file, extract the mermaid block
# If the requested input doesn't exist at the path provided, try to find a copy
# in the target .bin directory (this happens when previous runs archived sources).
if [[ ! -f "$real_input" ]]; then
  output_dir_guess=$(dirname "$real_output")
  bin_candidate="$output_dir_guess/.bin/$(basename "$INPUT")"
  if [[ -f "$bin_candidate" ]]; then
    echo "[render-diagram] input not found at $real_input; using archived copy $bin_candidate"
    real_input="$(realpath "$bin_candidate")"
  else
    echo "[render-diagram] ERROR: input file not found: $real_input" >&2
    exit 3
  fi
fi

# Determine source type and if necessary extract mermaid block from markdown.
case "$real_input" in
  *.md|*.markdown)
    extracted_mermaid=$(mktemp --suffix .mermaid)
    echo "[render-diagram] extracting mermaid block from markdown to $extracted_mermaid"
    awk '/```mermaid/{flag=1;next}/```/{flag=0}flag' "$real_input" > "$extracted_mermaid"
    if [[ ! -s "$extracted_mermaid" ]]; then
      echo "[render-diagram] ERROR: no mermaid block found in $real_input" >&2
      exit 4
    fi
    source_mermaid="$extracted_mermaid"
    ;;
  *.mmd|*.mermaid)
    source_mermaid="$real_input"
    ;;
  *)
    echo "[render-diagram] Unsupported input type: $real_input" >&2
    exit 5
    ;;
esac

# Always render from a temporary working copy so the canonical source isn't touched by cleanup.
tmp_mermaid="$(mktemp --suffix .mermaid)"
cp -f "$source_mermaid" "$tmp_mermaid"
MERMAID="$tmp_mermaid"

echo "[render-diagram] using mermaid source: $MERMAID"

# Retry logic
max_attempts=3
attempt=1
backoff=2
while (( attempt <= max_attempts )); do
  echo "[render-diagram] attempt $attempt/$max_attempts"
  if npx -y @mermaid-js/mermaid-cli -i "$MERMAID" -o "$real_output"; then
    echo "[render-diagram] mermaid-cli succeeded"
    break
  else
    echo "[render-diagram] mermaid-cli failed on attempt $attempt"
    if (( attempt == max_attempts )); then
      echo "[render-diagram] reached max attempts, aborting" >&2
      exit 5
    fi
    sleep $backoff
    backoff=$(( backoff * 2 ))
    attempt=$(( attempt + 1 ))
  fi
done

# Verify output exists and is > 1KB
if [[ ! -f "$real_output" ]]; then
  echo "[render-diagram] ERROR: output not created: $real_output" >&2
  exit 6
fi
size=$(stat --printf=%s "$real_output")
if (( size < 1024 )); then
  echo "[render-diagram] ERROR: output size too small ($size bytes)" >&2
  exit 7
fi

echo "[render-diagram] SUCCESS: $real_output ($size bytes)"

# --- Post-render cleanup: move everything except PNGs into a temporary bin folder
# The bin folder is flushed at the start of each run (older contents deleted).
output_dir=$(dirname "$real_output")
bin_dir="$output_dir/.bin"
mkdir -p "$bin_dir"
# Flush existing bin contents
if [[ -d "$bin_dir" ]]; then
  rm -rf "$bin_dir"/* || true
fi

echo "[render-diagram] moving non-PNG files from $output_dir to $bin_dir"
shopt -s dotglob
for f in "$output_dir"/*; do
  # skip bin dir
  if [[ "$f" == "$bin_dir" ]]; then
    continue
  fi
  # skip PNG files (keep them in place)
  if [[ -f "$f" && "$f" == *.png ]]; then
    continue
  fi
  # do not move the canonical input file (keep it in place); skip if basename matches the provided INPUT
  if [[ -e "$f" && "$(realpath "$f")" == "$(realpath --canonicalize-missing "$INPUT")" ]]; then
    echo "[render-diagram] preserving canonical input: $f"
    continue
  fi
  # move everything else into bin (including directories and SVGs)
  mv -f "$f" "$bin_dir" || true
done
shopt -u dotglob

echo "[render-diagram] cleanup complete; non-PNG files saved in $bin_dir"

# Copy the workflow/runbook into the bin so it's stored alongside artifacts
workflow_file="$(pwd)/generate_diagram_workflow.md"
if [[ -f "$workflow_file" ]]; then
  cp -f "$workflow_file" "$bin_dir/" || true
  echo "[render-diagram] workflow saved to $bin_dir/$(basename "$workflow_file")"
else
  echo "[render-diagram] workflow file not found: $workflow_file (skipping)"
fi

exit 0
