# controlador.py
# Pasarela de enlace pura Python (PyMySQL) -> Procedimientos Almacenados en MySQL (proyect_db)
# Separación estricta de ecosistemas: Python NO contiene consultas SQL ni cálculos de negocio;
# delega el 100% de la lógica al motor MySQL mediante `cursor.callproc("sp_*", args)`.
# Compatible tanto con la Web App multiusuario (FastAPI) como con el respaldo local (Tkinter).

import json
import sys
sys.dont_write_bytecode = True

from pymysql.err import MySQLError as Error
from conexion import obtener_conexion, cerrar_conexion

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# =====================================================================
# 0. SESIÓN ACTIVA (RESPALDO LOCAL) Y HELPERS MULTI-SESIÓN
# =====================================================================

SESION_ACTIVA = {
    "usuario": "admin",
    "rol": "Administrador",
    "id_sucursal": None,
    "nombre_sucursal": "Todas las Sedes (Central)",
    "persona": "Gerencia General"
}


def establecer_sesion_activa(usuario: str, rol: str, id_sucursal=None, nombre_sucursal=None, persona=None):
    """Mantiene en memoria el contexto de sesión para el cliente de escritorio local."""
    SESION_ACTIVA["usuario"] = usuario
    SESION_ACTIVA["rol"] = rol
    SESION_ACTIVA["id_sucursal"] = int(id_sucursal) if id_sucursal is not None else None
    SESION_ACTIVA["nombre_sucursal"] = nombre_sucursal or "Todas las Sedes (Central)"
    SESION_ACTIVA["persona"] = persona or usuario


def obtener_sesion_activa():
    return dict(SESION_ACTIVA)


def _resolver_sesion(sesion=None):
    """Retorna el contexto de sesión explícito (FastAPI) o el global (Tkinter)."""
    return sesion if sesion is not None else SESION_ACTIVA


def _mensaje_error_comercial(exc, fallback="No se pudo completar la operación solicitada."):
    """
    Traduce errores de MySQL a mensajes comerciales limpios sin exponer nombres de tablas
    ni jerga técnica. Los errores de negocio lanzados por MySQL (errno 1644 / SIGNAL 45000)
    ya vienen redactados en lenguaje comercial.
    """
    if isinstance(exc, Error) and exc.args:
        codigo = exc.args[0]
        detalle = str(exc.args[1]) if len(exc.args) > 1 else ""
        if codigo == 1644 and detalle:
            return detalle
        if codigo == 1062:
            return "Ya existe un registro con ese dato único (código, usuario, RUC o teléfono duplicado)."
        if codigo == 1451:
            return "No se puede retirar este registro porque tiene movimientos o historial asociado."
        if codigo == 1406:
            return "Uno de los campos excede la longitud máxima permitida."
    print(f"[ERROR CONTROLADOR]: {exc}")
    return fallback


def _leer_todos_resultsets(cursor):
    """Lee todos los conjuntos de resultados devueltos por un Stored Procedure."""
    conjuntos = []
    if cursor.description is not None:
        conjuntos.append(cursor.fetchall())
    while cursor.nextset():
        if cursor.description is not None:
            conjuntos.append(cursor.fetchall())
    return conjuntos


def _invocar_sp_lectura(sp_name, args=(), multi=False):
    """Invoca un SP de consulta pura vía cursor.callproc y retorna filas o lista de result sets."""
    conexion = obtener_conexion()
    if not conexion:
        return [] if not multi else []
    cursor = None
    try:
        cursor = conexion.cursor()
        cursor.callproc(sp_name, args)
        if multi:
            return _leer_todos_resultsets(cursor)
        return cursor.fetchall()
    except Error as e:
        print(f"[ERROR {sp_name}]: {e}")
        return []
    finally:
        cerrar_conexion(conexion, cursor)


def _rollback_seguro(conexion):
    """Revierte la transacción activa sin propagar errores si la conexión cayó."""
    try:
        if conexion is not None and conexion.open:
            conexion.rollback()
    except Error:
        pass


def _invocar_sp_escritura(sp_name, args=(), sesion=None, fijar_auditoria=False, fallback="No se pudo guardar el cambio."):
    """Invoca un SP transaccional con commit/rollback y contexto opcional de auditoría."""
    conexion = obtener_conexion()
    if not conexion:
        return False, None, "Sin conexión con el sistema."
    cursor = None
    try:
        cursor = conexion.cursor()
        if fijar_auditoria:
            ctx = _resolver_sesion(sesion)
            cursor.callproc("sp_fijar_contexto_auditoria", (ctx["usuario"], ctx["rol"]))
        cursor.callproc(sp_name, args)
        conjuntos = _leer_todos_resultsets(cursor)
        conexion.commit()
        return True, conjuntos, "Operación completada correctamente."
    except (Error, ValueError, TypeError) as e:
        _rollback_seguro(conexion)
        return False, None, _mensaje_error_comercial(e, fallback)
    finally:
        cerrar_conexion(conexion, cursor)


# =====================================================================
# 1. AUTENTICACIÓN, SEGURIDAD Y CREDENCIALES
# =====================================================================

