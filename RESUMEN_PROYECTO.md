# Documentación Integral del Proyecto — Sistema de Gestión de Heladería Polo Norte (`proyect_db`)

**Universidad Nacional de Trujillo** — Facultad de Ciencias Físicas y Matemáticas — Escuela Profesional de Ingeniería Informática  
**Experiencia Curricular:** Base de Datos II (Unidad 3 — Laboratorios 11, 12 y 13)  
**Motor de Base de Datos:** MySQL Server (`proyect_db`, `localhost:3306` / despliegue nube Azure MySQL 8.4 LTS)  
**Capa de Aplicación:** Python 3 + `PyMySQL` + **Web `FastAPI` + `Jinja2`** *(con respaldo local de escritorio `tkinter`/`ttk`)*

---

## 1. Arquitectura y Separación Estricta de Ecosistemas (Python vs. MySQL)

El sistema implementa una **arquitectura centrada íntegramente en el motor MySQL (`proyect_db`)**, preservando intacto el diagrama relacional original de **25 tablas base** (23 tablas de negocio + `credenciales_hash` y `bitacora_auditoria`):

- **Ecosistema MySQL (`proyect_db`):** Concentra el **100% de la lógica de negocio**: cifrado criptográfico (`SHA2(..., 256)`), resolución de roles y sedes mediante la vista `vw_credenciales_roles`, blindaje de precios oficiales, cálculo del carrito y vuelto (`sp_calcular_resumen_carrito`), venta atómica ACID con correlativo pesimista `FOR UPDATE` (`sp_registrar_venta_completa`), arqueo de caja multi-fecha por sede (`sp_arqueo_caja_sede` / `sp_arqueo_caja_rango` / `sp_arqueo_caja_resumen`), **8 Stored Procedures del Dashboard de Gerencia**, control sanitario de insumos perecibles (`F_Vencimiento`), gestión de toppings, recetas/escandallos, almacenes, proveedores, compras/lotes, Mini-CRM, productividad del equipo y **11 Disparadores Automáticos (`TRIGGERS`)**.
- **Ecosistema Python ([controlador.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/controlador.py) + [app.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/app.py) + respaldo [interfaz.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/interfaz.py)):** Actúa exclusivamente como **capa visual comercial (sin jerga técnica de back-end)** y pasarela de llamadas mediante `cursor.callproc("sp_...", args)`, con **0 consultas SQL embebidas** y **0 cálculos de negocio** en Python.

### Estructura de Archivos del Proyecto
| Archivo / Ruta | Rol dentro del Proyecto |
| :--- | :--- |
| [AGENTS.md](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/AGENTS.md) | Reglas permanentes del workspace para mantener sincronizado `RESUMEN_PROYECTO.md`, la separación Python–MySQL y la interfaz comercial limpia. |
| [RESUMEN_PROYECTO.md](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/RESUMEN_PROYECTO.md) | Documentación viva y bitácora oficial de cambios confirmados del proyecto. |
| [.gitignore](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/.gitignore) / [.env.example](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/.env.example) | Protección de secretos locales (`.env`, certificados `.pem`/`.crt`) y plantilla de variables de entorno para local y nube. |
| [config.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/config.py) | Carga segura de parámetros MySQL, TLS/SSL y clave de sesión desde variables de entorno (`.env`, sin contraseñas en el código). |
| [conexion.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/conexion.py) | Gestión de conexión (`obtener_conexion`), soporte TLS/SSL cloud, cierre seguro (`cerrar_conexion`) y diagnóstico vía `callproc` (`probar_conexion`). |
| [controlador.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/controlador.py) | Pasarela pura multi-sesión (FastAPI + respaldo Tkinter) que invoca exclusivamente los **74 Procedimientos Almacenados (`sp_*`)** en MySQL con sanitización comercial de errores. |
| [app.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/app.py) | Aplicación Web POS/ERP en **FastAPI + Jinja2** con sesiones firmadas `HttpOnly`, RBAC estricto en servidor, aislamiento multi-sede y exportación CSV. |
| `templates/` (`13` plantillas) | Vistas comerciales con el Sistema de Diseño **Polo Norte**: `login.html`, `pos.html`, `arqueo.html`, `ticket.html` (`80 mm`), `dashboard.html`, `catalogo.html`, `almacen.html`, `clientes.html`, `personal.html`, `historial.html`, `base.html` y parciales de POS (`partials/`). |
| `static/` | Sistema de diseño [polo_norte.css](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/static/css/polo_norte.css), atajos de teclado e interactividad POS [polo_norte.js](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/static/js/polo_norte.js) y emblema oficial `static/img/polo_norte_logo.jpg`. |
| [interfaz.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/interfaz.py) / [main.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/main.py) | Respaldo local de escritorio (`tkinter`/`ttk`) 100% compatible con `controlador.py` y `proyect_db`. |
| [archivos_bd/seguridad_roles_hash.sql](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/archivos_bd/seguridad_roles_hash.sql) | Script DDL/DML idempotente y portable (`DATABASE()`): tablas `credenciales_hash` y `bitacora_auditoria`, vista `vw_credenciales_roles`, **11 Triggers** y **74 Stored Procedures**. |

