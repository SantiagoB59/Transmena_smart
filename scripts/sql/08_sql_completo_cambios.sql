-- =============================================================
-- SQL UNICO DE EJECUCION - CAMBIOS YA IMPLEMENTADOS
-- Motor: MySQL 5.7 (sin WITH / sin ROW_NUMBER)
-- IMPORTANTE: selecciona la BD antes de ejecutar (descomenta una):
--   USE transmena_23112026;
--   USE transmena_smart_backup;
-- =============================================================
-- SI EJECUTAR:
--   1. Respaldo de las tablas que se tocan
--   2. Deteccion de correctivos repetidos
--   3. Reenlace de FK de alertas (SOLO FK, sin cambiar estado
--      ni alerta_valor)
--   4. Borrado de correctivos repetidos: vehiculos y maquinaria
--   5. Validacion final
--
-- NO INCLUIDO / SE DEJA TAL CUAL:
--   - 02_correccion_alerta_valor.sql  -> intacto, no se ejecuta aqui
--   - 03_sincronizar_ultimo_km.sql    -> intacto, no se ejecuta aqui
--   - 04_corregir_km_vehiculos.sql    -> intacto, no se ejecuta aqui
--   - No se modifica alerta_valor, ultimo_km, ultima_fecha,
--     km_actual, km_base_control ni km_gps_inicial.
--
-- NOTA: los IDs 171, 232 y 263 ya fueron eliminados. El bloque
-- generico de abajo cubre cualquier otro correctivo repetido.
--
-- REGLA: de cada item del plan se conserva el PRIMER arreglo
-- (fecha, id) y se borran los demas.
-- =============================================================

-- -------------------------------------------------------------
-- 0. EVITAR ERROR 1175 DE WORKBENCH (SAFE UPDATE)
-- -------------------------------------------------------------
SET SQL_SAFE_UPDATES = 0;

-- -------------------------------------------------------------
-- 1. RESPALDO
-- -------------------------------------------------------------
DROP TABLE IF EXISTS mantenimientos_bak_corr_20261124;
CREATE TABLE mantenimientos_bak_corr_20261124 LIKE mantenimientos;
INSERT INTO mantenimientos_bak_corr_20261124 SELECT * FROM mantenimientos;

DROP TABLE IF EXISTS maquinaria_mantenimientos_bak_corr_20261124;
CREATE TABLE maquinaria_mantenimientos_bak_corr_20261124 LIKE maquinaria_mantenimientos;
INSERT INTO maquinaria_mantenimientos_bak_corr_20261124 SELECT * FROM maquinaria_mantenimientos;

DROP TABLE IF EXISTS alertas_bak_corr_20261124;
CREATE TABLE alertas_bak_corr_20261124 LIKE alertas;
INSERT INTO alertas_bak_corr_20261124 SELECT * FROM alertas;