def consultar_info_usuario(usuario):
    """Invoca `sp_consultar_jerarquia_usuario` (compatible con Tkinter — 9 columnas)."""
    if not usuario or not usuario.strip():
        return None
    filas = _invocar_sp_lectura("sp_consultar_jerarquia_usuario", (usuario.strip(),))
    return filas[0] if filas else None


def consultar_info_usuario_web(usuario):
    """Invoca `sp_consultar_jerarquia_usuario_web` (incluye Área Comercial e Intentos Restantes)."""
    if not usuario or not usuario.strip():
        return None
    filas = _invocar_sp_lectura("sp_consultar_jerarquia_usuario_web", (usuario.strip(),))
    if not filas:
        return None
    r = filas[0]
    return {
        "id_credencial": r[0],
        "usuario": r[1],
        "requiere_password": bool(int(r[2])),
        "rol": r[3],
        "area_comercial": r[4],
        "intentos_fallidos": int(r[5]),
        "intentos_restantes": int(r[6]),
        "estado": r[7],
        "persona": r[8],
        "id_sucursal": int(r[9]) if r[9] is not None else None,
        "nombre_sucursal": r[10],
    }


def validar_login_web(usuario, password=""):
    """
    Invoca `sp_validar_login` sin mutar estado global (seguro para FastAPI multiusuario).
    Retorna dict con {exito, usuario, rol, mensaje, id_sucursal, nombre_sucursal, persona}.
    """
    usuario_limpio = usuario.strip() if usuario else ""
    if not usuario_limpio:
        return {"exito": False, "mensaje": "Seleccione o ingrese una cuenta de acceso."}

    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_validar_login",
        (usuario_limpio, password or ""),
        fallback="No se pudo completar el inicio de sesión."
    )
    if not ok or not conjuntos or not conjuntos[0]:
        return {"exito": False, "mensaje": msg}

    exito, user_bd, rango_rol, mensaje, id_suc, nom_suc, persona = conjuntos[0][0]
    return {
        "exito": bool(int(exito)),
        "usuario": user_bd,
        "rol": rango_rol,
        "mensaje": mensaje,
        "id_sucursal": int(id_suc) if id_suc is not None else None,
        "nombre_sucursal": nom_suc or "Todas las Sedes (Central)",
        "persona": persona or user_bd,
    }


def validar_login(usuario, password=""):
    """Wrapper compatible con el cliente de escritorio local (Tkinter)."""
    res = validar_login_web(usuario, password)
    if res.get("exito") and res.get("usuario") and res.get("rol"):
        establecer_sesion_activa(
            res["usuario"], res["rol"], res["id_sucursal"], res["nombre_sucursal"], res["persona"]
        )
    return res.get("exito", False), res.get("usuario"), res.get("rol"), res.get("mensaje", "")


def asignar_credencial_empleado(id_empleado, usuario, password="", confirmar_password="", sesion=None):
    try:
        emp_val = int(id_empleado)
    except (ValueError, TypeError):
        return False, "Seleccione un colaborador válido."
    usuario_limpio = usuario.strip() if usuario else ""
    if len(usuario_limpio) < 3:
        return False, "El nombre de usuario debe contener al menos 3 caracteres."
    if (password or confirmar_password) and password != confirmar_password:
        return False, "La contraseña y su confirmación no coinciden."

    ctx = _resolver_sesion(sesion)
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_asignar_credencial_empleado",
        (emp_val, usuario_limpio, password or "", ctx["usuario"]),
        fallback="No se pudo asignar el acceso administrativo."
    )
    if not ok:
        return False, msg
    if conjuntos and conjuntos[0]:
        exito, mensaje = conjuntos[0][0]
        return bool(int(exito)), mensaje
    return False, "No se recibió confirmación del servidor."


def listar_usuarios_credenciales():
    return _invocar_sp_lectura("sp_listar_credenciales")


def restablecer_bloqueo_usuario(usuario, sesion=None):
    ctx = _resolver_sesion(sesion)
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_reactivar_cuenta",
        (usuario.strip(), ctx["usuario"]),
        fallback="No se pudo reactivar la cuenta seleccionada."
    )
    if not ok:
        return False, msg
    if conjuntos and conjuntos[0]:
        return bool(int(conjuntos[0][0][0])), conjuntos[0][0][1]
    return True, f"El acceso de '{usuario}' ha sido restablecido."


# =====================================================================
# 2. MÓDULO DE CLIENTES Y MINI-CRM
# =====================================================================

def listar_clientes(filtro=""):
    return _invocar_sp_lectura("sp_listar_clientes", (filtro.strip() if filtro else "",))


def insertar_cliente(nombres, ap_paterno, ap_materno, celular):
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_insertar_cliente",
        (nombres, ap_paterno, ap_materno, celular),
        fallback="No se pudo registrar al cliente. Verifique los datos ingresados."
    )
    if not ok:
        return False, msg
    id_nuevo = conjuntos[0][0][0] if conjuntos and conjuntos[0] else ""
    return True, f"Cliente registrado correctamente (Código #{id_nuevo})."