---

## 2. Inventario Real de Base de Datos (`proyect_db`)

- **25 Tablas Base (todas con `PRIMARY KEY` explícita, 0 tablas nuevas):**
  - **23 tablas del diagrama de negocio:** `administradores`, `almacen`, `cliente`, `compra`, `detalle_compra`, `detalle_pedido`, `detalle_receta`, `detalle_venta`, `empleados`, `estado`, `insumo`, `metodo_pago`, `pago`, `pedido`, `producto`, `producto_topping`, `proveedor`, `receta`, `rol`, `surcusal`, `topping`, `unidadmedida`, `venta`.
  - **2 tablas de seguridad y trazabilidad:** `credenciales_hash` y `bitacora_auditoria`.
  - **Columnas de `detalle_venta`:** `ID_Detalle_Venta`, `ID_Producto`, `Cantidad`, `Precio_Unitario`, `ID_Topping`, `Precio_Topping`, `ID_Venta`.
- **1 Vista (`VIEW`):** `vw_credenciales_roles` (resuelve en tiempo real rol, persona asignada y sucursal activa).
- **3 Sucursales (`surcusal`):**
  1. `1 - Sede Quintanas` (`Urb. Las Quintanas Mz R Lote 14, Trujillo`)
  2. `2 - Sede UPAO` (`Av. America Sur 3145 (Frente a UPAO), Trujillo`)
  3. `3 - Sede Mall Plaza` (`Av. Mansiche s/n C.C. Mall Plaza Nivel 1, Trujillo`)

---

## 3. Modelo de Acceso: 3 Cuentas Back-Office vs. 3 Cajas Diarias por Sede

| Cuenta (`credenciales_hash`) | Asignación (`vw_credenciales_roles`) | Rol Resuelto | Sede Vinculada | Seguridad | Módulos Visibles |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `admin` | Gerencia General (Back-Office) | `Administrador` | Todas las Sedes (Central) | `SHA-256` (bloqueo al 3er intento) | Panel de Gerencia, POS, Arqueo, Clientes, Catálogo/Toppings/Recetas, Almacén/Proveedores/Compras, Personal/Accesos e Historial |
| `rrhh_etel` | Etel Quispe (`ID_Empleado = 1`) | `RecursosHumanos` | Sede Quintanas | `SHA-256` (bloqueo al 3er intento) | Personal, Sedes y Productividad (sin bajas ni gestión de accesos) |
| `log_joel` | Joel Mendoza (`ID_Empleado = 2`) | `AsistenteLogistico` | Sede Quintanas | `SHA-256` (bloqueo al 3er intento) | Catálogo, Toppings, Recetas, Almacén, Proveedores y Compras (sin eliminaciones) |
| `caja_quintanas` | Caja Diaria — Sede Quintanas | `Multifuncional` | `1 - Sede Quintanas` | *(Ingreso directo 1 clic)* | Punto de Venta, Arqueo, Tickets propios y Clientes |
| `caja_upao` | Caja Diaria — Sede UPAO | `Multifuncional` | `2 - Sede UPAO` | *(Ingreso directo 1 clic)* | Punto de Venta, Arqueo, Tickets propios y Clientes |
| `caja_mall` | Caja Diaria — Sede Mall Plaza | `Multifuncional` | `3 - Sede Mall Plaza` | *(Ingreso directo 1 clic)* | Punto de Venta, Arqueo, Tickets propios y Clientes |

