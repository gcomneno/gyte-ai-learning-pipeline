#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$PROJECT_ROOT/bin/gyte-lesson-kindle"
DESTINATION="$HOME/.local/bin/gyte-lesson-kindle"

mkdir -p "$HOME/.local/bin"

if [ ! -x "$SOURCE" ]; then
    echo "ERRORE: comando sorgente assente o non eseguibile:"
    echo "$SOURCE"
    exit 1
fi

ln -sfn "$SOURCE" "$DESTINATION"

echo "OK: collegamento locale installato."
echo "$DESTINATION -> $SOURCE"