def insertar_cliente_con_id(nombres, ap_paterno, ap_materno, celular):
    """Alta rápida inline en POS retornando (ok, id_nuevo, mensaje)."""
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_insertar_cliente",
        (nombres, ap_paterno, ap_materno, celular),
        fallback="No se pudo registrar al cliente. Verifique el celular (máx. 9 dígitos)."
    )
    if not ok:
        return False, None, msg
    id_nuevo = int(conjuntos[0][0][0]) if conjuntos and conjuntos[0] else None
    return True, id_nuevo, f"Cliente registrado correctamente (Código #{id_nuevo})."


def actualizar_cliente(id_cliente, nombres, ap_paterno, ap_materno, celular):
    try:
        cli_val = int(id_cliente)
    except (ValueError, TypeError):
        return False, "Código de cliente no válido."
    ok, _, msg = _invocar_sp_escritura(
        "sp_actualizar_cliente",
        (cli_val, nombres, ap_paterno, ap_materno, celular),
        fallback="No se pudo actualizar al cliente."
    )
    return (True, f"Datos del cliente #{cli_val} actualizados correctamente.") if ok else (False, msg)


def eliminar_cliente(id_cliente):
    try:
        cli_val = int(id_cliente)
    except (ValueError, TypeError):
        return False, "Código de cliente no válido."
    ok, _, msg = _invocar_sp_escritura(
        "sp_eliminar_cliente",
        (cli_val,),
        fallback="No se puede eliminar este cliente porque cuenta con compras registradas."
    )
    return (True, f"El cliente #{cli_val} fue retirado del directorio.") if ok else (False, msg)


def perfil_cliente_historial(id_cliente):
    """Invoca `sp_perfil_cliente_historial` -> (resumen_fila, lista_ventas)."""
    conjuntos = _invocar_sp_lectura("sp_perfil_cliente_historial", (int(id_cliente),), multi=True)
    resumen = conjuntos[0][0] if len(conjuntos) > 0 and conjuntos[0] else None
    ventas = conjuntos[1] if len(conjuntos) > 1 else []
    return resumen, ventas


# =====================================================================
# 3. MÓDULO DE CATÁLOGO DE PRODUCTOS, TOPPINGS Y RECETAS
# =====================================================================

def listar_productos(filtro=""):
    return _invocar_sp_lectura("sp_listar_productos", (filtro.strip() if filtro else "",))


def insertar_producto(nom_producto, descripcion, precio_venta, sesion=None):
    try:
        precio_val = float(precio_venta)
    except (ValueError, TypeError):
        return False, "Ingrese un precio válido para el producto."
    ctx = _resolver_sesion(sesion)
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_insertar_producto",
        (nom_producto, descripcion, precio_val, ctx["usuario"], ctx["rol"]),
        fallback="Verifique los datos y el precio ingresado."
    )
    if not ok:
        return False, msg
    id_nuevo = conjuntos[0][0][0] if conjuntos and conjuntos[0] else ""
    return True, f"Producto incorporado al catálogo (Código #{id_nuevo})."


def actualizar_producto(id_producto, nom_producto, descripcion, precio_venta, sesion=None):
    try:
        id_val = int(id_producto)
        precio_val = float(precio_venta)
    except (ValueError, TypeError):
        return False, "Verifique el código y el precio oficial del producto."
    ctx = _resolver_sesion(sesion)
    ok, _, msg = _invocar_sp_escritura(
        "sp_actualizar_producto",
        (id_val, nom_producto, descripcion, precio_val, ctx["usuario"], ctx["rol"]),
        fallback="No se pudo actualizar el producto."
    )
    return (True, f"Producto #{id_val} actualizado en el catálogo.") if ok else (False, msg)


def eliminar_producto(id_producto, sesion=None):
    try:
        prod_val = int(id_producto)
    except (ValueError, TypeError):
        return False, "Código de producto no válido."
    ok, _, msg = _invocar_sp_escritura(
        "sp_eliminar_producto",
        (prod_val,),
        sesion=sesion,
        fijar_auditoria=True,
        fallback="No se puede eliminar un producto que ya posee recetas o ventas asociadas."
    )
    return (True, f"Producto #{prod_val} eliminado del catálogo.") if ok else (False, msg)


def listar_toppings(filtro=""):
    return _invocar_sp_lectura("sp_listar_toppings", (filtro.strip() if filtro else "",))


def insertar_topping(nom_topping, precio_agregado, sesion=None):
    try:
        precio_val = float(precio_agregado)
    except (ValueError, TypeError):
        return False, "Ingrese un precio adicional válido para el topping."
    ctx = _resolver_sesion(sesion)
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_insertar_topping",
        (nom_topping, precio_val, ctx["usuario"], ctx["rol"]),
        fallback="No se pudo registrar el topping."
    )
    if not ok:
        return False, msg
    id_nuevo = conjuntos[0][0][0] if conjuntos and conjuntos[0] else ""
    return True, f"Topping registrado correctamente (Código #{id_nuevo})."


