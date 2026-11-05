"""fragmentar.py - división de un texto en fragmentos (chunks) con traslape.

Estrategia: se corta por oraciones y se agrupan hasta alcanzar max_words
palabras. Cada fragmento repite al inicio las últimas oraciones del anterior
(hasta overlap palabras) para no perder contexto en los bordes.
"""
import re


def _oraciones(texto):
    return [s for s in re.split(r"(?<=[.!?:])\s+", texto.strip()) if s]


def _cortar_oracion_larga(oracion, max_words, overlap):
    """Una oración más larga que max_words se parte en ventanas de palabras."""
    palabras = oracion.split()
    paso = max(1, max_words - overlap)
    return [" ".join(palabras[i:i + max_words]) for i in range(0, len(palabras), paso)]


def fragmentar(texto, max_words=120, overlap=20):
    """Devuelve la lista de fragmentos de `texto`."""
    piezas = []
    for o in _oraciones(texto):
        if len(o.split()) > max_words:
            piezas.extend(_cortar_oracion_larga(o, max_words, overlap))
        else:
            piezas.append(o)

    fragmentos = []
    actual = []        # oraciones del fragmento en construcción
    n_actual = 0       # palabras en `actual`
    hay_nuevas = False  # ¿contiene algo más que el traslape?
    for p in piezas:
        w = len(p.split())
        if actual and n_actual + w > max_words:
            if hay_nuevas:
                fragmentos.append(" ".join(actual))
            # traslape: últimas oraciones hasta `overlap` palabras
            cola, n_cola = [], 0
            for previa in reversed(actual):
                pw = len(previa.split())
                if n_cola + pw > overlap:
                    break
                cola.insert(0, previa)
                n_cola += pw
            actual, n_actual, hay_nuevas = cola, n_cola, False
            while actual and n_actual + w > max_words:  # que quepa la nueva oración
                n_actual -= len(actual.pop(0).split())
        actual.append(p)
        n_actual += w
        hay_nuevas = True
    if actual and hay_nuevas:
        fragmentos.append(" ".join(actual))
    return fragmentos
