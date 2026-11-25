-- =============================================================
-- ELIMINAR ALERTAS DE VEHÍCULOS INACTIVOS
-- Motor: MySQL 5.7 (sin WITH / sin ROW_NUMBER)
-- IMPORTANTE: selecciona la BD antes de ejecutar (descomenta una):
--   USE transmena_23112026;
--   USE transmena_smart_backup;
-- =============================================================
-- Criterio de "vehículo inactivo" (el mismo que usa el backend):
--   UPPER(TRIM(estado)) = 'INACTIVO'  OR  activo = 0
--
-- Se borran las alertas vinculadas por CUALQUIERA de estas rutas:
--   1. alertas.vehiculo_id directo
--   2. alertas.vehiculo_plan_item_id -> vehiculo_plan_item.vehiculo_id
--   3. alertas.vehiculo_plan_item_detalle_id
--        -> vehiculo_plan_item_detalles.vehiculo_plan_item_id
--        -> vehiculo_plan_item.vehiculo_id
--
-- No se tocan mantenimientos, planes, km ni alerta_valor.
-- No existen FKs que referencien la tabla alertas, por lo que
-- borrar estas filas no afecta otras tablas.
--
-- NOTA: la tabla de trabajo es NORMAL (no TEMPORARY) porque MySQL 5.7
-- no permite referenciar una tabla temporal más de una vez en la
-- misma consulta (Error 1137: Can't reopen table).
-- =============================================================

-- -------------------------------------------------------------
-- 0. EVITAR ERROR 1175 DE WORKBENCH (SAFE UPDATE)
-- -------------------------------------------------------------
SET SQL_SAFE_UPDATES = 0;

-- -------------------------------------------------------------
-- 1. VEHÍCULOS INACTIVOS (TABLA NORMAL DE TRABAJO)
-- -------------------------------------------------------------
-- Por si quedó una temporal de un intento anterior en la misma sesión
DROP TEMPORARY TABLE IF EXISTS tmp_vehiculos_inactivos;

DROP TABLE IF EXISTS tmp_vehiculos_inactivos_20261125;

CREATE TABLE tmp_vehiculos_inactivos_20261125 (
    id INT NOT NULL PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

INSERT INTO tmp_vehiculos_inactivos_20261125 (id)
SELECT v.id
FROM vehiculos v
WHERE UPPER(TRIM(COALESCE(v.estado, ''))) = 'INACTIVO'
   OR v.activo = 0;

-- -------------------------------------------------------------
-- 2. RESPALDO DE LAS ALERTAS QUE SE VAN A BORRAR
-- -------------------------------------------------------------
DROP TABLE IF EXISTS alertas_bak_inactivas_20261125;

CREATE TABLE alertas_bak_inactivas_20261125 LIKE alertas;

INSERT INTO alertas_bak_inactivas_20261125
SELECT a.*
FROM alertas a
WHERE a.id > 0
  AND (
        a.vehiculo_id IN (SELECT id FROM tmp_vehiculos_inactivos_20261125)
     OR a.vehiculo_plan_item_id IN (
            SELECT vpi.id
            FROM vehiculo_plan_item vpi
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
     OR a.vehiculo_plan_item_detalle_id IN (
            SELECT vpd.id
            FROM vehiculo_plan_item_detalles vpd
            INNER JOIN vehiculo_plan_item vpi
                    ON vpi.id = vpd.vehiculo_plan_item_id
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
  );

-- -------------------------------------------------------------
-- 3. DETECCIÓN / PREVIEW
--    Antes de borrar, revisa qué se va a eliminar.
-- -------------------------------------------------------------
SELECT
    a.id AS alerta_id,
    a.vehiculo_id,
    v.placa,
    v.estado,
    v.activo,
    a.tipo,
    a.categoria,
    a.estado AS estado_alerta,
    a.created_at
FROM alertas a
LEFT JOIN vehiculos v
       ON v.id = a.vehiculo_id
LEFT JOIN vehiculo_plan_item vpi
       ON vpi.id = a.vehiculo_plan_item_id
LEFT JOIN vehiculo_plan_item_detalles vpd
       ON vpd.id = a.vehiculo_plan_item_detalle_id
WHERE a.id > 0
  AND (
        a.vehiculo_id IN (SELECT id FROM tmp_vehiculos_inactivos_20261125)
     OR vpi.vehiculo_id IN (SELECT id FROM tmp_vehiculos_inactivos_20261125)
     OR vpd.vehiculo_plan_item_id IN (
            SELECT id
            FROM vehiculo_plan_item
            WHERE vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
  )
ORDER BY a.id;

-- Total que se va a borrar
SELECT COUNT(*) AS alertas_a_eliminar
FROM alertas a
WHERE a.id > 0
  AND (
        a.vehiculo_id IN (SELECT id FROM tmp_vehiculos_inactivos_20261125)
     OR a.vehiculo_plan_item_id IN (
            SELECT vpi.id
            FROM vehiculo_plan_item vpi
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
     OR a.vehiculo_plan_item_detalle_id IN (
            SELECT vpd.id
            FROM vehiculo_plan_item_detalles vpd
            INNER JOIN vehiculo_plan_item vpi
                    ON vpi.id = vpd.vehiculo_plan_item_id
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
  );

-- -------------------------------------------------------------
-- 4. BORRADO
-- -------------------------------------------------------------
DELETE FROM alertas
WHERE id > 0
  AND (
        vehiculo_id IN (SELECT id FROM tmp_vehiculos_inactivos_20261125)
     OR vehiculo_plan_item_id IN (
            SELECT vpi.id
            FROM vehiculo_plan_item vpi
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
     OR vehiculo_plan_item_detalle_id IN (
            SELECT vpd.id
            FROM vehiculo_plan_item_detalles vpd
            INNER JOIN vehiculo_plan_item vpi
                    ON vpi.id = vpd.vehiculo_plan_item_id
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
  );

-- -------------------------------------------------------------
-- 5. VALIDACIÓN FINAL
--    Debe devolver 0 en las tres consultas.
-- -------------------------------------------------------------
SELECT COUNT(*) AS alertas_restantes_inactivos
FROM alertas a
WHERE a.id > 0
  AND (
        a.vehiculo_id IN (SELECT id FROM tmp_vehiculos_inactivos_20261125)
     OR a.vehiculo_plan_item_id IN (
            SELECT vpi.id
            FROM vehiculo_plan_item vpi
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
     OR a.vehiculo_plan_item_detalle_id IN (
            SELECT vpd.id
            FROM vehiculo_plan_item_detalles vpd
            INNER JOIN vehiculo_plan_item vpi
                    ON vpi.id = vpd.vehiculo_plan_item_id
            WHERE vpi.vehiculo_id IN (
                SELECT id FROM tmp_vehiculos_inactivos_20261125
            )
        )
  );

SELECT
    v.id,
    v.placa,
    v.estado,
    COUNT(a.id) AS alertas_que_quedaron
FROM vehiculos v
LEFT JOIN alertas a ON a.vehiculo_id = v.id
WHERE v.id IN (SELECT id FROM tmp_vehiculos_inactivos_20261125)
GROUP BY v.id, v.placa, v.estado
ORDER BY v.id;

SELECT COUNT(*) AS copia_seguridad
FROM alertas_bak_inactivas_20261125;

-- -------------------------------------------------------------
-- 6. LIMPIEZA Y RESTAURA DE SAFE UPDATE
-- -------------------------------------------------------------
DROP TABLE IF EXISTS tmp_vehiculos_inactivos_20261125;

SET SQL_SAFE_UPDATES = 1;

-- -------------------------------------------------------------
-- RESTAURA (solo si necesitas devolver las alertas borradas):
--   INSERT INTO alertas
--   SELECT * FROM alertas_bak_inactivas_20261125;
--
-- Ojo: ejecutarla solo si no se han creado alertas nuevas con los
-- mismos IDs; si hay conflicto usa INSERT IGNORE.
-- -------------------------------------------------------------
