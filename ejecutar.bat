@echo off
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo No se encontro el entorno virtual.
    echo Ejecuta instalar.bat primero.
    pause
    exit /b 1
)

echo Iniciando Web Monitor...
venv\Scripts\python app.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error al iniciar la aplicacion.
    echo Si el problema persiste, ejecuta instalar.bat nuevamente.
    pause
)
