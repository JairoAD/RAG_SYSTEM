"""ask.py - consulta del sistema RAG: recuperación en Oracle y respuesta con Ollama.

Flujo de cada pregunta:
  1. La pregunta se vectoriza con el MISMO modelo de embeddings de los fragmentos.
  2. Oracle devuelve los k fragmentos más cercanos (VECTOR_DISTANCE, coseno).
     Con --documento se filtra por manual: búsqueda híbrida (vectorial + relacional).
  3. Los fragmentos se entregan a llama3.2:3b dentro de un prompt que le ordena
     responder solo con ese contexto y, si no está, decir una frase exacta.
  4. La aplicación muestra las fuentes recuperadas (documento, sección y página);
     no se depende de que el modelo pequeño las cite.

Uso:
  python ask.py "How do I charge the Galaxy Watch8?"
  python ask.py --documento watch --k 4 "How do I turn it off?"
  python ask.py --csv pruebas.csv "Who won the last football world cup?"
  python ask.py                      # modo interactivo
"""
import argparse
import array
import csv
import os
import sys
import time

from common import conectar, embeddings, generar

# Frase exacta que el modelo debe usar cuando la respuesta no está en el contexto.
NO_INFO = "I can't find that information in the documents."

SQL_BUSQUEDA = """
SELECT d.titulo, s.titulo, s.pagina_inicio, f.texto,
       VECTOR_DISTANCE(f.embedding, :qv, COSINE) AS distancia
FROM   fragmento f
JOIN   seccion   s ON s.id_seccion   = f.id_seccion
JOIN   documento d ON d.id_documento = s.id_documento
{filtro}
ORDER  BY distancia
FETCH  FIRST :k ROWS ONLY
"""


def recuperar(cur, pregunta, k, documento=None):
    """Devuelve los k fragmentos más cercanos como tuplas
    (documento, sección, página, texto, distancia)."""
    qv = array.array("f", embeddings([pregunta])[0])
    binds = {"qv": qv, "k": k}
    filtro = ""
    if documento:  # búsqueda híbrida: similitud vectorial + filtro relacional
        filtro = "WHERE LOWER(d.titulo) LIKE '%' || LOWER(:doc) || '%'"
        binds["doc"] = documento
    cur.execute(SQL_BUSQUEDA.format(filtro=filtro), binds)
    return cur.fetchall()


def construir_prompt(pregunta, filas, version="v1"):
    """v1 = prompt base. v2 = v1 + dos instrucciones añadidas tras analizar las pruebas:
    responder completo (todas las opciones del contexto) y, si la pregunta no nombra un
    dispositivo, dar una respuesta breve por cada dispositivo del contexto."""
    contexto = "\n".join(
        "[%s - %s, p.%s] %s" % (doc, sec, pag, texto) for doc, sec, pag, texto, _ in filas)
    extra = ""
    if version == "v2":
        extra = (
            "Give a complete answer: if the context lists several options or steps, include all of them.\n"
            "If the question does not name a device and the context contains several devices, "
            "give one short answer for each device, naming the device.\n")
    return (
        "You answer questions about Samsung device user manuals.\n"
        "Use ONLY the context below. Do not use outside knowledge.\n"
        "The context may come from different devices: answer for the device named in the "
        "question; if no device is named, say which device each part of the answer refers to.\n"
        + extra +
        "If the answer is not in the context, reply exactly: \"%s\"\n\n"
        "Context:\n%s\n\nQuestion: %s\nAnswer:" % (NO_INFO, contexto, pregunta))


def responder(cur, pregunta, k, documento=None, umbral=None, version="v1"):
    """Devuelve (respuesta, filas). Con umbral, si el fragmento más cercano está más
    lejos que el umbral, ni siquiera se consulta al modelo."""
    filas = recuperar(cur, pregunta, k, documento)
    if not filas:
        return NO_INFO, filas
    if umbral is not None and filas[0][4] > umbral:
        return NO_INFO + " (descartada por umbral de distancia)", filas
    return generar(construir_prompt(pregunta, filas, version)).strip(), filas


def _mostrar(pregunta, respuesta, filas, segundos):
    print("\nPregunta: %s" % pregunta)
    print("\nRespuesta:\n%s" % respuesta)
    print("\nFuentes recuperadas (menor distancia = más similar):")
    for doc, sec, pag, _, dist in filas:
        print("  %.3f  %s | %s | p.%s" % (dist, doc, sec, pag))
    print("(%.1f s)\n" % segundos)


def _registrar_csv(ruta, pregunta, documento, respuesta, filas, segundos):
    """Agrega una fila al CSV, para armar la tabla de pruebas del informe."""
    nuevo = not os.path.exists(ruta)
    with open(ruta, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if nuevo:
            w.writerow(["Pregunta", "Filtro de documento", "Fragmentos recuperados (distancia)",
                        "Respuesta", "Segundos"])
        recuperados = " || ".join(
            "%s > %s p.%s (%.3f)" % (d, s, p, dist) for d, s, p, _, dist in filas)
        w.writerow([pregunta, documento or "", recuperados, respuesta, "%.1f" % segundos])


def _consultar(cur, args, pregunta):
    inicio = time.time()
    respuesta, filas = responder(cur, pregunta, args.k, args.documento, args.umbral, args.prompt)
    segundos = time.time() - inicio
    _mostrar(pregunta, respuesta, filas, segundos)
    if args.csv:
        _registrar_csv(args.csv, pregunta, args.documento, respuesta, filas, segundos)


def main():
    ap = argparse.ArgumentParser(description="Consulta el sistema RAG.")
    ap.add_argument("pregunta", nargs="?", help="si se omite, se abre el modo interactivo")
    ap.add_argument("--k", type=int, default=4, help="fragmentos que recibe el modelo")
    ap.add_argument("--documento", help="filtra por manual (texto contenido en el título)")
    ap.add_argument("--umbral", type=float, default=None,
                    help="distancia máxima aceptable; si se supera, se responde que no hay información")
    ap.add_argument("--prompt", choices=["v1", "v2"], default="v1", help="versión del prompt")
    ap.add_argument("--csv", help="archivo CSV donde se registra cada consulta")
    args = ap.parse_args()

    conn = conectar()
    cur = conn.cursor()
    if args.pregunta:
        _consultar(cur, args, args.pregunta)
    else:
        print("Modo interactivo. Escriba la pregunta (en inglés) y Enter; línea vacía para salir.")
        while True:
            try:
                pregunta = input("Question> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not pregunta:
                break
            _consultar(cur, args, pregunta)
    conn.close()


if __name__ == "__main__":
    main()
