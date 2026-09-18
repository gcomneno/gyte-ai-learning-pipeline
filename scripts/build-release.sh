#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OUTPUT_DIR="${1:-$PROJECT_ROOT/dist}"

VERSION="$(
    PYTHONPATH="$PROJECT_ROOT/src" \
        python3 -c 'from gyte_study_tools import __version__; print(__version__)'
)"

case "$VERSION" in
    *-dev)
        echo "ERROR: refusing to build a release from development version: $VERSION" >&2
        exit 1
        ;;
esac

RELEASE_NAME="gyte-ai-learning-pipeline-$VERSION"
ARCHIVE_NAME="$RELEASE_NAME.tar.gz"

STAGING_PARENT="$(mktemp -d)"
STAGING_ROOT="$STAGING_PARENT/$RELEASE_NAME"

cleanup() {
    rm -rf "$STAGING_PARENT"
}
trap cleanup EXIT

mkdir -p \
    "$STAGING_ROOT/bin" \
    "$STAGING_ROOT/docs" \
    "$STAGING_ROOT/scripts" \
    "$STAGING_ROOT/src" \
    "$STAGING_ROOT/consumer-contracts" \
    "$STAGING_ROOT/prompts" \
    "$STAGING_ROOT/templates"

cp "$PROJECT_ROOT/README.md" "$STAGING_ROOT/README.md"
cp "$PROJECT_ROOT/CHANGELOG.md" "$STAGING_ROOT/CHANGELOG.md"
cp "$PROJECT_ROOT/docs/installation.md" "$STAGING_ROOT/docs/installation.md"
cp "$PROJECT_ROOT/docs/release-notes-v0.5.0.md" \
    "$STAGING_ROOT/docs/release-notes-v0.5.0.md"

cp -R "$PROJECT_ROOT/src/gyte_study_tools" "$STAGING_ROOT/src/"

for command in "$PROJECT_ROOT"/bin/gyte-*; do
    cp "$command" "$STAGING_ROOT/bin/"
done

cp "$PROJECT_ROOT/scripts/install-local.sh" "$STAGING_ROOT/scripts/"
cp -R "$PROJECT_ROOT/consumer-contracts/." "$STAGING_ROOT/consumer-contracts/"
cp -R "$PROJECT_ROOT/prompts/." "$STAGING_ROOT/prompts/"
cp -R "$PROJECT_ROOT/templates/." "$STAGING_ROOT/templates/"

find "$STAGING_ROOT" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGING_ROOT" -type f -name '*.pyc' -delete

mkdir -p "$OUTPUT_DIR"

ARCHIVE_PATH="$OUTPUT_DIR/$ARCHIVE_NAME"
CHECKSUM_PATH="$OUTPUT_DIR/SHA256SUMS"

rm -f "$ARCHIVE_PATH" "$CHECKSUM_PATH"

tar \
    --sort=name \
    --mtime='UTC 1970-01-01' \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    --format=gnu \
    -C "$STAGING_PARENT" \
    -cf - \
    "$RELEASE_NAME" \
    | gzip -n > "$ARCHIVE_PATH"

(
    cd "$OUTPUT_DIR" &&
        sha256sum "$ARCHIVE_NAME" > SHA256SUMS
)

echo "Release artifact: $ARCHIVE_PATH"
echo "Checksums: $CHECKSUM_PATH"
