#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION="$(
    PYTHONPATH="$PROJECT_ROOT/src" \
        python3 -c 'from gyte_study_tools import __version__; print(__version__)'
)"

INSTALL_BASE="$HOME/.local/share/gyte-ai-learning-pipeline"
INSTALL_ROOT="$INSTALL_BASE/$VERSION"
BIN_ROOT="$HOME/.local/bin"

COMMANDS=(
    gyte-editorial-candidate
    gyte-fact-check
    gyte-lesson-kindle
    gyte-publication-reproducibility
    gyte-public-candidate
    gyte-repository-handoff
)

if [ ! -d "$PROJECT_ROOT/src/gyte_study_tools" ]; then
    echo "ERROR: GYTE AI Learning Pipeline Python sources are missing." >&2
    exit 1
fi

for command in "${COMMANDS[@]}"; do
    if [ ! -f "$PROJECT_ROOT/bin/$command" ]; then
        echo "ERROR: command source is missing: bin/$command" >&2
        exit 1
    fi
done

for command in "${COMMANDS[@]}"; do
    destination="$BIN_ROOT/$command"
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        echo "ERROR: command destination already exists: $destination" >&2
        echo "Remove or relocate it explicitly before installing this release." >&2
        exit 1
    fi
done

if [ -e "$INSTALL_ROOT" ]; then
    echo "ERROR: version $VERSION is already installed: $INSTALL_ROOT" >&2
    exit 1
fi

mkdir -p "$INSTALL_ROOT" "$BIN_ROOT"

cp -R "$PROJECT_ROOT/src" "$INSTALL_ROOT/src"
mkdir -p "$INSTALL_ROOT/bin"

for command in "${COMMANDS[@]}"; do
    source_command="$PROJECT_ROOT/bin/$command"
    installed_source="$INSTALL_ROOT/bin/$command.source"
    installed_command="$INSTALL_ROOT/bin/$command"

    cp "$source_command" "$installed_source"
    chmod +x "$installed_source"

    cat > "$installed_command" <<EOF
#!/usr/bin/env bash
INSTALL_ROOT="$INSTALL_ROOT"
export PYTHONPATH="\$INSTALL_ROOT/src\${PYTHONPATH:+:\$PYTHONPATH}"
exec "\$INSTALL_ROOT/bin/$command.source" "\$@"
EOF

    chmod +x "$installed_command"
    ln -sfn "$installed_command" "$BIN_ROOT/$command"
done

echo "GYTE AI Learning Pipeline $VERSION installed."
echo "Installation: $INSTALL_ROOT"
echo "Commands: $BIN_ROOT/gyte-*"
