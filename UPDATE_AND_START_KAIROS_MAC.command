#!/bin/zsh
# Double-click on first use or after requirements.txt changes.
SCRIPT_DIR="${0:A:h}"
exec "$SCRIPT_DIR/START_KAIROS_MAC.command" --update