def actualizar_topping(id_topping, nom_topping, precio_agregado, sesion=None):
    try:
        id_val = int(id_topping)
        precio_val = float(precio_agregado)
    except (ValueError, TypeError):
        return False, "Verifique el código y el precio del topping."
    ctx = _resolver_sesion(sesion)
    ok, _, msg = _invocar_sp_escritura(
        "sp_actualizar_topping",
        (id_val, nom_topping, precio_val, ctx["usuario"], ctx["rol"]),
        fallback="No se pudo actualizar el topping."
    )
    return (True, f"Topping #{id_val} actualizado correctamente.") if ok else (False, msg)


def eliminar_topping(id_topping):
    try:
        top_val = int(id_topping)
    except (ValueError, TypeError):
        return False, "Código de topping no válido."
    ok, _, msg = _invocar_sp_escritura(
        "sp_eliminar_topping",
        (top_val,),
        fallback="No se pudo retirar el topping porque tiene registros asociados."
    )
    return (True, f"Topping #{top_val} retirado del catálogo.") if ok else (False, msg)


def listar_matriz_producto_topping():
    return _invocar_sp_lectura("sp_listar_matriz_producto_topping")


def gestionar_producto_topping(id_producto, id_topping, accion="AGREGAR"):
    try:
        vals = (int(id_producto), int(id_topping), accion)
    except (ValueError, TypeError):
        return False, "Seleccione un producto y un topping válidos."
    ok, _, msg = _invocar_sp_escritura(
        "sp_gestionar_producto_topping",
        vals,
        fallback="No se pudo actualizar la asignación de topping."
    )
    return (True, "Asignación de topping actualizada.") if ok else (False, msg)


def listar_recetas():
    return _invocar_sp_lectura("sp_listar_recetas")


def obtener_detalle_receta(id_producto):
    return _invocar_sp_lectura("sp_obtener_detalle_receta", (int(id_producto),))


def guardar_detalle_receta(id_producto, id_insumo, cantidad_requerida, marg_error=0.0):
    try:
        vals = (int(id_producto), int(id_insumo), float(cantidad_requerida), float(marg_error or 0.0))
    except (ValueError, TypeError):
        return False, "Verifique la cantidad y el porcentaje de merma ingresados."
    ok, _, msg = _invocar_sp_escritura(
        "sp_guardar_detalle_receta",
        vals,
        fallback="No se pudo guardar el ingrediente en la receta."
    )
    return (True, "Ingrediente guardado en la receta del producto.") if ok else (False, msg)


def eliminar_detalle_receta(id_producto, id_insumo):
    try:
        vals = (int(id_producto), int(id_insumo))
    except (ValueError, TypeError):
        return False, "Seleccione un producto e insumo válidos."
    ok, _, msg = _invocar_sp_escritura(
        "sp_eliminar_detalle_receta",
        vals,
        fallback="No se pudo quitar el ingrediente de la receta."
    )
    return (True, "Ingrediente retirado de la receta.") if ok else (False, msg)


# =====================================================================
# 4. MÓDULO DE ALMACÉN, INSUMOS, PROVEEDORES Y COMPRAS
# =====================================================================

def listar_unidades_medida():
    return _invocar_sp_lectura("sp_listar_unidades_medida")


def listar_insumos(filtro=""):
    return _invocar_sp_lectura("sp_listar_insumos", (filtro.strip() if filtro else "",))


def resumen_sanitario_insumos():
    filas = _invocar_sp_lectura("sp_resumen_sanitario_insumos")
    if not filas:
        return {"total": 0, "vencidos": 0, "por_vencer": 0, "vigentes": 0, "no_perecibles": 0}
    r = filas[0]
    return {
        "total": int(r[0]),
        "vencidos": int(r[1]),
        "por_vencer": int(r[2]),
        "vigentes": int(r[3]),
        "no_perecibles": int(r[4]),
    }


def insertar_insumo(id_unidad_medida, nombre_insumo, unidad_medida, es_perecible, f_vencimiento, sesion=None):
    try:
        um_val = int(id_unidad_medida)
        per_val = int(es_perecible)
    except (ValueError, TypeError):
        return False, "Seleccione una unidad de medida y condición sanitaria válidas."
    ctx = _resolver_sesion(sesion)
    fecha_val = f_vencimiento.strip() if f_vencimiento and f_vencimiento.strip() not in ("", "No aplica") else None
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_insertar_insumo",
        (um_val, nombre_insumo, unidad_medida, per_val, fecha_val, ctx["usuario"], ctx["rol"]),
        fallback="Verifique los datos y el formato de fecha (AAAA-MM-DD)."
    )
    if not ok:
        return False, msg
    id_nuevo = conjuntos[0][0][0] if conjuntos and conjuntos[0] else ""
    return True, f"Insumo registrado en almacén (Código #{id_nuevo})."


def actualizar_insumo(id_insumo, id_unidad_medida, nombre_insumo, unidad_medida, es_perecible, f_vencimiento, sesion=None):
    try:
        id_val = int(id_insumo)
        um_val = int(id_unidad_medida)
        per_val = int(es_perecible)
    except (ValueError, TypeError):
        return False, "Verifique los datos seleccionados para el insumo."
    fecha_val = f_vencimiento.strip() if f_vencimiento and f_vencimiento.strip() not in ("", "No aplica") else None
    ok, _, msg = _invocar_sp_escritura(
        "sp_actualizar_insumo",
        (id_val, um_val, nombre_insumo, unidad_medida, per_val, fecha_val),
        sesion=sesion,
        fijar_auditoria=True,
        fallback="No se pudo actualizar el insumo."
    )
    return (True, f"Insumo #{id_val} actualizado en almacén.") if ok else (False, msg)


