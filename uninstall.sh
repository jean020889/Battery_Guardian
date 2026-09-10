
#!/bin/bash
# =========================================================
#  Battery Guardian - Desinstalador v2.2.1
# =========================================================
#  Elimina TODO lo que install.sh instaló, incluyendo el
#  archivo de sudoers.
# =========================================================

APP_NAME="Battery Guardian"
APP_SLUG="battery-guardian"
INSTALL_DIR="$HOME/Apps/Battery_Guardian"

DESKTOP_FILE="$HOME/Desktop/${APP_SLUG}.desktop"
MENU_FILE="$HOME/.local/share/applications/${APP_SLUG}.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/${APP_SLUG}.desktop"
BIN_LINK="$HOME/.local/bin/${APP_SLUG}"
SYSTEMD_FILE="$HOME/.config/systemd/user/${APP_SLUG}.service"
SUDOERS_FILE="/etc/sudoers.d/battery-guardian"
CONFIG_DIR="$HOME/.config/battery_guardian"

echo "═══════════════════════════════════════════════════════"
echo "  🔋 Desinstalando $APP_NAME"
echo "═══════════════════════════════════════════════════════"
echo ""

# 1) Detener y deshabilitar servicio systemd
echo "▶ [1/7] Deteniendo servicio systemd..."
if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
    echo "   ✓ Servicio detenido y deshabilitado"
else
    echo "   (no había servicio systemd)"
fi
echo ""

# 2) Matar procesos residuales
echo "▶ [2/7] Matando procesos residuales..."
if pgrep -f "battery_guardian.py" &>/dev/null; then
    pkill -9 -f "battery_guardian.py" 2>/dev/null || true
    sleep 1
    echo "   ✓ Procesos detenidos"
else
    echo "   (no había procesos activos)"
fi
echo ""

# 3) Eliminar archivo del servicio systemd
echo "▶ [3/7] Eliminando archivo del servicio systemd..."
if [ -f "$SYSTEMD_FILE" ]; then
    rm -f "$SYSTEMD_FILE"
    systemctl --user daemon-reload
    echo "   ✓ $SYSTEMD_FILE eliminado"
else
    echo "   (no existía)"
fi
echo ""

# 4) Eliminar archivo sudoers
echo "▶ [4/7] Eliminando archivo sudoers..."
if [ -f "$SUDOERS_FILE" ]; then
    sudo rm -f "$SUDOERS_FILE"
    echo "   ✓ $SUDOERS_FILE eliminado"
else
    echo "   (no existía)"
fi
echo ""

# 5) Eliminar accesos directos y enlaces
echo "▶ [5/7] Eliminando accesos directos..."
[ -f "$DESKTOP_FILE" ]   && rm -f "$DESKTOP_FILE"   && echo "   ✓ Escritorio"
[ -f "$MENU_FILE" ]      && rm -f "$MENU_FILE"      && echo "   ✓ Menú"
[ -f "$AUTOSTART_FILE" ] && rm -f "$AUTOSTART_FILE" && echo "   ✓ Autostart"
[ -L "$BIN_LINK" ]       && rm -f "$BIN_LINK"       && echo "   ✓ Enlace CLI"
[ -f "$BIN_LINK" ]       && rm -f "$BIN_LINK"       && echo "   ✓ Enlace CLI"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo ""

# 6) Eliminar carpeta de instalación
echo "▶ [6/7] Eliminando carpeta de instalación..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "   ✓ $INSTALL_DIR eliminada (incluye venv)"
else
    echo "   (no existía)"
fi
echo ""

# 7) Configuración del usuario
echo "▶ [7/7] Configuración del usuario..."
if [ -d "$CONFIG_DIR" ]; then
    echo "   ⚙  Configuración en: $CONFIG_DIR"
    read -r -p "   ¿Eliminar también la configuración y los logs? (s/N): " RESP
    if [[ "$RESP" =~ ^[sS]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo "   ✓ Configuración eliminada"
    else
        echo "   → Conservada en $CONFIG_DIR"
    fi
else
    echo "   (no había configuración guardada)"
fi
echo ""

echo "═══════════════════════════════════════════════════════"
echo "  ✅ Desinstalación completada"
echo "═══════════════════════════════════════════════════════"
echo ""
