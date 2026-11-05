/* =====================================================================
   02_prueba_vectores.sql
   Proyecto: Mini sistema RAG con Oracle AI Database 26ai

   OBJETIVO
   Comprobar, como RAG_USER y SIN usar la red, que la imagen "lite"
   soporta lo que el Plan B necesita de la base de datos:
     C1. tipo VECTOR y búsqueda por similitud con VECTOR_DISTANCE
     C2. fragmentación con VECTOR_CHUNKS (si falla, se fragmenta en Python)

   CONTEXTO
   La base no puede llamar a Ollama porque en esta imagen no existe el
   paquete SYS.DBMS_NETWORK_ACL_ADMIN (ver bitácora). Por eso los vectores
   se generarán desde Python y Oracle se usará para almacenarlos y buscar.

   EJECUTAR: en SQL Developer, conectado como RAG_USER (sesión nueva).
   ===================================================================== */

-- C1. Tipo VECTOR y distancia coseno con vectores de 3 dimensiones.
CREATE TABLE prueba_vec (
  id NUMBER,
  v  VECTOR(3, FLOAT32)
);

INSERT INTO prueba_vec VALUES (1, '[1, 0, 0]');
INSERT INTO prueba_vec VALUES (2, '[0, 1, 0]');
INSERT INTO prueba_vec VALUES (3, '[0.9, 0.1, 0]');
COMMIT;

-- RESULTADO ESPERADO, en este orden:
--   id 1 -> distancia 0
--   id 3 -> distancia cercana a 0.006
--   id 2 -> distancia 1
SELECT id,
       VECTOR_DISTANCE(v, TO_VECTOR('[1, 0, 0]'), COSINE) AS distancia
FROM   prueba_vec
ORDER  BY distancia;

DROP TABLE prueba_vec PURGE;


-- C2. Fragmentación con VECTOR_CHUNKS sobre un texto de ejemplo.
-- RESULTADO ESPERADO: varias filas con chunk_offset, chunk_length y chunk_text.
-- (MAX 10 es el mínimo permitido; OVERLAP debe estar entre 5 % y 20 % de MAX.)
SELECT c.chunk_offset, c.chunk_length, c.chunk_text
FROM   (SELECT 'Turn the device on. Press and hold the Side button for a few seconds. '
             || 'Release the button when the logo appears. Wait until the Home screen '
             || 'is displayed. Then follow the on-screen instructions to finish the setup.' AS txt
        FROM dual) d,
       VECTOR_CHUNKS(d.txt
                     BY WORDS
                     MAX 10
                     OVERLAP 1
                     SPLIT BY SENTENCE
                     NORMALIZE ALL) c;

/* =====================================================================
   QUÉ REPORTAR
   El resultado de C1 y C2, o el mensaje de error completo desde la
   primera línea. Si algo falla, reconectar antes de volver a intentar.
   ===================================================================== */