def eliminar_insumo(id_insumo, sesion=None):
    try:
        ins_val = int(id_insumo)
    except (ValueError, TypeError):
        return False, "Código de insumo no válido."
    ok, _, msg = _invocar_sp_escritura(
        "sp_eliminar_insumo",
        (ins_val,),
        sesion=sesion,
        fijar_auditoria=True,
        fallback="No se puede retirar este insumo porque forma parte de recetas o pedidos."
    )
    return (True, f"Insumo #{ins_val} retirado del almacén.") if ok else (False, msg)


def listar_almacenes_sucursales():
    return _invocar_sp_lectura("sp_listar_almacenes_sucursales")


def actualizar_almacen_sucursal(id_almacen, cantidad_disponible):
    try:
        vals = (int(id_almacen), int(cantidad_disponible))
    except (ValueError, TypeError):
        return False, "Ingrese una cantidad entera válida para el almacén."
    ok, _, msg = _invocar_sp_escritura(
        "sp_actualizar_almacen_sucursal",
        vals,
        fallback="No se pudo actualizar el saldo del almacén."
    )
    return (True, "Capacidad de almacén actualizada.") if ok else (False, msg)


def listar_proveedores(filtro=""):
    return _invocar_sp_lectura("sp_listar_proveedores", (filtro.strip() if filtro else "",))


def guardar_proveedor(id_proveedor, razon_social, ruc, telefono, email, persona_natural=0, id_empleado=2):
    try:
        vals = (int(id_proveedor or 0), razon_social, ruc, telefono, email, int(persona_natural or 0), int(id_empleado or 2))
    except (ValueError, TypeError):
        return False, "Verifique los datos del proveedor."
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_guardar_proveedor",
        vals,
        fallback="No se pudo guardar el proveedor (verifique RUC, razón social y teléfono únicos)."
    )
    if not ok:
        return False, msg
    id_p = conjuntos[0][0][0] if conjuntos and conjuntos[0] else ""
    return True, f"Proveedor guardado correctamente (Código #{id_p})."


def listar_compras_abastecimiento(id_proveedor=0, fecha_desde=None, fecha_hasta=None):
    return _invocar_sp_lectura(
        "sp_listar_compras_abastecimiento",
        (int(id_proveedor or 0), fecha_desde or None, fecha_hasta or None)
    )


def registrar_pedido_y_compra(id_proveedor, id_insumo, cantidad, precio_unitario, fecha_vencimiento=None, sesion=None):
    try:
        prov_val = int(id_proveedor)
        ins_val = int(id_insumo)
        cant_val = int(cantidad)
        pu_val = float(precio_unitario)
    except (ValueError, TypeError):
        return False, "Verifique proveedor, insumo, cantidad y precio unitario."
    ctx = _resolver_sesion(sesion)
    fecha_val = fecha_vencimiento.strip() if fecha_vencimiento and fecha_vencimiento.strip() else None
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_registrar_pedido_y_compra",
        (prov_val, ins_val, cant_val, pu_val, fecha_val, ctx["usuario"], ctx["rol"]),
        fallback="No se pudo registrar el ingreso de compra."
    )
    if not ok:
        return False, msg
    if conjuntos and conjuntos[0]:
        id_c, id_p, total = conjuntos[0][0]
        return True, f"Compra #{id_c} (Pedido #{id_p}) registrada por S/ {float(total):.2f}."
    return True, "Compra registrada correctamente."


# =====================================================================
# 5. MÓDULO DE PUNTO DE VENTA (CAJA DIARIA POR SEDE, TOPPINGS Y ARQUEO)
# =====================================================================

def listar_ventas(id_sucursal=None, sesion=None):
    ctx = _resolver_sesion(sesion)
    suc = id_sucursal if id_sucursal is not None else ctx.get("id_sucursal")
    return _invocar_sp_lectura("sp_listar_ventas", (int(suc) if suc else 0,))


def buscar_ventas(id_sucursal=0, fecha_desde=None, fecha_hasta=None, canal="Todos", id_metodo=0, texto=""):
    return _invocar_sp_lectura(
        "sp_buscar_ventas",
        (int(id_sucursal or 0), fecha_desde or None, fecha_hasta or None, canal or "Todos", int(id_metodo or 0), texto.strip() if texto else "")
    )


def obtener_detalle_venta(id_venta):
    """Invoca `sp_obtener_detalle_venta` -> (cabecera, lineas)."""
    conjuntos = _invocar_sp_lectura("sp_obtener_detalle_venta", (int(id_venta),), multi=True)
    cabecera = conjuntos[0][0] if len(conjuntos) > 0 and conjuntos[0] else None
    lineas = conjuntos[1] if len(conjuntos) > 1 else []
    return cabecera, lineas


