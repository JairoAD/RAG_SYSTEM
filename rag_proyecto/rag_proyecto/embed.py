"""embed.py - fragmenta las secciones, genera los embeddings y los guarda en Oracle.

Flujo:
  SECCION.contenido  ->  fragmentos (con traslape)  ->  Ollama (embeddings)
                     ->  FRAGMENTO (texto + vector VECTOR(384, FLOAT32))

Por qué los vectores se generan aquí y no dentro de la base de datos: la imagen
oracle-free-lite no incluye SYS.DBMS_NETWORK_ACL_ADMIN, de modo que la base no
puede llamar a Ollama (alternativa b del apartado 5.2 del enunciado).

Contexto en el embedding: el texto que se vectoriza lleva al inicio el nombre
del manual y de la sección ("Galaxy Watch8 ... - Apps and features > Camera: ...").
Los tres manuales repiten secciones (cámara, batería...), y este encabezado
ayuda a distinguirlos. En la tabla se guarda el texto original, sin encabezado.
Para medir su efecto se puede repetir la carga con --sin-contexto.

Uso:
  python embed.py                         # MAX 120 palabras, OVERLAP 20
  python embed.py --max-words 80 --overlap 12 --rehacer
  python embed.py --sin-contexto --rehacer
"""
import argparse
import array
import sys
import time

from common import EMBED_DIM, EMBED_MODEL, conectar, embeddings
from fragmentar import fragmentar


def main():
    ap = argparse.ArgumentParser(description="Genera y guarda los embeddings de los fragmentos.")
    ap.add_argument("--max-words", type=int, default=120, help="tamaño máximo del fragmento")
    ap.add_argument("--overlap", type=int, default=20, help="palabras de traslape")
    ap.add_argument("--lote", type=int, default=32, help="fragmentos por petición a Ollama")
    ap.add_argument("--rehacer", action="store_true", help="borra los fragmentos y los recalcula")
    ap.add_argument("--sin-contexto", action="store_true",
                    help="vectoriza solo el texto, sin el encabezado de documento y sección")
    args = ap.parse_args()

    conn = conectar()
    cur = conn.cursor()

    if args.rehacer:
        cur.execute("DELETE FROM fragmento")
        conn.commit()
    else:
        cur.execute("SELECT COUNT(*) FROM fragmento")
        if cur.fetchone()[0]:
            sys.exit("Ya hay fragmentos cargados. Use --rehacer para recalcularlos.")

    cur.execute(
        "SELECT s.id_seccion, d.titulo, s.titulo, s.contenido "
        "FROM seccion s JOIN documento d ON d.id_documento = s.id_documento "
        "ORDER BY s.id_seccion")
    secciones = cur.fetchall()
    if not secciones:
        sys.exit("No hay secciones. Ejecute primero: python ingest.py")

    # Lista de (id_seccion, posición, texto, texto_a_vectorizar)
    items = []
    for id_seccion, doc, sec, contenido in secciones:
        for pos, texto in enumerate(fragmentar(contenido, args.max_words, args.overlap), 1):
            a_vectorizar = texto if args.sin_contexto else "%s - %s: %s" % (doc, sec, texto)
            items.append((id_seccion, pos, texto, a_vectorizar))
    print("%d secciones -> %d fragmentos (MAX %d, OVERLAP %d, modelo %s, contexto: %s)"
          % (len(secciones), len(items), args.max_words, args.overlap, EMBED_MODEL,
             "no" if args.sin_contexto else "sí"))

    inicio = time.time()
    for i in range(0, len(items), args.lote):
        lote = items[i:i + args.lote]
        vectores = embeddings([it[3] for it in lote])
        if len(vectores[0]) != EMBED_DIM:
            sys.exit("El modelo devolvió %d dimensiones y la columna espera %d. "
                     "Ajuste EMBED_DIM y VECTOR(n, FLOAT32) a la dimensión del modelo."
                     % (len(vectores[0]), EMBED_DIM))
        filas = [(it[0], it[1], it[2], array.array("f", v)) for it, v in zip(lote, vectores)]
        cur.executemany(
            "INSERT INTO fragmento (id_seccion, posicion, texto, embedding) "
            "VALUES (:1, :2, :3, :4)", filas)
        conn.commit()
        hechos = min(i + args.lote, len(items))
        print("\r  %d / %d fragmentos (%.0f s)" % (hechos, len(items), time.time() - inicio),
              end="", flush=True)
    print("\nListo.")

    cur.execute("SELECT COUNT(*), MIN(VECTOR_DIMENSION_COUNT(embedding)), "
                "MAX(VECTOR_DIMENSION_COUNT(embedding)) FROM fragmento")
    total, dmin, dmax = cur.fetchone()
    print("Verificación en la base: %d fragmentos, dimensiones %s a %s." % (total, dmin, dmax))
    conn.close()


if __name__ == "__main__":
    main()
