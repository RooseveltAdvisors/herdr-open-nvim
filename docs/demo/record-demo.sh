#!/usr/bin/env bash
# Re-record docs/demo/open-in-nvim.gif against a real Herdr session.
#
# Drives a throwaway named Herdr session (its own server + socket, so the
# session you are working in is untouched) through the prefix+e flow while
# asciinema captures the pty, then renders the GIF with agg. Keystrokes are
# injected with `tmux send-keys`, which writes straight into the pty, so the
# outer tmux never eats the prefix.
#
# Requires: herdr, tmux, asciinema, agg, fzf, nvim, python3, ffmpeg.
# Usage: docs/demo/record-demo.sh [output-dir]
set -eu

REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:-$REPO/docs/demo}
WORK=$(mktemp -d)
CAST=$WORK/demo.cast
SESSION=herdr-open-nvim-demo
TMUX_SESSION=herdr-open-nvim-rec
trap 'rm -rf "$WORK"' EXIT

tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
herdr session stop "$SESSION" >/dev/null 2>&1 || true
herdr session delete "$SESSION" >/dev/null 2>&1 || true
# a swap file left by an interrupted take makes nvim open on a recovery prompt
rm -f "$HOME/.local/state/nvim/swap/"*herdr-open-nvim*pick-and-open.swp

tmux new-session -d -s "$TMUX_SESSION" -x 110 -y 36 -c "$REPO" \
    "cd '$REPO' && exec asciinema rec --overwrite -f asciicast-v2 -q -c 'herdr --session $SESSION' '$CAST'"
sleep 12
if tmux capture-pane -p -t "$TMUX_SESSION" | head -1 | grep -q 'spaces'; then
    tmux send-keys -t "$TMUX_SESSION" C-a b     # collapse the sidebar to its rail
    sleep 2
fi
tmux send-keys -t "$TMUX_SESSION" 'clear' Enter
sleep 2

type_slow() {
    local text=$1 i
    for ((i = 0; i < ${#text}; i++)); do
        tmux send-keys -t "$TMUX_SESSION" -l "${text:$i:1}"
        sleep 0.042
    done
    tmux send-keys -t "$TMUX_SESSION" Enter
}

# Fill the transcript with the file links the plugin extracts. The verbose test
# run matters: it scrolls the pane, so the plugin reads real retained
# scrollback rather than just the viewport.
sleep 1.5
type_slow 'python3 -m unittest discover -s tests -v'
sleep 2.2
type_slow 'grep -rnE "def (resolve|extract_targets|exec_nvim)\(" scripts/'
sleep 2.0
type_slow 'printf "wrote notes to file://%s/README.md\n" "$PWD"'
sleep 3.5

tmux send-keys -t "$TMUX_SESSION" C-a e   # prefix+e -> picker overlay
sleep 5.0
tmux send-keys -t "$TMUX_SESSION" Up      # newest-first list: one up == pick-and-open:259
sleep 3.5
tmux send-keys -t "$TMUX_SESSION" Enter   # nvim opens on line 259
sleep 8.0
tmux send-keys -t "$TMUX_SESSION" ':q' Enter
sleep 4.0
tmux send-keys -t "$TMUX_SESSION" 'exit' Enter
sleep 4
tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true

# Drop the session start-up, then render.
python3 - "$CAST" "$WORK/trimmed.cast" <<'PY'
import json, sys

src, dst = sys.argv[1], sys.argv[2]
lines = open(src).read().splitlines()
header, events = json.loads(lines[0]), [json.loads(l) for l in lines[1:] if l.strip()]
start = next(t for t, kind, data in events if "python3" in data) - 0.4
prelude = "".join(data for t, kind, data in events if t < start and kind == "o")
kept = [[round(t - start, 3), kind, data] for t, kind, data in events if t >= start]
out = [json.dumps(header), json.dumps([0.0, "o", prelude])]
out += [json.dumps([max(t, 0.01), kind, data]) for t, kind, data in kept]
open(dst, "w").write("\n".join(out) + "\n")
PY

agg --font-size 15 --idle-time-limit 1.4 --last-frame-duration 3 \
    "$WORK/trimmed.cast" "$OUT/open-in-nvim.gif"
echo "wrote $OUT/open-in-nvim.gif"
