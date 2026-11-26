-- =================================================================================
-- SISTEMA DE GESTIÓN HELADERÍA POLO NORTE — LÓGICA EN BASE DE DATOS
-- • Separación Estricta Python (Capa Visual) <-> MySQL (100% Lógica en SPs y Triggers)
-- • 25 Tablas Base · 1 Vista · 74 Procedimientos Almacenados · 11 Disparadores Automáticos
-- • Cuentas Administrativas (SHA-256) vs. Cajas Diarias por Sede (Multifuncional)
-- • Toppings + Precio Unitario Blindado + Correlativo Automático + Arqueo + Dashboard
-- • Portable para MySQL Server local y Azure Database for MySQL 8.4 LTS (sin DEFINER)
-- =================================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;
SET collation_connection = 'utf8mb4_general_ci';

-- ---------------------------------------------------------------------------------
-- 1. COMPLETAR ROLES EN LA TABLA `rol` Y ASIGNAR EMPLEADOS (IDEMPOTENTE)
-- ---------------------------------------------------------------------------------
INSERT IGNORE INTO rol (ID_Rol, RecursosHumanos, AsistenteLogistico, Multifuncional) VALUES
(1, 0, 0, 1),  -- ID_Rol 1: Multifuncional (Operativo de Caja Diaria por Sede)
(2, 0, 1, 0),  -- ID_Rol 2: Logística y Almacén (Catálogo e Insumos - SHA-256)
(3, 1, 0, 0);  -- ID_Rol 3: Recursos Humanos (Personal y Sedes - SHA-256)

UPDATE empleados SET ID_Rol = 3 WHERE ID_Empleado = 1 AND ID_Rol <> 3; -- Etel Quispe -> Recursos Humanos
UPDATE empleados SET ID_Rol = 2 WHERE ID_Empleado = 2 AND ID_Rol <> 2; -- Joel Mendoza -> Logística
UPDATE empleados SET ID_Rol = 1 WHERE ID_Empleado >= 3 AND ID_Rol <> 1; -- Resto -> Multifuncional por Sede

-- ---------------------------------------------------------------------------------
-- 2. TABLA `credenciales_hash` (3 ADMINISTRATIVAS SHA-256 + 3 CAJAS DIARIAS POR SEDE)
-- ---------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credenciales_hash (
    ID_Credencial INT NOT NULL AUTO_INCREMENT,
    Usuario VARCHAR(45) NOT NULL UNIQUE,
    Hash_Password CHAR(64) NULL,
    Requiere_Password TINYINT(1) NOT NULL DEFAULT 1,
    ID_Administrador INT NULL,
    ID_Empleado INT NULL UNIQUE,
    ID_Sucursal INT NULL UNIQUE,
    Intentos_Fallidos INT NOT NULL DEFAULT 0,
    Estado ENUM('Activo', 'Bloqueado') NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (ID_Credencial),
    CONSTRAINT fk_cred_admin FOREIGN KEY (ID_Administrador) REFERENCES administradores(ID_Administrador) ON DELETE CASCADE,
    CONSTRAINT fk_cred_empleado FOREIGN KEY (ID_Empleado) REFERENCES empleados(ID_Empleado) ON DELETE CASCADE,
    CONSTRAINT fk_cred_sucursal FOREIGN KEY (ID_Sucursal) REFERENCES surcusal(ID_Surcusal) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Sembrar de forma idempotente las 3 cuentas administrativas (SHA-256) y las 3 Cajas Diarias por Sede
INSERT IGNORE INTO credenciales_hash
(Usuario, Hash_Password, Requiere_Password, ID_Administrador, ID_Empleado, ID_Sucursal, Intentos_Fallidos, Estado)
VALUES
('admin',          SHA2('admin123', 256), 1, 1,    NULL, NULL, 0, 'Activo'),
('rrhh_etel',      SHA2('rrhh123', 256),  1, NULL, 1,    NULL, 0, 'Activo'),
('log_joel',       SHA2('log123', 256),   1, NULL, 2,    NULL, 0, 'Activo'),
('caja_quintanas', NULL,                  0, NULL, NULL, 1,    0, 'Activo'),
('caja_upao',      NULL,                  0, NULL, NULL, 2,    0, 'Activo'),
('caja_mall',      NULL,                  0, NULL, NULL, 3,    0, 'Activo');

-- ---------------------------------------------------------------------------------
-- 3. VISTA `vw_credenciales_roles` (COLACIÓN HOMOGÉNEA Y PORTABLE PARA MYSQL 8.4)
-- ---------------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_credenciales_roles;
CREATE SQL SECURITY INVOKER VIEW vw_credenciales_roles AS
SELECT 
    c.ID_Credencial,
    c.Usuario,
    c.Hash_Password,
    c.Requiere_Password,
    c.ID_Administrador,
    c.ID_Empleado,
    COALESCE(c.ID_Sucursal, e.ID_Sucursal) AS ID_Sucursal,
    CAST(IFNULL(s.Nombre_Suc, 'Todas las Sedes (Central)') AS CHAR(100)) COLLATE utf8mb4_general_ci AS Nombre_Sucursal,
    CAST(
        CASE
            WHEN c.ID_Administrador IS NOT NULL THEN 'Gerencia General'
            WHEN c.ID_Sucursal IS NOT NULL THEN CONCAT('Caja Diaria — ', s.Nombre_Suc)
            ELSE CONCAT(e.Nombres, ' ', e.Apellido_Paterno)
        END AS CHAR(120)
    ) COLLATE utf8mb4_general_ci AS Persona_Asignada,
    CAST(
        CASE
            WHEN c.ID_Administrador IS NOT NULL THEN 'Administrador'
            WHEN c.ID_Sucursal IS NOT NULL THEN 'Multifuncional'
            WHEN r.RecursosHumanos = 1 THEN 'RecursosHumanos'
            WHEN r.AsistenteLogistico = 1 THEN 'AsistenteLogistico'
            ELSE 'Multifuncional'
        END AS CHAR(45)
    ) COLLATE utf8mb4_general_ci AS Rango_Rol,
    c.Intentos_Fallidos,
    c.Estado
FROM credenciales_hash c
LEFT JOIN empleados e ON c.ID_Empleado = e.ID_Empleado
LEFT JOIN rol r ON e.ID_Rol = r.ID_Rol
LEFT JOIN surcusal s ON COALESCE(c.ID_Sucursal, e.ID_Sucursal) = s.ID_Surcusal;

-- ---------------------------------------------------------------------------------
-- 4. TRAZABILIDAD DE TOPPING EN `detalle_venta` E ÍNDICE ÚNICO EN `venta`
-- ---------------------------------------------------------------------------------
SET @col_id_top = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detalle_venta' AND COLUMN_NAME = 'ID_Topping'
);
SET @sql_add_id_top = IF(@col_id_top = 0,
    'ALTER TABLE detalle_venta ADD COLUMN ID_Topping INT NULL DEFAULT NULL AFTER Precio_Unitario',
    'SELECT 1');
PREPARE stmt3 FROM @sql_add_id_top; EXECUTE stmt3; DEALLOCATE PREPARE stmt3;

SET @col_prec_top = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detalle_venta' AND COLUMN_NAME = 'Precio_Topping'
);
SET @sql_add_prec_top = IF(@col_prec_top = 0,
    'ALTER TABLE detalle_venta ADD COLUMN Precio_Topping DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER ID_Topping',
    'SELECT 1');
PREPARE stmt4 FROM @sql_add_prec_top; EXECUTE stmt4; DEALLOCATE PREPARE stmt4;

SET @uk_num_comp = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'venta' AND INDEX_NAME = 'uk_venta_num_comprobante'
);
SET @sql_add_uk_comp = IF(@uk_num_comp = 0,
    'ALTER TABLE venta ADD UNIQUE INDEX uk_venta_num_comprobante (Num_Comprobante)',
    'SELECT 1');
PREPARE stmt5 FROM @sql_add_uk_comp; EXECUTE stmt5; DEALLOCATE PREPARE stmt5;

-- ---------------------------------------------------------------------------------
-- 5. TABLA `bitacora_auditoria` Y 11 DISPARADORES AUTOMÁTICOS (TRIGGERS EN MYSQL)
-- ---------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bitacora_auditoria (
    ID_Evento INT NOT NULL AUTO_INCREMENT,
    Usuario_Responsable VARCHAR(45) NOT NULL DEFAULT 'sistema_mysql',
    Rol_Responsable VARCHAR(45) NOT NULL DEFAULT 'Motor_BD',
    Tipo_Accion ENUM('LOGIN', 'INSERT', 'UPDATE', 'DELETE', 'BLOQUEO') NOT NULL,
    Tabla_Afectada VARCHAR(45) NOT NULL,
    Detalle_Cambio VARCHAR(255) NOT NULL,
    Fecha_Hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ID_Evento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Purgar filas redundantes sin cambio real en personal y normalizar textos históricos a lenguaje comercial
DELETE FROM bitacora_auditoria
WHERE Tabla_Afectada = 'empleados'
  AND Tipo_Accion = 'UPDATE'
  AND (
      Detalle_Cambio LIKE '%Rol: 1 -> 1%'
      OR Detalle_Cambio LIKE '%Rol: 2 -> 2%'
      OR Detalle_Cambio LIKE '%Rol: 3 -> 3%'
      OR Detalle_Cambio LIKE '%Sede: 1->1 | Cargo: 1->1%'
      OR Detalle_Cambio LIKE '%Sede: 1->1 | Cargo: 2->2%'
      OR Detalle_Cambio LIKE '%Sede: 1->1 | Cargo: 3->3%'
      OR Detalle_Cambio LIKE '%Sede: 2->2 | Cargo: 1->1%'
      OR Detalle_Cambio LIKE '%Sede: 3->3 | Cargo: 1->1%'
  );

UPDATE bitacora_auditoria
SET Detalle_Cambio = TRIM(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
        Detalle_Cambio,
        '[TRIGGER] ', ''),
        '[SP_LOGIN] ', ''),
        '[SP_CREDENCIAL] ', ''),
        'Autenticación SHA-256 exitosa', 'Ingreso administrativo verificado'),
        'Ingreso operativo directo sin clave', 'Ingreso directo de caja'),
        'Rol BD:', 'Área:'),
        'RecursosHumanos', 'Recursos Humanos'),
        'AsistenteLogistico', 'Logística y Almacén'),
        'Multifuncional', 'Caja Diaria'),
        'Empleado ID ', 'Colaborador #')
)
WHERE Detalle_Cambio LIKE '%[%'
   OR Detalle_Cambio LIKE '%SHA-256%'
   OR Detalle_Cambio LIKE '%Rol BD:%'
   OR Detalle_Cambio LIKE '%RecursosHumanos%'
   OR Detalle_Cambio LIKE '%AsistenteLogistico%'
   OR Detalle_Cambio LIKE '%Multifuncional%'
   OR Detalle_Cambio LIKE '%Empleado ID %';

DROP TRIGGER IF EXISTS trg_auditoria_producto_insert;
CREATE TRIGGER trg_auditoria_producto_insert
AFTER INSERT ON producto
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'sistema'),
    IFNULL(@rol_sesion, 'Logística'),
    'INSERT',
    'producto',
    CONCAT('Alta de producto #', NEW.ID_Producto, ': ', NEW.Nom_Producto, ' (S/ ', FORMAT(NEW.Precio_Venta, 2), ')'),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_producto_update;
CREATE TRIGGER trg_auditoria_producto_update
AFTER UPDATE ON producto
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'sistema'),
    IFNULL(@rol_sesion, 'Logística'),
    'UPDATE',
    'producto',
    CONCAT('Actualización de producto #', NEW.ID_Producto, ' (', NEW.Nom_Producto, ') Precio: S/ ', FORMAT(OLD.Precio_Venta, 2), ' -> S/ ', FORMAT(NEW.Precio_Venta, 2)),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_venta_insert;
CREATE TRIGGER trg_auditoria_venta_insert
AFTER INSERT ON venta
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'caja_sede'),
    IFNULL(@rol_sesion, 'Multifuncional'),
    'INSERT',
    'venta',
    CONCAT('Venta registrada #', NEW.ID_Venta, ' — Comprobante: ', NEW.Num_Comprobante, ' (Canal: ', NEW.Canal_Atencion, ')'),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_insumo_insert;
CREATE TRIGGER trg_auditoria_insumo_insert
AFTER INSERT ON insumo
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'sistema'),
    IFNULL(@rol_sesion, 'Logística'),
    'INSERT',
    'insumo',
    CONCAT('Ingreso de insumo #', NEW.ID_Insumo, ': ', NEW.Nombre_Insumo, ' (', NEW.Unidad_Medida, ')'),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_empleado_update;
DELIMITER $$
CREATE TRIGGER trg_auditoria_empleado_update
AFTER UPDATE ON empleados
FOR EACH ROW
BEGIN
    IF OLD.ID_Sucursal <> NEW.ID_Sucursal
       OR OLD.ID_Rol <> NEW.ID_Rol
       OR IFNULL(OLD.Nombres, '') <> IFNULL(NEW.Nombres, '')
       OR IFNULL(OLD.Apellido_Paterno, '') <> IFNULL(NEW.Apellido_Paterno, '')
       OR IFNULL(OLD.Apellido_Materno, '') <> IFNULL(NEW.Apellido_Materno, '') THEN
        INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
        VALUES (
            IFNULL(@usuario_sesion, 'sistema'),
            IFNULL(@rol_sesion, 'RecursosHumanos'),
            'UPDATE',
            'empleados',
            CONCAT('Actualización de colaborador #', NEW.ID_Empleado, ' (', NEW.Nombres, ' ', NEW.Apellido_Paterno, ') — Sede #', OLD.ID_Sucursal, ' -> #', NEW.ID_Sucursal),
            NOW()
        );
    END IF;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_auditoria_insumo_update;
CREATE TRIGGER trg_auditoria_insumo_update
AFTER UPDATE ON insumo
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'sistema'),
    IFNULL(@rol_sesion, 'AsistenteLogistico'),
    'UPDATE',
    'insumo',
    CONCAT('Actualización de insumo #', NEW.ID_Insumo, ': ', NEW.Nombre_Insumo, ' | Venc.: ', IFNULL(DATE_FORMAT(OLD.F_Vencimiento, '%Y-%m-%d'), 'N/A'), ' -> ', IFNULL(DATE_FORMAT(NEW.F_Vencimiento, '%Y-%m-%d'), 'N/A')),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_insumo_delete;
CREATE TRIGGER trg_auditoria_insumo_delete
AFTER DELETE ON insumo
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'admin'),
    IFNULL(@rol_sesion, 'Administrador'),
    'DELETE',
    'insumo',
    CONCAT('Retiro de insumo #', OLD.ID_Insumo, ': ', OLD.Nombre_Insumo),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_producto_delete;
CREATE TRIGGER trg_auditoria_producto_delete
AFTER DELETE ON producto
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'admin'),
    IFNULL(@rol_sesion, 'Administrador'),
    'DELETE',
    'producto',
    CONCAT('Baja de producto #', OLD.ID_Producto, ': ', OLD.Nom_Producto, ' (S/ ', FORMAT(OLD.Precio_Venta, 2), ')'),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_empleado_delete;
CREATE TRIGGER trg_auditoria_empleado_delete
AFTER DELETE ON empleados
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'admin'),
    IFNULL(@rol_sesion, 'Administrador'),
    'DELETE',
    'empleados',
    CONCAT('Baja de colaborador #', OLD.ID_Empleado, ': ', OLD.Nombres, ' ', OLD.Apellido_Paterno),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_topping_update;