- **Aislamiento Estricto por Sede:** Tanto en el servidor FastAPI como dentro de `sp_registrar_venta_completa`, las Cajas Diarias solo pueden operar con colaboradores de su propia sucursal, generar correlativos de su serie (`B001`/`B002`/`B003`), consultar arqueos propios y visualizar únicamente comprobantes de su sede.

---

## 4. Catálogo de los 74 Procedimientos Almacenados (`STORED PROCEDURES`)

1. **Seguridad, Sesiones y Catálogos Comerciales (8):** `sp_consultar_jerarquia_usuario`, `sp_consultar_jerarquia_usuario_web`, `sp_validar_login`, `sp_asignar_credencial_empleado`, `sp_listar_credenciales`, `sp_reactivar_cuenta`, `sp_fijar_contexto_auditoria`, `sp_catalogo_roles`.
2. **Clientes y Mini-CRM (5):** `sp_listar_clientes`, `sp_insertar_cliente`, `sp_actualizar_cliente`, `sp_eliminar_cliente`, `sp_perfil_cliente_historial`.
3. **Productos, Toppings y Recetas (14):** `sp_listar_productos`, `sp_insertar_producto`, `sp_actualizar_producto`, `sp_eliminar_producto`, `sp_listar_toppings`, `sp_insertar_topping`, `sp_actualizar_topping`, `sp_eliminar_topping`, `sp_listar_matriz_producto_topping`, `sp_gestionar_producto_topping`, `sp_listar_recetas`, `sp_obtener_detalle_receta`, `sp_guardar_detalle_receta`, `sp_eliminar_detalle_receta`.
4. **Insumos, Control Sanitario, Almacenes, Proveedores y Compras (12):** `sp_listar_unidades_medida`, `sp_listar_insumos`, `sp_resumen_sanitario_insumos`, `sp_insertar_insumo`, `sp_actualizar_insumo`, `sp_eliminar_insumo`, `sp_listar_almacenes_sucursales`, `sp_actualizar_almacen_sucursal`, `sp_listar_proveedores`, `sp_guardar_proveedor`, `sp_listar_compras_abastecimiento`, `sp_registrar_pedido_y_compra`.
5. **Punto de Venta, Carrito ACID, Tickets y Arqueo (19):** `sp_listar_ventas`, `sp_buscar_ventas`, `sp_obtener_detalle_venta`, `sp_catalogo_clientes`, `sp_catalogo_empleados`, `sp_catalogo_empleados_sede`, `sp_catalogo_metodos_pago`, `sp_catalogo_productos`, `sp_catalogo_toppings_producto`, `sp_calcular_linea_carrito`, `sp_calcular_resumen_carrito`, `sp_generar_correlativo_comprobante`, `sp_crear_cabecera_venta`, `sp_insertar_detalle_carrito` *(precios blindados en BD)*, `sp_registrar_venta_completa` *(transacción ACID + `FOR UPDATE`)*, `sp_eliminar_venta` *(transaccional)*, `sp_arqueo_caja_sede` *(corregido)*, `sp_arqueo_caja_rango`, `sp_arqueo_caja_resumen`.
6. **Dashboard Ejecutivo de Gerencia General (8):** `sp_dashboard_kpis_generales`, `sp_dashboard_ventas_por_sede`, `sp_dashboard_ventas_por_metodo_pago`, `sp_dashboard_top_productos`, `sp_dashboard_top_toppings`, `sp_dashboard_ventas_por_canal`, `sp_dashboard_tendencia_diaria`, `sp_dashboard_alertas_operativas`.
7. **Personal, Sedes y Productividad — RRHH (6):** `sp_listar_empleados`, `sp_listar_sucursales`, `sp_insertar_empleado`, `sp_actualizar_empleado`, `sp_eliminar_empleado`, `sp_reporte_desempeno_empleados`.
8. **Bitácora de Auditoría (2):** `sp_listar_bitacora`, `sp_listar_bitacora_comercial` *(traducción 100% comercial sin jerga SQL)*.

---

## 5. Disparadores Automáticos (`TRIGGERS`) en MySQL — 11 Activos

