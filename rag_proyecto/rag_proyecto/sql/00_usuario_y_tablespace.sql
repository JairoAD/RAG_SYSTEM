/* =====================================================================
   00_usuario_y_tablespace.sql
   Proyecto: Mini sistema RAG con Oracle AI Database 26ai
   EJECUTAR: como SYSTEM, conectado a FREEPDB1.

   DECISIONES
   - Tablespace propio (RAG_DATA) con gestión automática de espacio de
     segmentos: el tablespace SYSTEM no admite columnas VECTOR (ORA-43853) y
     la imagen oracle-free-lite no trae el tablespace USERS.
   - El archivo de datos queda en /opt/oracle/oradata, la carpeta que el
     contenedor monta como volumen persistente: los datos sobreviven si se
     recrea el contenedor.
   - Usuario del proyecto sin privilegios de administrador (DB_DEVELOPER_ROLE).
   ===================================================================== */

CREATE TABLESPACE rag_data
  DATAFILE '/opt/oracle/oradata/FREE/FREEPDB1/rag_data01.dbf' SIZE 200M
  AUTOEXTEND ON NEXT 50M MAXSIZE 1G
  EXTENT MANAGEMENT LOCAL SEGMENT SPACE MANAGEMENT AUTO;

-- Cambiar CAMBIAR_ESTA_CLAVE por una clave propia. NO subirla al repositorio:
-- se guarda solo en el archivo .env local.
CREATE USER rag_user IDENTIFIED BY "CAMBIAR_ESTA_CLAVE"
  DEFAULT TABLESPACE rag_data QUOTA UNLIMITED ON rag_data;

GRANT DB_DEVELOPER_ROLE TO rag_user;

-- VERIFICACIÓN: DEFAULT_TABLESPACE debe ser RAG_DATA.
SELECT username, default_tablespace FROM dba_users WHERE username = 'RAG_USER';
