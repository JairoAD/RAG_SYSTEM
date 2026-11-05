/* =====================================================================
   04_consulta_similitud.sql
   Proyecto: Mini sistema RAG con Oracle AI Database 26ai
   EJECUTAR: como RAG_USER, en FREEPDB1, después de python embed.py.

   OBJETIVO
   Mostrar la recuperación por similitud en SQL puro (requisito del
   enunciado y parte del video). Los vectores de las preguntas los genera
   Python (ask.py) y llegan a esta misma consulta como variable :qv; aquí
   se usa como vector de referencia el de un fragmento ya guardado, para
   poder ejecutarla sin salir de SQL Developer.
   ===================================================================== */

-- Q0. Estado de la carga: documentos, secciones y fragmentos con vector.
-- RESULTADO ESPERADO (carga por defecto): 3 documentos, 186 secciones, 975 fragmentos.
SELECT (SELECT COUNT(*) FROM documento)                        AS documentos,
       (SELECT COUNT(*) FROM seccion)                          AS secciones,
       (SELECT COUNT(*) FROM fragmento)                        AS fragmentos,
       (SELECT COUNT(*) FROM fragmento WHERE embedding IS NOT NULL) AS con_vector
FROM   dual;

-- Q1. Los 6 fragmentos más cercanos al primer fragmento de
--     "Charging the battery" del reloj.
-- RESULTADO ESPERADO: la primera fila es el propio fragmento (distancia 0);
-- las siguientes suelen ser de secciones de carga de los otros manuales.
WITH ref AS (
  SELECT f.embedding
  FROM   fragmento f
  JOIN   seccion   s ON s.id_seccion   = f.id_seccion
  JOIN   documento d ON d.id_documento = s.id_documento
  WHERE  d.titulo LIKE '%Watch8%'
  AND    s.titulo LIKE '%Charging the battery%'
  ORDER  BY f.posicion
  FETCH  FIRST 1 ROWS ONLY
)
SELECT d.titulo AS documento,
       s.titulo AS seccion,
       ROUND(VECTOR_DISTANCE(f.embedding, ref.embedding, COSINE), 4) AS distancia,
       SUBSTR(f.texto, 1, 90) AS inicio_del_texto
FROM   fragmento f
JOIN   seccion   s ON s.id_seccion   = f.id_seccion
JOIN   documento d ON d.id_documento = s.id_documento
CROSS  JOIN ref
ORDER  BY distancia
FETCH  FIRST 6 ROWS ONLY;

-- Q2. Búsqueda híbrida: la misma similitud, pero solo dentro del manual de la
--     tableta (filtro relacional por documento). Es el elemento opcional
--     "búsqueda híbrida" del apartado 5.3 del enunciado.
WITH ref AS (
  SELECT f.embedding
  FROM   fragmento f
  JOIN   seccion   s ON s.id_seccion   = f.id_seccion
  JOIN   documento d ON d.id_documento = s.id_documento
  WHERE  d.titulo LIKE '%Watch8%'
  AND    s.titulo LIKE '%Charging the battery%'
  ORDER  BY f.posicion
  FETCH  FIRST 1 ROWS ONLY
)
SELECT d.titulo AS documento,
       s.titulo AS seccion,
       ROUND(VECTOR_DISTANCE(f.embedding, ref.embedding, COSINE), 4) AS distancia,
       SUBSTR(f.texto, 1, 90) AS inicio_del_texto
FROM   fragmento f
JOIN   seccion   s ON s.id_seccion   = f.id_seccion
JOIN   documento d ON d.id_documento = s.id_documento
CROSS  JOIN ref
WHERE  d.titulo LIKE '%tablet%'
ORDER  BY distancia
FETCH  FIRST 6 ROWS ONLY;

/* Q3. La consulta que ejecuta ask.py para cada pregunta (referencia; no se
   corre aquí porque :qv es el vector de la pregunta, generado en Python):

   SELECT d.titulo, s.titulo, s.pagina_inicio, f.texto,
          VECTOR_DISTANCE(f.embedding, :qv, COSINE) AS distancia
   FROM   fragmento f
   JOIN   seccion   s ON s.id_seccion   = f.id_seccion
   JOIN   documento d ON d.id_documento = s.id_documento
   [WHERE LOWER(d.titulo) LIKE '%' || LOWER(:doc) || '%']   -- búsqueda híbrida
   ORDER  BY distancia
   FETCH  FIRST :k ROWS ONLY;
*/
