#!/bin/bash
# Lanzador rápido de Battery Guardian
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$PROJECT_DIR/battery_guardian.py" "$@"
