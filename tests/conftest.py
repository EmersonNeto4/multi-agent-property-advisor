import sys
from pathlib import Path

# Garante que a raiz do projeto está no sys.path independentemente do cwd de
# onde o pytest é invocado (ex: CI a correr de um diretório diferente).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
