@echo off
cd /d "%~dp0"
setlocal EnableDelayedExpansion
title Compilar MonitoreoWeb

echo.
echo  ==============================================
echo   MonitoreoWeb CPAU - Compilacion
echo  ==============================================
echo.

:: Cerrar la app si esta corriendo (evita errores de archivo en uso).
:: Solo se cierra el node.exe que Playwright usa DENTRO de dist\MonitoreoWeb;
:: los demas node.exe de la computadora (otras herramientas) no se tocan.
taskkill /IM MonitoreoWeb.exe /F > nul 2>&1
powershell -NoProfile -Command "$dist = (Resolve-Path -LiteralPath '.').Path + '\dist\MonitoreoWeb\'; Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($dist, [StringComparison]::OrdinalIgnoreCase) } | Stop-Process -Force" > nul 2>&1
timeout /t 1 /nobreak > nul

:: Verificar entorno virtual
if not exist venv\Scripts\python.exe (
    echo  ERROR: No existe el entorno virtual.
    echo  Ejecuta primero instalar.bat y vuelve a intentarlo.
    echo.
    pause
    exit /b 1
)

:: [1/5] Instalar herramientas de compilacion
echo  [1/5] Instalando PyInstaller y Pillow...
venv\Scripts\python -m pip install pyinstaller pillow --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  ERROR al instalar dependencias de compilacion.
    pause
    exit /b 1
)
echo        OK

:: [2/5] Convertir icono a .ico
echo  [2/5] Preparando icono...
venv\Scripts\python -c "from PIL import Image; img=Image.open('static/app_icon.png').convert('RGBA'); img.save('static/app_icon.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
if errorlevel 1 (
    echo        Advertencia: no se pudo convertir el icono. Se usara el icono por defecto.
) else (
    echo        OK
)

:: [3/5] Compilar ejecutable
echo  [3/5] Compilando ejecutable (puede tardar 2-5 minutos)...
echo        No cierres esta ventana.
echo.
:: La carpeta de trabajo temporal va fuera de OneDrive: dentro de OneDrive la
:: limpieza (--clean) falla con "Acceso denegado" por la sincronizacion.
venv\Scripts\python -m PyInstaller monitoreo.spec --noconfirm --clean --workpath "%TEMP%\monitoreo-pyi-build"
if errorlevel 1 (
    echo.
    echo  ERROR en la compilacion. Revisa los mensajes anteriores.
    pause
    exit /b 1
)

:: [4/5] Copiar archivos de datos junto al ejecutable
echo  [4/5] Copiando archivos de datos...
if exist urls.txt (
    copy /Y urls.txt "dist\MonitoreoWeb\urls.txt" > nul
    echo        urls.txt copiado
)
if exist web_monitoring_hashes.json (
    copy /Y web_monitoring_hashes.json "dist\MonitoreoWeb\web_monitoring_hashes.json" > nul
    echo        web_monitoring_hashes.json copiado
)
if exist last_run_results.json (
    copy /Y last_run_results.json "dist\MonitoreoWeb\last_run_results.json" > nul
    echo        last_run_results.json copiado
)

:: [5/5] Verificar resultado
echo  [5/5] Verificando...
if not exist "dist\MonitoreoWeb\MonitoreoWeb.exe" (
    echo  ERROR: No se encontro el ejecutable generado.
    pause
    exit /b 1
)
echo        OK

echo.
echo  ==============================================
echo   Compilacion exitosa.
echo.
echo   Ejecutable listo en:
echo   %CD%\dist\MonitoreoWeb\MonitoreoWeb.exe
echo  ==============================================
echo.

:: Crear acceso directo en el escritorio
set /p CREAR_ACC="  Crear acceso directo en el escritorio? [S/N]: "
if /i "!CREAR_ACC!"=="S" (
    set "_EXE=%CD%\dist\MonitoreoWeb\MonitoreoWeb.exe"
    set "_DIR=%CD%\dist\MonitoreoWeb"
    powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Monitoreo Web CPAU.lnk'); $s.TargetPath = '!_EXE!'; $s.WorkingDirectory = '!_DIR!'; $s.Description = 'CPAU Seleccion Informativa - Monitoreo web'; $s.Save()"
    echo   Acceso directo creado en el escritorio.
)

echo.
pause
