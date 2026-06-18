#!/usr/bin/env bash
# task_runner.sh — Compact オーケストレータ (T-025)
# inotifywait で input/ を監視 → claude -p で自動実行
# 使い方: trun (alias)

WORKSPACE="/home/nilab/trun"
INPUT_DIR="$WORKSPACE/input"
RUNNING_DIR="$INPUT_DIR/running"
DONE_DIR="$INPUT_DIR/done"
FAILED_DIR="$INPUT_DIR/failed"
LOG_FILE="$WORKSPACE/task_runner.log"

mkdir -p "$RUNNING_DIR" "$DONE_DIR" "$FAILED_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

get_meta() {
  local file="$1" key="$2" default="$3"
  local val
  val=$(sed -n '/^---$/,/^---$/{ /^'"$key"':/{ s/^'"$key"': *//; s/ *$//; p; } }' "$file" || true)
  echo "${val:-$default}"
}

# YAMLフロントマター(---〜---)を除去して本文のみ返す
get_body() {
  local file="$1"
  if head -1 "$file" | grep -q '^---$'; then
    # 2つ目の---の行番号を取得し、その次の行から出力
    local end_line
    end_line=$(awk 'NR>1 && /^---$/{print NR; exit}' "$file")
    if [ -n "$end_line" ]; then
      tail -n +"$((end_line + 1))" "$file"
    else
      cat "$file"
    fi
  else
    cat "$file"
  fi
}

dispatch_file() {
  local filepath="$1"
  local filename
  filename=$(basename "$filepath")

  local model effort body running_path start_time end_time duration

  model=$(get_meta "$filepath" "model" "sonnet")
  effort=$(get_meta "$filepath" "effort" "high")

  log "▶ 検知: $filename (model=$model, effort=$effort)"

  mv "$filepath" "$RUNNING_DIR/$filename"
  running_path="$RUNNING_DIR/$filename"

  log "🚀 実行開始: $filename"
  start_time=$(date +%s)

  local exit_code=0
  cd "$WORKSPACE"
  claude -p --model "$model" --effort "$effort" < "$running_path" \
    > "$WORKSPACE/output/${filename%.md}_out.md" 2>&1 \
    || exit_code=$?

  end_time=$(date +%s)
  duration=$(( end_time - start_time ))

  if [ "$exit_code" -eq 0 ]; then
    mv "$running_path" "$DONE_DIR/$filename"
    log "✅ 完了: $filename (${duration}s)"
  else
    mv "$running_path" "$FAILED_DIR/$filename"
    log "❌ 失敗: $filename (${duration}s, exit=$exit_code)"
  fi
}

# --- メイン ---

log "=== task_runner 起動 ==="
log "監視対象: $INPUT_DIR"

# inotify監視ループ（起動時の残存ファイルは処理しない）

inotifywait -m -q "$INPUT_DIR" -e close_write --format '%f' | while read -r filename; do
  [[ "$filename" != *.md ]] && continue
  [[ "$filename" == _template.md ]] && continue
  [[ "$filename" == .* ]] && continue

  filepath="$INPUT_DIR/$filename"
  [ -f "$filepath" ] || continue

  dispatch_file "$filepath" &
done