def obtener_catalogos_venta(id_sucursal=None, sesion=None):
    ctx = _resolver_sesion(sesion)
    suc = id_sucursal if id_sucursal is not None else ctx.get("id_sucursal")
    conexion = obtener_conexion()
    if not conexion:
        return [], [], [], []
    cursor = None
    try:
        cursor = conexion.cursor()
        cursor.callproc("sp_catalogo_clientes")
        clientes = cursor.fetchall()

        cursor.callproc("sp_catalogo_empleados_sede", (int(suc) if suc else 0,))
        empleados = cursor.fetchall()

        cursor.callproc("sp_catalogo_metodos_pago")
        metodos = cursor.fetchall()

        cursor.callproc("sp_catalogo_productos")
        productos = cursor.fetchall()

        return clientes, empleados, metodos, productos
    except Error as e:
        print(f"[ERROR obtener_catalogos_venta]: {e}")
        return [], [], [], []
    finally:
        cerrar_conexion(conexion, cursor)


def obtener_toppings_por_producto(id_producto):
    return _invocar_sp_lectura("sp_catalogo_toppings_producto", (int(id_producto),))


def calcular_linea_carrito_bd(id_producto, cantidad, id_topping=0):
    filas = _invocar_sp_lectura(
        "sp_calcular_linea_carrito",
        (int(id_producto), int(cantidad), int(id_topping or 0))
    )
    return filas[0] if filas else None


def calcular_resumen_carrito_bd(items_lista, monto_recibido=0.0):
    """
    Delega el 100% del cálculo del carrito y vuelto a MySQL (`sp_calcular_resumen_carrito`).
    items_lista: [{"id_producto": int, "cantidad": int, "id_topping": int}, ...]
    """
    payload = json.dumps(items_lista or [])
    conjuntos = _invocar_sp_lectura("sp_calcular_resumen_carrito", (payload, float(monto_recibido or 0.0)), multi=True)
    lineas = conjuntos[0] if len(conjuntos) > 0 else []
    resumen_raw = conjuntos[1][0] if len(conjuntos) > 1 and conjuntos[1] else (0, 0, 0.0, 0.0, 0.0, 0.0)
    resumen = {
        "total_lineas": int(resumen_raw[0]),
        "total_unidades": int(resumen_raw[1]),
        "total_cobrar": float(resumen_raw[2]),
        "monto_recibido": float(resumen_raw[3]),
        "vuelto": float(resumen_raw[4]),
        "faltante": float(resumen_raw[5]),
    }
    return lineas, resumen


def generar_correlativo_comprobante(tipo_comprobante="Boleta", id_sucursal=None, sesion=None):
    ctx = _resolver_sesion(sesion)
    suc = id_sucursal if id_sucursal is not None else ctx.get("id_sucursal")
    filas = _invocar_sp_lectura(
        "sp_generar_correlativo_comprobante",
        (tipo_comprobante or "Boleta", int(suc) if suc else 1)
    )
    return filas[0][0] if filas and filas[0][0] else "B001-0101"


def registrar_venta_completa_bd(tipo_comprobante, id_sucursal, canal_atencion, id_empleado,
                                id_cliente, id_metodo_pago, items_lista, sesion=None):
    """
    Emite la venta de forma 100% atómica ACID dentro de MySQL (`sp_registrar_venta_completa`).
    Retorna (ok: bool, datos: dict | None, mensaje: str).
    """
    if not items_lista:
        return False, None, "Agregue al menos un producto al pedido antes de cobrar."
    try:
        emp_val = int(id_empleado)
        cli_val = int(id_cliente)
        met_val = int(id_metodo_pago)
    except (ValueError, TypeError):
        return False, None, "Verifique cajero, cliente y medio de pago seleccionados."
    ctx = _resolver_sesion(sesion)
    suc = id_sucursal if id_sucursal is not None else ctx.get("id_sucursal")
    payload = json.dumps(items_lista)
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_registrar_venta_completa",
        (
            tipo_comprobante or "Boleta",
            int(suc) if suc else 0,
            canal_atencion or "Sede",
            emp_val,
            cli_val,
            met_val,
            payload,
            ctx["usuario"],
            ctx["rol"],
        ),
        fallback="No se pudo procesar el comprobante (operación revertida)."
    )
    if not ok or not conjuntos or not conjuntos[0]:
        return False, None, msg
    id_venta, id_pago, num_comp, total_cobrado = conjuntos[0][0]
    datos = {
        "id_venta": int(id_venta),
        "id_pago": int(id_pago),
        "num_comprobante": num_comp,
        "total_cobrado": float(total_cobrado),
    }
    return True, datos, f"Comprobante {num_comp} emitido correctamente por S/ {float(total_cobrado):.2f}."


