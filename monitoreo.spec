# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para MonitoreoWeb CPAU
# Genera: dist/MonitoreoWeb/MonitoreoWeb.exe  (modo onedir, sin consola)

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

# ── Playwright: recolectar todo (incluye el driver Node.js de ~80 MB) ──────
pw_datas, pw_binaries, pw_hidden = collect_all('playwright')

# ── Metadatos de paquetes que los consultan en runtime ─────────────────────
# Flask/Werkzeug usan importlib.metadata para leer versiones y entry points.
# Sin estos .dist-info PyInstaller lanza "No package metadata was found".
pkg_metadata = (
    copy_metadata('werkzeug') +
    copy_metadata('flask') +
    copy_metadata('jinja2') +
    copy_metadata('click') +
    copy_metadata('requests') +
    copy_metadata('charset-normalizer') +
    copy_metadata('certifi') +
    copy_metadata('urllib3') +
    copy_metadata('idna') +
    copy_metadata('beautifulsoup4') +
    copy_metadata('pyee')
)

# ── Assets locales ─────────────────────────────────────────────────────────
local_datas = [
    ('templates', 'templates'),
    ('static',    'static'),
]

# ── Icono del ejecutable ───────────────────────────────────────────────────
_icon = 'static/app_icon.ico' if os.path.exists('static/app_icon.ico') else None

# ── Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=pw_binaries,
    datas=local_datas + pw_datas + pkg_metadata,
    hiddenimports=pw_hidden + [
        # Flask / Werkzeug
        'flask',
        'flask.helpers',
        'flask.templating',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.debug',
        'werkzeug.middleware.shared_data',
        # HTTP / parsers
        'bs4',
        'requests',
        'certifi',
        'charset_normalizer',
        'idna',
        'urllib3',
        'urllib3.util.ssl_',
        # Async / playwright internals
        'greenlet',
        'pyee',
        'pyee.base',
        'asyncio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'PIL',
        'IPython', 'notebook', 'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MonitoreoWeb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # Sin ventana de terminal
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='MonitoreoWeb',
)
