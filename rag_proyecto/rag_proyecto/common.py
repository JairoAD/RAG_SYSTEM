"""common.py - configuración y utilidades compartidas por los scripts del proyecto.

Las credenciales y direcciones se leen del archivo .env (que NO se sube al
repositorio). Ver .env.example para los nombres de las variables.
"""
import os

from dotenv import load_dotenv

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER", "rag_user")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-minilm")
EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")


def conectar():
    """Abre la conexión a Oracle (modo thin: no requiere Oracle Client)."""
    import oracledb

    if not ORACLE_PASSWORD:
        raise SystemExit("Falta ORACLE_PASSWORD en el archivo .env")
    # Devuelve los CLOB como str en lugar de objetos LOB.
    oracledb.defaults.fetch_lobs = False
    return oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)


def embeddings(textos, modelo=None):
    """Pide a Ollama los vectores de una lista de textos (una sola petición)."""
    import requests

    r = requests.post(
        OLLAMA_URL + "/api/embed",
        json={"model": modelo or EMBED_MODEL, "input": textos},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["embeddings"]


def generar(prompt, modelo=None):
    """Pide a Ollama una respuesta del modelo de lenguaje (sin streaming).

    temperature=0 hace las respuestas reproducibles, útil para documentar las pruebas.
    """
    import requests

    r = requests.post(
        OLLAMA_URL + "/api/generate",
        json={"model": modelo or LLM_MODEL, "prompt": prompt, "stream": False,
              "options": {"temperature": 0}},
        timeout=900,
    )
    r.raise_for_status()
    return r.json()["response"]
