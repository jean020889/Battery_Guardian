#!/bin/bash
# =========================================================
#  Battery Guardian - Instalador
# =========================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="$PROJECT_DIR/battery_guardian.py"
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/battery-guardian.desktop"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/battery-guardian.desktop"
BIN_DIR="$HOME/.local/bin"
BIN_LINK="$BIN_DIR/battery-guardian"

echo "🔋 Instalando Battery Guardian..."
echo "   Proyecto: $PROJECT_DIR"

# --- Comprobaciones ---
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 no está instalado."
    exit 1
fi

if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "❌ Tkinter no está instalado. Instálalo con:"
    echo "   sudo apt install python3-tk"
    exit 1
fi

if ! command -v upower &>/dev/null; then
    echo "❌ upower no está instalado. Instálalo con:"
    echo "   sudo apt install upower"
    exit 1
fi

# --- Permisos ---
chmod +x "$APP_FILE"

# --- Enlace simbólico en ~/.local/bin ---
mkdir -p "$BIN_DIR"
ln -sf "$APP_FILE" "$BIN_LINK"
echo "✓ Enlace creado: $BIN_LINK"

# --- Autostart ---
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_FILE" << DESKTOP
[Desktop Entry]
Type=Application
Name=Battery Guardian
Comment=Cuida la batería de tu portátil
Exec=python3 $APP_FILE
Icon=battery
Terminal=false
Categories=Utility;System;
X-GNOME-Autostart-enabled=true
DESKTOP
echo "✓ Autostart creado: $AUTOSTART_FILE"

# --- Menú de aplicaciones ---
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Type=Application
Name=Battery Guardian
Comment=Cuida la batería de tu portátil
Exec=python3 $APP_FILE
Icon=battery
Terminal=false
Categories=Utility;System;
DESKTOP
echo "✓ Acceso en menú creado: $DESKTOP_FILE"

# --- Asegurar que ~/.local/bin esté en PATH ---
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo ""
    echo "⚠  NOTA: Añade ~/.local/bin a tu PATH si no lo está:"
    echo '   echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
fi

echo ""
echo "✅ Instalación completada."
echo "   Ejecuta el programa con:  battery-guardian"
echo "   O búscalo en el menú de aplicaciones como 'Battery Guardian'."
