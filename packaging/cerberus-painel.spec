# -*- mode: python ; coding: utf-8 -*-
#
# Spec do PyInstaller para o painel desktop do Cerberus.
# Gera UM executavel standalone (onefile), sem console, para Linux ou Windows.
#
# Build:  pyinstaller packaging/cerberus-painel.spec
# Saida:  dist/cerberus-painel         (Linux)
#         dist/cerberus-painel.exe      (Windows)

block_cipher = None

a = Analysis(
    ['cerberus_painel_launcher.py'],
    pathex=['..'],                     # permite importar o pacote cerberus
    binaries=[],
    datas=[],
    hiddenimports=['cerberus', 'cerberus.painel_desktop', 'cerberus.varredura',
                   'cerberus.relatorio', 'cerberus.assinaturas'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cerberus-painel',
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,                     # GUI: sem janela de terminal
)
