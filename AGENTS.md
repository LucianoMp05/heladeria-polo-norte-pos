# Reglas del Proyecto — Sistema de Gestión de Heladería Polo Norte (`proyect_db`)

Estas reglas se aplican automáticamente a cualquier tarea o conversación dentro de la carpeta `3 UNIDAD DATA BASE`.

## 1. Actualización Obligatoria de `RESUMEN_PROYECTO.md`
- **Solo tras confirmación del usuario:** Cada vez que el usuario confirme una modificación, nueva funcionalidad, corrección o cambio estructural (en MySQL, Python, interfaz o flujo de negocio) y esta se implemente, actualizar obligatoriamente `RESUMEN_PROYECTO.md` antes de finalizar la respuesta.
- **Qué registrar en `RESUMEN_PROYECTO.md`:**
  - Mantener actualizadas las secciones afectadas (tablas, vistas, triggers, procedimientos almacenados, cuentas/roles y archivos del proyecto).
  - Añadir una entrada fechada en la sección **Registro de Cambios Confirmados** indicando qué se implementó o eliminó y qué archivos fueron modificados.
- **Cuándo NO modificar `RESUMEN_PROYECTO.md`:** No actualizar el documento cuando el usuario solo solicite estructurar, analizar, redactar borradores en LaTeX o evaluar propuestas que todavía no hayan sido confirmadas para implementación.

## 2. Separación Estricta de Ecosistemas (Python vs. MySQL)
- **Motor MySQL (`proyect_db` en `localhost:3306`):** Concentra el 100% de la lógica de negocio, cifrado (`SHA2(..., 256)`), vistas (`vw_credenciales_roles`), cálculos de importes y subtotales, correlativos automáticos, arqueo de caja por sede, evaluación de vencimientos (`F_Vencimiento`), transacciones ACID y auditoría mediante Stored Procedures (`sp_*`) y Triggers.
- **Cliente Python (`controlador.py`, `interfaz.py`, `main.py`):** Actúa únicamente como capa visual (`tkinter`/`ttk`) y pasarela de invocación vía `cursor.callproc("sp_...", args)`. **No escribir consultas SQL directas ni fórmulas de cálculo de negocio en el código Python.**
- **Integridad del Diagrama Relacional:** No crear nuevas tablas de negocio (como `descuento`) sin confirmación explícita del usuario, para preservar el diagrama Entidad-Relación y Relacional original de la base de datos `proyect_db` (23 tablas de negocio + `credenciales_hash` y `bitacora_auditoria`).

## 3. Reglas de Seguridad y Acceso (Back-Office vs. Cajas Diarias por Sede)
- Solo los **3 perfiles de Back-Office** (`Administrador`, `RecursosHumanos`, `AsistenteLogistico`) poseen cuentas con contraseña `SHA-256` y bloqueo automático al 3er intento fallido.
- Los trabajadores **Multifuncionales** no usan cuentas individuales; operan mediante las **3 Cajas Diarias por Sede** (`caja_quintanas`, `caja_upao`, `caja_mall` con `Requiere_Password = 0`), filtrando automáticamente el personal de su sucursal (`surcusal`).

## 4. Diseño de Interfaz Comercial Limpia (`interfaz.py`)
- Mantener la interfaz gráfica 100% orientada al lenguaje comercial de **Heladería Polo Norte**.
- **No mostrar jerga técnica de back-end ni de base de datos** en etiquetas, botones, pestañas o cuadros de diálogo (evitar `sp_*`, `CALL`, `CRUD`, `ACID`, `Combobox`, `Entry`, `Treeview`, `Triggers` o nombres de tablas SQL).
- En el Punto de Venta, mantener el `Precio Base (S/)` como **solo lectura (`readonly`)** y mostrar el precio oficial junto al nombre del producto en el desplegable (`[S/ X.XX]`).

## 5. Verificación Antes de Dar por Terminado un Cambio
- Tras modificar `archivos_bd/seguridad_roles_hash.sql`, ejecutarlo en MySQL `proyect_db` con `--default-character-set=utf8mb4` y comprobar los objetos activos (`SHOW TRIGGERS`, `SHOW PROCEDURE STATUS`, `DESCRIBE`).
- Tras modificar archivos `.py`, compilar con `py_compile` y probar las invocaciones reales contra `proyect_db` antes de responder al usuario.