CREATE TRIGGER trg_auditoria_topping_update
AFTER UPDATE ON topping
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'sistema'),
    IFNULL(@rol_sesion, 'AsistenteLogistico'),
    'UPDATE',
    'topping',
    CONCAT('Actualización de topping #', NEW.ID_Topping, ' (', NEW.Nom_Topping, ') Precio: S/ ', FORMAT(OLD.Precio_Agregado, 2), ' -> S/ ', FORMAT(NEW.Precio_Agregado, 2)),
    NOW()
);

DROP TRIGGER IF EXISTS trg_auditoria_compra_insert;
CREATE TRIGGER trg_auditoria_compra_insert
AFTER INSERT ON compra
FOR EACH ROW
INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio, Fecha_Hora)
VALUES (
    IFNULL(@usuario_sesion, 'sistema'),
    IFNULL(@rol_sesion, 'AsistenteLogistico'),
    'INSERT',
    'compra',
    CONCAT('Ingreso de compra #', NEW.ID_Compra, ' (Pedido #', NEW.ID_Pedido, ') por S/ ', FORMAT(NEW.Monto_Total, 2)),
    NOW()
);

-- =================================================================================
-- 6. PROCEDIMIENTOS ALMACENADOS (STORED PROCEDURES) EN MYSQL
-- =================================================================================

DELIMITER $$

-- ---------------------------------------------------------------------------------
-- 6.1. SEGURIDAD, LOGIN DE CAJAS DIARIAS / BACK-OFFICE Y GESTIÓN DE ACCESOS
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_consultar_jerarquia_usuario$$
CREATE PROCEDURE sp_consultar_jerarquia_usuario(
    IN p_usuario VARCHAR(45)
)
BEGIN
    SELECT ID_Credencial,
           Usuario,
           Requiere_Password,
           Rango_Rol,
           Intentos_Fallidos,
           Estado,
           Persona_Asignada,
           ID_Sucursal,
           Nombre_Sucursal
    FROM vw_credenciales_roles
    WHERE Usuario COLLATE utf8mb4_bin = p_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_validar_login$$