1. `trg_auditoria_producto_insert` (`AFTER INSERT ON producto`)
2. `trg_auditoria_producto_update` (`AFTER UPDATE ON producto`)
3. `trg_auditoria_producto_delete` (`AFTER DELETE ON producto`)
4. `trg_auditoria_venta_insert` (`AFTER INSERT ON venta`)
5. `trg_auditoria_insumo_insert` (`AFTER INSERT ON insumo`)
6. `trg_auditoria_insumo_update` (`AFTER UPDATE ON insumo`)
7. `trg_auditoria_insumo_delete` (`AFTER DELETE ON insumo`)
8. `trg_auditoria_empleado_update` (`AFTER UPDATE ON empleados`)
9. `trg_auditoria_empleado_delete` (`AFTER DELETE ON empleados`)
10. `trg_auditoria_topping_update` (`AFTER UPDATE ON topping`)
11. `trg_auditoria_compra_insert` (`AFTER INSERT ON compra`)

---

## 6. Estado de Avance por Fases y Herramientas del Entorno

| Fase | Estado | Resumen de lo Completado |
| :--- | :---: | :--- |
| **Fase 0 — Decisiones Clave** | ✅ **Confirmada** | Arquitectura Web **FastAPI + Jinja2** (respaldo local Tkinter), **Azure Database for MySQL – Flexible Server** (`Azure for Students`, conexión `az login` verificada en estado `Enabled`), hosting **Render Free** (\$0 permanente). Instalados **Azure CLI (`2.93.0`)** y **GitHub CLI (`2.105.0`)**. |
| **Fase 1 — Benchmark y MoSCoW** | ✅ **Aprobada** | Comparativa con fuentes oficiales de 7 líderes POS/ERP (Square, Toast, Lightspeed, Loyverse, Odoo POS, Shopify POS, SAP Business One) y matriz **MoSCoW** aprobada en **Alcance B — Integral** (`M1–M7` + `S1–S4` + `C1–C2`, **0 tablas nuevas**). |
| **Fase 2 — Rediseño, SPs y Web App** | ✅ **Completada y verificada** | Sistema de Diseño **Polo Norte**, emblema oficial `static/img/polo_norte_logo.jpg`, prototipo interactivo de 6 pantallas, ampliación a **74 SPs y 11 Triggers** en `proyect_db`, Web App completa (`app.py`, 13 plantillas, `controlador.py` multi-sesión, `.env` sin contraseñas en `config.py`). Verificada con `py_compile`, pruebas integrales (`TestClient`), inspección en navegador y auditoría independiente `AGENTS.md` (incluyendo los 6 ajustes de endurecimiento: aislamiento de sucursal en `sp_registrar_venta_completa`, bloqueo IDOR en tickets, normalización comercial de registros históricos en `/historial`, sanitización de `/health`, XSS-safe en `polo_norte.js` y limpieza de comentarios HTML). |
| **Fase 3 — Despliegue Cloud y GitHub** | ⏳ **Pendiente** | Lista para ejecutarse tras confirmación de Fase 2 (ver detalle abajo). |
| **Fase 4 — Plan de Cierre y Sustentación** | ⏳ **Pendiente** | Roadmap semanal, plan formal de pruebas y guion de demo de 5 minutos (ver detalle abajo). |

---

## 7. Pendientes por Completar

