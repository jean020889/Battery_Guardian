
#!/bin/bash
# =========================================================
#  Battery Guardian - Desinstalador v2.2.4
# =========================================================
#  Elimina TODO lo que install.sh instaló, incluyendo:
#      - Servicio systemd --user
#      - Procesos activos
#      - Archivo sudoers
#      - Icono del escritorio
#      - Entrada del menú de aplicaciones
#      - Autostart (si existía)
#      - Enlace CLI en ~/.local/bin
#      - Carpeta de instalación completa (venv + código)
#      - Configuración del usuario (opcional, pregunta)
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

# Colores
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"
NC="\033[0m"

print_ok()   { echo -e "   [${GREEN}✓${NC}] $1"; }
print_fail() { echo -e "   [${RED}✗${NC}] $1"; }
print_warn() { echo -e "   [${YELLOW}⚠${NC}] $1"; }
print_info() { echo -e "   [i] $1"; }

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  🔋 Desinstalando $APP_NAME v2.2.4${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""


# =========================================================
#  1) Detener y deshabilitar servicio systemd
# =========================================================
echo -e "${BLUE}${BOLD}▶ [1/8] Deteniendo servicio systemd...${NC}"
if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
    print_ok "Servicio detenido y deshabilitado"
else
    echo "   (no había servicio systemd)"
fi
echo ""


# =========================================================
#  2) Matar procesos residuales
# =========================================================
echo -e "${BLUE}${BOLD}▶ [2/8] Matando procesos residuales...${NC}"
if pgrep -f "battery_guardian.py" &>/dev/null; then
    pkill -9 -f "battery_guardian.py" 2>/dev/null || true
    sleep 1
    print_ok "Procesos detenidos"
else
    echo "   (no había procesos activos)"
fi
echo ""


# =========================================================
#  3) Eliminar archivo del servicio systemd
# =========================================================
echo -e "${BLUE}${BOLD}▶ [3/8] Eliminando archivo del servicio systemd...${NC}"
if [ -f "$SYSTEMD_FILE" ]; then
    rm -f "$SYSTEMD_FILE"
    systemctl --user daemon-reload
    print_ok "$SYSTEMD_FILE eliminado"
else
    echo "   (no existía)"
fi
echo ""


# =========================================================
#  4) Eliminar archivo sudoers
# =========================================================
echo -e "${BLUE}${BOLD}▶ [4/8] Eliminando archivo sudoers...${NC}"
if [ -f "$SUDOERS_FILE" ]; then
    sudo rm -f "$SUDOERS_FILE"
    print_ok "$SUDOERS_FILE eliminado"
else
    echo "   (no existía)"
fi
echo ""


# =========================================================
#  5) Eliminar accesos directos y enlaces
# =========================================================
echo -e "${BLUE}${BOLD}▶ [5/8] Eliminando accesos directos...${NC}"
if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    print_ok "Icono del escritorio eliminado"
else
    echo "   (sin icono en el escritorio)"
fi

if [ -f "$MENU_FILE" ]; then
    rm -f "$MENU_FILE"
    print_ok "Entrada del menú eliminada"
else
    echo "   (sin entrada en el menú)"
fi

if [ -f "$AUTOSTART_FILE" ]; then
    rm -f "$AUTOSTART_FILE"
    print_ok "Autostart eliminado"
else
    echo "   (sin autostart)"
fi

if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    print_ok "Enlace CLI eliminado"
else
    echo "   (sin enlace CLI)"
fi

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo ""


# =========================================================
#  6) Eliminar carpeta de instalación (venv + código)
# =========================================================
echo -e "${BLUE}${BOLD}▶ [6/8] Eliminando carpeta de instalación...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    print_ok "$INSTALL_DIR eliminada (incluye venv)"
else
    echo "   (no existía)"
fi

# Si ~/Apps quedó vacía, la eliminamos también
if [ -d "$HOME/Apps" ] && [ -z "$(ls -A "$HOME/Apps" 2>/dev/null)" ]; then
    rmdir "$HOME/Apps" 2>/dev/null && print_ok "$HOME/Apps (estaba vacía) eliminada"
fi
echo ""


# =========================================================
#  7) Configuración del usuario (opcional)
# =========================================================
echo -e "${BLUE}${BOLD}▶ [7/8] Configuración del usuario...${NC}"
if [ -d "$CONFIG_DIR" ]; then
    echo "   ⚙  Configuración en: $CONFIG_DIR"
    read -r -p "   ¿Eliminar también la configuración y los logs? (s/N): " RESP
    if [[ "$RESP" =~ ^[sS]$ ]]; then
        rm -rf "$CONFIG_DIR"
        print_ok "Configuración eliminada"
    else
        echo "   → Conservada en $CONFIG_DIR"
    fi
else
    echo "   (no había configuración guardada)"
fi
echo ""


# =========================================================
#  8) Verificación final (restos)
# =========================================================
echo -e "${BLUE}${BOLD}▶ [8/8] Verificando restos...${NC}"
LEFTOVERS=0

if [ -d "$INSTALL_DIR" ]; then
    print_warn "Resto: $INSTALL_DIR"
    LEFTOVERS=1
fi
if [ -f "$DESKTOP_FILE" ]; then
    print_warn "Resto: $DESKTOP_FILE"
    LEFTOVERS=1
fi
if [ -f "$MENU_FILE" ]; then
    print_warn "Resto: $MENU_FILE"
    LEFTOVERS=1
fi
if [ -f "$AUTOSTART_FILE" ]; then
    print_warn "Resto: $AUTOSTART_FILE"
    LEFTOVERS=1
fi
if [ -L "$BIN_LINK" ]; then
    print_warn "Resto: $BIN_LINK"
    LEFTOVERS=1
fi
if [ -f "$SYSTEMD_FILE" ]; then
    print_warn "Resto: $SYSTEMD_FILE"
    LEFTOVERS=1
fi
if [ -f "$SUDOERS_FILE" ]; then
    print_warn "Resto: $SUDOERS_FILE"
    LEFTOVERS=1
fi

if [ $LEFTOVERS -eq 0 ]; then
    print_ok "Sin restos"
fi
echo ""


echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ Desinstalación completada${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "  📌 Notas:"
echo "      - Las dependencias del sistema (xdotool, x11-utils,"
echo "        xprintidle, python3-tk, upower) NO se eliminan"
echo "        porque pueden ser usadas por otros programas."
echo "      - Si quieres eliminarlas manualmente:"
echo "          sudo apt remove xdotool x11-utils xprintidle"
echo ""
