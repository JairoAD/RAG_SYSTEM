# Mini sistema RAG con Oracle AI Database 26ai

Proyecto de investigación (Indagación) · Programación de Computadoras IV · Grupo 2026C3-G01
Universidad Castro Carazo · Ingeniería Informática, Sede Occidente · Docente: William Orozco Retana

Sistema de **generación aumentada por recuperación (RAG)** que responde preguntas sobre tres manuales de
usuario de Samsung (un reloj, una familia de teléfonos y una tableta). Oracle AI Database 26ai almacena los
fragmentos de texto con su vector y los recupera por similitud con SQL (`VECTOR_DISTANCE`); un modelo de
lenguaje local (llama3.2:3b, con Ollama) redacta la respuesta usando **solo** el contexto recuperado.

## Arquitectura

![Arquitectura del sistema](docs/arquitectura_rag.png)

**Proceso 1: preparación (una vez).** `ingest.py` divide cada PDF en secciones y las guarda en `DOCUMENTO` y
`SECCION`. `embed.py` fragmenta cada sección (120 palabras, traslape de 20), pide los embeddings a Ollama
(`all-minilm`, 384 dimensiones) y los guarda en `FRAGMENTO.EMBEDDING` (`VECTOR(384, FLOAT32)`).

**Proceso 2: cada pregunta.** `ask.py` vectoriza la pregunta con el mismo modelo, Oracle devuelve los 4
fragmentos más cercanos (distancia coseno, con filtro opcional por manual), y llama3.2:3b genera la respuesta.
La aplicación muestra las fuentes recuperadas (documento, sección, página y distancia).

### Decisión clave: los vectores se generan desde Python, no dentro de la base

La guía propone que la base llame a Ollama con `DBMS_VECTOR.UTL_TO_EMBEDDING`. En la imagen
`oracle-free-lite` eso falla (`ORA-29332` / `PLS-00201`) porque el paquete `SYS.DBMS_NETWORK_ACL_ADMIN` no
existe en el contenedor raíz (`ORA-04043`). Por eso se usa la alternativa (b) del enunciado: generación
externa de los vectores y búsqueda por similitud en SQL. El diagnóstico está en `sql/01_diagnostico_red_ollama.sql`.

## Tecnologías

| Componente | Versión / modelo |
|---|---|
| Base de datos | Oracle AI Database 26ai Free 23.26.3, imagen `database/free:latest-lite`, en Docker Desktop (Windows) |
| Lenguaje | Python 3.12 (`pypdf`, `oracledb`, `requests`, `python-dotenv`) |
| Embeddings | `all-minilm` con Ollama (384 dimensiones) |
| Modelo de lenguaje | `llama3.2:3b` con Ollama (temperatura 0) |

## Estructura del repositorio

```
.
├── ingest.py          # PDF -> secciones -> tablas DOCUMENTO y SECCION
├── fragmentar.py      # división en fragmentos por oraciones, con traslape
├── embed.py           # fragmentos + embeddings (Ollama) -> tabla FRAGMENTO
├── ask.py             # consulta RAG (recuperación en Oracle + respuesta con llama3.2:3b)
├── pruebas.py         # ejecuta las 9 pruebas y genera el CSV de resultados
├── common.py          # configuración (.env), conexión a Oracle y llamadas a Ollama
├── requirements.txt
├── .env.example       # nombres de las variables de entorno (sin valores reales)
├── sql/
│   ├── 00_usuario_y_tablespace.sql    # tablespace RAG_DATA y usuario rag_user
│   ├── 01_diagnostico_red_ollama.sql  # diagnóstico: la base no puede llamar a Ollama en lite
│   ├── 02_prueba_vectores.sql         # prueba del tipo VECTOR y de VECTOR_DISTANCE
│   ├── 03_esquema.sql                 # tablas documento, seccion y fragmento
│   ├── 04_consulta_similitud.sql      # consultas de similitud y búsqueda híbrida
│   └── 05_carga_y_verificacion.sql    # sentencias de carga que usa Python y consultas de verificación
├── docs/arquitectura_rag.png
├── resultados/resultados_chunk120_v2_valorado.xlsx   # resultados finales de las pruebas
└── manuales/          # aquí van los PDF (ver manuales/LEEME.md)
```