### 7.1. Fase 3 — Despliegue en la Nube, GitHub y Entrega al Profesor
- [ ] **Dump reproducible desde `proyect_db`:** Exportar esquema + datos + 11 Triggers + 74 SPs directamente desde el esquema activo `proyect_db` (sin depender de `heladeriaV2.sql`), sanitizado sin cláusulas `DEFINER` y verificado para MySQL 8.4 LTS.
- [ ] **Provisionar Azure Database for MySQL – Flexible Server:** Crear instancia `Standard_B1ms` (12 meses gratis en **Azure for Students** ya conectado), habilitar firewall/TLS (`DigiCertGlobalRootG2`), configurar zona horaria `-05:00` (Perú) e importar el dump de `proyect_db`.
- [ ] **Usuario de solo lectura para el profesor:** Crear cuenta dedicada en Azure MySQL con privilegios mínimos (`SELECT`, `SHOW VIEW`, `SHOW_ROUTINE`) y verificar que rechace escrituras (`INSERT`/`UPDATE`/`DELETE`).
- [ ] **Instalar Git en Windows y publicar repositorio en GitHub:** Completar instalación de `Git.Git` (requirió elevación de administrador en el intento previo), inicializar repositorio, generar `requirements.txt`, `render.yaml` y `README.md` profesional (arquitectura, diagrama ER, instrucciones local/nube y cuentas de prueba) y subir a GitHub validando que `.env` y respaldos locales queden excluidos por `.gitignore`.
- [ ] **Desplegar Web App en Render Free:** Crear cuenta/servicio Web en Render (región Virginia/Ohio, plan Free \$0), configurar variables de entorno (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL`, `SESSION_SECRET`, `APP_ENV=production`) apuntando a Azure MySQL y verificar la URL HTTPS pública en vivo.

### 7.2. Fase 4 — Plan de Cierre, Pruebas Formales y Sustentación
- [ ] **Definir fecha de entrega / sustentación** para calibrar el roadmap semanal con hitos, criterios de aceptación y matriz de riesgos.
- [ ] **Ejecutar y documentar plan de pruebas final** en producción (SPs, 11 Triggers, bloqueo exacto al 3er intento + reactivación, transacción ACID con rollback, aislamiento por sede, arqueo y Dashboard).
- [ ] **Guion de demostración de 5 minutos** y **checklist final de entrega** para el docente.

### 7.3. Mejoras del Benchmark Bloqueadas por Integridad del Diagrama *(Requieren aprobación explícita)*
No implementadas para preservar intactas las **25 tablas base** de `proyect_db` (`AGENTS.md` Regla 2):
- `S5` Control formal de turnos de caja (fondo inicial, retiros y conteo ciego Esperado vs. Contado).
- `S6` Inventario perpetuo (Kárdex por insumo–sucursal con descarga automática por receta).
- `C3` Múltiples toppings por una misma línea de venta (`detalle_venta_topping`).
- `C4` Pagos divididos / mixtos en un solo comprobante.
- `C5` Descuentos, cupones o puntos de fidelidad.
- `C6` Pantalla de preparación en barra (KDS) y seguimiento de despacho Delivery.

---

## 8. Registro de Cambios Confirmados

- **2026-11-18:** Rediseño de autenticación en [seguridad_roles_hash.sql](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/archivos_bd/seguridad_roles_hash.sql), [controlador.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/controlador.py) e [interfaz.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/interfaz.py): segregación entre 3 cuentas Back-Office (`SHA-256`) y 3 Cajas Diarias por Sede sin contraseña; precio oficial bloqueado (`readonly`); integración de *toppings*, correlativo automático, arqueo por sede, estado sanitario e interfaz comercial limpia.
- **2026-11-20:** Eliminación completa del módulo de descuentos para conservar intacto el diagrama original de 25 tablas; creación de [AGENTS.md](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/AGENTS.md) y sincronización inicial de `RESUMEN_PROYECTO.md`.
- **2026-11-20 (Fase 0 + Fase 1 + Fase 2 confirmadas):**
  - **MySQL (`proyect_db`, [seguridad_roles_hash.sql](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/archivos_bd/seguridad_roles_hash.sql)):** Ampliación de **37 a 74 Stored Procedures** y de **5 a 11 Triggers** preservando estrictamente las **25 tablas base** (0 tablas nuevas). Corrección del bug en `sp_arqueo_caja_sede` (ahora muestra los 4 medios de pago incluso en `S/ 0.00`), blindaje de precios oficiales en `sp_insertar_detalle_carrito`, emisión atómica ACID (`sp_registrar_venta_completa` con `FOR UPDATE` y validación de sucursal), cálculo de carrito/vuelto en MySQL (`sp_calcular_resumen_carrito`), 8 SPs de Dashboard de Gerencia, activación completa de Toppings, Recetas/Escandallos, Almacenes por sede, Proveedores, Compras/Lotes, Mini-CRM de clientes, productividad por colaborador y bitácora comercial normalizada (`sp_listar_bitacora_comercial`). Portabilidad garantizada (`DATABASE()`, `COLLATE utf8mb4_bin`, `CREATE TABLE IF NOT EXISTS credenciales_hash`).
  - **Seguridad y Conexión ([config.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/config.py), [conexion.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/conexion.py), [.gitignore](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/.gitignore), [.env.example](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/.env.example)):** Contraseña removida de `config.py` y migrada a `.env`; soporte TLS/SSL listo para Azure MySQL; eliminación de toda consulta SQL directa en `conexion.py`.
  - **Pasarela Multi-Sesión y Web App POS/ERP ([controlador.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/controlador.py), [app.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/app.py), `templates/`, `static/`):** Construcción de la interfaz web moderna con **Sistema de Diseño Polo Norte** (Login Dual, POS rápido con cuadrícula táctil, atajos `1–7`/`F9`, toppings en 1 clic, ticket térmico `80 mm`, Arqueo por sede, Dashboard de Gerencia, Catálogo/Toppings/Recetas, Almacén/Proveedores/Compras, Clientes Mini-CRM, Personal/Accesos e Historial comercial con exportación CSV), manteniendo 100% de compatibilidad con el respaldo local [interfaz.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/interfaz.py). Verificado con `py_compile`, pruebas integrales `TestClient`, auditoría independiente `AGENTS.md` y pruebas visuales en navegador.
- **2026-11-24:** Actualización integral de [RESUMEN_PROYECTO.md](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/RESUMEN_PROYECTO.md) incorporando el estado consolidado hasta el cierre de Fase 2 (incluyendo herramientas instaladas, conexión de Azure for Students y los 6 ajustes de auditoría) y el listado detallado de tareas pendientes para **Fase 3** (despliegue en Azure MySQL + GitHub + Render Free), **Fase 4** (cierre, pruebas y guion de demo) e ítems bloqueados que requieren aprobación de diagrama.
- **2026-11-24 (Endurecimiento Integral Pre-Nube — Auditoría QA 100% Aprobada):**
  - **MySQL (`proyect_db`, [seguridad_roles_hash.sql](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/archivos_bd/seguridad_roles_hash.sql)):** Eliminación de `USE proyect_db` y bloque residual de descuentos; vista `vw_credenciales_roles` convertida a `SQL SECURITY INVOKER` con colación homogénea `utf8mb4_general_ci`; índice único `uk_venta_num_comprobante` en `venta`; trigger `trg_auditoria_empleado_update` optimizado para auditar solo cambios reales (y asignación inicial idempotente sin ruido); zona horaria `-05:00` (Perú) reforzada en SPs de operación, sanidad y dashboard; normalización comercial completa en `sp_listar_bitacora_comercial` (categorías `ACCESO`/`ALTA`/`CAMBIO`/`BAJA`/`SEGURIDAD` y depuración de registros históricos en `bitacora_auditoria`); validaciones CRUD de borde (`Precio_Venta > 0`, campos obligatorios no vacíos, limpieza de cabecera `receta` huérfana y validación de rol operativo `ID_Rol = 1` en `sp_registrar_venta_completa`).
  - **Backend Web y Configuración ([config.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/config.py), [controlador.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/controlador.py), [app.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/app.py)):** Validación obligatoria de `SESSION_SECRET` en `APP_ENV=production` y parseo resiliente de `DB_PORT`; protección anti-CSRF por verificación estricta de `Origin`/`Referer`/`Sec-Fetch-Site` en mutaciones; minimización de `GET /api/login/estado`; zona horaria `-05:00` en filtros de arqueo; exportación CSV con BOM UTF-8 y encabezados comerciales; `_rollback_seguro` y validación de conversiones numéricas en `controlador.py`.
  - **Frontend Web y Respaldo Escritorio (`templates/`, [polo_norte.js](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/static/js/polo_norte.js), [polo_norte.css](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/static/css/polo_norte.css), [interfaz.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/interfaz.py)):** Eliminación de los 27 comentarios HTML (`<!-- -->` -> `{# #}`), reemplazo de `onsubmit="return confirm(...)"` por `data-confirm` centralizado y de `.innerHTML` por `DOMParser`/`replaceChildren`; bloqueo de `Enter` en efectivo recibido para recalcular vuelto sin cobrar accidentalmente; limpieza de vuelto al cambiar medio de pago y bloqueo de atajos con modales abiertos o teclas modificadoras; reglas `@page` `80 mm` y clases responsivas `.pn-split-main`/`.pn-split-aside`/`.pn-receta-form-grid`; alineación completa de [interfaz.py](file:///c:/Users/LucianoMejia/Desktop/3%20UNIDAD%20DATA%20BASE/interfaz.py) con `AGENTS.md` Reglas 2 y 4 (cálculos delegados a MySQL, emisión atómica `registrar_venta_completa_bd`, bitácora comercial y retiro de claves en texto plano). Verificado con `py_compile`, ejecución real en `proyect_db` (`25` tablas, `1` vista, `74` SPs, `11` triggers) y batería E2E integral (`14/14` suites PASS con reversión exacta de datos).
