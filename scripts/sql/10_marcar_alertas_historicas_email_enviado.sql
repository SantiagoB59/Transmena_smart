-- =============================================================
-- DEFINITIVO: EVITAR LA AVALANCHA DE CORREOS DE ALERTAS ANTIGUAS
-- Motor: MySQL 5.7 (sin WITH / sin ROW_NUMBER)
-- IMPORTANTE: seleccionar la BD antes de ejecutar:
--   USE transmena_blanco;
-- =============================================================
-- Motivo:
--   El motor de alertas corre cada 15 min y REUTILIZA las filas
--   existentes. Las alertas históricas tienen email_enviado = 0,
--   por lo que el primer ciclo después de desplegar el control
--   "un correo por episodio" envió un correo por cada alerta vieja.
--
-- Qué hace:
--   1. Crea una copia de seguridad de `alertas`.
--   2. Muestra cuántas filas se van a marcar.
--   3. Marca TODAS las alertas existentes como ya notificadas.
--   4. Verifica el resultado.
--
-- Las alertas nuevas que se creen DESPUÉS de este script seguirán
-- naciendo con email_enviado = 0 y enviarán su correo normalmente.
--
-- No se tocan mantenimientos, planes, km ni el estado de las alertas.
-- =============================================================

-- -------------------------------------------------------------
-- 0. EVITAR ERROR 1175 DE WORKBENCH (SAFE UPDATE)
-- -------------------------------------------------------------
SET SQL_SAFE_UPDATES = 0;

-- -------------------------------------------------------------
-- 1. RESPALDO
-- -------------------------------------------------------------
DROP TABLE IF EXISTS alertas_bak_email_20261126;

CREATE TABLE alertas_bak_email_20261126 LIKE alertas;

INSERT INTO alertas_bak_email_20261126
SELECT * FROM alertas;

-- -------------------------------------------------------------
-- 2. PREVIEW: cuántas se van a marcar
-- -------------------------------------------------------------
SELECT
    COUNT(*) AS total_alertas,
    SUM(email_enviado = 0 OR email_enviado IS NULL) AS sin_email,
    SUM(
        estado = 'ACTIVA'
        AND prioridad IN ('CRITICA', 'ALTA')
        AND (email_enviado = 0 OR email_enviado IS NULL)
    ) AS criticas_activas_sin_email
FROM alertas;

-- -------------------------------------------------------------
-- 3. MARCADO
-- -------------------------------------------------------------
UPDATE alertas
SET email_enviado = 1
WHERE email_enviado = 0
   OR email_enviado IS NULL;

-- -------------------------------------------------------------
-- 4. VALIDACIÓN: debe devolver 0
-- -------------------------------------------------------------
SELECT COUNT(*) AS alertas_sin_email_restantes
FROM alertas
WHERE email_enviado = 0
   OR email_enviado IS NULL;

SELECT
    estado,
    prioridad,
    COUNT(*) AS total,
    SUM(email_enviado = 1) AS notificadas
FROM alertas
GROUP BY estado, prioridad
ORDER BY estado, prioridad;

-- -------------------------------------------------------------
-- 5. RESTAURA DE SAFE UPDATE
-- -------------------------------------------------------------
SET SQL_SAFE_UPDATES = 1;

-- -------------------------------------------------------------
-- RESTAURA (solo si necesitás volver al estado anterior):
--   UPDATE alertas a
--   JOIN alertas_bak_email_20261126 b ON b.id = a.id
--   SET a.email_enviado = b.email_enviado;
-- -------------------------------------------------------------