def registrar_venta_carrito(num_comprobante, canal_atencion, id_empleado, id_cliente,
                            tipo_comprobante, id_metodo_pago, items_carrito, sesion=None):
    """Wrapper transaccional compatible con el cliente de escritorio local (Tkinter)."""
    if not items_carrito:
        return False, "Agregue al menos un producto al pedido antes de registrar la venta."
    ctx = _resolver_sesion(sesion)
    conexion = obtener_conexion()
    if not conexion:
        return False, "Sin conexión con el servidor."
    cursor = None
    try:
        cursor = conexion.cursor()
        cursor.callproc(
            "sp_crear_cabecera_venta",
            (
                num_comprobante.strip(),
                canal_atencion,
                int(id_empleado),
                int(id_cliente),
                tipo_comprobante,
                int(id_metodo_pago),
                ctx["usuario"],
                ctx["rol"],
            ),
        )
        cabecera = cursor.fetchone()
        if not cabecera:
            raise ValueError("No se pudo generar el comprobante de venta.")
        id_venta = int(cabecera[0])
        for item in items_carrito:
            cursor.callproc(
                "sp_insertar_detalle_carrito",
                (
                    id_venta,
                    int(item["id_prod"]),
                    int(item["cantidad"]),
                    float(item["precio_base"]),
                    int(item["id_top"]),
                    float(item["precio_top"]),
                ),
            )
        conexion.commit()
        return True, f"Comprobante {num_comprobante} (Pedido #{id_venta}) registrado exitosamente."
    except (Error, ValueError, KeyError) as e:
        _rollback_seguro(conexion)
        return False, _mensaje_error_comercial(e, "No se pudo procesar la venta (operación revertida).")
    finally:
        cerrar_conexion(conexion, cursor)


def eliminar_venta(id_venta, sesion=None):
    ctx = _resolver_sesion(sesion)
    ok, _, msg = _invocar_sp_escritura(
        "sp_eliminar_venta",
        (int(id_venta), ctx["usuario"], ctx["rol"]),
        fallback="No se pudo anular el comprobante seleccionado."
    )
    return (True, f"El comprobante #{id_venta} fue anulado correctamente.") if ok else (False, msg)


def obtener_arqueo_caja_sede(id_sucursal=None, sesion=None):
    ctx = _resolver_sesion(sesion)
    suc = id_sucursal if id_sucursal is not None else ctx.get("id_sucursal")
    return _invocar_sp_lectura("sp_arqueo_caja_sede", (int(suc) if suc else 0,))


def obtener_arqueo_rango(id_sucursal=0, fecha_desde=None, fecha_hasta=None):
    desglose = _invocar_sp_lectura(
        "sp_arqueo_caja_rango",
        (int(id_sucursal or 0), fecha_desde or None, fecha_hasta or None)
    )
    resumen_rows = _invocar_sp_lectura(
        "sp_arqueo_caja_resumen",
        (int(id_sucursal or 0), fecha_desde or None, fecha_hasta or None)
    )
    r = resumen_rows[0] if resumen_rows else ("Todas las Sedes", 0, 0.0, 0.0, 0, 0)
    resumen = {
        "nombre_sucursal": r[0],
        "total_ventas": int(r[1]),
        "total_recaudado": float(r[2]),
        "ticket_promedio": float(r[3]),
        "ventas_sede": int(r[4]),
        "ventas_delivery": int(r[5]),
    }
    return desglose, resumen


# =====================================================================
# 6. DASHBOARD DE GERENCIA GENERAL (100% CALCULADO EN MYSQL)
# =====================================================================

def obtener_dashboard_gerencia(id_sucursal=0, fecha_desde=None, fecha_hasta=None):
    """Reúne en un solo objeto las métricas calculadas por los 8 SPs analíticos de `proyect_db`."""
    suc = int(id_sucursal or 0)
    f_ini = fecha_desde or None
    f_fin = fecha_hasta or None

    kpis_rows = _invocar_sp_lectura("sp_dashboard_kpis_generales", (suc, f_ini, f_fin))
    k = kpis_rows[0] if kpis_rows else (0.0, 0, 0.0, 0, 0, 0, 0, 0)
    kpis = {
        "total_ingresos": float(k[0]),
        "cantidad_ventas": int(k[1]),
        "ticket_promedio": float(k[2]),
        "unidades_vendidas": int(k[3]),
        "clientes_unicos": int(k[4]),
        "insumos_vencidos": int(k[5]),
        "insumos_por_vencer": int(k[6]),
        "cuentas_bloqueadas": int(k[7]),
    }

    alertas_sets = _invocar_sp_lectura("sp_dashboard_alertas_operativas", (), multi=True)
    return {
        "kpis": kpis,
        "ventas_sede": _invocar_sp_lectura("sp_dashboard_ventas_por_sede", (f_ini, f_fin)),
        "ventas_metodo": _invocar_sp_lectura("sp_dashboard_ventas_por_metodo_pago", (suc, f_ini, f_fin)),
        "top_productos": _invocar_sp_lectura("sp_dashboard_top_productos", (suc, f_ini, f_fin, 7)),
        "top_toppings": _invocar_sp_lectura("sp_dashboard_top_toppings", (suc, f_ini, f_fin)),
        "ventas_canal": _invocar_sp_lectura("sp_dashboard_ventas_por_canal", (suc, f_ini, f_fin)),
        "tendencia_diaria": _invocar_sp_lectura("sp_dashboard_tendencia_diaria", (suc, f_ini, f_fin)),
        "desempeno_empleados": _invocar_sp_lectura("sp_reporte_desempeno_empleados", (suc, f_ini, f_fin)),
        "alertas_insumos": alertas_sets[0] if len(alertas_sets) > 0 else [],
        "alertas_bloqueos": alertas_sets[1] if len(alertas_sets) > 1 else [],
        "alertas_recetas": alertas_sets[2] if len(alertas_sets) > 2 else [],
    }