CREATE PROCEDURE sp_validar_login(
    IN p_usuario VARCHAR(45),
    IN p_password VARCHAR(100)
)
BEGIN
    DECLARE v_id_cred INT DEFAULT NULL;
    DECLARE v_user_bd VARCHAR(45);
    DECLARE v_hash_bd CHAR(64);
    DECLARE v_req_pass TINYINT(1);
    DECLARE v_rango_rol VARCHAR(45);
    DECLARE v_area_comercial VARCHAR(60);
    DECLARE v_intentos INT;
    DECLARE v_estado VARCHAR(20);
    DECLARE v_persona VARCHAR(120);
    DECLARE v_id_suc INT;
    DECLARE v_nom_suc VARCHAR(100);
    DECLARE v_nuevos_intentos INT;
    DECLARE v_nuevo_estado VARCHAR(20);

    SET time_zone = '-05:00';

    SELECT ID_Credencial, Usuario, Hash_Password, Requiere_Password, Rango_Rol,
           Intentos_Fallidos, Estado, Persona_Asignada, ID_Sucursal, Nombre_Sucursal
    INTO v_id_cred, v_user_bd, v_hash_bd, v_req_pass, v_rango_rol,
         v_intentos, v_estado, v_persona, v_id_suc, v_nom_suc
    FROM vw_credenciales_roles
    WHERE Usuario COLLATE utf8mb4_bin = p_usuario
    LIMIT 1;

    SET v_area_comercial = CASE v_rango_rol
        WHEN 'Administrador' THEN 'Gerencia General'
        WHEN 'RecursosHumanos' THEN 'Recursos Humanos'
        WHEN 'AsistenteLogistico' THEN 'Logística y Almacén'
        ELSE 'Caja Diaria'
    END;

    IF v_id_cred IS NULL THEN
        SELECT 0 AS Exito, NULL AS Usuario, NULL AS Rango_Rol,
               'La cuenta ingresada no se encuentra registrada en el sistema.' AS Mensaje,
               NULL AS ID_Sucursal, NULL AS Nombre_Sucursal, NULL AS Persona_Asignada;
    ELSEIF v_estado = 'Bloqueado' OR v_intentos >= 3 THEN
        SELECT 0 AS Exito, v_user_bd AS Usuario, v_rango_rol AS Rango_Rol,
               CONCAT('ACCESO BLOQUEADO: La cuenta ''', v_user_bd, ''' superó los 3 intentos permitidos. Solicite reactivación a Gerencia.') AS Mensaje,
               v_id_suc AS ID_Sucursal, v_nom_suc AS Nombre_Sucursal, v_persona AS Persona_Asignada;
    ELSEIF v_req_pass = 0 THEN
        -- Apertura de Caja Diaria por Sede (Sin requerimiento de contraseña)
        UPDATE credenciales_hash SET Intentos_Fallidos = 0 WHERE ID_Credencial = v_id_cred;
        INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio)
        VALUES (v_user_bd, v_rango_rol, 'LOGIN', 'credenciales_hash',
                CONCAT('Apertura de ', v_persona, ' (Sede: ', v_nom_suc, ')'));
        SELECT 1 AS Exito, v_user_bd AS Usuario, v_rango_rol AS Rango_Rol,
               CONCAT('Turno iniciado en ', v_persona, '.') AS Mensaje,
               v_id_suc AS ID_Sucursal, v_nom_suc AS Nombre_Sucursal, v_persona AS Persona_Asignada;
    ELSE
        -- Cuentas Administrativas (Gerencia, RRHH, Logística)
        IF p_password IS NULL OR CHAR_LENGTH(p_password) = 0 THEN
            SELECT 0 AS Exito, v_user_bd AS Usuario, v_rango_rol AS Rango_Rol,
                   CONCAT('Ingrese la contraseña de acceso para ', v_persona, '.') AS Mensaje,
                   v_id_suc AS ID_Sucursal, v_nom_suc AS Nombre_Sucursal, v_persona AS Persona_Asignada;
        ELSEIF SHA2(p_password, 256) = v_hash_bd THEN
            UPDATE credenciales_hash SET Intentos_Fallidos = 0, Estado = 'Activo' WHERE ID_Credencial = v_id_cred;
            INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio)
            VALUES (v_user_bd, v_rango_rol, 'LOGIN', 'credenciales_hash',
                    CONCAT('Ingreso administrativo exitoso: ', v_persona, ' (', v_area_comercial, ')'));
            SELECT 1 AS Exito, v_user_bd AS Usuario, v_rango_rol AS Rango_Rol,
                   CONCAT('Bienvenido(a) ', v_persona, '.') AS Mensaje,
                   v_id_suc AS ID_Sucursal, v_nom_suc AS Nombre_Sucursal, v_persona AS Persona_Asignada;
        ELSE
            SET v_nuevos_intentos = v_intentos + 1;
            SET v_nuevo_estado = IF(v_nuevos_intentos >= 3, 'Bloqueado', 'Activo');
            UPDATE credenciales_hash
            SET Intentos_Fallidos = v_nuevos_intentos, Estado = v_nuevo_estado
            WHERE ID_Credencial = v_id_cred;

            IF v_nuevo_estado = 'Bloqueado' THEN
                INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio)
                VALUES (v_user_bd, v_rango_rol, 'BLOQUEO', 'credenciales_hash',
                        CONCAT('Bloqueo preventivo tras 3 intentos fallidos (', v_persona, ')'));
                SELECT 0 AS Exito, v_user_bd AS Usuario, v_rango_rol AS Rango_Rol,
                       CONCAT('CUENTA BLOQUEADA: Ha superado los 3 intentos permitidos para ''', v_user_bd, '''.') AS Mensaje,
                       v_id_suc AS ID_Sucursal, v_nom_suc AS Nombre_Sucursal, v_persona AS Persona_Asignada;
            ELSE
                SELECT 0 AS Exito, v_user_bd AS Usuario, v_rango_rol AS Rango_Rol,
                       CONCAT('Contraseña incorrecta. Intentos restantes: ', (3 - v_nuevos_intentos), ' de 3.') AS Mensaje,
                       v_id_suc AS ID_Sucursal, v_nom_suc AS Nombre_Sucursal, v_persona AS Persona_Asignada;
            END IF;
        END IF;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_asignar_credencial_empleado$$
CREATE PROCEDURE sp_asignar_credencial_empleado(
    IN p_id_empleado INT,
    IN p_usuario VARCHAR(45),
    IN p_password VARCHAR(100),
    IN p_admin_usr VARCHAR(45)
)
BEGIN
    DECLARE v_id_rol INT DEFAULT NULL;
    DECLARE v_nom_emp VARCHAR(120);
    DECLARE v_rango VARCHAR(45);
    DECLARE v_area_comercial VARCHAR(60);
    DECLARE v_existe_usr INT DEFAULT 0;
    DECLARE v_existe_emp INT DEFAULT 0;

    SET time_zone = '-05:00';

    SELECT e.ID_Rol, CONCAT(e.Nombres, ' ', e.Apellido_Paterno),
           CASE
               WHEN r.RecursosHumanos = 1 THEN 'RecursosHumanos'
               WHEN r.AsistenteLogistico = 1 THEN 'AsistenteLogistico'
               ELSE 'Multifuncional'
           END
    INTO v_id_rol, v_nom_emp, v_rango
    FROM empleados e
    INNER JOIN rol r ON e.ID_Rol = r.ID_Rol
    WHERE e.ID_Empleado = p_id_empleado
    LIMIT 1;

    SET v_area_comercial = CASE v_rango
        WHEN 'RecursosHumanos' THEN 'Recursos Humanos'
        WHEN 'AsistenteLogistico' THEN 'Logística y Almacén'
        ELSE 'Caja Diaria'
    END;

    IF v_id_rol IS NULL THEN
        SELECT 0 AS Exito, 'El colaborador seleccionado no existe.' AS Mensaje;
    ELSEIF v_rango = 'Multifuncional' THEN
        DELETE FROM credenciales_hash WHERE ID_Empleado = p_id_empleado;
        SELECT 0 AS Exito,
               CONCAT(v_nom_emp, ' tiene cargo Multifuncional: ingresa directamente mediante la Caja Diaria de su sede (no requiere cuenta individual).') AS Mensaje;
    ELSE
        SELECT COUNT(*) INTO v_existe_usr
        FROM credenciales_hash
        WHERE Usuario COLLATE utf8mb4_bin = p_usuario
          AND (ID_Empleado IS NULL OR ID_Empleado <> p_id_empleado);

        IF v_existe_usr > 0 THEN
            SELECT 0 AS Exito, CONCAT('El usuario ''', p_usuario, ''' ya está en uso.') AS Mensaje;
        ELSEIF p_password IS NULL OR CHAR_LENGTH(p_password) < 4 THEN
            SELECT 0 AS Exito, CONCAT('El área ', v_area_comercial, ' requiere una contraseña de al menos 4 caracteres.') AS Mensaje;
        ELSE
            SELECT COUNT(*) INTO v_existe_emp
            FROM credenciales_hash
            WHERE ID_Empleado = p_id_empleado;

            IF v_existe_emp > 0 THEN
                UPDATE credenciales_hash
                SET Usuario = p_usuario,
                    Hash_Password = SHA2(p_password, 256),
                    Requiere_Password = 1,
                    Intentos_Fallidos = 0,
                    Estado = 'Activo'
                WHERE ID_Empleado = p_id_empleado;
            ELSE
                INSERT INTO credenciales_hash
                (Usuario, Hash_Password, Requiere_Password, ID_Administrador, ID_Empleado, ID_Sucursal, Intentos_Fallidos, Estado)
                VALUES (p_usuario, SHA2(p_password, 256), 1, NULL, p_id_empleado, NULL, 0, 'Activo');
            END IF;

            INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio)
            VALUES (IFNULL(p_admin_usr, 'admin'), 'Administrador', 'INSERT', 'credenciales_hash',
                    CONCAT('Cuenta administrativa ''', p_usuario, ''' asignada a ', v_nom_emp, ' (', v_area_comercial, ')'));

            SELECT 1 AS Exito,
                   CONCAT('Cuenta administrativa ''', p_usuario, ''' asignada correctamente a ', v_nom_emp, ' (', v_area_comercial, ').') AS Mensaje;
        END IF;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_listar_credenciales$$
CREATE PROCEDURE sp_listar_credenciales()
BEGIN
    SELECT ID_Credencial,
           Usuario,
           Rango_Rol,
           IF(Requiere_Password = 1, 'Con Clave', 'Caja Directa') AS Pide_Clave,
           Intentos_Fallidos,
           Estado,
           Persona_Asignada,
           ID_Sucursal,
           Nombre_Sucursal
    FROM vw_credenciales_roles
    ORDER BY Requiere_Password ASC, ID_Credencial ASC;
END$$

DROP PROCEDURE IF EXISTS sp_reactivar_cuenta$$
CREATE PROCEDURE sp_reactivar_cuenta(
    IN p_usuario VARCHAR(45),
    IN p_admin_usr VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';

    UPDATE credenciales_hash
    SET Intentos_Fallidos = 0, Estado = 'Activo'
    WHERE Usuario = p_usuario;

    INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio)
    VALUES (IFNULL(p_admin_usr, 'admin'), 'Administrador', 'UPDATE', 'credenciales_hash',
            CONCAT('Cuenta ''', p_usuario, ''' desbloqueada y restablecida por Gerencia'));

    SELECT 1 AS Exito, CONCAT('El acceso de ''', p_usuario, ''' fue reactivado correctamente.') AS Mensaje;
END$$

-- ---------------------------------------------------------------------------------
-- 6.2. PROCEDIMIENTOS ALMACENADOS: CLIENTES (Tabla `cliente`)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_clientes$$
CREATE PROCEDURE sp_listar_clientes(
    IN p_filtro VARCHAR(100)
)
BEGIN
    IF p_filtro IS NULL OR TRIM(p_filtro) = '' THEN
        SELECT ID_Cliente, Nombres, Apellido_Paterno, Apellido_Materno, Celular
        FROM cliente
        ORDER BY ID_Cliente DESC;
    ELSE
        SELECT ID_Cliente, Nombres, Apellido_Paterno, Apellido_Materno, Celular
        FROM cliente
        WHERE Nombres LIKE CONCAT('%', TRIM(p_filtro), '%')
           OR Apellido_Paterno LIKE CONCAT('%', TRIM(p_filtro), '%')
           OR Celular LIKE CONCAT('%', TRIM(p_filtro), '%')
        ORDER BY ID_Cliente DESC;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_insertar_cliente$$
CREATE PROCEDURE sp_insertar_cliente(
    IN p_nombres VARCHAR(45),
    IN p_ap_paterno VARCHAR(45),
    IN p_ap_materno VARCHAR(45),
    IN p_celular VARCHAR(15)
)
BEGIN
    IF TRIM(IFNULL(p_nombres, '')) = '' OR TRIM(IFNULL(p_ap_paterno, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese al menos los nombres y el apellido paterno del cliente.';
    END IF;
    INSERT INTO cliente (Nombres, Apellido_Paterno, Apellido_Materno, Celular)
    VALUES (TRIM(p_nombres), TRIM(p_ap_paterno), TRIM(IFNULL(p_ap_materno, '')), TRIM(IFNULL(p_celular, '')));
    SELECT LAST_INSERT_ID() AS ID_Nuevo;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_cliente$$
CREATE PROCEDURE sp_actualizar_cliente(
    IN p_id_cliente INT,
    IN p_nombres VARCHAR(45),
    IN p_ap_paterno VARCHAR(45),
    IN p_ap_materno VARCHAR(45),
    IN p_celular VARCHAR(15)
)
BEGIN
    IF TRIM(IFNULL(p_nombres, '')) = '' OR TRIM(IFNULL(p_ap_paterno, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese al menos los nombres y el apellido paterno del cliente.';
    END IF;
    UPDATE cliente
    SET Nombres = TRIM(p_nombres),
        Apellido_Paterno = TRIM(p_ap_paterno),
        Apellido_Materno = TRIM(IFNULL(p_ap_materno, '')),
        Celular = TRIM(IFNULL(p_celular, ''))
    WHERE ID_Cliente = p_id_cliente;
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_cliente$$
CREATE PROCEDURE sp_eliminar_cliente(
    IN p_id_cliente INT
)
BEGIN
    DELETE FROM cliente WHERE ID_Cliente = p_id_cliente;
END$$

-- ---------------------------------------------------------------------------------
-- 6.3. PROCEDIMIENTOS ALMACENADOS: PRODUCTOS (Tabla `producto`)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_productos$$
CREATE PROCEDURE sp_listar_productos(
    IN p_filtro VARCHAR(100)
)
BEGIN
    IF p_filtro IS NULL OR TRIM(p_filtro) = '' THEN
        SELECT ID_Producto, Nom_Producto, Descripcion, Precio_Venta
        FROM producto
        ORDER BY ID_Producto DESC;
    ELSE
        SELECT ID_Producto, Nom_Producto, Descripcion, Precio_Venta
        FROM producto
        WHERE Nom_Producto LIKE CONCAT('%', TRIM(p_filtro), '%')
           OR Descripcion LIKE CONCAT('%', TRIM(p_filtro), '%')
        ORDER BY ID_Producto DESC;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_insertar_producto$$
CREATE PROCEDURE sp_insertar_producto(
    IN p_nom_producto VARCHAR(45),
    IN p_descripcion VARCHAR(100),
    IN p_precio_venta DECIMAL(10,2),
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nom_producto, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese el nombre oficial del producto.';
    END IF;
    IF p_precio_venta IS NULL OR p_precio_venta <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El precio oficial de venta debe ser mayor a cero.';
    END IF;
    SET @usuario_sesion = p_usuario_sesion;
    SET @rol_sesion = p_rol_sesion;
    INSERT INTO producto (Nom_Producto, Descripcion, Precio_Venta)
    VALUES (TRIM(p_nom_producto), TRIM(IFNULL(p_descripcion, '')), p_precio_venta);
    SELECT LAST_INSERT_ID() AS ID_Nuevo;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_producto$$
CREATE PROCEDURE sp_actualizar_producto(
    IN p_id_producto INT,
    IN p_nom_producto VARCHAR(45),
    IN p_descripcion VARCHAR(100),
    IN p_precio_venta DECIMAL(10,2),
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nom_producto, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese el nombre oficial del producto.';
    END IF;
    IF p_precio_venta IS NULL OR p_precio_venta <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El precio oficial de venta debe ser mayor a cero.';
    END IF;
    SET @usuario_sesion = p_usuario_sesion;
    SET @rol_sesion = p_rol_sesion;
    UPDATE producto
    SET Nom_Producto = TRIM(p_nom_producto),
        Descripcion = TRIM(IFNULL(p_descripcion, '')),
        Precio_Venta = p_precio_venta
    WHERE ID_Producto = p_id_producto;
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_producto$$
CREATE PROCEDURE sp_eliminar_producto(
    IN p_id_producto INT
)
BEGIN
    DECLARE v_ventas INT DEFAULT 0;
    DECLARE v_ingredientes INT DEFAULT 0;

    SELECT COUNT(*) INTO v_ventas FROM detalle_venta WHERE ID_Producto = p_id_producto;
    IF v_ventas > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No se puede retirar este producto porque ya tiene ventas registradas.';
    END IF;

    SELECT COUNT(*) INTO v_ingredientes
    FROM detalle_receta dr
    INNER JOIN receta r ON dr.ID_Receta = r.ID_Receta
    WHERE r.ID_Producto = p_id_producto;
    IF v_ingredientes > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Retire primero los ingredientes de la receta antes de eliminar este producto.';
    END IF;

    DELETE FROM receta WHERE ID_Producto = p_id_producto;
    DELETE FROM producto_topping WHERE ID_Producto = p_id_producto;
    DELETE FROM producto WHERE ID_Producto = p_id_producto;
END$$

-- ---------------------------------------------------------------------------------
-- 6.4. PROCEDIMIENTOS ALMACENADOS: INSUMOS Y ALERTAS DE VENCIMIENTO EN MYSQL
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_unidades_medida$$
CREATE PROCEDURE sp_listar_unidades_medida()
BEGIN
    SELECT ID_Unidad_Medida, Nombre_Unidad, Abreviatura
    FROM unidadmedida
    ORDER BY ID_Unidad_Medida;
END$$

DROP PROCEDURE IF EXISTS sp_listar_insumos$$
CREATE PROCEDURE sp_listar_insumos(
    IN p_filtro VARCHAR(100)
)
BEGIN
    SET time_zone = '-05:00';
    SELECT i.ID_Insumo,
           i.Nombre_Insumo,
           i.ID_Unidad_Medida,
           i.Unidad_Medida,
           IF(i.Es_Perecible = 1, 'Sí', 'No') AS Perecible,
           IFNULL(DATE_FORMAT(i.F_Vencimiento, '%Y-%m-%d'), 'No aplica') AS Vencimiento,
           CASE
               WHEN i.Es_Perecible = 0 OR i.F_Vencimiento IS NULL THEN 'NO PERECIBLE'
               WHEN DATE(i.F_Vencimiento) < CURDATE() THEN 'VENCIDO - RETIRAR'
               WHEN DATEDIFF(DATE(i.F_Vencimiento), CURDATE()) <= 30 THEN 'POR VENCER'
               ELSE 'VIGENTE'
           END AS Estado_Sanitario
    FROM insumo i
    WHERE (p_filtro IS NULL OR TRIM(p_filtro) = ''
           OR i.Nombre_Insumo LIKE CONCAT('%', TRIM(p_filtro), '%')
           OR i.Unidad_Medida LIKE CONCAT('%', TRIM(p_filtro), '%'))
    ORDER BY i.ID_Insumo DESC;
END$$

DROP PROCEDURE IF EXISTS sp_insertar_insumo$$
CREATE PROCEDURE sp_insertar_insumo(
    IN p_id_unidad_medida INT,
    IN p_nombre_insumo VARCHAR(45),
    IN p_unidad_medida VARCHAR(45),
    IN p_es_perecible TINYINT(1),
    IN p_f_vencimiento DATE,
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nombre_insumo, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese el nombre del insumo.';
    END IF;
    SET @usuario_sesion = p_usuario_sesion;
    SET @rol_sesion = p_rol_sesion;
    INSERT INTO insumo (ID_Unidad_Medida, Nombre_Insumo, Unidad_Medida, Es_Perecible, F_Vencimiento)
    VALUES (p_id_unidad_medida, TRIM(p_nombre_insumo), TRIM(p_unidad_medida), p_es_perecible, p_f_vencimiento);
    SELECT LAST_INSERT_ID() AS ID_Nuevo;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_insumo$$
CREATE PROCEDURE sp_actualizar_insumo(
    IN p_id_insumo INT,
    IN p_id_unidad_medida INT,
    IN p_nombre_insumo VARCHAR(45),
    IN p_unidad_medida VARCHAR(45),
    IN p_es_perecible TINYINT(1),
    IN p_f_vencimiento DATE
)
BEGIN
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nombre_insumo, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese el nombre del insumo.';
    END IF;
    UPDATE insumo
    SET ID_Unidad_Medida = p_id_unidad_medida,
        Nombre_Insumo = TRIM(p_nombre_insumo),
        Unidad_Medida = TRIM(p_unidad_medida),
        Es_Perecible = p_es_perecible,
        F_Vencimiento = p_f_vencimiento
    WHERE ID_Insumo = p_id_insumo;
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_insumo$$
CREATE PROCEDURE sp_eliminar_insumo(
    IN p_id_insumo INT
)
BEGIN
    DELETE FROM insumo WHERE ID_Insumo = p_id_insumo;
END$$

-- ---------------------------------------------------------------------------------
-- 6.5. PROCEDIMIENTOS ALMACENADOS: PUNTO DE VENTA, TOPPINGS Y ARQUEO DE CAJA
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_ventas$$
CREATE PROCEDURE sp_listar_ventas(
    IN p_id_sucursal INT
)
BEGIN
    SELECT v.ID_Venta,
           v.Num_Comprobante,
           v.Canal_Atencion,
           DATE_FORMAT(v.Fecha_Hora, '%Y-%m-%d %H:%i') AS Fecha,
           CONCAT(c.Nombres, ' ', c.Apellido_Paterno) AS Cliente,
           CONCAT(e.Nombres, ' ', e.Apellido_Paterno, ' (', s.Nombre_Suc, ')') AS Empleado_Sede,
           mp.Nombre_Metodo AS Metodo_Pago,
           IFNULL(
               ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.0))), 2),
               0.00
           ) AS Total
    FROM venta v
    INNER JOIN cliente c ON v.ID_Cliente = c.ID_Cliente
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
    INNER JOIN pago p ON v.ID_Pago = p.ID_Pago
    INNER JOIN metodo_pago mp ON p.ID_Metodo_Pago = mp.ID_Metodo_Pago
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
    GROUP BY v.ID_Venta, v.Num_Comprobante, v.Canal_Atencion, v.Fecha_Hora,
             Cliente, Empleado_Sede, Metodo_Pago
    ORDER BY v.ID_Venta DESC;
END$$

DROP PROCEDURE IF EXISTS sp_catalogo_clientes$$
CREATE PROCEDURE sp_catalogo_clientes()
BEGIN
    SELECT ID_Cliente, CONCAT(ID_Cliente, ' - ', Nombres, ' ', Apellido_Paterno) AS Etiqueta
    FROM cliente
    ORDER BY ID_Cliente DESC;
END$$

DROP PROCEDURE IF EXISTS sp_catalogo_empleados$$
CREATE PROCEDURE sp_catalogo_empleados()
BEGIN
    SELECT e.ID_Empleado,
           CONCAT(e.ID_Empleado, ' - ', e.Nombres, ' ', e.Apellido_Paterno, ' (', s.Nombre_Suc, ')') AS Etiqueta
    FROM empleados e
    INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
    WHERE e.ID_Rol = 1
    ORDER BY e.ID_Sucursal ASC, e.ID_Empleado ASC;
END$$

DROP PROCEDURE IF EXISTS sp_catalogo_empleados_sede$$
CREATE PROCEDURE sp_catalogo_empleados_sede(
    IN p_id_sucursal INT
)
BEGIN
    IF p_id_sucursal IS NULL OR p_id_sucursal = 0 THEN
        SELECT e.ID_Empleado,
               CONCAT(e.ID_Empleado, ' - ', e.Nombres, ' ', e.Apellido_Paterno, ' (', s.Nombre_Suc, ')') AS Etiqueta
        FROM empleados e
        INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
        WHERE e.ID_Rol = 1
        ORDER BY e.ID_Sucursal ASC, e.ID_Empleado ASC;
    ELSE
        SELECT e.ID_Empleado,
               CONCAT(e.ID_Empleado, ' - ', e.Nombres, ' ', e.Apellido_Paterno) AS Etiqueta
        FROM empleados e
        WHERE e.ID_Sucursal = p_id_sucursal
          AND e.ID_Rol = 1
        ORDER BY e.ID_Empleado ASC;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_catalogo_metodos_pago$$
CREATE PROCEDURE sp_catalogo_metodos_pago()
BEGIN
    SELECT ID_Metodo_Pago, CONCAT(ID_Metodo_Pago, ' - ', Nombre_Metodo) AS Etiqueta
    FROM metodo_pago
    ORDER BY ID_Metodo_Pago ASC;
END$$

-- Catálogo de productos con el Precio Unitario al lado en el mismo desplegable
DROP PROCEDURE IF EXISTS sp_catalogo_productos$$
CREATE PROCEDURE sp_catalogo_productos()
BEGIN
    SELECT ID_Producto,
           CONCAT(ID_Producto, ' - ', Nom_Producto, ' [S/ ', FORMAT(Precio_Venta, 2), ']') AS Etiqueta,
           Precio_Venta,
           Nom_Producto
    FROM producto
    ORDER BY ID_Producto ASC;
END$$

-- Catálogo de Toppings vinculados al producto seleccionado (desde `producto_topping` y `topping`)
DROP PROCEDURE IF EXISTS sp_catalogo_toppings_producto$$
CREATE PROCEDURE sp_catalogo_toppings_producto(
    IN p_id_producto INT
)
BEGIN
    DECLARE v_tiene_vinculos INT DEFAULT 0;

    SELECT COUNT(*) INTO v_tiene_vinculos
    FROM producto_topping
    WHERE ID_Producto = p_id_producto;

    IF v_tiene_vinculos > 0 THEN
        SELECT 0 AS ID_Topping, '0 - Sin Topping adicional (+S/ 0.00)' AS Etiqueta_Topping, 0.00 AS Precio_Agregado
        UNION ALL
        SELECT t.ID_Topping,
               CONCAT(t.ID_Topping, ' - ', t.Nom_Topping, ' (+S/ ', FORMAT(t.Precio_Agregado, 2), ')') AS Etiqueta_Topping,
               t.Precio_Agregado
        FROM producto_topping pt
        INNER JOIN topping t ON pt.ID_Topping = t.ID_Topping
        WHERE pt.ID_Producto = p_id_producto
        ORDER BY ID_Topping ASC;
    ELSE
        SELECT 0 AS ID_Topping, '0 - Sin Topping adicional (+S/ 0.00)' AS Etiqueta_Topping, 0.00 AS Precio_Agregado
        UNION ALL
        SELECT t.ID_Topping,
               CONCAT(t.ID_Topping, ' - ', t.Nom_Topping, ' (+S/ ', FORMAT(t.Precio_Agregado, 2), ')') AS Etiqueta_Topping,
               t.Precio_Agregado
        FROM topping t
        ORDER BY ID_Topping ASC;
    END IF;
END$$

-- Cálculo íntegro de la línea del pedido en el motor MySQL (Precio Base + Topping * Cantidad)
DROP PROCEDURE IF EXISTS sp_calcular_linea_carrito$$
CREATE PROCEDURE sp_calcular_linea_carrito(
    IN p_id_producto INT,
    IN p_cantidad INT,
    IN p_id_topping INT
)
BEGIN
    DECLARE v_nom_prod VARCHAR(60);
    DECLARE v_precio_base DECIMAL(10,2) DEFAULT 0.00;
    DECLARE v_nom_top VARCHAR(60) DEFAULT 'Sin Topping';
    DECLARE v_precio_top DECIMAL(10,2) DEFAULT 0.00;
    DECLARE v_precio_unit_final DECIMAL(10,2) DEFAULT 0.00;
    DECLARE v_subtotal DECIMAL(10,2) DEFAULT 0.00;

    SELECT Nom_Producto, Precio_Venta
    INTO v_nom_prod, v_precio_base
    FROM producto
    WHERE ID_Producto = p_id_producto
    LIMIT 1;

    IF p_id_topping IS NOT NULL AND p_id_topping > 0 THEN
        SELECT Nom_Topping, Precio_Agregado
        INTO v_nom_top, v_precio_top
        FROM topping
        WHERE ID_Topping = p_id_topping
        LIMIT 1;
    END IF;

    SET v_precio_unit_final = ROUND(v_precio_base + v_precio_top, 2);
    SET v_subtotal = ROUND(p_cantidad * v_precio_unit_final, 2);

    SELECT p_id_producto AS ID_Producto,
           v_nom_prod AS Nom_Producto,
           p_cantidad AS Cantidad,
           v_precio_base AS Precio_Base,
           IFNULL(p_id_topping, 0) AS ID_Topping,
           v_nom_top AS Nom_Topping,
           v_precio_top AS Precio_Topping,
           v_precio_unit_final AS Precio_Unitario_Final,
           v_subtotal AS Subtotal_Linea;
END$$

-- Generación automática del correlativo de comprobante en MySQL (B001/B002/B003 o F001/F002/F003)
DROP PROCEDURE IF EXISTS sp_generar_correlativo_comprobante$$
CREATE PROCEDURE sp_generar_correlativo_comprobante(
    IN p_tipo_comprobante VARCHAR(45),
    IN p_id_sucursal INT
)
BEGIN
    DECLARE v_prefijo_letra CHAR(1);
    DECLARE v_serie VARCHAR(6);
    DECLARE v_max_num INT DEFAULT 0;
    DECLARE v_suc INT;

    SET v_suc = IF(p_id_sucursal IS NULL OR p_id_sucursal <= 0, 1, p_id_sucursal);
    SET v_prefijo_letra = IF(UPPER(TRIM(p_tipo_comprobante)) = 'FACTURA', 'F', 'B');
    SET v_serie = CONCAT(v_prefijo_letra, LPAD(v_suc, 3, '0'), '-');

    SELECT IFNULL(MAX(CAST(SUBSTRING_INDEX(Num_Comprobante, '-', -1) AS UNSIGNED)), 100)
    INTO v_max_num
    FROM venta
    WHERE Num_Comprobante LIKE CONCAT(v_serie, '%');

    SELECT CONCAT(v_serie, LPAD(v_max_num + 1, 4, '0')) AS Comprobante_Sugerido;
END$$

DROP PROCEDURE IF EXISTS sp_crear_cabecera_venta$$
CREATE PROCEDURE sp_crear_cabecera_venta(
    IN p_num_comprobante VARCHAR(45),
    IN p_canal_atencion VARCHAR(45),
    IN p_id_empleado INT,
    IN p_id_cliente INT,
    IN p_tipo_comprobante VARCHAR(45),
    IN p_id_metodo_pago INT,
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    DECLARE v_id_pago INT;
    DECLARE v_id_venta INT;

    SET time_zone = '-05:00';
    SET @usuario_sesion = p_usuario_sesion;
    SET @rol_sesion = p_rol_sesion;

    INSERT INTO pago (Tipo_Comprobante, ID_Metodo_Pago)
    VALUES (p_tipo_comprobante, p_id_metodo_pago);
    SET v_id_pago = LAST_INSERT_ID();

    INSERT INTO venta (Num_Comprobante, Canal_Atencion, Fecha_Hora, ID_Empleado, ID_Cliente, ID_Pago)
    VALUES (TRIM(p_num_comprobante), p_canal_atencion, NOW(), p_id_empleado, p_id_cliente, v_id_pago);
    SET v_id_venta = LAST_INSERT_ID();

    SELECT v_id_venta AS ID_Venta_Generada, v_id_pago AS ID_Pago_Generado;
END$$

DROP PROCEDURE IF EXISTS sp_insertar_detalle_carrito$$
CREATE PROCEDURE sp_insertar_detalle_carrito(
    IN p_id_venta INT,
    IN p_id_producto INT,
    IN p_cantidad INT,
    IN p_precio_unitario DECIMAL(10,2),
    IN p_id_topping INT,
    IN p_precio_topping DECIMAL(10,2)
)
BEGIN
    DECLARE v_precio_oficial DECIMAL(10,2) DEFAULT NULL;
    DECLARE v_precio_top_oficial DECIMAL(10,2) DEFAULT 0.00;
    DECLARE v_top_val INT DEFAULT NULL;

    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cantidad del producto debe ser mayor a cero.';
    END IF;

    -- Blindaje de precios: MySQL ignora valores enviados desde el cliente y toma el precio oficial vigente
    SELECT Precio_Venta INTO v_precio_oficial
    FROM producto
    WHERE ID_Producto = p_id_producto
    LIMIT 1;

    IF v_precio_oficial IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El producto seleccionado no existe en el catálogo.';
    END IF;

    IF p_id_topping IS NOT NULL AND p_id_topping > 0 THEN
        SELECT Precio_Agregado INTO v_precio_top_oficial
        FROM topping
        WHERE ID_Topping = p_id_topping
        LIMIT 1;

        IF v_precio_top_oficial IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El topping seleccionado no existe en el catálogo.';
        END IF;
        SET v_top_val = p_id_topping;
    END IF;

    INSERT INTO detalle_venta
    (ID_Producto, Cantidad, Precio_Unitario, ID_Topping, Precio_Topping, ID_Venta)
    VALUES
    (p_id_producto, p_cantidad, v_precio_oficial, v_top_val, v_precio_top_oficial, p_id_venta);
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_venta$$
CREATE PROCEDURE sp_eliminar_venta(
    IN p_id_venta INT,
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    DECLARE v_id_pago INT DEFAULT NULL;
    DECLARE v_comprobante VARCHAR(45) DEFAULT '';
    DECLARE v_total DECIMAL(10,2) DEFAULT 0.00;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET time_zone = '-05:00';

    START TRANSACTION;
        SELECT v.ID_Pago, v.Num_Comprobante,
               IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00)
        INTO v_id_pago, v_comprobante, v_total
        FROM venta v
        LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
        WHERE v.ID_Venta = p_id_venta
        GROUP BY v.ID_Pago, v.Num_Comprobante
        LIMIT 1;

        IF v_id_pago IS NULL AND v_comprobante = '' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El comprobante indicado no existe o ya fue anulado.';
        END IF;

        DELETE FROM detalle_venta WHERE ID_Venta = p_id_venta;
        DELETE FROM venta WHERE ID_Venta = p_id_venta;
        IF v_id_pago IS NOT NULL THEN
            DELETE FROM pago WHERE ID_Pago = v_id_pago;
        END IF;

        INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio)
        VALUES (
            IFNULL(p_usuario_sesion, 'admin'),
            IFNULL(p_rol_sesion, 'Administrador'),
            'DELETE',
            'venta',
            CONCAT('Anulación de comprobante ', v_comprobante, ' (Venta #', p_id_venta, ') por S/ ', FORMAT(v_total, 2))
        );
    COMMIT;
END$$

-- Arqueo Rápido de Caja Diaria por Sede (corregido: muestra siempre los 4 medios de pago incluso en S/ 0.00)
DROP PROCEDURE IF EXISTS sp_arqueo_caja_sede$$
CREATE PROCEDURE sp_arqueo_caja_sede(
    IN p_id_sucursal INT
)
BEGIN
    SELECT mp.Nombre_Metodo AS Metodo_Pago,
           IFNULL(vs.Cantidad_Ventas, 0) AS Cantidad_Ventas,
           IFNULL(vs.Monto_Recaudado, 0.00) AS Monto_Recaudado
    FROM metodo_pago mp
    LEFT JOIN (
        SELECT p.ID_Metodo_Pago,
               COUNT(DISTINCT v.ID_Venta) AS Cantidad_Ventas,
               ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2) AS Monto_Recaudado
        FROM pago p
        INNER JOIN venta v ON p.ID_Pago = v.ID_Pago
        INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
        LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
        WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
        GROUP BY p.ID_Metodo_Pago
    ) vs ON mp.ID_Metodo_Pago = vs.ID_Metodo_Pago
    ORDER BY mp.ID_Metodo_Pago ASC;
END$$

-- ---------------------------------------------------------------------------------
-- 6.6. PROCEDIMIENTOS ALMACENADOS: PERSONAL, SEDES Y ROLES (RRHH)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_empleados$$
CREATE PROCEDURE sp_listar_empleados(
    IN p_filtro VARCHAR(100)
)
BEGIN
    SELECT e.ID_Empleado,
           e.Nombres,
           e.Apellido_Paterno,
           e.Apellido_Materno,
           CONCAT(s.ID_Surcusal, ' - ', s.Nombre_Suc) AS Sucursal,
           CASE
               WHEN r.RecursosHumanos = 1 THEN '3 - Recursos Humanos'
               WHEN r.AsistenteLogistico = 1 THEN '2 - Logística y Almacén'
               ELSE '1 - Multifuncional (Caja)'
           END AS Rol_Asignado,
           CASE
               WHEN c.Usuario IS NOT NULL THEN c.Usuario
               WHEN e.ID_Rol = 1 THEN CONCAT('Caja Sede #', s.ID_Surcusal)
               ELSE 'Sin cuenta'
           END AS Cuenta_Acceso
    FROM empleados e
    INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
    INNER JOIN rol r ON e.ID_Rol = r.ID_Rol
    LEFT JOIN credenciales_hash c ON e.ID_Empleado = c.ID_Empleado
    WHERE (p_filtro IS NULL OR TRIM(p_filtro) = ''
           OR e.Nombres LIKE CONCAT('%', TRIM(p_filtro), '%')
           OR e.Apellido_Paterno LIKE CONCAT('%', TRIM(p_filtro), '%'))
    ORDER BY e.ID_Empleado DESC;
END$$

DROP PROCEDURE IF EXISTS sp_listar_sucursales$$
CREATE PROCEDURE sp_listar_sucursales()
BEGIN
    SET time_zone = '-05:00';
    SELECT CONCAT(ID_Surcusal, ' - ', Nombre_Suc) AS Sucursal_Item
    FROM surcusal
    ORDER BY ID_Surcusal ASC;
END$$

DROP PROCEDURE IF EXISTS sp_insertar_empleado$$
CREATE PROCEDURE sp_insertar_empleado(
    IN p_id_sucursal INT,
    IN p_id_rol INT,
    IN p_nombres VARCHAR(45),
    IN p_ap_paterno VARCHAR(45),
    IN p_ap_materno VARCHAR(45),
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nombres, '')) = '' OR TRIM(IFNULL(p_ap_paterno, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Complete los nombres y el apellido paterno del colaborador.';
    END IF;
    SET @usuario_sesion = p_usuario_sesion;
    SET @rol_sesion = p_rol_sesion;

    INSERT INTO empleados (ID_Sucursal, ID_Rol, Nombres, Apellido_Paterno, Apellido_Materno, ID_Administrador)
    VALUES (p_id_sucursal, p_id_rol, TRIM(p_nombres), TRIM(p_ap_paterno), TRIM(IFNULL(p_ap_materno, '')), 1);

    SELECT LAST_INSERT_ID() AS ID_Nuevo;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_empleado$$
CREATE PROCEDURE sp_actualizar_empleado(
    IN p_id_empleado INT,
    IN p_id_sucursal INT,
    IN p_id_rol INT,
    IN p_nombres VARCHAR(45),
    IN p_ap_paterno VARCHAR(45),
    IN p_ap_materno VARCHAR(45),
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nombres, '')) = '' OR TRIM(IFNULL(p_ap_paterno, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Complete los nombres y el apellido paterno del colaborador.';
    END IF;
    SET @usuario_sesion = p_usuario_sesion;
    SET @rol_sesion = p_rol_sesion;

    UPDATE empleados
    SET ID_Sucursal = p_id_sucursal,
        ID_Rol = p_id_rol,
        Nombres = TRIM(p_nombres),
        Apellido_Paterno = TRIM(p_ap_paterno),
        Apellido_Materno = TRIM(IFNULL(p_ap_materno, ''))
    WHERE ID_Empleado = p_id_empleado;

    -- Si pasa a Multifuncional (ID_Rol = 1), usa la Caja Diaria de su sede y no cuenta personal
    IF p_id_rol = 1 THEN
        DELETE FROM credenciales_hash WHERE ID_Empleado = p_id_empleado;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_empleado$$
CREATE PROCEDURE sp_eliminar_empleado(
    IN p_id_empleado INT
)
BEGIN
    SET time_zone = '-05:00';
    DELETE FROM empleados WHERE ID_Empleado = p_id_empleado;
END$$

-- ---------------------------------------------------------------------------------
-- 6.7. PROCEDIMIENTOS ALMACENADOS: BITÁCORA DE AUDITORÍA
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_bitacora$$
CREATE PROCEDURE sp_listar_bitacora(
    IN p_accion VARCHAR(20),
    IN p_tabla VARCHAR(45)
)
BEGIN
    SELECT ID_Evento,
           Usuario_Responsable,
           Rol_Responsable,
           Tipo_Accion,
           Tabla_Afectada,
           Detalle_Cambio,
           DATE_FORMAT(Fecha_Hora, '%Y-%m-%d %H:%i:%s') AS Fecha
    FROM bitacora_auditoria
    WHERE (p_accion IS NULL OR p_accion = '' OR p_accion = 'Todos' OR Tipo_Accion = p_accion)
      AND (p_tabla IS NULL OR p_tabla = '' OR p_tabla = 'Todas' OR Tabla_Afectada = p_tabla)
    ORDER BY ID_Evento DESC;
END$$

-- =================================================================================
-- 7. PROCEDIMIENTOS ALMACENADOS FASE 2 — POS WEB ATÓMICO, DASHBOARD DE GERENCIA,
--    TOPPINGS, RECETAS, PROVEEDORES/COMPRAS, ALMACENES Y MINI-CRM (0 TABLAS NUEVAS)
-- =================================================================================

-- ---------------------------------------------------------------------------------
-- 7.1. CONTEXTO DE AUDITORÍA, SEGURIDAD WEB Y CATÁLOGOS COMERCIALES
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_fijar_contexto_auditoria$$
CREATE PROCEDURE sp_fijar_contexto_auditoria(
    IN p_usuario VARCHAR(45),
    IN p_rol VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';
    SET @usuario_sesion = p_usuario;
    SET @rol_sesion = p_rol;
END$$

DROP PROCEDURE IF EXISTS sp_consultar_jerarquia_usuario_web$$
CREATE PROCEDURE sp_consultar_jerarquia_usuario_web(
    IN p_usuario VARCHAR(45)
)
BEGIN
    SELECT ID_Credencial,
           Usuario,
           Requiere_Password,
           Rango_Rol,
           CASE Rango_Rol
               WHEN 'Administrador' THEN 'Gerencia General'
               WHEN 'RecursosHumanos' THEN 'Recursos Humanos'
               WHEN 'AsistenteLogistico' THEN 'Logística y Almacén'
               ELSE 'Caja Diaria'
           END AS Area_Comercial,
           Intentos_Fallidos,
           GREATEST(0, 3 - Intentos_Fallidos) AS Intentos_Restantes,
           Estado,
           Persona_Asignada,
           ID_Sucursal,
           Nombre_Sucursal
    FROM vw_credenciales_roles
    WHERE Usuario COLLATE utf8mb4_bin = p_usuario
    LIMIT 1;
END$$

DROP PROCEDURE IF EXISTS sp_catalogo_roles$$
CREATE PROCEDURE sp_catalogo_roles()
BEGIN
    SELECT ID_Rol,
           CASE
               WHEN RecursosHumanos = 1 THEN 'Recursos Humanos'
               WHEN AsistenteLogistico = 1 THEN 'Logística y Almacén'
               ELSE 'Multifuncional (Caja)'
           END AS Nombre_Comercial
    FROM rol
    ORDER BY ID_Rol ASC;
END$$

DROP PROCEDURE IF EXISTS sp_resumen_sanitario_insumos$$
CREATE PROCEDURE sp_resumen_sanitario_insumos()
BEGIN
    SET time_zone = '-05:00';
    SELECT COUNT(*) AS Total_Insumos,
           IFNULL(SUM(CASE WHEN Es_Perecible = 1 AND F_Vencimiento IS NOT NULL AND DATE(F_Vencimiento) < CURDATE() THEN 1 ELSE 0 END), 0) AS Total_Vencidos,
           IFNULL(SUM(CASE WHEN Es_Perecible = 1 AND F_Vencimiento IS NOT NULL AND DATE(F_Vencimiento) >= CURDATE() AND DATEDIFF(DATE(F_Vencimiento), CURDATE()) <= 30 THEN 1 ELSE 0 END), 0) AS Total_Por_Vencer,
           IFNULL(SUM(CASE WHEN Es_Perecible = 1 AND F_Vencimiento IS NOT NULL AND DATEDIFF(DATE(F_Vencimiento), CURDATE()) > 30 THEN 1 ELSE 0 END), 0) AS Total_Vigentes,
           IFNULL(SUM(CASE WHEN Es_Perecible = 0 OR F_Vencimiento IS NULL THEN 1 ELSE 0 END), 0) AS Total_No_Perecibles
    FROM insumo;
END$$

DROP PROCEDURE IF EXISTS sp_listar_bitacora_comercial$$
CREATE PROCEDURE sp_listar_bitacora_comercial(
    IN p_accion VARCHAR(30),
    IN p_modulo VARCHAR(50),
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SELECT b.ID_Evento,
           DATE_FORMAT(b.Fecha_Hora, '%Y-%m-%d %H:%i:%s') AS Fecha_Hora,
           CASE b.Usuario_Responsable
               WHEN 'trigger_mysql' THEN 'sistema'
               WHEN 'sistema_mysql' THEN 'sistema'
               ELSE b.Usuario_Responsable
           END AS Usuario_Responsable,
           CASE b.Rol_Responsable
               WHEN 'Administrador' THEN 'Gerencia General'
               WHEN 'RecursosHumanos' THEN 'Recursos Humanos'
               WHEN 'AsistenteLogistico' THEN 'Logística y Almacén'
               WHEN 'Multifuncional' THEN 'Caja Diaria'
               WHEN 'Trigger_BD' THEN 'Sistema Automático'
               WHEN 'Motor_BD' THEN 'Sistema Automático'
               ELSE b.Rol_Responsable
           END AS Area_Responsable,
           CASE b.Tipo_Accion
               WHEN 'LOGIN' THEN 'ACCESO'
               WHEN 'INSERT' THEN 'ALTA'
               WHEN 'UPDATE' THEN 'CAMBIO'
               WHEN 'DELETE' THEN 'BAJA'
               WHEN 'BLOQUEO' THEN 'SEGURIDAD'
               ELSE b.Tipo_Accion
           END AS Categoria_Evento,
           CASE b.Tipo_Accion
               WHEN 'LOGIN' THEN 'Inicio de Sesión'
               WHEN 'INSERT' THEN 'Registro'
               WHEN 'UPDATE' THEN 'Actualización'
               WHEN 'DELETE' THEN 'Eliminación / Anulación'
               WHEN 'BLOQUEO' THEN 'Bloqueo Preventivo'
               ELSE b.Tipo_Accion
           END AS Evento_Comercial,
           CASE b.Tabla_Afectada
               WHEN 'credenciales_hash' THEN 'Seguridad y Accesos'
               WHEN 'producto' THEN 'Catálogo de Productos'
               WHEN 'insumo' THEN 'Almacén e Insumos'
               WHEN 'venta' THEN 'Punto de Venta'
               WHEN 'empleados' THEN 'Personal y Sedes'
               WHEN 'topping' THEN 'Toppings y Adicionales'
               WHEN 'compra' THEN 'Compras y Abastecimiento'
               ELSE b.Tabla_Afectada
           END AS Modulo_Comercial,
           TRIM(
               REPLACE(
               REPLACE(
               REPLACE(
               REPLACE(
               REPLACE(
               REPLACE(
               REPLACE(
               REPLACE(
               REPLACE(
               REPLACE(
                   b.Detalle_Cambio,
                   '[TRIGGER] ', ''),
                   '[SP_LOGIN] ', ''),
                   '[SP_CREDENCIAL] ', ''),
                   'Autenticación SHA-256 exitosa', 'Ingreso administrativo verificado'),
                   'Ingreso operativo directo sin clave', 'Ingreso directo de caja'),
                   'Rol BD:', 'Área:'),
                   'RecursosHumanos', 'Recursos Humanos'),
                   'AsistenteLogistico', 'Logística y Almacén'),
                   'Multifuncional', 'Caja Diaria'),
                   'Empleado ID ', 'Colaborador #')
           ) AS Detalle_Cambio
    FROM bitacora_auditoria b
    WHERE (p_accion IS NULL OR p_accion = '' OR p_accion = 'Todos'
           OR b.Tipo_Accion = p_accion
           OR CASE b.Tipo_Accion
                  WHEN 'LOGIN' THEN 'ACCESO'
                  WHEN 'INSERT' THEN 'ALTA'
                  WHEN 'UPDATE' THEN 'CAMBIO'
                  WHEN 'DELETE' THEN 'BAJA'
                  WHEN 'BLOQUEO' THEN 'SEGURIDAD'
                  ELSE b.Tipo_Accion
              END = p_accion
           OR CASE b.Tipo_Accion
                  WHEN 'LOGIN' THEN 'Inicio de Sesión'
                  WHEN 'INSERT' THEN 'Registro'
                  WHEN 'UPDATE' THEN 'Actualización'
                  WHEN 'DELETE' THEN 'Eliminación / Anulación'
                  WHEN 'BLOQUEO' THEN 'Bloqueo Preventivo'
                  ELSE b.Tipo_Accion
              END = p_accion)
      AND (p_modulo IS NULL OR p_modulo = '' OR p_modulo = 'Todos' OR
           CASE b.Tabla_Afectada
               WHEN 'credenciales_hash' THEN 'Seguridad y Accesos'
               WHEN 'producto' THEN 'Catálogo de Productos'
               WHEN 'insumo' THEN 'Almacén e Insumos'
               WHEN 'venta' THEN 'Punto de Venta'
               WHEN 'empleados' THEN 'Personal y Sedes'
               WHEN 'topping' THEN 'Toppings y Adicionales'
               WHEN 'compra' THEN 'Compras y Abastecimiento'
               ELSE b.Tabla_Afectada
           END = p_modulo)
      AND (p_fecha_desde IS NULL OR DATE(b.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(b.Fecha_Hora) <= p_fecha_hasta)
    ORDER BY b.ID_Evento DESC;
END$$

-- ---------------------------------------------------------------------------------
-- 7.2. POS WEB RÁPIDO, CÁLCULO DE CARRITO EN MYSQL, VENTA ATÓMICA ACID Y ARQUEO
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_calcular_resumen_carrito$$
CREATE PROCEDURE sp_calcular_resumen_carrito(
    IN p_items_json JSON,
    IN p_monto_recibido DECIMAL(10,2)
)
BEGIN
    DECLARE v_total_cobrar DECIMAL(10,2) DEFAULT 0.00;
    DECLARE v_total_lineas INT DEFAULT 0;
    DECLARE v_total_unidades INT DEFAULT 0;
    DECLARE v_recibido DECIMAL(10,2) DEFAULT 0.00;

    IF p_items_json IS NULL OR JSON_LENGTH(p_items_json) = 0 THEN
        SELECT 0 AS Linea_Idx, 0 AS ID_Producto, '' AS Nom_Producto, 0 AS Cantidad,
               0.00 AS Precio_Base, 0 AS ID_Topping, 'Sin Topping' AS Nom_Topping,
               0.00 AS Precio_Topping, 0.00 AS Precio_Unitario_Final, 0.00 AS Subtotal_Linea
        WHERE 1 = 0;

        SELECT 0 AS Total_Lineas, 0 AS Total_Unidades, 0.00 AS Total_Cobrar,
               IFNULL(p_monto_recibido, 0.00) AS Monto_Recibido, 0.00 AS Vuelto, 0.00 AS Faltante;
    ELSE
        -- Result-set 1: Detalle valorizado exclusivamente con precios oficiales de MySQL
        SELECT jt.linea_idx AS Linea_Idx,
               p.ID_Producto,
               p.Nom_Producto,
               jt.cantidad AS Cantidad,
               p.Precio_Venta AS Precio_Base,
               IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.ID_Topping, 0) AS ID_Topping,
               IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.Nom_Topping, 'Sin Topping') AS Nom_Topping,
               IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.Precio_Agregado, 0.00) AS Precio_Topping,
               ROUND(p.Precio_Venta + IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.Precio_Agregado, 0.00), 2) AS Precio_Unitario_Final,
               ROUND(jt.cantidad * (p.Precio_Venta + IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.Precio_Agregado, 0.00)), 2) AS Subtotal_Linea
        FROM JSON_TABLE(
            p_items_json,
            '$[*]' COLUMNS(
                linea_idx   FOR ORDINALITY,
                id_producto INT PATH '$.id_producto',
                cantidad    INT PATH '$.cantidad',
                id_topping  INT PATH '$.id_topping' DEFAULT '0' ON EMPTY DEFAULT '0' ON ERROR
            )
        ) jt
        INNER JOIN producto p ON p.ID_Producto = jt.id_producto
        LEFT JOIN topping t ON t.ID_Topping = jt.id_topping AND jt.id_topping > 0
        WHERE jt.cantidad > 0
        ORDER BY jt.linea_idx ASC;

        -- Result-set 2: Resumen total del pedido y cálculo de vuelto en MySQL
        SELECT COUNT(*),
               IFNULL(SUM(jt.cantidad), 0),
               IFNULL(ROUND(SUM(jt.cantidad * (p.Precio_Venta + IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.Precio_Agregado, 0.00))), 2), 0.00)
        INTO v_total_lineas, v_total_unidades, v_total_cobrar
        FROM JSON_TABLE(
            p_items_json,
            '$[*]' COLUMNS(
                id_producto INT PATH '$.id_producto',
                cantidad    INT PATH '$.cantidad',
                id_topping  INT PATH '$.id_topping' DEFAULT '0' ON EMPTY DEFAULT '0' ON ERROR
            )
        ) jt
        INNER JOIN producto p ON p.ID_Producto = jt.id_producto
        LEFT JOIN topping t ON t.ID_Topping = jt.id_topping AND jt.id_topping > 0
        WHERE jt.cantidad > 0;

        SET v_recibido = IFNULL(p_monto_recibido, 0.00);
        SELECT v_total_lineas AS Total_Lineas,
               v_total_unidades AS Total_Unidades,
               v_total_cobrar AS Total_Cobrar,
               v_recibido AS Monto_Recibido,
               IF(v_recibido >= v_total_cobrar AND v_recibido > 0, ROUND(v_recibido - v_total_cobrar, 2), 0.00) AS Vuelto,
               IF(v_recibido > 0 AND v_recibido < v_total_cobrar, ROUND(v_total_cobrar - v_recibido, 2), 0.00) AS Faltante;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_registrar_venta_completa$$
CREATE PROCEDURE sp_registrar_venta_completa(
    IN p_tipo_comprobante VARCHAR(45),
    IN p_id_sucursal INT,
    IN p_canal_atencion VARCHAR(45),
    IN p_id_empleado INT,
    IN p_id_cliente INT,
    IN p_id_metodo_pago INT,
    IN p_items_json JSON,
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    DECLARE v_total_items INT DEFAULT 0;
    DECLARE v_valid_items INT DEFAULT 0;
    DECLARE v_emp_suc INT DEFAULT NULL;
    DECLARE v_emp_rol INT DEFAULT NULL;
    DECLARE v_cli_ok INT DEFAULT 0;
    DECLARE v_mp_ok INT DEFAULT 0;
    DECLARE v_suc_final INT DEFAULT 1;
    DECLARE v_prefijo CHAR(1);
    DECLARE v_serie VARCHAR(6);
    DECLARE v_max_num INT DEFAULT 100;
    DECLARE v_comprobante VARCHAR(45);
    DECLARE v_id_pago INT;
    DECLARE v_id_venta INT;
    DECLARE v_total_cobrado DECIMAL(10,2) DEFAULT 0.00;
    DECLARE v_canal_clean VARCHAR(45);
    DECLARE v_doc_clean VARCHAR(45);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET time_zone = '-05:00';

    IF p_items_json IS NULL OR JSON_LENGTH(p_items_json) = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Agregue al menos un producto al pedido antes de emitir el comprobante.';
    END IF;

    SET v_canal_clean = IF(UPPER(TRIM(IFNULL(p_canal_atencion, 'Sede'))) = 'DELIVERY', 'Delivery', 'Sede');
    SET v_doc_clean = IF(UPPER(TRIM(IFNULL(p_tipo_comprobante, 'Boleta'))) = 'FACTURA', 'Factura', 'Boleta');

    START TRANSACTION;
        SELECT ID_Sucursal, ID_Rol INTO v_emp_suc, v_emp_rol FROM empleados WHERE ID_Empleado = p_id_empleado LIMIT 1;
        IF v_emp_suc IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El colaborador seleccionado no existe.';
        END IF;

        IF v_emp_rol <> 1 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El colaborador seleccionado no pertenece al equipo operativo de caja.';
        END IF;

        IF p_id_sucursal IS NOT NULL AND p_id_sucursal > 0 AND v_emp_suc <> p_id_sucursal THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El colaborador seleccionado no pertenece a la sucursal de esta caja.';
        END IF;

        SELECT COUNT(*) INTO v_cli_ok FROM cliente WHERE ID_Cliente = p_id_cliente;
        IF v_cli_ok = 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El cliente seleccionado no existe.';
        END IF;

        SELECT COUNT(*) INTO v_mp_ok FROM metodo_pago WHERE ID_Metodo_Pago = p_id_metodo_pago;
        IF v_mp_ok = 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El medio de pago seleccionado no es válido.';
        END IF;

        -- Validar integridad 100% de todas las líneas antes de escribir
        SELECT COUNT(*) INTO v_total_items
        FROM JSON_TABLE(
            p_items_json,
            '$[*]' COLUMNS(
                id_producto INT PATH '$.id_producto',
                cantidad    INT PATH '$.cantidad',
                id_topping  INT PATH '$.id_topping' DEFAULT '0' ON EMPTY DEFAULT '0' ON ERROR
            )
        ) jt;

        SELECT COUNT(*) INTO v_valid_items
        FROM JSON_TABLE(
            p_items_json,
            '$[*]' COLUMNS(
                id_producto INT PATH '$.id_producto',
                cantidad    INT PATH '$.cantidad',
                id_topping  INT PATH '$.id_topping' DEFAULT '0' ON EMPTY DEFAULT '0' ON ERROR
            )
        ) jt
        INNER JOIN producto p ON p.ID_Producto = jt.id_producto
        LEFT JOIN topping t ON t.ID_Topping = jt.id_topping AND jt.id_topping > 0
        WHERE jt.cantidad > 0
          AND (jt.id_topping = 0 OR t.ID_Topping IS NOT NULL);

        IF v_total_items = 0 OR v_valid_items <> v_total_items THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Uno o más productos, cantidades o toppings del pedido no son válidos. Operación revertida.';
        END IF;

        -- Correlativo atómico por sede con bloqueo pesimista FOR UPDATE
        SET v_suc_final = IF(p_id_sucursal IS NOT NULL AND p_id_sucursal > 0, p_id_sucursal, v_emp_suc);
        SET v_prefijo = IF(v_doc_clean = 'Factura', 'F', 'B');
        SET v_serie = CONCAT(v_prefijo, LPAD(v_suc_final, 3, '0'), '-');

        SELECT IFNULL(MAX(CAST(SUBSTRING_INDEX(Num_Comprobante, '-', -1) AS UNSIGNED)), 100)
        INTO v_max_num
        FROM venta
        WHERE Num_Comprobante LIKE CONCAT(v_serie, '%')
        FOR UPDATE;

        SET v_comprobante = CONCAT(v_serie, LPAD(v_max_num + 1, 4, '0'));

        SET @usuario_sesion = IFNULL(p_usuario_sesion, 'caja_sede');
        SET @rol_sesion = IFNULL(p_rol_sesion, 'Multifuncional');

        INSERT INTO pago (Tipo_Comprobante, ID_Metodo_Pago)
        VALUES (v_doc_clean, p_id_metodo_pago);
        SET v_id_pago = LAST_INSERT_ID();

        INSERT INTO venta (Num_Comprobante, Canal_Atencion, Fecha_Hora, ID_Empleado, ID_Cliente, ID_Pago)
        VALUES (v_comprobante, v_canal_clean, NOW(), p_id_empleado, p_id_cliente, v_id_pago);
        SET v_id_venta = LAST_INSERT_ID();

        -- Inserción masiva tomando exclusivamente precios oficiales vigentes en MySQL
        INSERT INTO detalle_venta (ID_Producto, Cantidad, Precio_Unitario, ID_Topping, Precio_Topping, ID_Venta)
        SELECT p.ID_Producto,
               jt.cantidad,
               p.Precio_Venta,
               IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.ID_Topping, NULL),
               IF(jt.id_topping > 0 AND t.ID_Topping IS NOT NULL, t.Precio_Agregado, 0.00),
               v_id_venta
        FROM JSON_TABLE(
            p_items_json,
            '$[*]' COLUMNS(
                id_producto INT PATH '$.id_producto',
                cantidad    INT PATH '$.cantidad',
                id_topping  INT PATH '$.id_topping' DEFAULT '0' ON EMPTY DEFAULT '0' ON ERROR
            )
        ) jt
        INNER JOIN producto p ON p.ID_Producto = jt.id_producto
        LEFT JOIN topping t ON t.ID_Topping = jt.id_topping AND jt.id_topping > 0;

        SELECT IFNULL(ROUND(SUM(Cantidad * (Precio_Unitario + IFNULL(Precio_Topping, 0.00))), 2), 0.00)
        INTO v_total_cobrado
        FROM detalle_venta
        WHERE ID_Venta = v_id_venta;
    COMMIT;

    SELECT v_id_venta AS ID_Venta_Generada,
           v_id_pago AS ID_Pago_Generado,
           v_comprobante AS Num_Comprobante,
           v_total_cobrado AS Total_Cobrado;
END$$

DROP PROCEDURE IF EXISTS sp_arqueo_caja_rango$$
CREATE PROCEDURE sp_arqueo_caja_rango(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    DECLARE v_gran_total DECIMAL(10,2) DEFAULT 0.00;

    SELECT IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00)
    INTO v_gran_total
    FROM venta v
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    INNER JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
      AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta);

    SELECT mp.ID_Metodo_Pago,
           mp.Nombre_Metodo AS Metodo_Pago,
           IFNULL(vs.Cantidad_Ventas, 0) AS Cantidad_Ventas,
           IFNULL(vs.Monto_Recaudado, 0.00) AS Monto_Recaudado,
           IF(v_gran_total > 0, ROUND((IFNULL(vs.Monto_Recaudado, 0.00) / v_gran_total) * 100, 1), 0.0) AS Porcentaje_Participacion
    FROM metodo_pago mp
    LEFT JOIN (
        SELECT p.ID_Metodo_Pago,
               COUNT(DISTINCT v.ID_Venta) AS Cantidad_Ventas,
               ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2) AS Monto_Recaudado
        FROM pago p
        INNER JOIN venta v ON p.ID_Pago = v.ID_Pago
        INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
        LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
        WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
          AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
          AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
        GROUP BY p.ID_Metodo_Pago
    ) vs ON mp.ID_Metodo_Pago = vs.ID_Metodo_Pago
    ORDER BY mp.ID_Metodo_Pago ASC;
END$$

DROP PROCEDURE IF EXISTS sp_arqueo_caja_resumen$$
CREATE PROCEDURE sp_arqueo_caja_resumen(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    DECLARE v_nom_suc VARCHAR(100) DEFAULT 'Todas las Sedes (Central)';
    IF p_id_sucursal IS NOT NULL AND p_id_sucursal > 0 THEN
        SELECT Nombre_Suc INTO v_nom_suc FROM surcusal WHERE ID_Surcusal = p_id_sucursal LIMIT 1;
    END IF;

    SELECT v_nom_suc AS Nombre_Sucursal,
           COUNT(DISTINCT v.ID_Venta) AS Total_Ventas,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Total_Recaudado,
           IF(COUNT(DISTINCT v.ID_Venta) > 0,
              ROUND(IFNULL(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 0.00) / COUNT(DISTINCT v.ID_Venta), 2),
              0.00) AS Ticket_Promedio,
           COUNT(DISTINCT CASE WHEN v.Canal_Atencion = 'Sede' THEN v.ID_Venta END) AS Ventas_Sede,
           COUNT(DISTINCT CASE WHEN v.Canal_Atencion = 'Delivery' THEN v.ID_Venta END) AS Ventas_Delivery
    FROM venta v
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
      AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta);
END$$

DROP PROCEDURE IF EXISTS sp_obtener_detalle_venta$$
CREATE PROCEDURE sp_obtener_detalle_venta(
    IN p_id_venta INT
)
BEGIN
    -- Result-set 1: Cabecera completa del comprobante para visor y ticket 80mm
    SELECT v.ID_Venta,
           v.Num_Comprobante,
           p.Tipo_Comprobante,
           v.Canal_Atencion,
           DATE_FORMAT(v.Fecha_Hora, '%Y-%m-%d %H:%i') AS Fecha_Hora,
           s.ID_Surcusal AS ID_Sucursal,
           s.Nombre_Suc AS Nombre_Sucursal,
           s.Direccion AS Direccion_Sucursal,
           s.Telefono AS Telefono_Sucursal,
           CONCAT(e.Nombres, ' ', e.Apellido_Paterno) AS Cajero,
           CONCAT(c.Nombres, ' ', c.Apellido_Paterno) AS Cliente,
           IFNULL(c.Celular, '') AS Celular_Cliente,
           mp.Nombre_Metodo AS Metodo_Pago,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Total_Venta
    FROM venta v
    INNER JOIN pago p ON v.ID_Pago = p.ID_Pago
    INNER JOIN metodo_pago mp ON p.ID_Metodo_Pago = mp.ID_Metodo_Pago
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
    INNER JOIN cliente c ON v.ID_Cliente = c.ID_Cliente
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE v.ID_Venta = p_id_venta
    GROUP BY v.ID_Venta, v.Num_Comprobante, p.Tipo_Comprobante, v.Canal_Atencion, v.Fecha_Hora,
             s.ID_Surcusal, s.Nombre_Suc, s.Direccion, s.Telefono, Cajero, Cliente, c.Celular, mp.Nombre_Metodo;

    -- Result-set 2: Líneas del comprobante
    SELECT dv.ID_Detalle_Venta,
           dv.ID_Producto,
           pr.Nom_Producto,
           dv.Cantidad,
           dv.Precio_Unitario,
           IFNULL(t.Nom_Topping, 'Sin Topping') AS Nom_Topping,
           IFNULL(dv.Precio_Topping, 0.00) AS Precio_Topping,
           ROUND(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00)), 2) AS Subtotal_Linea
    FROM detalle_venta dv
    INNER JOIN producto pr ON dv.ID_Producto = pr.ID_Producto
    LEFT JOIN topping t ON dv.ID_Topping = t.ID_Topping
    WHERE dv.ID_Venta = p_id_venta
    ORDER BY dv.ID_Detalle_Venta ASC;
END$$

DROP PROCEDURE IF EXISTS sp_buscar_ventas$$
CREATE PROCEDURE sp_buscar_ventas(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE,
    IN p_canal VARCHAR(20),
    IN p_id_metodo INT,
    IN p_texto VARCHAR(100)
)
BEGIN
    SELECT v.ID_Venta,
           v.Num_Comprobante,
           p.Tipo_Comprobante,
           v.Canal_Atencion,
           DATE_FORMAT(v.Fecha_Hora, '%Y-%m-%d %H:%i') AS Fecha,
           CONCAT(c.Nombres, ' ', c.Apellido_Paterno) AS Cliente,
           CONCAT(e.Nombres, ' ', e.Apellido_Paterno) AS Cajero,
           s.Nombre_Suc AS Sede,
           mp.Nombre_Metodo AS Metodo_Pago,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Total
    FROM venta v
    INNER JOIN cliente c ON v.ID_Cliente = c.ID_Cliente
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
    INNER JOIN pago p ON v.ID_Pago = p.ID_Pago
    INNER JOIN metodo_pago mp ON p.ID_Metodo_Pago = mp.ID_Metodo_Pago
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
      AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
      AND (p_canal IS NULL OR p_canal = '' OR p_canal = 'Todos' OR v.Canal_Atencion = p_canal)
      AND (p_id_metodo IS NULL OR p_id_metodo = 0 OR p.ID_Metodo_Pago = p_id_metodo)
      AND (p_texto IS NULL OR TRIM(p_texto) = ''
           OR v.Num_Comprobante LIKE CONCAT('%', TRIM(p_texto), '%')
           OR CONCAT(c.Nombres, ' ', c.Apellido_Paterno) LIKE CONCAT('%', TRIM(p_texto), '%')
           OR CONCAT(e.Nombres, ' ', e.Apellido_Paterno) LIKE CONCAT('%', TRIM(p_texto), '%'))
    GROUP BY v.ID_Venta, v.Num_Comprobante, p.Tipo_Comprobante, v.Canal_Atencion, v.Fecha_Hora,
             Cliente, Cajero, Sede, Metodo_Pago
    ORDER BY v.ID_Venta DESC;
END$$

-- ---------------------------------------------------------------------------------
-- 7.3. DASHBOARD EJECUTIVO DE GERENCIA GENERAL (8 STORED PROCEDURES ANALÍTICOS)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_dashboard_kpis_generales$$
CREATE PROCEDURE sp_dashboard_kpis_generales(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    DECLARE v_vencidos INT DEFAULT 0;
    DECLARE v_por_vencer INT DEFAULT 0;
    DECLARE v_bloqueadas INT DEFAULT 0;

    SET time_zone = '-05:00';

    SELECT IFNULL(SUM(CASE WHEN Es_Perecible = 1 AND F_Vencimiento IS NOT NULL AND DATE(F_Vencimiento) < CURDATE() THEN 1 ELSE 0 END), 0),
           IFNULL(SUM(CASE WHEN Es_Perecible = 1 AND F_Vencimiento IS NOT NULL AND DATE(F_Vencimiento) >= CURDATE() AND DATEDIFF(DATE(F_Vencimiento), CURDATE()) <= 30 THEN 1 ELSE 0 END), 0)
    INTO v_vencidos, v_por_vencer
    FROM insumo;

    SELECT COUNT(*) INTO v_bloqueadas
    FROM credenciales_hash
    WHERE Estado = 'Bloqueado' OR Intentos_Fallidos >= 3;

    SELECT IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Total_Ingresos,
           COUNT(DISTINCT v.ID_Venta) AS Cantidad_Ventas,
           IF(COUNT(DISTINCT v.ID_Venta) > 0,
              ROUND(IFNULL(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 0.00) / COUNT(DISTINCT v.ID_Venta), 2),
              0.00) AS Ticket_Promedio,
           IFNULL(SUM(dv.Cantidad), 0) AS Unidades_Vendidas,
           COUNT(DISTINCT v.ID_Cliente) AS Clientes_Unicos,
           v_vencidos AS Insumos_Vencidos,
           v_por_vencer AS Insumos_Por_Vencer,
           v_bloqueadas AS Cuentas_Bloqueadas
    FROM venta v
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
      AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta);
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_ventas_por_sede$$
CREATE PROCEDURE sp_dashboard_ventas_por_sede(
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    DECLARE v_total_red DECIMAL(10,2) DEFAULT 0.00;

    SELECT IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00)
    INTO v_total_red
    FROM venta v
    INNER JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta);

    SELECT s.ID_Surcusal AS ID_Sucursal,
           s.Nombre_Suc AS Nombre_Sucursal,
           IFNULL(ag.Cantidad_Ventas, 0) AS Cantidad_Ventas,
           IFNULL(ag.Total_Ingresos, 0.00) AS Total_Ingresos,
           IF(IFNULL(ag.Cantidad_Ventas, 0) > 0, ROUND(ag.Total_Ingresos / ag.Cantidad_Ventas, 2), 0.00) AS Ticket_Promedio,
           IF(v_total_red > 0, ROUND((IFNULL(ag.Total_Ingresos, 0.00) / v_total_red) * 100, 1), 0.0) AS Porcentaje_Participacion
    FROM surcusal s
    LEFT JOIN (
        SELECT e.ID_Sucursal,
               COUNT(DISTINCT v.ID_Venta) AS Cantidad_Ventas,
               ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2) AS Total_Ingresos
        FROM empleados e
        INNER JOIN venta v ON e.ID_Empleado = v.ID_Empleado
        LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
        WHERE (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
          AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
        GROUP BY e.ID_Sucursal
    ) ag ON s.ID_Surcusal = ag.ID_Sucursal
    ORDER BY Total_Ingresos DESC, s.ID_Surcusal ASC;
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_ventas_por_metodo_pago$$
CREATE PROCEDURE sp_dashboard_ventas_por_metodo_pago(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    CALL sp_arqueo_caja_rango(p_id_sucursal, p_fecha_desde, p_fecha_hasta);
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_top_productos$$
CREATE PROCEDURE sp_dashboard_top_productos(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE,
    IN p_limite INT
)
BEGIN
    DECLARE v_total_ing DECIMAL(10,2) DEFAULT 0.00;
    DECLARE v_lim INT DEFAULT 10;
    SET v_lim = IF(p_limite IS NULL OR p_limite <= 0, 10, p_limite);

    SELECT IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00)
    INTO v_total_ing
    FROM venta v
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    INNER JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
      AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta);

    SELECT pr.ID_Producto,
           pr.Nom_Producto,
           pr.Precio_Venta AS Precio_Actual,
           IFNULL(SUM(dv.Cantidad), 0) AS Unidades_Vendidas,
           IFNULL(ROUND(SUM(dv.Cantidad * dv.Precio_Unitario), 2), 0.00) AS Ingresos_Base,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Ingresos_Totales,
           IF(v_total_ing > 0, ROUND((IFNULL(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 0.00) / v_total_ing) * 100, 1), 0.0) AS Participacion_Pct
    FROM producto pr
    LEFT JOIN (
        SELECT dv.ID_Producto, dv.Cantidad, dv.Precio_Unitario, dv.Precio_Topping
        FROM detalle_venta dv
        INNER JOIN venta v ON dv.ID_Venta = v.ID_Venta
        INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
        WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
          AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
          AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
    ) dv ON pr.ID_Producto = dv.ID_Producto
    GROUP BY pr.ID_Producto, pr.Nom_Producto, pr.Precio_Venta
    ORDER BY Ingresos_Totales DESC, Unidades_Vendidas DESC
    LIMIT v_lim;
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_top_toppings$$
CREATE PROCEDURE sp_dashboard_top_toppings(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SELECT t.ID_Topping,
           t.Nom_Topping,
           t.Precio_Agregado,
           COUNT(dv.ID_Detalle_Venta) AS Veces_Solicitado,
           IFNULL(SUM(dv.Cantidad), 0) AS Unidades_Con_Topping,
           IFNULL(ROUND(SUM(dv.Cantidad * IFNULL(dv.Precio_Topping, 0.00)), 2), 0.00) AS Ingresos_Toppings
    FROM topping t
    LEFT JOIN (
        SELECT dv.ID_Detalle_Venta, dv.ID_Topping, dv.Cantidad, dv.Precio_Topping
        FROM detalle_venta dv
        INNER JOIN venta v ON dv.ID_Venta = v.ID_Venta
        INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
        WHERE dv.ID_Topping IS NOT NULL
          AND (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
          AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
          AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
    ) dv ON t.ID_Topping = dv.ID_Topping
    GROUP BY t.ID_Topping, t.Nom_Topping, t.Precio_Agregado
    ORDER BY Unidades_Con_Topping DESC, t.ID_Topping ASC;
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_ventas_por_canal$$
CREATE PROCEDURE sp_dashboard_ventas_por_canal(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    DECLARE v_total_v INT DEFAULT 0;
    SELECT COUNT(DISTINCT v.ID_Venta) INTO v_total_v
    FROM venta v
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
      AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta);

    SELECT c_ref.Canal AS Canal_Atencion,
           IFNULL(ag.Cantidad_Ventas, 0) AS Cantidad_Ventas,
           IFNULL(ag.Total_Ingresos, 0.00) AS Total_Ingresos,
           IF(IFNULL(ag.Cantidad_Ventas, 0) > 0, ROUND(ag.Total_Ingresos / ag.Cantidad_Ventas, 2), 0.00) AS Ticket_Promedio,
           IF(v_total_v > 0, ROUND((IFNULL(ag.Cantidad_Ventas, 0) / v_total_v) * 100, 1), 0.0) AS Porcentaje_Ventas
    FROM (SELECT 'Sede' AS Canal UNION ALL SELECT 'Delivery' AS Canal) c_ref
    LEFT JOIN (
        SELECT v.Canal_Atencion,
               COUNT(DISTINCT v.ID_Venta) AS Cantidad_Ventas,
               ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2) AS Total_Ingresos
        FROM venta v
        INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
        LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
        WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
          AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
          AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
        GROUP BY v.Canal_Atencion
    ) ag ON c_ref.Canal = ag.Canal_Atencion;
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_tendencia_diaria$$
CREATE PROCEDURE sp_dashboard_tendencia_diaria(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SELECT DATE_FORMAT(v.Fecha_Hora, '%Y-%m-%d') AS Fecha,
           COUNT(DISTINCT v.ID_Venta) AS Cantidad_Ventas,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Total_Ingresos
    FROM venta v
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
      AND (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
    GROUP BY DATE_FORMAT(v.Fecha_Hora, '%Y-%m-%d')
    ORDER BY Fecha ASC;
END$$

DROP PROCEDURE IF EXISTS sp_dashboard_alertas_operativas$$
CREATE PROCEDURE sp_dashboard_alertas_operativas()
BEGIN
    SET time_zone = '-05:00';
    -- Result-set 1: Insumos vencidos y próximos a vencer
    SELECT i.ID_Insumo,
           i.Nombre_Insumo,
           i.Unidad_Medida,
           DATE_FORMAT(i.F_Vencimiento, '%Y-%m-%d') AS Fecha_Vencimiento,
           DATEDIFF(DATE(i.F_Vencimiento), CURDATE()) AS Dias_Restantes,
           CASE
               WHEN DATE(i.F_Vencimiento) < CURDATE() THEN 'VENCIDO - RETIRAR'
               ELSE 'POR VENCER'
           END AS Estado_Sanitario
    FROM insumo i
    WHERE i.Es_Perecible = 1
      AND i.F_Vencimiento IS NOT NULL
      AND DATEDIFF(DATE(i.F_Vencimiento), CURDATE()) <= 30
    ORDER BY Dias_Restantes ASC;

    -- Result-set 2: Cuentas administrativas bloqueadas o con intentos fallidos
    SELECT ID_Credencial,
           Usuario,
           Persona_Asignada,
           CASE Rango_Rol
               WHEN 'Administrador' THEN 'Gerencia General'
               WHEN 'RecursosHumanos' THEN 'Recursos Humanos'
               WHEN 'AsistenteLogistico' THEN 'Logística y Almacén'
               ELSE 'Caja Diaria'
           END AS Area_Comercial,
           Intentos_Fallidos,
           Estado
    FROM vw_credenciales_roles
    WHERE Estado = 'Bloqueado' OR Intentos_Fallidos > 0
    ORDER BY Estado DESC, Intentos_Fallidos DESC;

    -- Result-set 3: Productos cuya receta depende de un insumo vencido
    SELECT p.ID_Producto,
           p.Nom_Producto,
           GROUP_CONCAT(DISTINCT i.Nombre_Insumo ORDER BY i.Nombre_Insumo SEPARATOR ', ') AS Insumos_Vencidos_Asociados,
           COUNT(DISTINCT i.ID_Insumo) AS Cantidad_Insumos_Vencidos
    FROM producto p
    INNER JOIN receta r ON p.ID_Producto = r.ID_Producto
    INNER JOIN detalle_receta dr ON r.ID_Receta = dr.ID_Receta
    INNER JOIN insumo i ON dr.ID_Insumo = i.ID_Insumo
    WHERE i.Es_Perecible = 1
      AND i.F_Vencimiento IS NOT NULL
      AND DATE(i.F_Vencimiento) < CURDATE()
    GROUP BY p.ID_Producto, p.Nom_Producto
    ORDER BY Cantidad_Insumos_Vencidos DESC, p.ID_Producto ASC;
END$$

-- ---------------------------------------------------------------------------------
-- 7.4. GESTIÓN DE TOPPINGS Y MATRIZ PRODUCTO-TOPPING (S1 — 0 TABLAS NUEVAS)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_toppings$$
CREATE PROCEDURE sp_listar_toppings(
    IN p_filtro VARCHAR(100)
)
BEGIN
    SELECT t.ID_Topping,
           t.Nom_Topping,
           t.Precio_Agregado,
           COUNT(DISTINCT pt.ID_Producto) AS Productos_Vinculados
    FROM topping t
    LEFT JOIN producto_topping pt ON t.ID_Topping = pt.ID_Topping
    WHERE (p_filtro IS NULL OR TRIM(p_filtro) = ''
           OR t.Nom_Topping LIKE CONCAT('%', TRIM(p_filtro), '%'))
    GROUP BY t.ID_Topping, t.Nom_Topping, t.Precio_Agregado
    ORDER BY t.ID_Topping ASC;
END$$

DROP PROCEDURE IF EXISTS sp_insertar_topping$$
CREATE PROCEDURE sp_insertar_topping(
    IN p_nom_topping VARCHAR(50),
    IN p_precio_agregado DECIMAL(10,2),
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    DECLARE v_id_nuevo INT;
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nom_topping, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese el nombre del topping.';
    END IF;
    IF p_precio_agregado IS NULL OR p_precio_agregado < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El precio adicional del topping no puede ser negativo.';
    END IF;
    INSERT INTO topping (Nom_Topping, Precio_Agregado)
    VALUES (TRIM(p_nom_topping), p_precio_agregado);
    SET v_id_nuevo = LAST_INSERT_ID();

    INSERT INTO bitacora_auditoria (Usuario_Responsable, Rol_Responsable, Tipo_Accion, Tabla_Afectada, Detalle_Cambio)
    VALUES (IFNULL(p_usuario_sesion, 'sistema'), IFNULL(p_rol_sesion, 'AsistenteLogistico'),
            'INSERT', 'topping', CONCAT('Alta de topping #', v_id_nuevo, ': ', TRIM(p_nom_topping), ' (+S/ ', FORMAT(p_precio_agregado, 2), ')'));
    SELECT v_id_nuevo AS ID_Nuevo;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_topping$$
CREATE PROCEDURE sp_actualizar_topping(
    IN p_id_topping INT,
    IN p_nom_topping VARCHAR(50),
    IN p_precio_agregado DECIMAL(10,2),
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    SET time_zone = '-05:00';
    IF TRIM(IFNULL(p_nom_topping, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ingrese el nombre del topping.';
    END IF;
    IF p_precio_agregado IS NULL OR p_precio_agregado < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El precio adicional del topping no puede ser negativo.';
    END IF;
    SET @usuario_sesion = p_usuario_sesion;
    SET @rol_sesion = p_rol_sesion;
    UPDATE topping
    SET Nom_Topping = TRIM(p_nom_topping),
        Precio_Agregado = p_precio_agregado
    WHERE ID_Topping = p_id_topping;
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_topping$$
CREATE PROCEDURE sp_eliminar_topping(
    IN p_id_topping INT
)
BEGIN
    DELETE FROM producto_topping WHERE ID_Topping = p_id_topping;
    DELETE FROM topping WHERE ID_Topping = p_id_topping;
END$$

DROP PROCEDURE IF EXISTS sp_listar_matriz_producto_topping$$
CREATE PROCEDURE sp_listar_matriz_producto_topping()
BEGIN
    SELECT p.ID_Producto,
           p.Nom_Producto,
           t.ID_Topping,
           t.Nom_Topping,
           IF(pt.ID_Producto IS NOT NULL, 1, 0) AS Asignado
    FROM producto p
    CROSS JOIN topping t
    LEFT JOIN producto_topping pt ON p.ID_Producto = pt.ID_Producto AND t.ID_Topping = pt.ID_Topping
    ORDER BY p.ID_Producto ASC, t.ID_Topping ASC;
END$$

DROP PROCEDURE IF EXISTS sp_gestionar_producto_topping$$
CREATE PROCEDURE sp_gestionar_producto_topping(
    IN p_id_producto INT,
    IN p_id_topping INT,
    IN p_accion VARCHAR(15)
)
BEGIN
    IF UPPER(TRIM(p_accion)) = 'QUITAR' THEN
        DELETE FROM producto_topping
        WHERE ID_Producto = p_id_producto AND ID_Topping = p_id_topping;
    ELSE
        INSERT IGNORE INTO producto_topping (ID_Producto, ID_Topping)
        VALUES (p_id_producto, p_id_topping);
    END IF;
END$$

-- ---------------------------------------------------------------------------------
-- 7.5. RECETAS / ESCANDALLOS Y CRUCE SANITARIO (S3 — 0 TABLAS NUEVAS)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_recetas$$
CREATE PROCEDURE sp_listar_recetas()
BEGIN
    SET time_zone = '-05:00';
    SELECT p.ID_Producto,
           p.Nom_Producto,
           p.Precio_Venta,
           IFNULL(r.ID_Receta, 0) AS ID_Receta,
           COUNT(dr.ID_Insumo) AS Cantidad_Insumos,
           IFNULL(SUM(CASE WHEN i.Es_Perecible = 1 AND i.F_Vencimiento IS NOT NULL AND DATE(i.F_Vencimiento) < CURDATE() THEN 1 ELSE 0 END), 0) AS Insumos_Vencidos
    FROM producto p
    LEFT JOIN receta r ON p.ID_Producto = r.ID_Producto
    LEFT JOIN detalle_receta dr ON r.ID_Receta = dr.ID_Receta
    LEFT JOIN insumo i ON dr.ID_Insumo = i.ID_Insumo
    GROUP BY p.ID_Producto, p.Nom_Producto, p.Precio_Venta, r.ID_Receta
    ORDER BY p.ID_Producto ASC;
END$$

DROP PROCEDURE IF EXISTS sp_obtener_detalle_receta$$
CREATE PROCEDURE sp_obtener_detalle_receta(
    IN p_id_producto INT
)
BEGIN
    SET time_zone = '-05:00';
    SELECT r.ID_Receta,
           p.ID_Producto,
           p.Nom_Producto,
           i.ID_Insumo,
           i.Nombre_Insumo,
           i.Unidad_Medida,
           dr.Cantidad_Requerida,
           IFNULL(dr.Marg_Error, 0.00) AS Marg_Error,
           CASE
               WHEN i.Es_Perecible = 0 OR i.F_Vencimiento IS NULL THEN 'NO PERECIBLE'
               WHEN DATE(i.F_Vencimiento) < CURDATE() THEN 'VENCIDO - RETIRAR'
               WHEN DATEDIFF(DATE(i.F_Vencimiento), CURDATE()) <= 30 THEN 'POR VENCER'
               ELSE 'VIGENTE'
           END AS Estado_Sanitario
    FROM producto p
    INNER JOIN receta r ON p.ID_Producto = r.ID_Producto
    INNER JOIN detalle_receta dr ON r.ID_Receta = dr.ID_Receta
    INNER JOIN insumo i ON dr.ID_Insumo = i.ID_Insumo
    WHERE p.ID_Producto = p_id_producto
    ORDER BY i.Nombre_Insumo ASC;
END$$

DROP PROCEDURE IF EXISTS sp_guardar_detalle_receta$$
CREATE PROCEDURE sp_guardar_detalle_receta(
    IN p_id_producto INT,
    IN p_id_insumo INT,
    IN p_cantidad_requerida DECIMAL(10,2),
    IN p_marg_error DECIMAL(5,2)
)
BEGIN
    DECLARE v_id_receta INT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_cantidad_requerida IS NULL OR p_cantidad_requerida <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cantidad requerida en la receta debe ser mayor a cero.';
    END IF;

    START TRANSACTION;
        SELECT ID_Receta INTO v_id_receta FROM receta WHERE ID_Producto = p_id_producto LIMIT 1 FOR UPDATE;
        IF v_id_receta IS NULL THEN
            SELECT IFNULL(MAX(ID_Receta), 0) + 1 INTO v_id_receta FROM receta FOR UPDATE;
            INSERT INTO receta (ID_Producto, ID_Receta) VALUES (p_id_producto, v_id_receta);
        END IF;

        INSERT INTO detalle_receta (ID_Receta, ID_Insumo, Cantidad_Requerida, Marg_Error)
        VALUES (v_id_receta, p_id_insumo, p_cantidad_requerida, IFNULL(p_marg_error, 0.00))
        ON DUPLICATE KEY UPDATE
            Cantidad_Requerida = VALUES(Cantidad_Requerida),
            Marg_Error = VALUES(Marg_Error);
    COMMIT;
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_detalle_receta$$
CREATE PROCEDURE sp_eliminar_detalle_receta(
    IN p_id_producto INT,
    IN p_id_insumo INT
)
BEGIN
    DECLARE v_id_receta INT DEFAULT NULL;
    DECLARE v_restantes INT DEFAULT 0;

    SELECT ID_Receta INTO v_id_receta FROM receta WHERE ID_Producto = p_id_producto LIMIT 1;
    IF v_id_receta IS NOT NULL THEN
        DELETE FROM detalle_receta
        WHERE ID_Receta = v_id_receta
          AND ID_Insumo = p_id_insumo;

        SELECT COUNT(*) INTO v_restantes FROM detalle_receta WHERE ID_Receta = v_id_receta;
        IF v_restantes = 0 THEN
            DELETE FROM receta WHERE ID_Receta = v_id_receta;
        END IF;
    END IF;
END$$

-- ---------------------------------------------------------------------------------
-- 7.6. ALMACENES POR SEDE, PROVEEDORES Y COMPRAS / LOTES (S2 & S4 — 0 TABLAS NUEVAS)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_listar_almacenes_sucursales$$
CREATE PROCEDURE sp_listar_almacenes_sucursales()
BEGIN
    SELECT s.ID_Surcusal AS ID_Sucursal,
           s.Nombre_Suc AS Nombre_Sucursal,
           s.Direccion,
           s.Telefono,
           a.ID_Almacen,
           IFNULL(a.cantidad_disponible, 0) AS Cantidad_Disponible
    FROM surcusal s
    INNER JOIN almacen a ON s.ID_Almacen = a.ID_Almacen
    ORDER BY s.ID_Surcusal ASC;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_almacen_sucursal$$
CREATE PROCEDURE sp_actualizar_almacen_sucursal(
    IN p_id_almacen INT,
    IN p_cantidad_disponible INT
)
BEGIN
    IF p_cantidad_disponible IS NULL OR p_cantidad_disponible < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La capacidad disponible no puede ser negativa.';
    END IF;
    UPDATE almacen SET cantidad_disponible = p_cantidad_disponible WHERE ID_Almacen = p_id_almacen;
END$$

DROP PROCEDURE IF EXISTS sp_listar_proveedores$$
CREATE PROCEDURE sp_listar_proveedores(
    IN p_filtro VARCHAR(100)
)
BEGIN
    SELECT pr.ID_Proveedor,
           pr.Razon_Social,
           pr.RUC,
           pr.Telefono,
           pr.Email,
           IF(IFNULL(pr.Persona_Natural, 0) = 1, 'Persona Natural', 'Empresa') AS Tipo_Proveedor,
           COUNT(DISTINCT ped.ID_Pedido) AS Total_Pedidos,
           IFNULL(ROUND(SUM(dc.Cantidad_Ingresada * dc.Precio_Unitario_Compra), 2), 0.00) AS Monto_Comprado_Exacto
    FROM proveedor pr
    LEFT JOIN pedido ped ON pr.ID_Proveedor = ped.ID_Proveedor
    LEFT JOIN compra com ON ped.ID_Pedido = com.ID_Pedido
    LEFT JOIN detalle_compra dc ON com.ID_Compra = dc.ID_Compra
    WHERE (p_filtro IS NULL OR TRIM(p_filtro) = ''
           OR pr.Razon_Social LIKE CONCAT('%', TRIM(p_filtro), '%')
           OR pr.RUC LIKE CONCAT('%', TRIM(p_filtro), '%'))
    GROUP BY pr.ID_Proveedor, pr.Razon_Social, pr.RUC, pr.Telefono, pr.Email, pr.Persona_Natural
    ORDER BY Monto_Comprado_Exacto DESC, pr.ID_Proveedor ASC;
END$$

DROP PROCEDURE IF EXISTS sp_guardar_proveedor$$
CREATE PROCEDURE sp_guardar_proveedor(
    IN p_id_proveedor INT,
    IN p_razon_social VARCHAR(45),
    IN p_ruc VARCHAR(20),
    IN p_telefono VARCHAR(20),
    IN p_email VARCHAR(100),
    IN p_persona_natural TINYINT(1),
    IN p_id_empleado INT
)
BEGIN
    DECLARE v_emp INT;
    SET v_emp = IF(p_id_empleado IS NULL OR p_id_empleado <= 0, 2, p_id_empleado);

    IF TRIM(IFNULL(p_razon_social, '')) = '' OR TRIM(IFNULL(p_ruc, '')) = '' OR TRIM(IFNULL(p_telefono, '')) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Complete razón social, RUC y teléfono del proveedor.';
    END IF;

    IF p_id_proveedor IS NULL OR p_id_proveedor <= 0 THEN
        INSERT INTO proveedor (Email, Telefono, RUC, Razon_Social, ID_Empleado, Persona_Natural)
        VALUES (TRIM(IFNULL(p_email, '')), TRIM(p_telefono), TRIM(p_ruc), TRIM(p_razon_social), v_emp, IFNULL(p_persona_natural, 0));
        SELECT LAST_INSERT_ID() AS ID_Proveedor;
    ELSE
        UPDATE proveedor
        SET Email = TRIM(IFNULL(p_email, '')),
            Telefono = TRIM(p_telefono),
            RUC = TRIM(p_ruc),
            Razon_Social = TRIM(p_razon_social),
            Persona_Natural = IFNULL(p_persona_natural, 0)
        WHERE ID_Proveedor = p_id_proveedor;
        SELECT p_id_proveedor AS ID_Proveedor;
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_listar_compras_abastecimiento$$
CREATE PROCEDURE sp_listar_compras_abastecimiento(
    IN p_id_proveedor INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SET time_zone = '-05:00';
    SELECT com.ID_Compra,
           ped.ID_Pedido,
           DATE_FORMAT(com.Fecha_Ingreso, '%Y-%m-%d %H:%i') AS Fecha_Ingreso,
           pr.Razon_Social AS Proveedor,
           i.Nombre_Insumo AS Insumo,
           IFNULL(est.Nombre_Estado, 'Entregado') AS Estado_Pedido,
           dc.Cantidad_Ingresada,
           dc.Precio_Unitario_Compra,
           ROUND(dc.Cantidad_Ingresada * dc.Precio_Unitario_Compra, 2) AS Subtotal_Exacto,
           IFNULL(DATE_FORMAT(dc.Fecha_Vencimiento, '%Y-%m-%d'), 'No aplica') AS Vencimiento_Lote,
           CASE
               WHEN dc.Fecha_Vencimiento IS NULL THEN 'NO PERECIBLE'
               WHEN DATE(dc.Fecha_Vencimiento) < CURDATE() THEN 'VENCIDO - RETIRAR'
               WHEN DATEDIFF(DATE(dc.Fecha_Vencimiento), CURDATE()) <= 30 THEN 'POR VENCER'
               ELSE 'VIGENTE'
           END AS Estado_Lote
    FROM compra com
    INNER JOIN pedido ped ON com.ID_Pedido = ped.ID_Pedido
    INNER JOIN proveedor pr ON ped.ID_Proveedor = pr.ID_Proveedor
    LEFT JOIN estado est ON ped.ID_Estado = est.ID_Estado
    INNER JOIN detalle_compra dc ON com.ID_Compra = dc.ID_Compra
    LEFT JOIN detalle_pedido dp ON ped.ID_Pedido = dp.ID_Pedido
    LEFT JOIN insumo i ON dp.ID_Insumo = i.ID_Insumo
    WHERE (p_id_proveedor IS NULL OR p_id_proveedor = 0 OR pr.ID_Proveedor = p_id_proveedor)
      AND (p_fecha_desde IS NULL OR DATE(com.Fecha_Ingreso) >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR DATE(com.Fecha_Ingreso) <= p_fecha_hasta)
    ORDER BY com.ID_Compra DESC;
END$$

DROP PROCEDURE IF EXISTS sp_registrar_pedido_y_compra$$
CREATE PROCEDURE sp_registrar_pedido_y_compra(
    IN p_id_proveedor INT,
    IN p_id_insumo INT,
    IN p_cantidad INT,
    IN p_precio_unitario DECIMAL(10,2),
    IN p_fecha_vencimiento DATE,
    IN p_usuario_sesion VARCHAR(45),
    IN p_rol_sesion VARCHAR(45)
)
BEGIN
    DECLARE v_id_pedido INT;
    DECLARE v_id_compra INT;
    DECLARE v_total_exacto DECIMAL(10,2);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET time_zone = '-05:00';

    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cantidad ingresada debe ser mayor a cero.';
    END IF;
    IF p_precio_unitario IS NULL OR p_precio_unitario <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El precio unitario de compra debe ser mayor a cero.';
    END IF;

    SET v_total_exacto = ROUND(p_cantidad * p_precio_unitario, 2);

    START TRANSACTION;
        INSERT IGNORE INTO estado (ID_Estado, Nombre_Estado) VALUES (1, 'Entregado');

        SET @usuario_sesion = IFNULL(p_usuario_sesion, 'log_joel');
        SET @rol_sesion = IFNULL(p_rol_sesion, 'AsistenteLogistico');

        INSERT INTO pedido (ID_Estado, Fecha_Pedido, ID_Proveedor)
        VALUES (1, NOW(), p_id_proveedor);
        SET v_id_pedido = LAST_INSERT_ID();

        INSERT INTO detalle_pedido (pedido_ID_Estado, Cantidad_Solicitada, ID_Insumo, ID_Pedido)
        VALUES (1, p_cantidad, p_id_insumo, v_id_pedido);

        INSERT INTO compra (Monto_Total, Fecha_Ingreso, ID_Pedido)
        VALUES (ROUND(v_total_exacto, 0), NOW(), v_id_pedido);
        SET v_id_compra = LAST_INSERT_ID();

        INSERT INTO detalle_compra (Cantidad_Ingresada, Precio_Unitario_Compra, Fecha_Vencimiento, ID_Compra)
        VALUES (p_cantidad, p_precio_unitario, p_fecha_vencimiento, v_id_compra);

        -- Si el lote trae una fecha de vencimiento vigente posterior, actualiza el insumo perecible
        IF p_fecha_vencimiento IS NOT NULL THEN
            UPDATE insumo
            SET Es_Perecible = 1, F_Vencimiento = p_fecha_vencimiento
            WHERE ID_Insumo = p_id_insumo;
        END IF;
    COMMIT;

    SELECT v_id_compra AS ID_Compra, v_id_pedido AS ID_Pedido, v_total_exacto AS Total_Exacto;
END$$

-- ---------------------------------------------------------------------------------
-- 7.7. MINI-CRM DE CLIENTES Y DESEMPEÑO DE COLABORADORES (C1 & C2 — 0 TABLAS NUEVAS)
-- ---------------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS sp_perfil_cliente_historial$$
CREATE PROCEDURE sp_perfil_cliente_historial(
    IN p_id_cliente INT
)
BEGIN
    DECLARE v_prod_favorito VARCHAR(80) DEFAULT 'Sin compras aún';

    SELECT pr.Nom_Producto INTO v_prod_favorito
    FROM venta v
    INNER JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    INNER JOIN producto pr ON dv.ID_Producto = pr.ID_Producto
    WHERE v.ID_Cliente = p_id_cliente
    GROUP BY pr.ID_Producto, pr.Nom_Producto
    ORDER BY SUM(dv.Cantidad) DESC
    LIMIT 1;

    -- Result-set 1: Resumen Mini-CRM del cliente
    SELECT c.ID_Cliente,
           CONCAT(c.Nombres, ' ', c.Apellido_Paterno, ' ', IFNULL(c.Apellido_Materno, '')) AS Nombre_Completo,
           IFNULL(c.Celular, '') AS Celular,
           COUNT(DISTINCT v.ID_Venta) AS Total_Visitas,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Gasto_Acumulado,
           IF(COUNT(DISTINCT v.ID_Venta) > 0,
              ROUND(IFNULL(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 0.00) / COUNT(DISTINCT v.ID_Venta), 2),
              0.00) AS Ticket_Promedio,
           IFNULL(DATE_FORMAT(MAX(v.Fecha_Hora), '%Y-%m-%d %H:%i'), 'Sin visitas') AS Ultima_Visita,
           v_prod_favorito AS Producto_Favorito
    FROM cliente c
    LEFT JOIN venta v ON c.ID_Cliente = v.ID_Cliente
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE c.ID_Cliente = p_id_cliente
    GROUP BY c.ID_Cliente, Nombre_Completo, c.Celular;

    -- Result-set 2: Últimas compras del cliente
    SELECT v.ID_Venta,
           v.Num_Comprobante,
           DATE_FORMAT(v.Fecha_Hora, '%Y-%m-%d %H:%i') AS Fecha,
           s.Nombre_Suc AS Sede,
           v.Canal_Atencion,
           mp.Nombre_Metodo AS Metodo_Pago,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Total
    FROM venta v
    INNER JOIN empleados e ON v.ID_Empleado = e.ID_Empleado
    INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
    INNER JOIN pago p ON v.ID_Pago = p.ID_Pago
    INNER JOIN metodo_pago mp ON p.ID_Metodo_Pago = mp.ID_Metodo_Pago
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE v.ID_Cliente = p_id_cliente
    GROUP BY v.ID_Venta, v.Num_Comprobante, v.Fecha_Hora, Sede, v.Canal_Atencion, Metodo_Pago
    ORDER BY v.ID_Venta DESC;
END$$

DROP PROCEDURE IF EXISTS sp_reporte_desempeno_empleados$$
CREATE PROCEDURE sp_reporte_desempeno_empleados(
    IN p_id_sucursal INT,
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SELECT e.ID_Empleado,
           CONCAT(e.Nombres, ' ', e.Apellido_Paterno) AS Colaborador,
           s.Nombre_Suc AS Sede,
           COUNT(DISTINCT v.ID_Venta) AS Tickets_Atendidos,
           IFNULL(ROUND(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 2), 0.00) AS Monto_Recaudado,
           IF(COUNT(DISTINCT v.ID_Venta) > 0,
              ROUND(IFNULL(SUM(dv.Cantidad * (dv.Precio_Unitario + IFNULL(dv.Precio_Topping, 0.00))), 0.00) / COUNT(DISTINCT v.ID_Venta), 2),
              0.00) AS Ticket_Promedio
    FROM empleados e
    INNER JOIN surcusal s ON e.ID_Sucursal = s.ID_Surcusal
    LEFT JOIN (
        SELECT v.ID_Venta, v.ID_Empleado
        FROM venta v
        WHERE (p_fecha_desde IS NULL OR DATE(v.Fecha_Hora) >= p_fecha_desde)
          AND (p_fecha_hasta IS NULL OR DATE(v.Fecha_Hora) <= p_fecha_hasta)
    ) v ON e.ID_Empleado = v.ID_Empleado
    LEFT JOIN detalle_venta dv ON v.ID_Venta = dv.ID_Venta
    WHERE e.ID_Rol = 1
      AND (p_id_sucursal IS NULL OR p_id_sucursal = 0 OR e.ID_Sucursal = p_id_sucursal)
    GROUP BY e.ID_Empleado, Colaborador, Sede
    ORDER BY Monto_Recaudado DESC, Tickets_Atendidos DESC;
END$$

DELIMITER ;
