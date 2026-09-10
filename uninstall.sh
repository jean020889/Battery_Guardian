#!/bin/bash
# =========================================================
#  Battery Guardian - Desinstalador v1.3.0
# =========================================================
#  Elimina TODO lo que install.sh instaló:
#      - Servicio systemd --user
#      - Procesos activos
#      - Icono del escritorio
#      - Entrada del menú de aplicaciones
#      - Autostart (si existía)
#      - Enlace CLI
#      - Carpeta de instalación completa (venv + código)
#      - Configuración del usuario (opcional, pregunta)
# =========================================================

APP_NAME="Battery Guardian"
APP_SLUG="battery-guardian"

INSTALL_BASE="$HOME/Apps"
INSTALL_DIR="$INSTALL_BASE/Battery_Guardian"

DESKTOP_FILE="$HOME/Desktop/${APP_SLUG}.desktop"
MENU_FILE="$HOME/.local/share/applications/${APP_SLUG}.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/${APP_SLUG}.desktop"
BIN_LINK="$HOME/.local/bin/${APP_SLUG}"
SYSTEMD_FILE="$HOME/.config/systemd/user/${APP_SLUG}.service"
CONFIG_DIR="$HOME/.config/battery_guardian"

echo "═══════════════════════════════════════════════════════"
echo "  🔋 Desinstalando $APP_NAME"
echo "═══════════════════════════════════════════════════════"
echo ""

# =========================================================
#  1) Detener y deshabilitar servicio systemd
# =========================================================
echo "▶ [1/6] Deteniendo servicio systemd..."

if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
    echo "   ✓ Servicio detenido y deshabilitado"
else
    echo "   (no había servicio systemd registrado)"
fi
echo ""

# =========================================================
#  2) Matar procesos residuales
# =========================================================
echo "▶ [2/6] Matando procesos residuales..."

if pgrep -f "battery_guardian.py" &>/dev/null; then
    pkill -9 -f "battery_guardian.py" 2>/dev/null || true
    sleep 1
    echo "   ✓ Procesos detenidos"
else
    echo "   (no había procesos activos)"
fi
echo ""

# =========================================================
#  3) Eliminar archivo del servicio systemd
# =========================================================
echo "▶ [3/6] Eliminando archivo del servicio systemd..."

if [ -f "$SYSTEMD_FILE" ]; then
    rm -f "$SYSTEMD_FILE"
    systemctl --user daemon-reload
    echo "   ✓ $SYSTEMD_FILE eliminado"
else
    echo "   (no existía)"
fi
echo ""

# =========================================================
#  4) Eliminar accesos directos y enlaces
# =========================================================
echo "▶ [4/6] Eliminando accesos directos..."

if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    echo "   ✓ Icono del escritorio eliminado"
else
    echo "   (sin icono en el escritorio)"
fi

if [ -f "$MENU_FILE" ]; then
    rm -f "$MENU_FILE"
    echo "   ✓ Entrada del menú eliminada"
else
    echo "   (sin entrada en el menú)"
fi

if [ -f "$AUTOSTART_FILE" ]; then
    rm -f "$AUTOSTART_FILE"
    echo "   ✓ Autostart eliminado"
else
    echo "   (sin autostart)"
fi

if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    echo "   ✓ Enlace CLI eliminado"
else
    echo "   (sin enlace CLI)"
fi

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo ""

# =========================================================
#  5) Eliminar carpeta de instalación (venv + código)
# =========================================================
echo "▶ [5/6] Eliminando carpeta de instalación..."

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "   ✓ $INSTALL_DIR eliminada (incluye el venv)"
else
    echo "   (no existía la carpeta de instalación)"
fi

# Si ~/Apps quedó vacía, la eliminamos también
if [ -d "$INSTALL_BASE" ] && [ -z "$(ls -A "$INSTALL_BASE" 2>/dev/null)" ]; then
    rmdir "$INSTALL_BASE" 2>/dev/null && echo "   ✓ $INSTALL_BASE (estaba vacía) eliminada"
fi
echo ""

# =========================================================
#  6) Configuración del usuario (preguntar)
# =========================================================
echo "▶ [6/6] Configuración del usuario..."

if [ -d "$CONFIG_DIR" ]; then
    echo "   ⚙  Configuración encontrada en:"
    echo "      $CONFIG_DIR"
    echo ""
    read -r -p "   ¿Eliminar también la configuración y los logs? (s/N): " RESP
    if [[ "$RESP" =~ ^[sS]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo "   ✓ Configuración eliminada"
    else
        echo "   → Configuración conservada en $CONFIG_DIR"
    fi
else
    echo "   (no había configuración guardada)"
fi
echo ""

# =========================================================
#  Verificación final
# =========================================================
echo "▶ Verificando restos..."

LEFTOVERS=0

[ -d "$INSTALL_DIR" ]    && { echo "   ⚠ Resto: $INSTALL_DIR";    LEFTOVERS=1; }
[ -f "$DESKTOP_FILE" ]   && { echo "   ⚠ Resto: $DESKTOP_FILE";   LEFTOVERS=1; }
[ -f "$MENU_FILE" ]      && { echo "   ⚠ Resto: $MENU_FILE";      LEFTOVERS=1; }
[ -f "$AUTOSTART_FILE" ] && { echo "   ⚠ Resto: $AUTOSTART_FILE"; LEFTOVERS=1; }
[ -L "$BIN_LINK" ]       && { echo "   ⚠ Resto: $BIN_LINK";       LEFTOVERS=1; }
[ -f "$SYSTEMD_FILE" ]   && { echo "   ⚠ Resto: $SYSTEMD_FILE";   LEFTOVERS=1; }

if [ $LEFTOVERS -eq 0 ]; then
    echo "   ✓ Sin restos"
fi
echo ""

echo "═══════════════════════════════════════════════════════"
echo "  ✅ Desinstalación completada"
echo "═══════════════════════════════════════════════════════"
echo ""