-- -------------------------------------------------------------
-- 2. DETECCION - VEHICULOS
--    Debe devolver los correctivos repetidos (se conserva el
--    primero (los demas se borran).
-- -------------------------------------------------------------
SELECT
    m.id,
    m.vehiculo_id,
    m.vehiculo_plan_item_id,
    m.fecha,
    m.km,
    m.tipo,
    k.id_conservar,
    k.total
FROM mantenimientos m
INNER JOIN vehiculo_plan_item vpi ON vpi.id = m.vehiculo_plan_item_id
INNER JOIN plan_items pi ON pi.id = vpi.plan_item_id
JOIN (
    SELECT
        m2.vehiculo_plan_item_id,
        CAST(SUBSTRING_INDEX(
            GROUP_CONCAT(m2.id ORDER BY m2.fecha ASC, m2.id ASC),
            ',', 1
        ) AS UNSIGNED) AS id_conservar,
        COUNT(*) AS total
    FROM mantenimientos m2
    INNER JOIN vehiculo_plan_item vpi2 ON vpi2.id = m2.vehiculo_plan_item_id
    INNER JOIN plan_items pi2 ON pi2.id = vpi2.plan_item_id
    WHERE m2.completado = 1
      AND TRIM(UPPER(pi2.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
    GROUP BY m2.vehiculo_plan_item_id
) k ON k.vehiculo_plan_item_id = m.vehiculo_plan_item_id
WHERE m.completado = 1
  AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
  AND TRIM(UPPER(COALESCE(m.tipo, ''))) NOT IN (
      'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
  )
  AND m.id <> k.id_conservar
ORDER BY m.vehiculo_plan_item_id, m.fecha, m.id;

-- -------------------------------------------------------------
-- 3. DETECCION - MAQUINARIA
-- -------------------------------------------------------------
SELECT
    m.id,
    m.maquinaria_id,
    m.maquinaria_plan_item_id,
    m.fecha,
    m.horas,
    m.tipo,
    k.id_conservar,
    k.total
FROM maquinaria_mantenimientos m
INNER JOIN maquinaria_plan_item mpi ON mpi.id = m.maquinaria_plan_item_id
INNER JOIN plan_items pi ON pi.id = mpi.plan_item_id
JOIN (
    SELECT
        m2.maquinaria_plan_item_id,
        CAST(SUBSTRING_INDEX(
            GROUP_CONCAT(m2.id ORDER BY m2.fecha ASC, m2.id ASC),
            ',', 1
        ) AS UNSIGNED) AS id_conservar,
        COUNT(*) AS total
    FROM maquinaria_mantenimientos m2
    INNER JOIN maquinaria_plan_item mpi2 ON mpi2.id = m2.maquinaria_plan_item_id
    INNER JOIN plan_items pi2 ON pi2.id = mpi2.plan_item_id
    WHERE m2.completado = 1
      AND TRIM(UPPER(pi2.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
    GROUP BY m2.maquinaria_plan_item_id
) k ON k.maquinaria_plan_item_id = m.maquinaria_plan_item_id
WHERE m.completado = 1
  AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
  AND TRIM(UPPER(COALESCE(m.tipo, ''))) NOT IN (
      'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
  )
  AND m.id <> k.id_conservar
ORDER BY m.maquinaria_plan_item_id, m.fecha, m.id;

-- -------------------------------------------------------------
-- 4. REENLACE DE FK DE ALERTAS - VEHICULOS
--    Solo FK. NO cambia estado, NO cambia alerta_valor.
-- -------------------------------------------------------------
UPDATE alertas a
JOIN (
    SELECT
        m.id AS id_borrar,
        k.id_conservar
    FROM mantenimientos m
    INNER JOIN vehiculo_plan_item vpi ON vpi.id = m.vehiculo_plan_item_id
    INNER JOIN plan_items pi ON pi.id = vpi.plan_item_id
    JOIN (
        SELECT
            m2.vehiculo_plan_item_id,
            CAST(SUBSTRING_INDEX(
                GROUP_CONCAT(m2.id ORDER BY m2.fecha ASC, m2.id ASC),
                ',', 1
            ) AS UNSIGNED) AS id_conservar
        FROM mantenimientos m2
        INNER JOIN vehiculo_plan_item vpi2 ON vpi2.id = m2.vehiculo_plan_item_id
        INNER JOIN plan_items pi2 ON pi2.id = vpi2.plan_item_id
        WHERE m2.completado = 1
          AND TRIM(UPPER(pi2.tipo_mantenimiento)) = 'CORRECTIVO'
          AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
              'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
          )
        GROUP BY m2.vehiculo_plan_item_id
    ) k ON k.vehiculo_plan_item_id = m.vehiculo_plan_item_id
    WHERE m.completado = 1
      AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
      AND m.id <> k.id_conservar
) d ON d.id_borrar = a.mantenimiento_id
SET a.mantenimiento_id = d.id_conservar
WHERE a.id > 0;

-- -------------------------------------------------------------
-- 5. REENLACE DE FK DE ALERTAS - MAQUINARIA
-- -------------------------------------------------------------
UPDATE alertas a
JOIN (
    SELECT
        m.id AS id_borrar,
        k.id_conservar
    FROM maquinaria_mantenimientos m
    INNER JOIN maquinaria_plan_item mpi ON mpi.id = m.maquinaria_plan_item_id
    INNER JOIN plan_items pi ON pi.id = mpi.plan_item_id
    JOIN (
        SELECT
            m2.maquinaria_plan_item_id,
            CAST(SUBSTRING_INDEX(
                GROUP_CONCAT(m2.id ORDER BY m2.fecha ASC, m2.id ASC),
                ',', 1
            ) AS UNSIGNED) AS id_conservar
        FROM maquinaria_mantenimientos m2
        INNER JOIN maquinaria_plan_item mpi2 ON mpi2.id = m2.maquinaria_plan_item_id
        INNER JOIN plan_items pi2 ON pi2.id = mpi2.plan_item_id
        WHERE m2.completado = 1
          AND TRIM(UPPER(pi2.tipo_mantenimiento)) = 'CORRECTIVO'
          AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
              'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
          )
        GROUP BY m2.maquinaria_plan_item_id
    ) k ON k.maquinaria_plan_item_id = m.maquinaria_plan_item_id
    WHERE m.completado = 1
      AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
      AND m.id <> k.id_conservar
) d ON d.id_borrar = a.maquinaria_mantenimiento_id
SET a.maquinaria_mantenimiento_id = d.id_conservar
WHERE a.id > 0;

-- -------------------------------------------------------------
-- 6. BORRADO DE CORRECTIVOS REPETIDOS - VEHICULOS
--    Unico cambio de datos permitido. No actualiza km ni alertas.
-- -------------------------------------------------------------
DELETE m
FROM mantenimientos m
JOIN (
    SELECT
        m2.id AS id_borrar
    FROM mantenimientos m2
    INNER JOIN vehiculo_plan_item vpi ON vpi.id = m2.vehiculo_plan_item_id
    INNER JOIN plan_items pi ON pi.id = vpi.plan_item_id
    JOIN (
        SELECT
            m3.vehiculo_plan_item_id,
            CAST(SUBSTRING_INDEX(
                GROUP_CONCAT(m3.id ORDER BY m3.fecha ASC, m3.id ASC),
                ',', 1
            ) AS UNSIGNED) AS id_conservar
        FROM mantenimientos m3
        INNER JOIN vehiculo_plan_item vpi3 ON vpi3.id = m3.vehiculo_plan_item_id
        INNER JOIN plan_items pi3 ON pi3.id = vpi3.plan_item_id
        WHERE m3.completado = 1
          AND TRIM(UPPER(pi3.tipo_mantenimiento)) = 'CORRECTIVO'
          AND TRIM(UPPER(COALESCE(m3.tipo, ''))) NOT IN (
              'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
          )
        GROUP BY m3.vehiculo_plan_item_id
    ) k ON k.vehiculo_plan_item_id = m2.vehiculo_plan_item_id
    WHERE m2.completado = 1
      AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
      AND m2.id <> k.id_conservar
) d ON d.id_borrar = m.id
WHERE m.id > 0;

-- -------------------------------------------------------------
-- 7. BORRADO DE CORRECTIVOS REPETIDOS - MAQUINARIA
-- -------------------------------------------------------------
DELETE mm
FROM maquinaria_mantenimientos mm
JOIN (
    SELECT
        m2.id AS id_borrar
    FROM maquinaria_mantenimientos m2
    INNER JOIN maquinaria_plan_item mpi ON mpi.id = m2.maquinaria_plan_item_id
    INNER JOIN plan_items pi ON pi.id = mpi.plan_item_id
    JOIN (
        SELECT
            m3.maquinaria_plan_item_id,
            CAST(SUBSTRING_INDEX(
                GROUP_CONCAT(m3.id ORDER BY m3.fecha ASC, m3.id ASC),
                ',', 1
            ) AS UNSIGNED) AS id_conservar
        FROM maquinaria_mantenimientos m3
        INNER JOIN maquinaria_plan_item mpi3 ON mpi3.id = m3.maquinaria_plan_item_id
        INNER JOIN plan_items pi3 ON pi3.id = mpi3.plan_item_id
        WHERE m3.completado = 1
          AND TRIM(UPPER(pi3.tipo_mantenimiento)) = 'CORRECTIVO'
          AND TRIM(UPPER(COALESCE(m3.tipo, ''))) NOT IN (
              'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
          )
        GROUP BY m3.maquinaria_plan_item_id
    ) k ON k.maquinaria_plan_item_id = m2.maquinaria_plan_item_id
    WHERE m2.completado = 1
      AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
      AND m2.id <> k.id_conservar
) d ON d.id_borrar = mm.id
WHERE mm.id > 0;

-- -------------------------------------------------------------
-- 8. VALIDACION FINAL
--    Las siguientes consultas deben devolver 0 filas.
-- -------------------------------------------------------------
SELECT id_borrar AS id, 'duplicado_vehiculo' AS problema
FROM (
    SELECT m.id AS id_borrar
    FROM mantenimientos m
    INNER JOIN vehiculo_plan_item vpi ON vpi.id = m.vehiculo_plan_item_id
    INNER JOIN plan_items pi ON pi.id = vpi.plan_item_id
    JOIN (
        SELECT
            m2.vehiculo_plan_item_id,
            CAST(SUBSTRING_INDEX(
                GROUP_CONCAT(m2.id ORDER BY m2.fecha ASC, m2.id ASC),
                ',', 1
            ) AS UNSIGNED) AS id_conservar
        FROM mantenimientos m2
        INNER JOIN vehiculo_plan_item vpi2 ON vpi2.id = m2.vehiculo_plan_item_id
        INNER JOIN plan_items pi2 ON pi2.id = vpi2.plan_item_id
        WHERE m2.completado = 1
          AND TRIM(UPPER(pi2.tipo_mantenimiento)) = 'CORRECTIVO'
          AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
              'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
          )
        GROUP BY m2.vehiculo_plan_item_id
    ) k ON k.vehiculo_plan_item_id = m.vehiculo_plan_item_id
    WHERE m.completado = 1
      AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
      AND m.id <> k.id_conservar
) v;

SELECT id_borrar AS id, 'duplicado_maquinaria' AS problema
FROM (
    SELECT m.id AS id_borrar
    FROM maquinaria_mantenimientos m
    INNER JOIN maquinaria_plan_item mpi ON mpi.id = m.maquinaria_plan_item_id
    INNER JOIN plan_items pi ON pi.id = mpi.plan_item_id
    JOIN (
        SELECT
            m2.maquinaria_plan_item_id,
            CAST(SUBSTRING_INDEX(
                GROUP_CONCAT(m2.id ORDER BY m2.fecha ASC, m2.id ASC),
                ',', 1
            ) AS UNSIGNED) AS id_conservar
        FROM maquinaria_mantenimientos m2
        INNER JOIN maquinaria_plan_item mpi2 ON mpi2.id = m2.maquinaria_plan_item_id
        INNER JOIN plan_items pi2 ON pi2.id = mpi2.plan_item_id
        WHERE m2.completado = 1
          AND TRIM(UPPER(pi2.tipo_mantenimiento)) = 'CORRECTIVO'
          AND TRIM(UPPER(COALESCE(m2.tipo, ''))) NOT IN (
              'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
          )
        GROUP BY m2.maquinaria_plan_item_id
    ) k ON k.maquinaria_plan_item_id = m.maquinaria_plan_item_id
    WHERE m.completado = 1
      AND TRIM(UPPER(pi.tipo_mantenimiento)) = 'CORRECTIVO'
      AND TRIM(UPPER(COALESCE(m.tipo, ''))) NOT IN (
          'PREVENTIVO', 'PR', 'INSPECCION', 'INSPECCIÓN', 'I', 'INS'
      )
      AND m.id <> k.id_conservar
) v;

SELECT a.id, 'fk_alerta_huerfana' AS problema
FROM alertas a
LEFT JOIN mantenimientos m ON m.id = a.mantenimiento_id
WHERE a.mantenimiento_id IS NOT NULL AND m.id IS NULL;

SELECT a.id, 'fk_alerta_maq_huerfana' AS problema
FROM alertas a
LEFT JOIN maquinaria_mantenimientos mm ON mm.id = a.maquinaria_mantenimiento_id
WHERE a.maquinaria_mantenimiento_id IS NOT NULL AND mm.id IS NULL;

-- Informativo: cuantos registros se borraron en los bloques 6 y 7
SELECT
    (SELECT COUNT(*) FROM mantenimientos_bak_corr_20261124)
      - (SELECT COUNT(*) FROM mantenimientos) AS mantenimientos_eliminados,
    (SELECT COUNT(*) FROM maquinaria_mantenimientos_bak_corr_20261124)
      - (SELECT COUNT(*) FROM maquinaria_mantenimientos) AS maquinaria_eliminada;
SET SQL_SAFE_UPDATES = 1;
