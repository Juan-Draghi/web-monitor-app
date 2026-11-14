# CLAUDE.md

Las instrucciones de trabajo de este proyecto están en `AGENTS.md`, que comparten
Codex y Claude Code. Editar las reglas allí, no en este archivo.

@AGENTS.md

## Datos operativos para Claude Code

- Aplicación: Flask local en `http://localhost:5000`. Servidor en `app.py`,
  lógica de monitoreo en `monitor.py`, interfaz en `templates/index.html` y
  `static/operational-ui.css`.
- Entorno virtual: `venv\` (lo crea `instalar.bat`). Usar siempre
  `venv\Scripts\python`, no el Python del sistema.
- Pruebas: `venv\Scripts\python -m unittest discover tests`
- Ejecutar en modo desarrollo: `ejecutar.bat` (o `venv\Scripts\python app.py`).
- Lista de URLs activa: `urls.txt` en la raíz del proyecto.
- No editar `build/` ni `dist/`: se regeneran con `compilar.bat`.
- No modificar a mano los datos de ejecución (`web_monitoring_hashes.json`,
  `web_monitoring_metadata.json`, `last_run_results.json`); los genera cada corrida.
