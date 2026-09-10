#!/bin/bash
# =========================================================
#  Battery Guardian - Desinstalador
# =========================================================
set -e

AUTOSTART_FILE="$HOME/.config/autostart/battery-guardian.desktop"
DESKTOP_FILE="$HOME/.local/share/applications/battery-guardian.desktop"
BIN_LINK="$HOME/.local/bin/battery-guardian"

echo "🔋 Desinstalando Battery Guardian..."

# Detener procesos activos
pkill -f battery_guardian.py 2>/dev/null || true

# Eliminar archivos
[ -f "$AUTOSTART_FILE" ] && rm -f "$AUTOSTART_FILE" && echo "✓ Autostart eliminado"
[ -f "$DESKTOP_FILE" ]   && rm -f "$DESKTOP_FILE"   && echo "✓ Acceso del menú eliminado"
[ -L "$BIN_LINK" ]       && rm -f "$BIN_LINK"       && echo "✓ Enlace simbólico eliminado"

echo ""
echo "✅ Desinstalación completada."
echo "   (La configuración en ~/.config/battery_guardian se conserva)."
echo "   Para borrarla también:  rm -rf ~/.config/battery_guardian"
