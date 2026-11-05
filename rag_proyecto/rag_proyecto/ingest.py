"""ingest.py - lee los manuales PDF y carga sus secciones en Oracle.

Qué hace:
  1. Divide cada PDF en secciones usando los marcadores (outline) del propio PDF.
  2. Limpia el texto (encabezados, números de página, íconos, viñetas).
  3. Guarda una fila en DOCUMENTO por manual y una fila en SECCION por sección.

Uso:
  python ingest.py --probar     # solo muestra lo que se cargaría (no toca la base)
  python ingest.py              # carga en Oracle (omite los manuales ya cargados)
  python ingest.py --reset      # borra todo y vuelve a cargar

Los PDF se colocan en la carpeta manuales/ (o la indicada con --carpeta).
"""
import argparse
import re
import sys
from pathlib import Path

from pypdf import PdfReader

from fragmentar import fragmentar

# Título legible de cada manual, según el prefijo del nombre del archivo.
TITULOS = {
    "SM-L32X": "Galaxy Watch8 / Watch8 Classic user guide",
    "SM-S93X": "Galaxy S25 / S24 series user guide",
    "SM-X21X": "Galaxy tablet SM-X210 / X216B / X218B user manual",
}

# Secciones que no responden preguntas de uso y ensucian la búsqueda.
GRUPOS_EXCLUIDOS = {"usage notices"}
TITULOS_EXCLUIDOS = re.compile(
    r"hearing aid|5925-7125|technical requirements for wi-fi", re.IGNORECASE
)
MIN_PALABRAS = 30  # una sección con menos palabras no aporta contexto


def _norm(s):
    return re.sub(r"\s+", " ", s.replace("\u2019", "'")).strip().lower()


def _recorrer(reader, items, nivel=0, salida=None):
    """Aplana el outline del PDF a una lista de (nivel, título, página)."""
    salida = [] if salida is None else salida
    for it in items:
        if isinstance(it, list):
            _recorrer(reader, it, nivel + 1, salida)
        else:
            try:
                pagina = reader.get_destination_page_number(it) + 1
            except Exception:
                pagina = None
            if pagina:
                salida.append((nivel, it.title.strip(), pagina))
    return salida


def _lineas_de_pagina(texto, grupos):
    """Líneas útiles de una página, sin el encabezado ni el número de página."""
    res = []
    for i, linea in enumerate(texto.split("\n")):
        s = linea.strip()
        if not s:
            continue
        if i == 0 and _norm(s) in grupos:  # encabezado: nombre del capítulo
            continue
        if i <= 2 and s.isdigit():  # número de página
            continue
        res.append(s)
    return res


def _limpiar(texto):
    texto = re.sub(r"[\ue000-\uf8ff\u200b\ufeff]", "", texto)  # íconos y invisibles
    texto = texto.replace("\u2022", "-")                       # viñetas
    texto = re.sub(r"\(\s*\)", "", texto)                       # paréntesis vacíos
    return re.sub(r"\s+", " ", texto).strip()


def extraer_secciones(pdf):
    """Devuelve (secciones, resumen) de un PDF.

    Cada sección es un dict con: titulo, pagina_inicio, pagina_fin, contenido,
    palabras. `resumen` cuenta lo omitido y los encabezados no localizados.
    """
    reader = PdfReader(str(pdf))
    entradas = _recorrer(reader, reader.outline)
    grupos = {_norm(t) for n, t, p in entradas if n == 0}

    secs, grupo = [], ""
    for nivel, titulo, pagina in entradas:
        if nivel == 0:
            grupo = titulo
        elif nivel == 1:
            secs.append({"grupo": grupo, "titulo": titulo, "pagina": pagina})

    # Texto limpio de todo el cuerpo, como lista de (página, línea).
    lineas = []
    for num in range(secs[0]["pagina"], len(reader.pages) + 1):
        for l in _lineas_de_pagina(reader.pages[num - 1].extract_text() or "", grupos):
            lineas.append((num, l))

    # Línea donde empieza cada sección: primero coincidencia exacta del
    # encabezado y, si no, por prefijo (los títulos largos se parten en dos líneas).
    inicios, previo, no_localizados = [], 0, []
    for s in secs:
        completo = _norm(s["titulo"])
        # El marcador a veces trae una aclaración entre paréntesis que el
        # encabezado impreso no tiene: "Multi window (Using multiple apps...)".
        sin_parentesis = re.sub(r"\s*\(.*$", "", completo).strip()
        prefijo = sin_parentesis[:25]
        en_pagina = [i for i in range(previo, len(lineas)) if lineas[i][0] == s["pagina"]]
        idx = next((i for i in en_pagina if _norm(lineas[i][1]) in (completo, sin_parentesis)), None)
        if idx is None:
            idx = next((i for i in en_pagina if _norm(lineas[i][1]).startswith(prefijo)), None)
        if idx is None:
            no_localizados.append(s["titulo"])
            idx = en_pagina[0] if en_pagina else previo
        idx = max(idx, previo)
        inicios.append(idx)
        previo = idx
    inicios.append(len(lineas))

    resultado = []
    omitidas = {"grupo": 0, "titulo": 0, "corta": 0}
    for k, s in enumerate(secs):
        tramo = lineas[inicios[k]:inicios[k + 1]]
        if not tramo:
            omitidas["corta"] += 1
            continue
        if _norm(s["grupo"]) in GRUPOS_EXCLUIDOS:
            omitidas["grupo"] += 1
            continue
        if TITULOS_EXCLUIDOS.search(s["titulo"]):
            omitidas["titulo"] += 1
            continue
        contenido = _limpiar(" ".join(l for _, l in tramo))
        palabras = len(contenido.split())
        if palabras < MIN_PALABRAS:
            omitidas["corta"] += 1
            continue
        resultado.append({
            "titulo": s["grupo"] + " > " + s["titulo"],
            "pagina_inicio": tramo[0][0],
            "pagina_fin": tramo[-1][0],
            "contenido": contenido,
            "palabras": palabras,
        })
    return resultado, {"omitidas": omitidas, "no_localizados": no_localizados,
                       "secciones_pdf": len(secs)}