## Requisitos

- Docker (o Podman) con un contenedor de Oracle AI Database 26ai Free **con volumen persistente**.
- [Ollama](https://ollama.com) en ejecución, con los modelos descargados:
  `ollama pull llama3.2:3b` y `ollama pull all-minilm`.
- Python 3.9 o superior.
- Los tres manuales PDF en la carpeta `manuales/` (ver `manuales/LEEME.md`).

## Instalación y ejecución

1. **Contenedor de Oracle** (ejemplo; en el curso se creó según la guía de la semana 1):
   ```
   docker run -d --name oracle-free-lite -p 1521:1521 -e ORACLE_PWD=<clave_de_system> ^
     -v oracle-free-lite-data:/opt/oracle/oradata container-registry.oracle.com/database/free:latest-lite
   ```
2. **Usuario y tablespace.** Conectado como `SYSTEM` a `FREEPDB1`, ejecutar `sql/00_usuario_y_tablespace.sql`
   (cambiando la clave). Luego, como `rag_user`, ejecutar `sql/02_prueba_vectores.sql` (opcional) y
   `sql/03_esquema.sql`.
3. **Entorno de Python:**
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
   Completar `ORACLE_PASSWORD` en `.env` con la clave de `rag_user`.
4. **Cargar y vectorizar:**
   ```
   python ingest.py --probar     # resumen sin tocar la base: 186 secciones, 975 fragmentos (120/20)
   python ingest.py              # carga documentos y secciones
   python embed.py               # genera los 975 vectores (unos 90 s)
   ```
   Verificar la carga con `sql/05_carga_y_verificacion.sql` (parte B).
5. **Consultar** (versión final del prompt: `v2`):
   ```
   python ask.py --prompt v2 "How do I charge the Galaxy Watch8?"
   python ask.py --prompt v2 --documento tablet "How do I insert a microSD card?"
   python ask.py --prompt v2            # modo interactivo
   ```
6. **Ejecutar las pruebas:** `python pruebas.py --prompt v2 --etiqueta chunk120_v2` genera
   `resultados_chunk120_v2.csv`. Las preguntas y sus referencias verificadas están en `pruebas.py`.

## Resultados de las pruebas

Nueve pruebas: seis con respuesta en los manuales, una repetición de la pregunta ambigua con filtro de
documento y dos sobre temas ausentes. Con el prompt v1, siete respuestas correctas y dos parciales (preguntas 5 y 6);
con el prompt v2, las nueve correctas, y en las dos preguntas ausentes el sistema respondió
*«I can't find that information in the documents.»* sin inventar. El detalle (fragmentos, distancias, respuesta
y análisis de cada prueba) está en `resultados/resultados_chunk120_v2_valorado.xlsx`.

Limitaciones: el conjunto de pruebas es pequeño, el prompt v2 se ajustó con las mismas preguntas, no se
comparó empíricamente el tamaño de fragmento, y la página que se muestra como fuente es la de inicio de la sección.

## Elementos opcionales implementados

- **Búsqueda híbrida:** `--documento` combina la similitud vectorial con un filtro relacional por manual.
- **Indicación de fuentes:** cada respuesta muestra documento, sección, página y distancia de los fragmentos usados.
- No se implementaron el índice vectorial ni la integración con Angular (ver trabajo futuro en el informe).

## Seguridad

El repositorio no contiene claves ni credenciales. La clave de la base de datos se guarda solo en el archivo
`.env` local, excluido con `.gitignore`; `.env.example` lista los nombres de las variables sin valores reales.

## Uso de inteligencia artificial

Se usó Claude (Anthropic) como apoyo en la investigación, el diseño, el código y la redacción. El detalle,
con la validación de cada resultado y una reflexión crítica, está en la bitácora (Anexo A del informe).
