-- =========================================================
-- IntelliFeet / Transmena Smart
-- Inventario de artículos del botiquín por vehículo
--
-- Script incremental e idempotente para MySQL 5.7+
-- No elimina vehículos, mantenimientos ni configuraciones.
-- =========================================================

-- ---------------------------------------------------------
-- 0. Detectar si la columna del catálogo todavía existe
-- ---------------------------------------------------------
SET @columna_fecha_existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'plan_item_detalles'
      AND COLUMN_NAME = 'fecha_vencimiento'
);

-- ---------------------------------------------------------
-- 1. Respaldo de las fechas que hoy viven en el catálogo
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS plan_item_detalles_fecha_backup (
    id INT NOT NULL,
    plan_item_id INT NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    cantidad INT NOT NULL,
    fecha_vencimiento DATE NULL,
    backed_up_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_backup_plan_item_detalle (id),
    INDEX idx_backup_fecha (fecha_vencimiento)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

SET @sql = IF(
    @columna_fecha_existe > 0,
    'INSERT INTO plan_item_detalles_fecha_backup (id, plan_item_id, nombre, cantidad, fecha_vencimiento)
     SELECT pid.id, pid.plan_item_id, pid.nombre, pid.cantidad, pid.fecha_vencimiento
     FROM plan_item_detalles pid
     WHERE pid.fecha_vencimiento IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM plan_item_detalles_fecha_backup b
           WHERE b.id = pid.id
             AND b.fecha_vencimiento = pid.fecha_vencimiento
       )',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------
-- 2. Tabla de inventario real por vehículo
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehiculo_plan_item_detalles (
    id INT NOT NULL AUTO_INCREMENT,
    vehiculo_plan_item_id INT NOT NULL,
    plan_item_detalle_id INT NOT NULL,
    cantidad INT NOT NULL DEFAULT 1,
    fecha_vencimiento DATE NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_vpid_vehiculo_plan_item (vehiculo_plan_item_id),
    INDEX idx_vpid_plan_item_detalle (plan_item_detalle_id),
    INDEX idx_vpid_vencimiento (fecha_vencimiento),
    CONSTRAINT fk_vpid_vehiculo_plan_item
        FOREIGN KEY (vehiculo_plan_item_id)
        REFERENCES vehiculo_plan_item (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_vpid_plan_item_detalle
        FOREIGN KEY (plan_item_detalle_id)
        REFERENCES plan_item_detalles (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT chk_vpid_cantidad
        CHECK (cantidad >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

-- ---------------------------------------------------------
-- 3. Migrar las fechas existentes del catálogo a cada vehículo
--    que tenga asignado ese mantenimiento.
-- ---------------------------------------------------------
SET @sql = IF(
    @columna_fecha_existe > 0,
    'INSERT INTO vehiculo_plan_item_detalles (
         vehiculo_plan_item_id, plan_item_detalle_id, cantidad, fecha_vencimiento
     )
     SELECT vpi.id, pid.id, pid.cantidad, pid.fecha_vencimiento
     FROM plan_item_detalles pid
     INNER JOIN vehiculo_plan_item vpi
         ON vpi.plan_item_id = pid.plan_item_id
     WHERE pid.fecha_vencimiento IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM vehiculo_plan_item_detalles vpid
           WHERE vpid.vehiculo_plan_item_id = vpi.id
             AND vpid.plan_item_detalle_id = pid.id
             AND vpid.fecha_vencimiento = pid.fecha_vencimiento
       )',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------
-- 4. Asociar las alertas al lote específico de inventario
-- ---------------------------------------------------------
SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE alertas ADD COLUMN vehiculo_plan_item_detalle_id INT NULL',
        'SELECT 1'
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'alertas'
      AND COLUMN_NAME = 'vehiculo_plan_item_detalle_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE alertas ADD INDEX idx_alertas_vehiculo_plan_item_detalle (vehiculo_plan_item_detalle_id)',
        'SELECT 1'
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'alertas'
      AND INDEX_NAME = 'idx_alertas_vehiculo_plan_item_detalle'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE alertas ADD CONSTRAINT fk_alertas_vehiculo_plan_item_detalle FOREIGN KEY (vehiculo_plan_item_detalle_id) REFERENCES vehiculo_plan_item_detalles (id) ON DELETE SET NULL',
        'SELECT 1'
    )
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'alertas'
      AND CONSTRAINT_NAME = 'fk_alertas_vehiculo_plan_item_detalle'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------
-- 5. Retirar la columna del catálogo únicamente si todas las
--    fechas existentes quedaron respaldadas.
-- ---------------------------------------------------------
SET @fechas_sin_respaldo = 0;

SET @sql = IF(
    @columna_fecha_existe > 0,
    'SELECT COUNT(*) INTO @fechas_sin_respaldo
     FROM plan_item_detalles pid
     WHERE pid.fecha_vencimiento IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM plan_item_detalles_fecha_backup b
           WHERE b.id = pid.id
             AND b.fecha_vencimiento = pid.fecha_vencimiento
       )',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    @columna_fecha_existe > 0
    AND @fechas_sin_respaldo = 0,
    'ALTER TABLE plan_item_detalles DROP COLUMN fecha_vencimiento',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------
-- 6. Verificación final
-- ---------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM vehiculo_plan_item_detalles)
        AS registros_inventario,
    (SELECT COUNT(*) FROM plan_item_detalles_fecha_backup)
        AS fechas_respaldadas,
    (
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'plan_item_detalles'
          AND COLUMN_NAME = 'fecha_vencimiento'
    ) AS columna_fecha_catalogo_existe;
