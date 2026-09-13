# 📖 Guía de instalación y desinstalación

Guía paso a paso para instalar **Battery Guardian v1.3.0** en Linux Mint
(o cualquier distro basada en Ubuntu/Debian) y desinstalarlo por completo.


### Instalación:

Ejecutar el instalador

```bash
chmod +x install.sh
./install.sh
```
Paso 3 — Esperar a que termine
El instalador hace 11 pasos automáticamente:

#	Acción
1	Comprobar dependencias del sistema
2	Comprobar el icono
3	Detener instancias antiguas
4	Copiar archivos a ~/Apps/Battery_Guardian/
5	Crear el entorno virtual
6	Instalar pystray y Pillow en el venv
7	Crear el lanzador run.sh
8	Crear el enlace CLI ~/.local/bin/battery-guardian
9	Crear el icono del escritorio y la entrada del menú
10	Instalar el servicio systemd --user (arranque + auto-reinicio)
11	Verificar que todo funciona
Al final verás:

text
═══════════════════════════════════════════════════════
  ✅ Instalación completada
═══════════════════════════════════════════════════════

  📌 El programa ya está corriendo en segundo plano.
     Búscalo en la bandeja del sistema (donde WiFi/Bluetooth).

### Desinstalación:

```bash
chmod +x uninstall.sh uninstall.sh
./uninstall.sh
```