# =====================================================================
# 7. MÓDULO DE PERSONAL Y SEDES (RRHH)
# =====================================================================

def listar_empleados(filtro=""):
    return _invocar_sp_lectura("sp_listar_empleados", (filtro.strip() if filtro else "",))


def obtener_sucursales_combo():
    filas = _invocar_sp_lectura("sp_listar_sucursales")
    return [r[0] for r in filas] if filas else []


def catalogo_roles():
    return _invocar_sp_lectura("sp_catalogo_roles")


def reporte_desempeno_empleados(id_sucursal=0, fecha_desde=None, fecha_hasta=None):
    return _invocar_sp_lectura(
        "sp_reporte_desempeno_empleados",
        (int(id_sucursal or 0), fecha_desde or None, fecha_hasta or None)
    )


def insertar_empleado(nombres, ap_paterno, ap_materno, id_sucursal, id_rol, sesion=None):
    try:
        suc_val = int(id_sucursal)
        rol_val = int(id_rol)
    except (ValueError, TypeError):
        return False, "Seleccione una sucursal y un cargo válidos."
    ctx = _resolver_sesion(sesion)
    ok, conjuntos, msg = _invocar_sp_escritura(
        "sp_insertar_empleado",
        (suc_val, rol_val, nombres, ap_paterno, ap_materno, ctx["usuario"], ctx["rol"]),
        fallback="No se pudo registrar al colaborador."
    )
    if not ok:
        return False, msg
    id_nuevo = conjuntos[0][0][0] if conjuntos and conjuntos[0] else ""
    return True, f"Colaborador registrado correctamente (Código #{id_nuevo})."


def actualizar_empleado(id_empleado, nombres, ap_paterno, ap_materno, id_sucursal, id_rol, sesion=None):
    try:
        emp_val = int(id_empleado)
        suc_val = int(id_sucursal)
        rol_val = int(id_rol)
    except (ValueError, TypeError):
        return False, "Verifique los datos seleccionados para el colaborador."
    ctx = _resolver_sesion(sesion)
    ok, _, msg = _invocar_sp_escritura(
        "sp_actualizar_empleado",
        (emp_val, suc_val, rol_val, nombres, ap_paterno, ap_materno, ctx["usuario"], ctx["rol"]),
        fallback="No se pudo actualizar al colaborador."
    )
    return (True, f"Datos del colaborador #{emp_val} actualizados.") if ok else (False, msg)


def eliminar_empleado(id_empleado, sesion=None):
    try:
        emp_val = int(id_empleado)
    except (ValueError, TypeError):
        return False, "Código de colaborador no válido."
    ok, _, msg = _invocar_sp_escritura(
        "sp_eliminar_empleado",
        (emp_val,),
        sesion=sesion,
        fijar_auditoria=True,
        fallback="No se puede dar de baja a un colaborador con historial de atención o compras."
    )
    return (True, f"Colaborador #{emp_val} dado de baja.") if ok else (False, msg)


# =====================================================================
# 8. MÓDULO DE HISTORIAL Y AUDITORÍA DE SEGURIDAD
# =====================================================================

def listar_bitacora_auditoria(filtro_accion="Todos", filtro_tabla="Todas"):
    return _invocar_sp_lectura("sp_listar_bitacora", (filtro_accion or "Todos", filtro_tabla or "Todas"))


def listar_bitacora_comercial(filtro_accion="Todos", filtro_modulo="Todos", fecha_desde=None, fecha_hasta=None):
    return _invocar_sp_lectura(
        "sp_listar_bitacora_comercial",
        (filtro_accion or "Todos", filtro_modulo or "Todos", fecha_desde or None, fecha_hasta or None)
    )


if __name__ == "__main__":
    print("=" * 78)
    print("  DIAGNÓSTICO DE SERVICIOS — HELADERÍA POLO NORTE (proyect_db)")
    print("=" * 78)
    print(f"[OK] Clientes registrados      : {len(listar_clientes())}")
    print(f"[OK] Productos en catálogo     : {len(listar_productos())}")
    print(f"[OK] Toppings disponibles      : {len(listar_toppings())}")
    print(f"[OK] Insumos en almacén        : {len(listar_insumos())}")
    print(f"[OK] Proveedores activos       : {len(listar_proveedores())}")
    print(f"[OK] Compras registradas       : {len(listar_compras_abastecimiento())}")
    print(f"[OK] Ventas registradas        : {len(listar_ventas())}")
    print(f"[OK] Colaboradores en nómina   : {len(listar_empleados())}")
    print(f"[OK] Accesos (Cajas y Gestión) : {len(listar_usuarios_credenciales())}")
    print(f"[OK] Eventos en historial      : {len(listar_bitacora_comercial())}")
    dash = obtener_dashboard_gerencia()
    print(f"[OK] Dashboard Gerencia (KPIs) : S/ {dash['kpis']['total_ingresos']:.2f} ({dash['kpis']['cantidad_ventas']} ventas)")
    print("=" * 78)
