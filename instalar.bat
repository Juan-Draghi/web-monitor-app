@echo off
echo =============================================
echo  Instalacion de Web Monitor
echo =============================================
echo.
echo Esto solo se hace una vez.
echo No cierres esta ventana hasta que termine.
echo.

REM Buscar Python
set PYTHON=
where py >nul 2>&1 && set PYTHON=py
if "%PYTHON%"=="" (
    where python >nul 2>&1 && set PYTHON=python
)
if "%PYTHON%"=="" (
    echo ERROR: No se encontro Python instalado.
    echo Instala Python desde https://www.python.org/downloads/
    echo Durante la instalacion, tilda "Add Python to PATH".
    pause
    exit /b 1
)
echo Python encontrado: %PYTHON%
echo.

echo [1/4] Creando entorno virtual en la carpeta del proyecto...
%PYTHON% -m venv venv
if errorlevel 1 (
    echo ERROR: No se pudo crear el entorno virtual.
    pause
    exit /b 1
)

echo.
echo [2/4] Instalando paquetes...
venv\Scripts\python -m pip install --upgrade requests beautifulsoup4 playwright flask
if errorlevel 1 (
    echo ERROR: No se pudieron instalar los paquetes.
    pause
    exit /b 1
)

echo.
echo [3/4] Descargando el navegador Chromium...
venv\Scripts\python -m playwright install chromium
if errorlevel 1 (
    echo ERROR: No se pudo descargar Chromium.
    echo Verifica tu conexion a internet e intenta de nuevo.
    pause
    exit /b 1
)

echo.
echo [4/4] Verificando la instalacion...
venv\Scripts\python -c "import flask, playwright; print('OK')"
if errorlevel 1 (
    echo ERROR: Algo no quedo bien instalado.
    pause
    exit /b 1
)

echo.
echo =============================================
echo  Instalacion completada correctamente.
echo  Ya podes usar ejecutar.bat todos los dias.
echo =============================================
echo.
pause