def _titulo_documento(pdf):
    for prefijo, titulo in TITULOS.items():
        if pdf.name.startswith(prefijo):
            return titulo
    return pdf.stem


def _probar(pdfs):
    total = {80: 0, 120: 0, 150: 0}
    for pdf in pdfs:
        secciones, res = extraer_secciones(pdf)
        palabras = sum(s["palabras"] for s in secciones)
        print("\n=== %s" % _titulo_documento(pdf))
        print("    archivo: %s" % pdf.name)
        print("    secciones en el PDF: %d | cargadas: %d | omitidas: %s | encabezados no localizados: %d"
              % (res["secciones_pdf"], len(secciones), res["omitidas"], len(res["no_localizados"])))
        for t in res["no_localizados"]:
            print("      (encabezado no localizado, se usa el inicio de su página) %s" % t[:70])
        print("    palabras cargadas: %d" % palabras)
        for s in secciones[:6]:
            print("      p%03d-%03d  %-60s %5d palabras" % (
                s["pagina_inicio"], s["pagina_fin"], s["titulo"][:60], s["palabras"]))
        print("      ...")
        for tam, traslape in ((80, 12), (120, 20), (150, 25)):
            n = sum(len(fragmentar(s["contenido"], tam, traslape)) for s in secciones)
            total[tam] += n
            print("    fragmentos con MAX %3d / OVERLAP %2d: %d" % (tam, traslape, n))
    print("\nTOTAL de fragmentos (todos los manuales): %s" % total)


def _cargar(pdfs, reset):
    import oracledb

    from common import conectar

    conn = conectar()
    cur = conn.cursor()
    if reset:
        cur.execute("DELETE FROM fragmento")
        cur.execute("DELETE FROM seccion")
        cur.execute("DELETE FROM documento")
        conn.commit()
        print("Tablas vaciadas.")
    for pdf in pdfs:
        cur.execute("SELECT COUNT(*) FROM documento WHERE fuente = :f", f=pdf.name)
        if cur.fetchone()[0]:
            print("Ya cargado, se omite: %s (use --reset para recargar)" % pdf.name)
            continue
        secciones, _ = extraer_secciones(pdf)
        id_doc = cur.var(int)
        cur.execute(
            "INSERT INTO documento (titulo, fuente) VALUES (:t, :f) RETURNING id_documento INTO :id",
            t=_titulo_documento(pdf), f=pdf.name, id=id_doc)
        id_documento = id_doc.getvalue()[0]
        for s in secciones:
            cur.setinputsizes(contenido=oracledb.DB_TYPE_CLOB)
            cur.execute(
                "INSERT INTO seccion (id_documento, titulo, pagina_inicio, pagina_fin, contenido) "
                "VALUES (:d, :t, :p_ini, :p_fin, :contenido)",
                d=id_documento, t=s["titulo"][:300], p_ini=s["pagina_inicio"],
                p_fin=s["pagina_fin"], contenido=s["contenido"])
        conn.commit()
        print("Cargado: %s (%d secciones)" % (pdf.name, len(secciones)))
    cur.execute("SELECT COUNT(*) FROM documento")
    n_doc = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM seccion")
    n_sec = cur.fetchone()[0]
    print("\nEn la base: %d documentos, %d secciones." % (n_doc, n_sec))
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Carga los manuales PDF en Oracle.")
    ap.add_argument("--carpeta", default="manuales", help="carpeta con los PDF")
    ap.add_argument("--probar", action="store_true", help="no toca la base; muestra el resumen")
    ap.add_argument("--reset", action="store_true", help="vacía las tablas antes de cargar")
    args = ap.parse_args()

    pdfs = sorted(Path(args.carpeta).glob("*.pdf"))
    if not pdfs:
        sys.exit("No hay PDF en la carpeta '%s'." % args.carpeta)
    if args.probar:
        _probar(pdfs)
    else:
        _cargar(pdfs, args.reset)


if __name__ == "__main__":
    main()
