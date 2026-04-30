#!/bin/sh
set -e

INSTALL_DIR="/home/claude/.local/bin"
BINARY="$INSTALL_DIR/github-mcp-server"

mkdir -p "$INSTALL_DIR"

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
  x86_64)  SRC="/workspace/.devcontainer/scripts/opt/github-mcp-server-linux-amd64" ;;
  aarch64) SRC="/workspace/.devcontainer/scripts/opt/github-mcp-server-linux-arm64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

if cp "$SRC" "$BINARY" 2>/dev/null; then
  chmod +x "$BINARY"
  echo "github-mcp-server installed at $BINARY"
else
  echo "⚠ github-mcp-server binary not found at $SRC (pre-installed or unavailable)"
fi
