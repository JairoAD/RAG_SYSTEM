/* =====================================================================
   NOTA IMPORTANTE (script de DIAGNÓSTICO, no forma parte de la solución final)
   Este script es el intento original de la guía: que la base de datos llame a
   Ollama con DBMS_VECTOR.UTL_TO_EMBEDDING. En la imagen oracle-free-lite FALLA
   (ORA-29332 / PLS-00201: no existe SYS.DBMS_NETWORK_ACL_ADMIN), por lo que los
   vectores se generan desde Python (embed.py). Se conserva como evidencia del
   análisis. El usuario y el tablespace se crean con 00_usuario_y_tablespace.sql.
   ===================================================================== */

/* =====================================================================
   01_entorno_y_prueba_ollama.sql
   Proyecto: Mini sistema RAG con Oracle AI Database 26ai

   OBJETIVO
   Dejar listo el usuario del proyecto y comprobar, ANTES de cargar
   datos, que la imagen "lite" soporta lo que necesitamos:
     (1) llamar a Ollama desde la base de datos (embeddings y texto)
     (2) fragmentar con VECTOR_CHUNKS
   Si alguna prueba falla, se documenta en la bitácora de IA y se
   decide entre pasar a la imagen completa o generar los vectores
   desde un script externo (alternativa b del apartado 5.2).

   CÓMO EJECUTARLO (sqlplus ya viene dentro del contenedor)
   Parte A, como administrador:
     docker exec -it oracle-free-lite sqlplus system@//localhost:1521/FREEPDB1
   Parte B, como rag_user:
     docker exec -it oracle-free-lite sqlplus rag_user@//localhost:1521/FREEPDB1
   Se pega cada bloque en la consola. Al conectarse al servicio
   FREEPDB1 no hace falta ALTER SESSION SET CONTAINER.
   ===================================================================== */


/* =====================================================================
   PARTE A - Como SYSTEM, en FREEPDB1
   ===================================================================== */

-- A1. Usuario del proyecto.
-- NO guardar la clave real en el repositorio (criterio de la rúbrica).
-- Cambiar CAMBIAR_ESTA_CLAVE antes de ejecutar y anotarla en el .env local.
CREATE USER rag_user IDENTIFIED BY "CAMBIAR_ESTA_CLAVE"
  DEFAULT TABLESPACE users QUOTA UNLIMITED ON users;

GRANT DB_DEVELOPER_ROLE TO rag_user;
-- CREATE MINING MODEL solo hace falta para la opción ONNX (alternativa a).
-- Con Ollama no se necesita, por eso no se otorga aquí.

-- A2. Permiso de red saliente hacia Ollama.
-- Oracle bloquea por defecto las conexiones salientes. Con Docker Desktop
-- en Windows, el equipo anfitrión se ve desde el contenedor como
-- host.docker.internal (puerto 11434).
BEGIN
  DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
    host => 'host.docker.internal',
    ace  => xs$ace_type(
              privilege_list => xs$name_list('connect'),
              principal_name => 'RAG_USER',
              principal_type => xs_acl.ptype_db));
END;
/


/* =====================================================================
   PARTE B - Como RAG_USER, en FREEPDB1  (pruebas de humo)
   ===================================================================== */

-- B1. Embedding con all-minilm.
-- RESULTADO ESPERADO: 384
SELECT VECTOR_DIMENSION_COUNT(
         DBMS_VECTOR.UTL_TO_EMBEDDING(
           'prueba de conexión',
           JSON('{
             "provider": "ollama",
             "host"    : "local",
             "url"     : "http://host.docker.internal:11434/api/embeddings",
             "model"   : "all-minilm"
           }'))) AS dimensiones
FROM   dual;

-- B2. Embedding con bge-m3 (multilingüe).
-- RESULTADO ESPERADO: 1024 (confirmar; de ese número depende VECTOR(n, FLOAT32)).
SELECT VECTOR_DIMENSION_COUNT(
         DBMS_VECTOR.UTL_TO_EMBEDDING(
           'prueba de conexión',
           JSON('{
             "provider": "ollama",
             "host"    : "local",
             "url"     : "http://host.docker.internal:11434/api/embeddings",
             "model"   : "bge-m3"
           }'))) AS dimensiones
FROM   dual;

-- B3. Generación de texto con llama3.2:3b.
-- RESULTADO ESPERADO: una respuesta corta (la primera vez tarda más porque
-- Ollama carga el modelo en memoria).
SELECT DBMS_VECTOR.UTL_TO_GENERATE_TEXT(
         'Responde solamente con la palabra OK.',
         JSON('{
           "provider": "ollama",
           "host"    : "local",
           "url"     : "http://host.docker.internal:11434/api/generate",
           "model"   : "llama3.2:3b"
         }')) AS respuesta
FROM   dual;

-- B4. Fragmentación con VECTOR_CHUNKS sobre un texto de ejemplo.
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
   Para cada prueba (B1 a B4): el resultado, o el mensaje de error
   completo (por ejemplo ORA-24247 = falta la ACL; ORA-29273 / ORA-12541 =
   Ollama inalcanzable). Con eso se decide el siguiente paso.
   ===================================================================== */
