# app.py
# Aplicación Web Comercial — Heladería Polo Norte (FastAPI + Jinja2)
# Capa visual pura: ZERO consultas SQL y ZERO fórmulas de negocio en Python.
# Toda lógica, cálculo, validación transaccional y auditoría se delega a MySQL (`proyect_db`)
# exclusivamente mediante `controlador.py` -> `cursor.callproc("sp_*", args)`.

import csv
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

sys.dont_write_bytecode = True

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
import conexion
import controlador

BASE_DIR = Path(__file__).resolve().parent
ZONA_PERU = timezone(timedelta(hours=-5))

app = FastAPI(
    title="Heladería Polo Norte — Sistema POS/ERP",
    docs_url=None,
    redoc_url=None,
)


@app.middleware("http")
async def proteger_origen_mutaciones(request: Request, call_next):
    """Protección anti-CSRF por validación estricta de Origin/Referer/Sec-Fetch-Site en mutaciones."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        sec_fetch = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if sec_fetch == "cross-site":
            return JSONResponse({"detail": "Solicitud externa rechazada."}, status_code=403)
        host = (request.headers.get("host") or "").strip().lower()
        origin = (request.headers.get("origin") or "").strip()
        referer = (request.headers.get("referer") or "").strip()
        if origin:
            if origin == "null" or (host and urlparse(origin).netloc.lower() != host):
                return JSONResponse({"detail": "Origen no autorizado."}, status_code=403)
        elif referer and host and urlparse(referer).netloc.lower() != host:
            return JSONResponse({"detail": "Referencia externa no autorizada."}, status_code=403)
    return await call_next(request)


app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie="pn_session",
    same_site="lax",
    https_only=(config.APP_ENV == "production"),
    max_age=60 * 60 * 12,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# =====================================================================
# HELPERS DE SESIÓN, RBAC Y MENSAJES FLASH (SOLO CAPA PRESENTACIÓN)
# =====================================================================

ETIQUETAS_ROL = {
    "Administrador": "Gerencia General",
    "RecursosHumanos": "Recursos Humanos",
    "AsistenteLogistico": "Logística y Almacén",
    "Multifuncional": "Caja Diaria",
}

INICIO_POR_ROL = {
    "Administrador": "/dashboard",
    "Multifuncional": "/pos",
    "AsistenteLogistico": "/catalogo",
    "RecursosHumanos": "/personal",
}

ICONOS_PRODUCTO = {
    1: "🍦",
    2: "🍨",
    3: "🍦",
    4: "🍧",
    5: "🥤",
    6: "☕",
    7: "🥛",
}


def _obtener_sesion(request: Request) -> Optional[dict]:
    return request.session.get("usuario_ctx")


def _fijar_flash(request: Request, tipo: str, texto: str, ticket_id: Optional[int] = None):
    request.session["flash"] = {"tipo": tipo, "texto": texto, "ticket_id": ticket_id}


def _consumir_flash(request: Request) -> Optional[dict]:
    return request.session.pop("flash", None)


def _exigir_roles(request: Request, roles_permitidos: tuple):
    sesion = _obtener_sesion(request)
    if not sesion:
        return None, RedirectResponse("/login", status_code=303)
    if sesion["rol"] not in roles_permitidos:
        _fijar_flash(request, "warn", "Tu perfil no tiene acceso a ese módulo.")
        destino = INICIO_POR_ROL.get(sesion["rol"], "/login")
        return None, RedirectResponse(destino, status_code=303)
    return sesion, None


def _ctx_base(request: Request, sesion: dict, pagina: str, titulo: str, subtitulo: str = "") -> dict:
    return {
        "request": request,
        "sesion": sesion,
        "es_admin": sesion["rol"] == "Administrador",
        "rol_etiqueta": ETIQUETAS_ROL.get(sesion["rol"], sesion["rol"]),
        "pagina": pagina,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "flash": _consumir_flash(request),
    }


def _sucursal_efectiva(sesion: dict, id_sucursal_param: int) -> int:
    """Si el usuario es una Caja Diaria, fija estrictamente su sede asignada."""
    if sesion["rol"] == "Multifuncional" and sesion.get("id_sucursal"):
        return int(sesion["id_sucursal"])
    return int(id_sucursal_param or 0)


# =====================================================================
# SALUD DEL SERVICIO Y ACCESO DUAL (CAJAS POR SEDE VS. BACK-OFFICE)
# =====================================================================

@app.get("/health")
def health_check():
    ok, _msg = conexion.probar_conexion()
    return JSONResponse({"status": "ok" if ok else "degraded"}, status_code=200 if ok else 503)


@app.get("/", response_class=HTMLResponse)
def raiz(request: Request):
    sesion = _obtener_sesion(request)
    if not sesion:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse(INICIO_POR_ROL.get(sesion["rol"], "/pos"), status_code=303)


@app.get("/login", response_class=HTMLResponse)
def vista_login(request: Request):
    sesion = _obtener_sesion(request)
    if sesion:
        return RedirectResponse(INICIO_POR_ROL.get(sesion["rol"], "/pos"), status_code=303)
    sedes = controlador.listar_almacenes_sucursales()
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "flash": _consumir_flash(request),
            "sedes": sedes,
        },
    )


@app.get("/api/login/estado")
def api_estado_login(usuario: str = Query("")):
    info = controlador.consultar_info_usuario_web(usuario)
    if not info:
        return JSONResponse({"encontrado": False})
    bloqueado = info["estado"] == "Bloqueado" or info["intentos_restantes"] <= 0
    return JSONResponse(
        {
            "encontrado": True,
            "requiere_password": info["requiere_password"],
            "bloqueado": bloqueado,
            "area_comercial": info["area_comercial"],
            "nombre_sucursal": info["nombre_sucursal"] if not info["requiere_password"] else "",
        }
    )


@app.post("/login")
def procesar_login(
    request: Request,
    usuario: str = Form(...),
    password: str = Form(""),
):
    res = controlador.validar_login_web(usuario, password)
    if not res.get("exito"):
        _fijar_flash(request, "err", res.get("mensaje", "Credenciales inválidas."))
        return RedirectResponse("/login", status_code=303)

    request.session["usuario_ctx"] = {
        "usuario": res["usuario"],
        "rol": res["rol"],
        "id_sucursal": res["id_sucursal"],
        "nombre_sucursal": res["nombre_sucursal"],
        "persona": res["persona"],
    }
    request.session["carrito"] = []
    _fijar_flash(request, "ok", res["mensaje"])
    return RedirectResponse(INICIO_POR_ROL.get(res["rol"], "/pos"), status_code=303)


@app.post("/login/caja/{cuenta_caja}")
def abrir_caja_directa(request: Request, cuenta_caja: str):
    if cuenta_caja not in ("caja_quintanas", "caja_upao", "caja_mall"):
        _fijar_flash(request, "err", "Caja diaria no reconocida.")
        return RedirectResponse("/login", status_code=303)
    res = controlador.validar_login_web(cuenta_caja, "")
    if not res.get("exito"):
        _fijar_flash(request, "err", res.get("mensaje", "No se pudo abrir la caja."))
        return RedirectResponse("/login", status_code=303)

    request.session["usuario_ctx"] = {
        "usuario": res["usuario"],
        "rol": res["rol"],
        "id_sucursal": res["id_sucursal"],
        "nombre_sucursal": res["nombre_sucursal"],
        "persona": res["persona"],
    }
    request.session["carrito"] = []
    _fijar_flash(request, "ok", res["mensaje"])
    return RedirectResponse("/pos", status_code=303)


@app.post("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    _fijar_flash(request, "ok", "Turno cerrado correctamente.")
    return RedirectResponse("/login", status_code=303)


# =====================================================================
# DASHBOARD EJECUTIVO DE GERENCIA GENERAL (100% MÉTRICAS DESDE MYSQL)
# =====================================================================

@app.get("/dashboard", response_class=HTMLResponse)
def vista_dashboard(
    request: Request,
    id_sucursal: int = Query(0),
    fecha_desde: str = Query(""),
    fecha_hasta: str = Query(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir

    datos = controlador.obtener_dashboard_gerencia(id_sucursal, fecha_desde or None, fecha_hasta or None)
    sedes = controlador.listar_almacenes_sucursales()
    ctx = _ctx_base(
        request,
        sesion,
        "dashboard",
        "Panel de Gerencia General",
        "Indicadores consolidados de las 3 sedes, productos líderes, alertas sanitarias y seguridad",
    )
    ctx.update(
        {
            "datos": datos,
            "sedes": sedes,
            "filtro_sede": id_sucursal,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        }
    )
    return templates.TemplateResponse(request, "dashboard.html", ctx)


# =====================================================================
# PUNTO DE VENTA (CAJA RÁPIDA, TOPPINGS, CARRITO MYSQL, TICKET Y ARQUEO)
# =====================================================================

@app.get("/pos", response_class=HTMLResponse)
def vista_pos(
    request: Request,
    canal: str = Query("Todos"),
    id_metodo: int = Query(0),
    texto: str = Query(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir

    suc_activa = sesion.get("id_sucursal") or 0
    clientes, empleados, metodos, productos = controlador.obtener_catalogos_venta(suc_activa, sesion=sesion)
    primer_prod_id = int(productos[0][0]) if productos else 0
    toppings_iniciales = controlador.obtener_toppings_por_producto(primer_prod_id) if primer_prod_id else []
    correlativo = controlador.generar_correlativo_comprobante("Boleta", suc_activa or 1, sesion=sesion)

    items_sesion = request.session.get("carrito", [])
    lineas_carrito, resumen_carrito = controlador.calcular_resumen_carrito_bd(items_sesion, 0.0)
    ventas = controlador.buscar_ventas(suc_activa, None, None, canal, id_metodo, texto)
    _, arqueo_resumen = controlador.obtener_arqueo_rango(suc_activa, None, None)

    ctx = _ctx_base(
        request,
        sesion,
        "pos",
        "Punto de Venta — Caja Rápida",
        f"{sesion['nombre_sucursal']} · Precios oficiales protegidos y comprobantes correlativos",
    )
    ctx.update(
        {
            "clientes": clientes,
            "empleados": empleados,
            "metodos": metodos,
            "productos": productos,
            "iconos_producto": ICONOS_PRODUCTO,
            "primer_prod_id": primer_prod_id,
            "primer_prod_precio": f"{float(productos[0][2]):.2f}" if productos else "0.00",
            "toppings_iniciales": toppings_iniciales,
            "correlativo": correlativo,
            "lineas_carrito": lineas_carrito,
            "resumen_carrito": resumen_carrito,
            "ventas": ventas[:25],
            "arqueo_resumen": arqueo_resumen,
            "filtro_canal": canal,
            "filtro_metodo": id_metodo,
            "filtro_texto": texto,
        }
    )
    return templates.TemplateResponse(request, "pos.html", ctx)


@app.get("/pos/parcial/toppings/{id_producto}", response_class=HTMLResponse)
def parcial_toppings_producto(request: Request, id_producto: int):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return HTMLResponse("", status_code=401)
    toppings = controlador.obtener_toppings_por_producto(id_producto)
    return templates.TemplateResponse(request, "partials/pos_toppings.html", {"toppings": toppings})


@app.get("/pos/api/correlativo")
def api_correlativo(request: Request, tipo: str = Query("Boleta")):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return JSONResponse({"error": "No autorizado"}, status_code=401)
    suc = sesion.get("id_sucursal") or 1
    corr = controlador.generar_correlativo_comprobante(tipo, suc, sesion=sesion)
    return JSONResponse({"correlativo": corr})


def _render_parcial_carrito(request: Request, monto_recibido: float = 0.0):
    items = request.session.get("carrito", [])
    lineas, resumen = controlador.calcular_resumen_carrito_bd(items, monto_recibido)
    return templates.TemplateResponse(
        request,
        "partials/pos_carrito.html",
        {"lineas_carrito": lineas, "resumen_carrito": resumen},
    )


@app.post("/pos/carrito/agregar", response_class=HTMLResponse)
def pos_carrito_agregar(
    request: Request,
    id_producto: int = Form(...),
    cantidad: int = Form(1),
    id_topping: int = Form(0),
    monto_recibido: str = Form("0"),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return HTMLResponse("", status_code=401)
    if cantidad > 0:
        items = list(request.session.get("carrito", []))
        items.append({"id_producto": int(id_producto), "cantidad": int(cantidad), "id_topping": int(id_topping or 0)})
        request.session["carrito"] = items
    rec = float(monto_recibido) if monto_recibido and monto_recibido.replace(".", "", 1).isdigit() else 0.0
    return _render_parcial_carrito(request, rec)


@app.post("/pos/carrito/quitar", response_class=HTMLResponse)
def pos_carrito_quitar(
    request: Request,
    indice: int = Form(...),
    monto_recibido: str = Form("0"),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return HTMLResponse("", status_code=401)
    items = list(request.session.get("carrito", []))
    if 0 <= indice < len(items):
        items.pop(indice)
        request.session["carrito"] = items
    rec = float(monto_recibido) if monto_recibido and monto_recibido.replace(".", "", 1).isdigit() else 0.0
    return _render_parcial_carrito(request, rec)


@app.post("/pos/carrito/vaciar", response_class=HTMLResponse)
def pos_carrito_vaciar(request: Request):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return HTMLResponse("", status_code=401)
    request.session["carrito"] = []
    return _render_parcial_carrito(request, 0.0)


@app.post("/pos/carrito/vuelto", response_class=HTMLResponse)
def pos_carrito_vuelto(request: Request, monto_recibido: str = Form("0")):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return HTMLResponse("", status_code=401)
    try:
        rec = max(0.0, float(monto_recibido or 0))
    except ValueError:
        rec = 0.0
    return _render_parcial_carrito(request, rec)


@app.post("/pos/ventas")
def pos_emitir_venta(
    request: Request,
    tipo_comprobante: str = Form("Boleta"),
    canal_atencion: str = Form("Sede"),
    id_empleado: int = Form(...),
    id_cliente: int = Form(...),
    id_metodo_pago: int = Form(...),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir

    items = request.session.get("carrito", [])
    if not items:
        _fijar_flash(request, "warn", "Agrega al menos un producto al pedido antes de emitir el comprobante.")
        return RedirectResponse("/pos", status_code=303)

    ok, datos, msg = controlador.registrar_venta_completa_bd(
        tipo_comprobante=tipo_comprobante,
        id_sucursal=sesion.get("id_sucursal") or 0,
        canal_atencion=canal_atencion,
        id_empleado=id_empleado,
        id_cliente=id_cliente,
        id_metodo_pago=id_metodo_pago,
        items_lista=items,
        sesion=sesion,
    )
    if ok and datos:
        request.session["carrito"] = []
        _fijar_flash(request, "ok", msg, ticket_id=datos["id_venta"])
    else:
        _fijar_flash(request, "err", msg)
    return RedirectResponse("/pos", status_code=303)


@app.post("/pos/ventas/{id_venta}/anular")
def pos_anular_venta(request: Request, id_venta: int):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.eliminar_venta(id_venta, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/pos", status_code=303)


@app.post("/pos/clientes/rapido")
def pos_cliente_rapido(
    request: Request,
    nombres: str = Form(...),
    ap_paterno: str = Form(...),
    ap_materno: str = Form(""),
    celular: str = Form(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir
    ok, _id_c, msg = controlador.insertar_cliente_con_id(nombres, ap_paterno, ap_materno, celular)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/pos", status_code=303)


@app.get("/pos/ventas/{id_venta}/ticket", response_class=HTMLResponse)
def vista_ticket(request: Request, id_venta: int):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir
    cabecera, lineas = controlador.obtener_detalle_venta(id_venta)
    if not cabecera:
        _fijar_flash(request, "err", "El comprobante solicitado no existe.")
        return RedirectResponse("/pos", status_code=303)
    if sesion["rol"] == "Multifuncional" and sesion.get("id_sucursal") and int(cabecera[5]) != int(sesion["id_sucursal"]):
        _fijar_flash(request, "warn", "Solo puedes consultar comprobantes emitidos en tu propia sucursal.")
        return RedirectResponse("/pos", status_code=303)
    return templates.TemplateResponse(
        request,
        "ticket.html",
        {"cabecera": cabecera, "lineas": lineas, "sesion": sesion},
    )


@app.get("/pos/arqueo", response_class=HTMLResponse)
def vista_arqueo(
    request: Request,
    id_sucursal: int = Query(0),
    periodo: str = Query("historico"),
    fecha_desde: str = Query(""),
    fecha_hasta: str = Query(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir

    suc = _sucursal_efectiva(sesion, id_sucursal)
    hoy = datetime.now(ZONA_PERU).date()
    f_ini, f_fin = fecha_desde or None, fecha_hasta or None
    if periodo == "hoy":
        f_ini = f_fin = hoy.isoformat()
    elif periodo == "7d":
        f_ini = (hoy - timedelta(days=6)).isoformat()
        f_fin = hoy.isoformat()
    elif periodo == "historico":
        f_ini = f_fin = None

    desglose, resumen = controlador.obtener_arqueo_rango(suc, f_ini, f_fin)
    sedes = controlador.listar_almacenes_sucursales()
    ventas_sede = controlador.obtener_dashboard_gerencia(0, f_ini, f_fin)["ventas_sede"] if sesion["rol"] == "Administrador" else []

    ctx = _ctx_base(
        request,
        sesion,
        "arqueo",
        "Arqueo de Caja por Sede",
        "Desglose completo de ingresos por los 4 medios de pago y modalidad de atención",
    )
    ctx.update(
        {
            "desglose": desglose,
            "resumen": resumen,
            "sedes": sedes,
            "filtro_sede": suc,
            "periodo": periodo,
            "fecha_desde": f_ini or "",
            "fecha_hasta": f_fin or "",
            "ventas_sede": ventas_sede,
        }
    )
    return templates.TemplateResponse(request, "arqueo.html", ctx)


@app.get("/pos/ventas/exportar.csv")
def exportar_ventas_csv(request: Request, id_sucursal: int = Query(0)):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    filas = controlador.buscar_ventas(id_sucursal, None, None, "Todos", 0, "")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["N°", "Comprobante", "Tipo", "Canal", "Fecha", "Cliente", "Cajero", "Sede", "Medio de Pago", "Total (S/)"])
    for f in filas:
        writer.writerow(list(f))
    buf.seek(0)
    return StreamingResponse(
        iter(["\ufeff" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ventas_polo_norte.csv"},
    )


# =====================================================================
# CATÁLOGO (PRODUCTOS, TOPPINGS Y RECETAS / ESCANDALLOS)
# =====================================================================

@app.get("/catalogo", response_class=HTMLResponse)
def vista_catalogo(
    request: Request,
    tab: str = Query("productos"),
    q: str = Query(""),
    id_producto_receta: int = Query(1),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir

    productos = controlador.listar_productos(q if tab == "productos" else "")
    toppings = controlador.listar_toppings(q if tab == "toppings" else "")
    matriz_pt = controlador.listar_matriz_producto_topping() if tab == "toppings" else []
    recetas = controlador.listar_recetas() if tab == "recetas" else []
    detalle_receta = controlador.obtener_detalle_receta(id_producto_receta) if tab == "recetas" else []
    insumos_all = controlador.listar_insumos("") if tab == "recetas" else []

    ctx = _ctx_base(
        request,
        sesion,
        "catalogo",
        "Catálogo de Productos, Toppings y Recetas",
        "Precios oficiales sincronizados en las 3 sedes y fichas técnicas de preparación",
    )
    ctx.update(
        {
            "tab": tab,
            "q": q,
            "productos": productos,
            "toppings": toppings,
            "matriz_pt": matriz_pt,
            "recetas": recetas,
            "id_producto_receta": id_producto_receta,
            "detalle_receta": detalle_receta,
            "insumos_all": insumos_all,
        }
    )
    return templates.TemplateResponse(request, "catalogo.html", ctx)


@app.post("/catalogo/productos/crear")
def crear_producto(
    request: Request,
    nom_producto: str = Form(...),
    descripcion: str = Form(""),
    precio_venta: float = Form(...),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.insertar_producto(nom_producto, descripcion, precio_venta, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/catalogo?tab=productos", status_code=303)


@app.post("/catalogo/productos/{id_producto}/editar")
def editar_producto(
    request: Request,
    id_producto: int,
    nom_producto: str = Form(...),
    descripcion: str = Form(""),
    precio_venta: float = Form(...),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.actualizar_producto(id_producto, nom_producto, descripcion, precio_venta, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/catalogo?tab=productos", status_code=303)


@app.post("/catalogo/productos/{id_producto}/eliminar")
def borrar_producto(request: Request, id_producto: int):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.eliminar_producto(id_producto, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/catalogo?tab=productos", status_code=303)


@app.post("/catalogo/toppings/crear")
def crear_topping(request: Request, nom_topping: str = Form(...), precio_agregado: float = Form(...)):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.insertar_topping(nom_topping, precio_agregado, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/catalogo?tab=toppings", status_code=303)


@app.post("/catalogo/toppings/{id_topping}/editar")
def editar_topping(request: Request, id_topping: int, nom_topping: str = Form(...), precio_agregado: float = Form(...)):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.actualizar_topping(id_topping, nom_topping, precio_agregado, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/catalogo?tab=toppings", status_code=303)


@app.post("/catalogo/toppings/{id_topping}/eliminar")
def borrar_topping(request: Request, id_topping: int):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.eliminar_topping(id_topping)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/catalogo?tab=toppings", status_code=303)


@app.post("/catalogo/toppings/asignar")
def asignar_topping_producto(
    request: Request,
    id_producto: int = Form(...),
    id_topping: int = Form(...),
    accion: str = Form("AGREGAR"),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.gestionar_producto_topping(id_producto, id_topping, accion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/catalogo?tab=toppings", status_code=303)


@app.post("/catalogo/recetas/guardar")
def guardar_receta(
    request: Request,
    id_producto: int = Form(...),
    id_insumo: int = Form(...),
    cantidad_requerida: float = Form(...),
    marg_error: float = Form(0.0),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.guardar_detalle_receta(id_producto, id_insumo, cantidad_requerida, marg_error)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse(f"/catalogo?tab=recetas&id_producto_receta={id_producto}", status_code=303)


@app.post("/catalogo/recetas/eliminar")
def quitar_ingrediente_receta(
    request: Request,
    id_producto: int = Form(...),
    id_insumo: int = Form(...),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.eliminar_detalle_receta(id_producto, id_insumo)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse(f"/catalogo?tab=recetas&id_producto_receta={id_producto}", status_code=303)


# =====================================================================
# ALMACÉN, CONTROL SANITARIO, PROVEEDORES Y COMPRAS
# =====================================================================

@app.get("/almacen", response_class=HTMLResponse)
def vista_almacen(
    request: Request,
    tab: str = Query("insumos"),
    q: str = Query(""),
    id_proveedor: int = Query(0),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir

    resumen_san = controlador.resumen_sanitario_insumos()
    insumos = controlador.listar_insumos(q if tab == "insumos" else "")
    unidades = controlador.listar_unidades_medida()
    almacenes = controlador.listar_almacenes_sucursales()
    proveedores = controlador.listar_proveedores(q if tab == "proveedores" else "")
    compras = controlador.listar_compras_abastecimiento(id_proveedor, None, None) if tab == "compras" else []

    ctx = _ctx_base(
        request,
        sesion,
        "almacen",
        "Almacén, Control Sanitario y Abastecimiento",
        "Monitoreo de vencimientos de insumos, capacidad por sede, proveedores y lotes de compra",
    )
    ctx.update(
        {
            "tab": tab,
            "q": q,
            "resumen_san": resumen_san,
            "insumos": insumos,
            "unidades": unidades,
            "almacenes": almacenes,
            "proveedores": proveedores,
            "compras": compras,
            "filtro_proveedor": id_proveedor,
        }
    )
    return templates.TemplateResponse(request, "almacen.html", ctx)


@app.post("/almacen/insumos/crear")
def crear_insumo(
    request: Request,
    id_unidad_medida: int = Form(...),
    nombre_insumo: str = Form(...),
    unidad_medida: str = Form(...),
    es_perecible: int = Form(0),
    f_vencimiento: str = Form(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.insertar_insumo(
        id_unidad_medida, nombre_insumo, unidad_medida, es_perecible, f_vencimiento, sesion=sesion
    )
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/almacen?tab=insumos", status_code=303)


@app.post("/almacen/insumos/{id_insumo}/editar")
def editar_insumo(
    request: Request,
    id_insumo: int,
    id_unidad_medida: int = Form(...),
    nombre_insumo: str = Form(...),
    unidad_medida: str = Form(...),
    es_perecible: int = Form(0),
    f_vencimiento: str = Form(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.actualizar_insumo(
        id_insumo, id_unidad_medida, nombre_insumo, unidad_medida, es_perecible, f_vencimiento, sesion=sesion
    )
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/almacen?tab=insumos", status_code=303)


@app.post("/almacen/insumos/{id_insumo}/eliminar")
def borrar_insumo(request: Request, id_insumo: int):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.eliminar_insumo(id_insumo, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/almacen?tab=insumos", status_code=303)


@app.post("/almacen/sedes/{id_almacen}/actualizar")
def actualizar_almacen_sede(request: Request, id_almacen: int, cantidad_disponible: int = Form(...)):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.actualizar_almacen_sucursal(id_almacen, cantidad_disponible)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/almacen?tab=sedes", status_code=303)


@app.post("/almacen/proveedores/guardar")
def guardar_proveedor(
    request: Request,
    id_proveedor: int = Form(0),
    razon_social: str = Form(...),
    ruc: str = Form(...),
    telefono: str = Form(...),
    email: str = Form(""),
    persona_natural: int = Form(0),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.guardar_proveedor(id_proveedor, razon_social, ruc, telefono, email, persona_natural, 2)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/almacen?tab=proveedores", status_code=303)


@app.post("/almacen/compras/registrar")
def registrar_compra(
    request: Request,
    id_proveedor: int = Form(...),
    id_insumo: int = Form(...),
    cantidad: int = Form(...),
    precio_unitario: float = Form(...),
    fecha_vencimiento: str = Form(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "AsistenteLogistico"))
    if redir:
        return redir
    ok, msg = controlador.registrar_pedido_y_compra(
        id_proveedor, id_insumo, cantidad, precio_unitario, fecha_vencimiento, sesion=sesion
    )
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/almacen?tab=compras", status_code=303)


# =====================================================================
# DIRECTORIO DE CLIENTES Y MINI-CRM
# =====================================================================

@app.get("/clientes", response_class=HTMLResponse)
def vista_clientes(request: Request, q: str = Query(""), ver: int = Query(0)):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir
    clientes = controlador.listar_clientes(q)
    perfil_resumen, perfil_ventas = (controlador.perfil_cliente_historial(ver) if ver > 0 else (None, []))

    ctx = _ctx_base(
        request,
        sesion,
        "clientes",
        "Directorio de Clientes",
        "Registro comercial e historial individual de consumo en las 3 sedes",
    )
    ctx.update(
        {
            "clientes": clientes,
            "q": q,
            "perfil_resumen": perfil_resumen,
            "perfil_ventas": perfil_ventas,
        }
    )
    return templates.TemplateResponse(request, "clientes.html", ctx)


@app.post("/clientes/crear")
def crear_cliente(
    request: Request,
    nombres: str = Form(...),
    ap_paterno: str = Form(...),
    ap_materno: str = Form(""),
    celular: str = Form(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir
    ok, msg = controlador.insertar_cliente(nombres, ap_paterno, ap_materno, celular)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/clientes", status_code=303)


@app.post("/clientes/{id_cliente}/editar")
def editar_cliente(
    request: Request,
    id_cliente: int,
    nombres: str = Form(...),
    ap_paterno: str = Form(...),
    ap_materno: str = Form(""),
    celular: str = Form(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "Multifuncional"))
    if redir:
        return redir
    ok, msg = controlador.actualizar_cliente(id_cliente, nombres, ap_paterno, ap_materno, celular)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/clientes", status_code=303)


@app.post("/clientes/{id_cliente}/eliminar")
def borrar_cliente(request: Request, id_cliente: int):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.eliminar_cliente(id_cliente)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/clientes", status_code=303)


# =====================================================================
# PERSONAL, SEDES (RRHH) Y CONTROL DE ACCESOS (GERENCIA)
# =====================================================================

@app.get("/personal", response_class=HTMLResponse)
def vista_personal(request: Request, q: str = Query("")):
    sesion, redir = _exigir_roles(request, ("Administrador", "RecursosHumanos"))
    if redir:
        return redir
    empleados = controlador.listar_empleados(q)
    sedes = controlador.listar_almacenes_sucursales()
    roles = controlador.catalogo_roles()
    desempeno = controlador.reporte_desempeno_empleados(0, None, None)
    credenciales = controlador.listar_usuarios_credenciales() if sesion["rol"] == "Administrador" else []

    ctx = _ctx_base(
        request,
        sesion,
        "personal",
        "Personal y Sedes",
        "Nómina por sucursal, desempeño operativo en caja y gestión de accesos administrativos",
    )
    ctx.update(
        {
            "empleados": empleados,
            "sedes": sedes,
            "roles": roles,
            "desempeno": desempeno,
            "credenciales": credenciales,
            "q": q,
        }
    )
    return templates.TemplateResponse(request, "personal.html", ctx)


@app.post("/personal/crear")
def crear_empleado(
    request: Request,
    nombres: str = Form(...),
    ap_paterno: str = Form(...),
    ap_materno: str = Form(""),
    id_sucursal: int = Form(...),
    id_rol: int = Form(...),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "RecursosHumanos"))
    if redir:
        return redir
    ok, msg = controlador.insertar_empleado(nombres, ap_paterno, ap_materno, id_sucursal, id_rol, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/personal", status_code=303)


@app.post("/personal/{id_empleado}/editar")
def editar_empleado(
    request: Request,
    id_empleado: int,
    nombres: str = Form(...),
    ap_paterno: str = Form(...),
    ap_materno: str = Form(""),
    id_sucursal: int = Form(...),
    id_rol: int = Form(...),
):
    sesion, redir = _exigir_roles(request, ("Administrador", "RecursosHumanos"))
    if redir:
        return redir
    ok, msg = controlador.actualizar_empleado(
        id_empleado, nombres, ap_paterno, ap_materno, id_sucursal, id_rol, sesion=sesion
    )
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/personal", status_code=303)


@app.post("/personal/{id_empleado}/eliminar")
def borrar_empleado(request: Request, id_empleado: int):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.eliminar_empleado(id_empleado, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/personal", status_code=303)


@app.post("/personal/credencial")
def asignar_credencial(
    request: Request,
    id_empleado: int = Form(...),
    usuario: str = Form(...),
    password: str = Form(""),
    confirmar_password: str = Form(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.asignar_credencial_empleado(
        id_empleado, usuario, password, confirmar_password, sesion=sesion
    )
    _fijar_flash(request, "ok" if ok else "err", msg)
    return RedirectResponse("/personal", status_code=303)


@app.post("/personal/reactivar")
def reactivar_cuenta(request: Request, usuario: str = Form(...), origen: str = Form("/personal")):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    ok, msg = controlador.restablecer_bloqueo_usuario(usuario, sesion=sesion)
    _fijar_flash(request, "ok" if ok else "err", msg)
    destino = origen if origen in ("/personal", "/dashboard") else "/personal"
    return RedirectResponse(destino, status_code=303)


# =====================================================================
# HISTORIAL DE OPERACIONES Y AUDITORÍA (100% LENGUAJE COMERCIAL)
# =====================================================================

@app.get("/historial", response_class=HTMLResponse)
def vista_historial(
    request: Request,
    accion: str = Query("Todos"),
    modulo: str = Query("Todos"),
    fecha_desde: str = Query(""),
    fecha_hasta: str = Query(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    eventos = controlador.listar_bitacora_comercial(accion, modulo, fecha_desde or None, fecha_hasta or None)

    ctx = _ctx_base(
        request,
        sesion,
        "historial",
        "Historial de Operaciones",
        "Trazabilidad automática de accesos, ventas, cambios de precios, insumos y personal",
    )
    ctx.update(
        {
            "eventos": eventos,
            "filtro_accion": accion,
            "filtro_modulo": modulo,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        }
    )
    return templates.TemplateResponse(request, "historial.html", ctx)


@app.get("/historial/exportar.csv")
def exportar_historial_csv(
    request: Request,
    accion: str = Query("Todos"),
    modulo: str = Query("Todos"),
    fecha_desde: str = Query(""),
    fecha_hasta: str = Query(""),
):
    sesion, redir = _exigir_roles(request, ("Administrador",))
    if redir:
        return redir
    eventos = controlador.listar_bitacora_comercial(accion, modulo, fecha_desde or None, fecha_hasta or None)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["N° Evento", "Fecha y Hora", "Usuario", "Área", "Categoría", "Evento", "Módulo", "Detalle de la Operación"])
    for ev in eventos:
        writer.writerow(list(ev))
    buf.seek(0)
    return StreamingResponse(
        iter(["\ufeff" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=historial_polo_norte.csv"},
    )
