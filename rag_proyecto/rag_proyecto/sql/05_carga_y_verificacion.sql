/* =====================================================================
   05_carga_y_verificacion.sql
   Proyecto: Mini sistema RAG con Oracle AI Database 26ai
   EJECUTAR: como RAG_USER, solo las consultas de verificación (parte B).

   PARTE A - Sentencias de carga que ejecutan los scripts de Python
   (referencia; las variables :nombre las asigna Python, por eso no se
   ejecutan a mano). La carga y la generación de vectores se hacen desde
   Python porque la imagen lite no permite que la base llame a Ollama
   (ver 01_diagnostico_red_ollama.sql).
   ===================================================================== */

-- A1. ingest.py: un documento por manual (devuelve el id generado).
-- INSERT INTO documento (titulo, fuente)
-- VALUES (:titulo, :nombre_del_pdf)
-- RETURNING id_documento INTO :id;

-- A2. ingest.py: una sección por cada marcador del PDF (texto limpio completo).
-- INSERT INTO seccion (id_documento, titulo, pagina_inicio, pagina_fin, contenido)
-- VALUES (:id_documento, :titulo, :p_ini, :p_fin, :contenido);

-- A3. embed.py: fragmentos de 120 palabras (traslape 20) y su vector de 384
--     dimensiones, calculado con all-minilm a través de Ollama.
-- INSERT INTO fragmento (id_seccion, posicion, texto, embedding)
-- VALUES (:id_seccion, :posicion, :texto, :vector);


/* =====================================================================
   PARTE B - Verificación de la carga (ejecutable)
   ===================================================================== */

-- B1. Conteo por manual.
-- RESULTADO ESPERADO (carga por defecto): 50, 74 y 62 secciones; 334, 396 y 245 fragmentos.
SELECT d.titulo,
       COUNT(DISTINCT s.id_seccion) AS secciones,
       COUNT(f.id_fragmento)        AS fragmentos
FROM   documento d
JOIN   seccion s      ON s.id_documento = d.id_documento
LEFT   JOIN fragmento f ON f.id_seccion = s.id_seccion
GROUP  BY d.titulo
ORDER  BY d.titulo;

-- B2. Todos los fragmentos tienen vector y su dimensión coincide con la columna.
-- RESULTADO ESPERADO: 975 fragmentos, 975 con vector, dimensiones 384 a 384.
SELECT COUNT(*)                                 AS fragmentos,
       COUNT(embedding)                         AS con_vector,
       MIN(VECTOR_DIMENSION_COUNT(embedding))   AS dim_min,
       MAX(VECTOR_DIMENSION_COUNT(embedding))   AS dim_max
FROM   fragmento;

-- B3. Muestra de fragmentos con su procedencia (documento, sección y posición).
SELECT d.titulo AS documento, s.titulo AS seccion, f.posicion,
       SUBSTR(f.texto, 1, 80) AS inicio_del_texto
FROM   fragmento f
JOIN   seccion   s ON s.id_seccion   = f.id_seccion
JOIN   documento d ON d.id_documento = s.id_documento
ORDER  BY f.id_fragmento
FETCH  FIRST 5 ROWS ONLY;
