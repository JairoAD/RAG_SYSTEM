"""pruebas.py - ejecuta el conjunto de preguntas de prueba y arma la tabla de resultados.

Cada pregunta se envía al sistema RAG (ask.responder) y el resultado se guarda en un CSV
con las columnas de la Tabla 5 del informe. Las columnas «verificación automática» son solo
una ayuda: la VALORACIÓN FINAL de cada respuesta la hace la persona, leyendo la respuesta
y comparándola con el manual (columna «Referencia en el manual»).

Cada pregunta con respuesta tiene una referencia verificada contra el texto de los PDF.
Las preguntas ausentes se eligieron comprobando que el tema no aparece en ningún manual.

Uso:
  python pruebas.py                       # resultados_base.csv
  python pruebas.py --etiqueta chunk80    # resultados_chunk80.csv (tras recalcular con otro tamaño)
  python pruebas.py --prompt v2 --etiqueta prompt_v2          # prompt mejorado
  python pruebas.py --prompt v2 --solo 5,6 --etiqueta v2_5_6  # solo algunas preguntas
"""
import argparse
import csv
import time

from ask import NO_INFO, responder
from common import conectar

PRUEBAS = [
    # n, tipo, pregunta, filtro, (documento, sección esperados), palabras clave, referencia
    (1, "Con respuesta", "How do I charge the Galaxy Watch8?", None,
     ("Watch8", "Charging the battery"), ["wireless charger"],
     "Watch8, Getting started > Charging the battery (desde p.13)"),
    (2, "Con respuesta", "How do I insert a microSD card?", "tablet",
     ("tablet", "microSD card"), ["ejection pin"],
     "Tableta, Getting started > microSD card (p.12-13)"),
    (3, "Con respuesta", "How do I capture a screenshot on the Galaxy S25?", None,
     ("S25", "Screen capture and screen record"), ["Side button", "Volume Down"],
     "S25/S24, Getting started > Screen capture and screen record (p.42)"),
    (4, "Con respuesta", "How many apps can I run at the same time in split screen view on the tablet?", None,
     ("tablet", "Multi window"), ["three"],
     "Tableta, Apps and features > Multi window (p.57): hasta tres apps"),
    # Corregida: el manual describe el botón Quick solo en la sección "Setting the Quick button
    # and using it (Galaxy Watch8 Classic)". La versión original preguntaba por el Watch8 a secas.
    (5, "Con respuesta", "What can I set the Quick button of the Galaxy Watch8 Classic to do?", None,
     ("Watch8", "Device layout and functions"), ["stopwatch", "torch", "Water lock"],
     "Watch8 Classic, Getting started > Device layout and functions (p.6-7), apartado del botón Quick"),
    (6, "Con respuesta (ambigua: no nombra el dispositivo)", "How do I turn off the device?", None,
     ("", "Turning the"), ["Side button"],
     "Tres manuales: S25 = Side + Volume Down; Watch8 = Home + Back; tableta = mantener Side"),
    ("6b", "Comparación con filtro de documento", "How do I turn off the device?", "tablet",
     ("tablet", "Turning the device on and off"), ["Side button"],
     "Tableta, Getting started > Turning the device on and off (p.14)"),
    (7, "Ausente (fuera del dominio)", "Who won the last football world cup?", None,
     None, None, "Ningún manual trata ese tema"),
    (8, "Ausente (del dominio, sin dato en los manuales)", "How much does the Galaxy S25 cost?", None,
     None, None, "Ningún manual menciona precios"),
]


def _norm(s):
    return s.replace("\u2019", "'").lower()


def main():
    ap = argparse.ArgumentParser(description="Ejecuta las preguntas de prueba.")
    ap.add_argument("--etiqueta", default="base", help="nombre de la configuración probada")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--umbral", type=float, default=None)
    ap.add_argument("--prompt", choices=["v1", "v2"], default="v1", help="versión del prompt")
    ap.add_argument("--solo", help="números de pregunta a ejecutar, separados por coma (ej. 5,6,6b)")
    args = ap.parse_args()

    ruta = "resultados_%s.csv" % args.etiqueta
    conn = conectar()
    cur = conn.cursor()
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["N.º", "Tipo", "Pregunta", "Filtro de documento",
                    "Fragmentos recuperados (distancia)", "Texto de los fragmentos", "Referencia en el manual",
                    "Verificación automática: recuperación", "Respuesta del sistema",
                    "Verificación automática: respuesta", "Segundos",
                    "Valoración (completar a mano)", "Análisis (completar a mano)"])
        solo = set(args.solo.split(",")) if args.solo else None
        for n, tipo, pregunta, filtro, esperado, claves, referencia in PRUEBAS:
            if solo and str(n) not in solo:
                continue
            inicio = time.time()
            respuesta, filas = responder(cur, pregunta, args.k, filtro, args.umbral, args.prompt)
            seg = time.time() - inicio

            recuperados = " || ".join(
                "%s > %s (%.3f)" % (d, s, dist) for d, s, _, _, dist in filas)
            textos = " ||| ".join(t for _, _, _, t, _ in filas)
            if esperado:
                ok = any(esperado[0].lower() in d.lower() and esperado[1].lower() in s.lower()
                         for d, s, _, _, _ in filas)
                auto_rec = "Sí: recuperó la sección esperada" if ok else "No: la sección esperada no está entre los fragmentos"
                faltan = [c for c in claves if _norm(c) not in _norm(respuesta)]
                auto_resp = ("Contiene las palabras clave" if not faltan
                             else "Faltan palabras clave: " + ", ".join(faltan))
            else:
                auto_rec = "No aplica"
                dijo_no = _norm(NO_INFO) in _norm(respuesta)
                auto_resp = ("Respondió la frase de no-información" if dijo_no
                             else "NO respondió la frase de no-información (revisar si inventó)")
            w.writerow([n, tipo, pregunta, filtro or "", recuperados, textos, referencia, auto_rec,
                        respuesta, auto_resp, "%.1f" % seg, "", ""])
            f.flush()
            print("[%s] %s\n     recuperación: %s | respuesta: %s | %.1f s"
                  % (n, pregunta, auto_rec, auto_resp, seg))
    conn.close()
    print("\nResultados guardados en %s (complete a mano las dos últimas columnas)." % ruta)


if __name__ == "__main__":
    main()
