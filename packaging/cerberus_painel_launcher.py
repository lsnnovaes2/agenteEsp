"""
Ponto de entrada para o executavel standalone do painel desktop do Cerberus.

O PyInstaller empacota este arquivo (e o pacote cerberus) em um unico binario,
para rodar o painel sem precisar instalar Python na maquina.
"""

from cerberus.painel_desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
