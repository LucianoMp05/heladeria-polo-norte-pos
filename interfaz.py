# interfaz.py
# Interfaz Gráfica Comercial — Heladería Polo Norte
# Diseño limpio orientado al usuario final (sin jerga técnica de base de datos)
# Toda la lógica y cálculos son ejecutados por MySQL mediante controlador.py

import sys
sys.dont_write_bytecode = True

import tkinter as tk
from tkinter import ttk, messagebox
from conexion import probar_conexion
import controlador


class HeladeriaApp:
    def __init__(self, root, usuario_autenticado="admin", rango_rol="Administrador", callback_logout=None):
        self.root = root
        self.usuario_actual = usuario_autenticado
        self.rango_rol = rango_rol
        self.callback_logout = callback_logout
        self.es_admin = (self.rango_rol == "Administrador")

        sesion = controlador.obtener_sesion_activa()
        self.id_sucursal_activa = sesion.get("id_sucursal")
        self.nombre_sucursal_activa = sesion.get("nombre_sucursal") or "Todas las Sedes (Central)"
        self.persona_activa = sesion.get("persona") or self.usuario_actual

        etiquetas_rol = {
            "Administrador": "Gerencia General",
            "RecursosHumanos": "Recursos Humanos",
            "AsistenteLogistico": "Logística y Almacén",
            "Multifuncional": f"Caja Diaria ({self.nombre_sucursal_activa})"
        }
        self.etiqueta_rol_visible = etiquetas_rol.get(self.rango_rol, self.rango_rol)

        self.root.title(
            f"Heladería Polo Norte — {self.persona_activa} | {self.etiqueta_rol_visible}"
        )
        self.root.geometry("1260x740")
        self.root.minsize(1120, 660)
        self.root.configure(bg="#f1f5f9")

        self._configurar_estilos()
        self._construir_encabezado()
        self._construir_barra_contexto()
        self._construir_notebook_por_rol()
        self._construir_barra_estado()

    def _configurar_estilos(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("TNotebook", background="#f1f5f9", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[16, 9])
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#0f172a"), ("!selected", "#e2e8f0")],
            foreground=[("selected", "#ffffff"), ("!selected", "#334155")]
        )

        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#1e3a8a",
            foreground="#ffffff",
            padding=6
        )
        style.configure(
            "Treeview",
            font=("Segoe UI", 9),
            rowheight=27,
            background="#ffffff",
            fieldbackground="#ffffff"
        )
        style.map("Treeview", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])

    # =====================================================================
    # ENCABEZADO COMERCIAL Y BARRA DE CONTEXTO DE SEDE
    # =====================================================================

    def _construir_encabezado(self):
        header = tk.Frame(self.root, bg="#0f172a", height=64)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        bloque_marca = tk.Frame(header, bg="#0f172a")
        bloque_marca.pack(side=tk.LEFT, padx=18)

        tk.Label(
            bloque_marca,
            text="🍦 HELADERÍA POLO NORTE",
            font=("Segoe UI", 14, "bold"),
            bg="#0f172a",
            fg="#ffffff"
        ).pack(anchor="w")

        tk.Label(
            bloque_marca,
            text=f"📍 Ubicación activa: {self.nombre_sucursal_activa}",
            font=("Segoe UI", 9),
            bg="#0f172a",
            fg="#38bdf8"
        ).pack(anchor="w")

        btn_logout = tk.Button(
            header,
            text="Cambiar Turno / Salir",
            font=("Segoe UI", 9, "bold"),
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._cerrar_sesion
        )
        btn_logout.pack(side=tk.RIGHT, padx=(8, 18))

        if self.es_admin:
            btn_desbloquear = tk.Button(
                header,
                text="Desbloquear Accesos",
                font=("Segoe UI", 9, "bold"),
                bg="#f59e0b",
                fg="#ffffff",
                activebackground="#d97706",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=12,
                pady=6,
                cursor="hand2",
                command=self._abrir_reactivacion_cuentas
            )
            btn_desbloquear.pack(side=tk.RIGHT, padx=6)

        lbl_usuario = tk.Label(
            header,
            text=f"👤 {self.persona_activa}   •   {self.etiqueta_rol_visible}",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#e2e8f0",
            padx=14,
            pady=6
        )
        lbl_usuario.pack(side=tk.RIGHT, padx=8)

    def _construir_barra_contexto(self):
        mensajes_area = {
            "Administrador": (
                "#dcfce7", "#166534",
                "Modo Gerencia General: Acceso completo a sucursales, catálogo de productos, almacén, personal e historial."
            ),
            "RecursosHumanos": (
                "#fef3c7", "#92400e",
                "Área de Recursos Humanos: Gestión de colaboradores, asignación de sucursales y cargos."
            ),
            "AsistenteLogistico": (
                "#e0f2fe", "#075985",
                "Área de Logística y Almacén: Administración de productos y control de vencimiento de insumos."
            ),
            "Multifuncional": (
                "#f3e8ff", "#6b21a8",
                f"Operación de Caja Diaria — {self.nombre_sucursal_activa}: Atención de pedidos, toppings y arqueo de turno."
            ),
        }
        color_bg, color_fg, texto_area = mensajes_area.get(
            self.rango_rol, ("#e2e8f0", "#1e293b", f"Área activa: {self.etiqueta_rol_visible}")
        )

        franja = tk.Frame(self.root, bg=color_bg, height=30)
        franja.pack(fill=tk.X, side=tk.TOP)
        franja.pack_propagate(False)

        tk.Label(
            franja,
            text=f"●  {texto_area}",
            font=("Segoe UI", 9, "bold"),
            bg=color_bg,
            fg=color_fg
        ).pack(side=tk.LEFT, padx=18)

    def _construir_barra_estado(self):
        barra = tk.Frame(self.root, bg="#e2e8f0", height=28)
        barra.pack(fill=tk.X, side=tk.BOTTOM)
        barra.pack_propagate(False)

        self.var_estado = tk.StringVar(
            value=f"Heladería Polo Norte — Sesión activa: {self.persona_activa} ({self.nombre_sucursal_activa})"
        )
        tk.Label(
            barra,
            textvariable=self.var_estado,
            font=("Segoe UI", 9),
            bg="#e2e8f0",
            fg="#334155"
        ).pack(side=tk.LEFT, padx=16)

    def _cerrar_sesion(self):
        if self.callback_logout:
            self.callback_logout()
        else:
            self.root.destroy()

    def _abrir_reactivacion_cuentas(self):
        usuarios = controlador.listar_usuarios_credenciales()
        bloqueados = [u[1] for u in usuarios if u[5] == "Bloqueado" or int(u[4]) > 0]
        if not bloqueados:
            messagebox.showinfo("Accesos Activos", "Todas las cuentas del personal se encuentran habilitadas.")
            return
        for usr in bloqueados:
            controlador.restablecer_bloqueo_usuario(usr)
        self.cargar_bitacora()
        messagebox.showinfo(
            "Accesos Restablecidos",
            f"Se han desbloqueado las siguientes cuentas: {', '.join(bloqueados)}"
        )

    # =====================================================================
    # MÓDULOS VISIBLES SEGÚN EL PERFIL ACTIVO
    # =====================================================================

    def _construir_notebook_por_rol(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        ver_clientes = self.rango_rol in ("Administrador", "Multifuncional")
        ver_productos = self.rango_rol in ("Administrador", "AsistenteLogistico")
        ver_insumos = self.rango_rol in ("Administrador", "AsistenteLogistico")
        ver_ventas = self.rango_rol in ("Administrador", "Multifuncional")
        ver_rrhh = self.rango_rol in ("Administrador", "RecursosHumanos")

        if ver_ventas:
            self.tab_ventas = tk.Frame(self.notebook, bg="#f1f5f9")
            self.notebook.add(self.tab_ventas, text="  🛒 Punto de Venta (Caja Diaria)  ")
            self._armar_tab_ventas()
            self.cargar_ventas()

        if ver_clientes:
            self.tab_clientes = tk.Frame(self.notebook, bg="#f1f5f9")
            self.notebook.add(self.tab_clientes, text="  👥 Directorio de Clientes  ")
            self._armar_tab_clientes()
            self.cargar_clientes()

        if ver_productos:
            self.tab_productos = tk.Frame(self.notebook, bg="#f1f5f9")
            self.notebook.add(self.tab_productos, text="  🍨 Catálogo de Productos  ")
            self._armar_tab_productos()
            self.cargar_productos()

        if ver_insumos:
            self.tab_insumos = tk.Frame(self.notebook, bg="#f1f5f9")
            self.notebook.add(self.tab_insumos, text="  📦 Almacén e Insumos  ")
            self._armar_tab_insumos()
            self.cargar_insumos()

        if ver_rrhh:
            self.tab_rrhh = tk.Frame(self.notebook, bg="#f1f5f9")
            self.notebook.add(self.tab_rrhh, text="  🪪 Personal y Sedes  ")
            self._armar_tab_rrhh()
            self.cargar_empleados()

        if self.es_admin:
            self.tab_auditoria = tk.Frame(self.notebook, bg="#f1f5f9")
            self.notebook.add(self.tab_auditoria, text="  🛡️ Historial de Operaciones  ")
            self._armar_tab_auditoria()
            self.cargar_bitacora()

    # =====================================================================
    # MÓDULO: DIRECTORIO DE CLIENTES
    # =====================================================================

    def _armar_tab_clientes(self):
        panel_izq = tk.LabelFrame(
            self.tab_clientes, text=" Datos del Cliente ", font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg="#0f172a", padx=16, pady=14
        )
        panel_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 8), pady=10)

        self.var_cli_id = tk.StringVar()
        self.var_cli_nombres = tk.StringVar()
        self.var_cli_paterno = tk.StringVar()
        self.var_cli_materno = tk.StringVar()
        self.var_cli_celular = tk.StringVar()

        campos = [
            ("Código de Cliente:", self.var_cli_id, True),
            ("Nombres:", self.var_cli_nombres, False),
            ("Apellido Paterno:", self.var_cli_paterno, False),
            ("Apellido Materno:", self.var_cli_materno, False),
            ("Teléfono / Celular:", self.var_cli_celular, False),
        ]

        for idx, (etiqueta, variable, solo_lectura) in enumerate(campos):
            tk.Label(panel_izq, text=etiqueta, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(
                row=idx * 2, column=0, sticky="w", pady=(6, 2)
            )
            estado = "readonly" if solo_lectura else "normal"
            entry = ttk.Entry(panel_izq, textvariable=variable, width=32, state=estado, font=("Segoe UI", 9))
            entry.grid(row=idx * 2 + 1, column=0, pady=(0, 6), ipady=3)

        frame_btns = tk.Frame(panel_izq, bg="#ffffff")
        frame_btns.grid(row=10, column=0, pady=14)

        tk.Button(frame_btns, text="Registrar Cliente", width=14, bg="#16a34a", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.guardar_cliente).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(frame_btns, text="Guardar Cambios", width=14, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.modificar_cliente).grid(row=0, column=1, padx=4, pady=4)

        if self.es_admin:
            tk.Button(frame_btns, text="Eliminar", width=14, bg="#dc2626", fg="white", font=("Segoe UI", 9, "bold"),
                      relief=tk.FLAT, cursor="hand2", command=self.borrar_cliente).grid(row=1, column=0, padx=4, pady=4)
            col_limpiar = 1
        else:
            col_limpiar = 0

        tk.Button(frame_btns, text="Limpiar Campos", width=14, bg="#64748b", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.limpiar_form_cliente).grid(
                      row=1, column=col_limpiar, columnspan=1 if self.es_admin else 2, padx=4, pady=4
                  )

        panel_der = tk.LabelFrame(
            self.tab_clientes, text=" Cartera de Clientes Registrados ", font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg="#0f172a", padx=12, pady=10
        )
        panel_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 10), pady=10)

        barra_busq = tk.Frame(panel_der, bg="#ffffff")
        barra_busq.pack(fill=tk.X, pady=(0, 8))

        tk.Label(barra_busq, text="Buscar cliente (Nombre o Celular):", bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.var_busq_cliente = tk.StringVar()
        entry_busq = ttk.Entry(barra_busq, textvariable=self.var_busq_cliente, width=30)
        entry_busq.pack(side=tk.LEFT, padx=8)
        entry_busq.bind("<Return>", lambda _e: self.cargar_clientes())
        tk.Button(barra_busq, text="Buscar", bg="#1e3a8a", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, padx=12, cursor="hand2", command=self.cargar_clientes).pack(side=tk.LEFT, padx=2)
        tk.Button(barra_busq, text="Ver Todos", bg="#475569", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, padx=12, cursor="hand2", command=lambda: (self.var_busq_cliente.set(""), self.cargar_clientes())).pack(side=tk.LEFT, padx=4)

        columnas = ("Código", "Nombres", "Apellido Paterno", "Apellido Materno", "Celular")
        self.tree_clientes = ttk.Treeview(panel_der, columns=columnas, show="headings")
        for col, ancho in zip(columnas, (70, 170, 160, 160, 120)):
            self.tree_clientes.heading(col, text=col)
            self.tree_clientes.column(col, width=ancho, anchor="center" if col in ("Código", "Celular") else "w")

        scroll_y = ttk.Scrollbar(panel_der, orient=tk.VERTICAL, command=self.tree_clientes.yview)
        self.tree_clientes.configure(yscrollcommand=scroll_y.set)
        self.tree_clientes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_clientes.bind("<<TreeviewSelect>>", self._seleccionar_fila_cliente)

    def cargar_clientes(self):
        if not hasattr(self, "tree_clientes"):
            return
        for item in self.tree_clientes.get_children():
            self.tree_clientes.delete(item)
        for fila in controlador.listar_clientes(self.var_busq_cliente.get()):
            self.tree_clientes.insert("", tk.END, values=fila)

    def _seleccionar_fila_cliente(self, _event):
        sel = self.tree_clientes.selection()
        if sel:
            v = self.tree_clientes.item(sel[0], "values")
            self.var_cli_id.set(v[0])
            self.var_cli_nombres.set(v[1])
            self.var_cli_paterno.set(v[2])
            self.var_cli_materno.set(v[3])
            self.var_cli_celular.set(v[4])

    def limpiar_form_cliente(self):
        self.var_cli_id.set("")
        self.var_cli_nombres.set("")
        self.var_cli_paterno.set("")
        self.var_cli_materno.set("")
        self.var_cli_celular.set("")
        self.tree_clientes.selection_remove(self.tree_clientes.selection())

    def guardar_cliente(self):
        if not self.var_cli_nombres.get().strip() or not self.var_cli_paterno.get().strip():
            messagebox.showwarning("Datos Incompletos", "Ingrese al menos los Nombres y el Apellido Paterno del cliente.")
            return
        ok, msg = controlador.insertar_cliente(
            self.var_cli_nombres.get(),
            self.var_cli_paterno.get(),
            self.var_cli_materno.get(),
            self.var_cli_celular.get()
        )
        if ok:
            messagebox.showinfo("Cliente Registrado", msg)
            self.limpiar_form_cliente()
            self.cargar_clientes()
            self._refrescar_combos_venta()
        else:
            messagebox.showerror("Atención", msg)

    def modificar_cliente(self):
        if not self.var_cli_id.get():
            messagebox.showwarning("Seleccione un Cliente", "Seleccione un cliente de la lista para actualizar sus datos.")
            return
        ok, msg = controlador.actualizar_cliente(
            self.var_cli_id.get(),
            self.var_cli_nombres.get(),
            self.var_cli_paterno.get(),
            self.var_cli_materno.get(),
            self.var_cli_celular.get()
        )
        if ok:
            messagebox.showinfo("Datos Actualizados", msg)
            self.limpiar_form_cliente()
            self.cargar_clientes()
            self._refrescar_combos_venta()
        else:
            messagebox.showerror("Atención", msg)

    def borrar_cliente(self):
        if not self.var_cli_id.get():
            messagebox.showwarning("Seleccione un Cliente", "Seleccione un cliente de la lista para retirarlo.")
            return
        if messagebox.askyesno("Confirmar", f"¿Desea retirar al cliente #{self.var_cli_id.get()} del directorio?"):
            ok, msg = controlador.eliminar_cliente(self.var_cli_id.get())
            if ok:
                messagebox.showinfo("Cliente Retirado", msg)
                self.limpiar_form_cliente()
                self.cargar_clientes()
                self._refrescar_combos_venta()
            else:
                messagebox.showwarning("No Permitido", msg)

    # =====================================================================
    # MÓDULO: CATÁLOGO DE PRODUCTOS
    # =====================================================================

    def _armar_tab_productos(self):
        panel_prod_form = tk.LabelFrame(
            self.tab_productos, text=" Ficha de Producto / Helado ", font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg="#0f172a", padx=15, pady=15
        )
        panel_prod_form.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 8), pady=10)

        self.var_prod_id = tk.StringVar()
        self.var_prod_nombre = tk.StringVar()
        self.var_prod_desc = tk.StringVar()
        self.var_prod_precio = tk.StringVar()

        campos_prod = [
            ("Código:", self.var_prod_id, True),
            ("Nombre del Producto:", self.var_prod_nombre, False),
            ("Descripción / Presentación:", self.var_prod_desc, False),
            ("Precio Oficial de Venta (S/):", self.var_prod_precio, False),
        ]

        for idx, (etiqueta, variable, solo_lectura) in enumerate(campos_prod):
            tk.Label(panel_prod_form, text=etiqueta, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").grid(
                row=idx * 2, column=0, sticky="w", pady=(6, 2)
            )
            estado = "readonly" if solo_lectura else "normal"
            ttk.Entry(panel_prod_form, textvariable=variable, width=34, state=estado, font=("Segoe UI", 9)).grid(
                row=idx * 2 + 1, column=0, pady=(0, 6), ipady=3
            )

        frame_btns_p = tk.Frame(panel_prod_form, bg="#ffffff")
        frame_btns_p.grid(row=8, column=0, pady=16)

        tk.Button(frame_btns_p, text="Agregar Producto", width=15, bg="#16a34a", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.guardar_producto).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(frame_btns_p, text="Actualizar Precio", width=15, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.modificar_producto).grid(row=0, column=1, padx=4, pady=4)

        if self.es_admin:
            tk.Button(frame_btns_p, text="Eliminar", width=15, bg="#dc2626", fg="white", font=("Segoe UI", 9, "bold"),
                      relief=tk.FLAT, cursor="hand2", command=self.borrar_producto).grid(row=1, column=0, padx=4, pady=4)
            col_limp_p = 1
        else:
            col_limp_p = 0

        tk.Button(frame_btns_p, text="Limpiar", width=15, bg="#64748b", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.limpiar_form_producto).grid(
                      row=1, column=col_limp_p, columnspan=1 if self.es_admin else 2, padx=4, pady=4
                  )

        panel_tabla_p = tk.LabelFrame(
            self.tab_productos, text=" Catálogo de Helados, Frappés y Presentaciones ", font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg="#0f172a", padx=12, pady=10
        )
        panel_tabla_p.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 10), pady=10)

        barra_busq = tk.Frame(panel_tabla_p, bg="#ffffff")
        barra_busq.pack(fill=tk.X, pady=(0, 8))
        tk.Label(barra_busq, text="Filtrar producto:", bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.var_busq_prod = tk.StringVar()
        ttk.Entry(barra_busq, textvariable=self.var_busq_prod, width=30).pack(side=tk.LEFT, padx=8)
        tk.Button(barra_busq, text="Buscar", bg="#1e3a8a", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, padx=12, cursor="hand2", command=self.cargar_productos).pack(side=tk.LEFT, padx=2)
        tk.Button(barra_busq, text="Mostrar Todos", bg="#475569", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, padx=12, cursor="hand2", command=lambda: (self.var_busq_prod.set(""), self.cargar_productos())).pack(side=tk.LEFT, padx=4)

        frame_tp = tk.Frame(panel_tabla_p, bg="#ffffff")
        frame_tp.pack(fill=tk.BOTH, expand=True)

        columnas_p = ("Código", "Producto", "Descripción / Presentación", "Precio Oficial (S/)")
        self.tree_productos = ttk.Treeview(frame_tp, columns=columnas_p, show="headings")
        for col, ancho in zip(columnas_p, (65, 210, 350, 125)):
            self.tree_productos.heading(col, text=col)
            self.tree_productos.column(col, width=ancho, anchor="center" if col in ("Código", "Precio Oficial (S/)") else "w")

        scroll_p = ttk.Scrollbar(frame_tp, orient=tk.VERTICAL, command=self.tree_productos.yview)
        self.tree_productos.configure(yscrollcommand=scroll_p.set)
        self.tree_productos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_p.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_productos.bind("<<TreeviewSelect>>", self._seleccionar_fila_producto)

    def cargar_productos(self):
        if not hasattr(self, "tree_productos"):
            return
        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)
        for fila in controlador.listar_productos(self.var_busq_prod.get()):
            self.tree_productos.insert("", tk.END, values=fila)

    def _seleccionar_fila_producto(self, _event):
        sel = self.tree_productos.selection()
        if sel:
            v = self.tree_productos.item(sel[0], "values")
            self.var_prod_id.set(v[0])
            self.var_prod_nombre.set(v[1])
            self.var_prod_desc.set(v[2])
            self.var_prod_precio.set(v[3])

    def limpiar_form_producto(self):
        self.var_prod_id.set("")
        self.var_prod_nombre.set("")
        self.var_prod_desc.set("")
        self.var_prod_precio.set("")
        self.tree_productos.selection_remove(self.tree_productos.selection())

    def guardar_producto(self):
        if not self.var_prod_nombre.get().strip() or not self.var_prod_precio.get().strip():
            messagebox.showwarning("Campos Incompletos", "Complete el nombre y el precio oficial del producto.")
            return
        ok, msg = controlador.insertar_producto(
            self.var_prod_nombre.get(), self.var_prod_desc.get(), self.var_prod_precio.get()
        )
        if ok:
            messagebox.showinfo("Catálogo Actualizado", msg)
            self.limpiar_form_producto()
            self.cargar_productos()
            self._refrescar_combos_venta()
            self.cargar_bitacora()
        else:
            messagebox.showerror("Atención", msg)

    def modificar_producto(self):
        if not self.var_prod_id.get():
            messagebox.showwarning("Seleccione un Producto", "Seleccione un producto de la tabla superior para actualizarlo.")
            return
        ok, msg = controlador.actualizar_producto(
            self.var_prod_id.get(), self.var_prod_nombre.get(), self.var_prod_desc.get(), self.var_prod_precio.get()
        )
        if ok:
            messagebox.showinfo("Precio Actualizado", msg)
            self.limpiar_form_producto()
            self.cargar_productos()
            self._refrescar_combos_venta()
            self.cargar_bitacora()
        else:
            messagebox.showerror("Atención", msg)

    def borrar_producto(self):
        if not self.var_prod_id.get():
            messagebox.showwarning("Seleccione un Producto", "Seleccione un producto para eliminarlo.")
            return
        if messagebox.askyesno("Confirmar", f"¿Desea retirar el producto #{self.var_prod_id.get()} del catálogo?"):
            ok, msg = controlador.eliminar_producto(self.var_prod_id.get())
            if ok:
                messagebox.showinfo("Producto Eliminado", msg)
                self.limpiar_form_producto()
                self.cargar_productos()
                self._refrescar_combos_venta()
                self.cargar_bitacora()
            else:
                messagebox.showwarning("No Permitido", msg)

    # =====================================================================
    # MÓDULO: ALMACÉN E INSUMOS (CON CONTROL DE VENCIMIENTOS)
    # =====================================================================

    def _armar_tab_insumos(self):
        panel_izq = tk.LabelFrame(
            self.tab_insumos, text=" Registro de Insumo ", font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg="#0f172a", padx=15, pady=15
        )
        panel_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 8), pady=10)

        unidades_db = controlador.listar_unidades_medida()
        self.lista_um = [f"{u[0]} - {u[1]}" for u in unidades_db] if unidades_db else ["1 - Gramos", "2 - Litros", "3 - Mililitros", "4 - Unidades"]

        self.var_ins_id = tk.StringVar()
        self.var_ins_nombre = tk.StringVar()
        self.var_ins_id_um = tk.StringVar(value=self.lista_um[0])
        self.var_ins_perecible = tk.StringVar(value="1 - Sí")
        self.var_ins_venc = tk.StringVar(value="2027-06-01")

        tk.Label(panel_izq, text="Código de Insumo:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=0, column=0, sticky="w", pady=(4, 2))
        ttk.Entry(panel_izq, textvariable=self.var_ins_id, width=32, state="readonly").grid(row=1, column=0, pady=(0, 6), ipady=3)

        tk.Label(panel_izq, text="Descripción del Insumo:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=2, column=0, sticky="w", pady=(4, 2))
        ttk.Entry(panel_izq, textvariable=self.var_ins_nombre, width=32).grid(row=3, column=0, pady=(0, 6), ipady=3)

        tk.Label(panel_izq, text="Unidad de Medida:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=4, column=0, sticky="w", pady=(4, 2))
        self.combo_um = ttk.Combobox(panel_izq, textvariable=self.var_ins_id_um, values=self.lista_um, state="readonly", width=30)
        self.combo_um.grid(row=5, column=0, pady=(0, 6), ipady=3)

        tk.Label(panel_izq, text="¿Es Perecible?:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=6, column=0, sticky="w", pady=(4, 2))
        self.combo_perecible = ttk.Combobox(panel_izq, textvariable=self.var_ins_perecible, values=["1 - Sí", "0 - No"], state="readonly", width=30)
        self.combo_perecible.grid(row=7, column=0, pady=(0, 6), ipady=3)

        tk.Label(panel_izq, text="Fecha de Caducidad (AAAA-MM-DD):", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=8, column=0, sticky="w", pady=(4, 2))
        ttk.Entry(panel_izq, textvariable=self.var_ins_venc, width=32).grid(row=9, column=0, pady=(0, 6), ipady=3)

        frame_btns = tk.Frame(panel_izq, bg="#ffffff")
        frame_btns.grid(row=10, column=0, pady=15)

        tk.Button(frame_btns, text="Registrar Insumo", width=14, bg="#16a34a", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.guardar_insumo).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(frame_btns, text="Guardar Cambios", width=14, bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.modificar_insumo).grid(row=0, column=1, padx=4, pady=4)

        if self.es_admin:
            tk.Button(frame_btns, text="Retirar", width=14, bg="#dc2626", fg="white", font=("Segoe UI", 9, "bold"),
                      relief=tk.FLAT, cursor="hand2", command=self.borrar_insumo).grid(row=1, column=0, padx=4, pady=4)
            col_limp_i = 1
        else:
            col_limp_i = 0

        tk.Button(frame_btns, text="Limpiar", width=14, bg="#64748b", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.limpiar_form_insumo).grid(
                      row=1, column=col_limp_i, columnspan=1 if self.es_admin else 2, padx=4, pady=4
                  )

        panel_der = tk.LabelFrame(
            self.tab_insumos, text=" Control de Existencias y Caducidad de Insumos ", font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg="#0f172a", padx=12, pady=10
        )
        panel_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 10), pady=10)

        barra_busq = tk.Frame(panel_der, bg="#ffffff")
        barra_busq.pack(fill=tk.X, pady=(0, 8))

        tk.Label(barra_busq, text="Buscar insumo:", bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.var_busq_ins = tk.StringVar()
        ttk.Entry(barra_busq, textvariable=self.var_busq_ins, width=28).pack(side=tk.LEFT, padx=8)
        tk.Button(barra_busq, text="Buscar", bg="#1e3a8a", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, padx=10, cursor="hand2", command=self.cargar_insumos).pack(side=tk.LEFT, padx=2)
        tk.Button(barra_busq, text="Ver Todos", bg="#475569", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, padx=10, cursor="hand2", command=lambda: (self.var_busq_ins.set(""), self.cargar_insumos())).pack(side=tk.LEFT, padx=4)

        self.lbl_alerta_insumos = tk.Label(
            barra_busq, text="", font=("Segoe UI", 8, "bold"), bg="#dcfce7", fg="#166534", padx=10, pady=3
        )
        self.lbl_alerta_insumos.pack(side=tk.RIGHT)

        columnas = ("Código", "Insumo", "Cód. UM", "Unidad", "Perecible", "Vencimiento", "Estado Sanitario")
        self.tree_insumos = ttk.Treeview(panel_der, columns=columnas, show="headings")
        for col, ancho in zip(columnas, (55, 205, 60, 105, 80, 105, 145)):
            self.tree_insumos.heading(col, text=col)
            self.tree_insumos.column(col, width=ancho, anchor="center" if col != "Insumo" else "w")

        self.tree_insumos.tag_configure("vencido", background="#fee2e2", foreground="#991b1b")
        self.tree_insumos.tag_configure("por_vencer", background="#fef3c7", foreground="#92400e")
        self.tree_insumos.tag_configure("vigente", background="#ffffff", foreground="#0f172a")

        scroll_y = ttk.Scrollbar(panel_der, orient=tk.VERTICAL, command=self.tree_insumos.yview)
        self.tree_insumos.configure(yscrollcommand=scroll_y.set)
        self.tree_insumos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_insumos.bind("<<TreeviewSelect>>", self._seleccionar_fila_insumo)

    def cargar_insumos(self):
        if not hasattr(self, "tree_insumos"):
            return
        for item in self.tree_insumos.get_children():
            self.tree_insumos.delete(item)
        registros = controlador.listar_insumos(self.var_busq_ins.get())
        for fila in registros:
            estado_san = fila[6] if len(fila) > 6 else "VIGENTE"
            if "VENCIDO" in estado_san:
                tag = "vencido"
            elif "POR VENCER" in estado_san:
                tag = "por_vencer"
            else:
                tag = "vigente"
            self.tree_insumos.insert("", tk.END, values=fila, tags=(tag,))

        resumen_san = controlador.resumen_sanitario_insumos()
        vencidos = resumen_san["vencidos"]
        por_vencer = resumen_san["por_vencer"]
        if hasattr(self, "lbl_alerta_insumos"):
            if vencidos > 0:
                self.lbl_alerta_insumos.config(
                    text=f"⚠ {vencidos} insumo(s) VENCIDO(S) — Retirar de almacén",
                    bg="#fee2e2", fg="#991b1b"
                )
            elif por_vencer > 0:
                self.lbl_alerta_insumos.config(
                    text=f"⏳ {por_vencer} insumo(s) próximos a vencer",
                    bg="#fef3c7", fg="#92400e"
                )
            else:
                self.lbl_alerta_insumos.config(
                    text="✔ Todos los insumos perecibles están vigentes",
                    bg="#dcfce7", fg="#166534"
                )

    def _seleccionar_fila_insumo(self, _event):
        sel = self.tree_insumos.selection()
        if sel:
            v = self.tree_insumos.item(sel[0], "values")
            self.var_ins_id.set(v[0])
            self.var_ins_nombre.set(v[1])
            self.var_ins_id_um.set(f"{v[2]} - {v[3]}")
            self.var_ins_perecible.set("1 - Sí" if v[4] == "Sí" else "0 - No")
            self.var_ins_venc.set(v[5])

    def limpiar_form_insumo(self):
        self.var_ins_id.set("")
        self.var_ins_nombre.set("")
        if self.lista_um:
            self.var_ins_id_um.set(self.lista_um[0])
        self.var_ins_perecible.set("1 - Sí")
        self.var_ins_venc.set("2027-06-01")
        self.tree_insumos.selection_remove(self.tree_insumos.selection())

    def guardar_insumo(self):
        if not self.var_ins_nombre.get().strip():
            messagebox.showwarning("Nombre Requerido", "Ingrese el nombre del insumo.")
            return
        partes_um = self.var_ins_id_um.get().split(" - ")
        id_um = partes_um[0]
        nom_um = partes_um[1] if len(partes_um) > 1 else "Unidades"
        es_per = self.var_ins_perecible.get().split(" - ")[0]
        ok, msg = controlador.insertar_insumo(id_um, self.var_ins_nombre.get(), nom_um, es_per, self.var_ins_venc.get())
        if ok:
            messagebox.showinfo("Insumo Registrado", msg)
            self.limpiar_form_insumo()
            self.cargar_insumos()
            self.cargar_bitacora()
        else:
            messagebox.showerror("Atención", msg)

    def modificar_insumo(self):
        if not self.var_ins_id.get():
            messagebox.showwarning("Seleccione un Insumo", "Seleccione un insumo de la tabla para actualizarlo.")
            return
        partes_um = self.var_ins_id_um.get().split(" - ")
        id_um = partes_um[0]
        nom_um = partes_um[1] if len(partes_um) > 1 else "Unidades"
        es_per = self.var_ins_perecible.get().split(" - ")[0]
        ok, msg = controlador.actualizar_insumo(
            self.var_ins_id.get(), id_um, self.var_ins_nombre.get(), nom_um, es_per, self.var_ins_venc.get()
        )
        if ok:
            messagebox.showinfo("Insumo Actualizado", msg)
            self.limpiar_form_insumo()
            self.cargar_insumos()
            self.cargar_bitacora()
        else:
            messagebox.showerror("Atención", msg)

    def borrar_insumo(self):
        if not self.var_ins_id.get():
            messagebox.showwarning("Seleccione un Insumo", "Seleccione un insumo para retirarlo.")
            return
        if messagebox.askyesno("Confirmar", f"¿Retirar el insumo #{self.var_ins_id.get()} del almacén?"):
            ok, msg = controlador.eliminar_insumo(self.var_ins_id.get())
            if ok:
                messagebox.showinfo("Insumo Retirado", msg)
                self.limpiar_form_insumo()
                self.cargar_insumos()
                self.cargar_bitacora()
            else:
                messagebox.showwarning("No Permitido", msg)

    # =====================================================================
    # MÓDULO: PUNTO DE VENTA (CAJA DIARIA POR SEDE Y TOPPINGS)
    # =====================================================================

    def _armar_tab_ventas(self):
        self.items_carrito = []
        self.mapa_precios_prod = {}

        # Panel izquierdo: Toma de Pedido
        panel_izq = tk.LabelFrame(
            self.tab_ventas,
            text=f" Toma de Pedido — {self.nombre_sucursal_activa} ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=14,
            pady=10
        )
        panel_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 6), pady=8)

        self.var_ven_comprobante = tk.StringVar()
        self.var_ven_tipo_comp = tk.StringVar(value="Boleta")
        self.var_ven_canal = tk.StringVar(value="Sede")
        self.var_ven_cliente = tk.StringVar()
        self.var_ven_empleado = tk.StringVar()
        self.var_ven_metodo = tk.StringVar()
        self.var_ven_producto = tk.StringVar()
        self.var_ven_cantidad = tk.StringVar(value="1")
        self.var_ven_precio = tk.StringVar(value="0.00")
        self.var_ven_topping = tk.StringVar()

        fila_g = 0
        frame_comp = tk.Frame(panel_izq, bg="#ffffff")
        frame_comp.grid(row=fila_g, column=0, sticky="we", pady=(2, 6))
        tk.Label(frame_comp, text="Comprobante:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=0, column=0, sticky="w")
        combo_tipo = ttk.Combobox(
            frame_comp, textvariable=self.var_ven_tipo_comp, values=["Boleta", "Factura"], state="readonly", width=9
        )
        combo_tipo.grid(row=1, column=0, padx=(0, 6), ipady=2)
        combo_tipo.bind("<<ComboboxSelected>>", self._actualizar_correlativo_sugerido)

        tk.Label(frame_comp, text="N° Correlativo:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=0, column=1, sticky="w")
        ttk.Entry(frame_comp, textvariable=self.var_ven_comprobante, width=13, state="readonly").grid(row=1, column=1, padx=(0, 6), ipady=2)

        tk.Label(frame_comp, text="Modalidad:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=0, column=2, sticky="w")
        ttk.Combobox(frame_comp, textvariable=self.var_ven_canal, values=["Sede", "Delivery"], state="readonly", width=9).grid(row=1, column=2, ipady=2)
        fila_g += 1

        tk.Label(panel_izq, text="Cliente:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=fila_g, column=0, sticky="w", pady=(2, 1))
        self.combo_ven_cliente = ttk.Combobox(panel_izq, textvariable=self.var_ven_cliente, state="readonly", width=36)
        self.combo_ven_cliente.grid(row=fila_g + 1, column=0, pady=(0, 4), ipady=2)
        fila_g += 2

        etiqueta_cajero = (
            f"Atendido por (Personal de {self.nombre_sucursal_activa}):"
            if self.id_sucursal_activa else "Atendido por (Colaborador / Sede):"
        )
        tk.Label(panel_izq, text=etiqueta_cajero, font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=fila_g, column=0, sticky="w", pady=(2, 1))
        self.combo_ven_empleado = ttk.Combobox(panel_izq, textvariable=self.var_ven_empleado, state="readonly", width=36)
        self.combo_ven_empleado.grid(row=fila_g + 1, column=0, pady=(0, 4), ipady=2)
        fila_g += 2

        tk.Label(panel_izq, text="Medio de Pago:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=fila_g, column=0, sticky="w", pady=(2, 1))
        self.combo_ven_metodo = ttk.Combobox(panel_izq, textvariable=self.var_ven_metodo, state="readonly", width=36)
        self.combo_ven_metodo.grid(row=fila_g + 1, column=0, pady=(0, 6), ipady=2)
        fila_g += 2

        ttk.Separator(panel_izq, orient="horizontal").grid(row=fila_g, column=0, sticky="we", pady=6)
        fila_g += 1

        tk.Label(
            panel_izq, text="SELECCIÓN DE PRODUCTOS Y TOPPINGS:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#1d4ed8"
        ).grid(row=fila_g, column=0, sticky="w", pady=(2, 4))
        fila_g += 1

        tk.Label(panel_izq, text="Producto y Precio Oficial:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=fila_g, column=0, sticky="w", pady=(2, 1))
        self.combo_ven_producto = ttk.Combobox(panel_izq, textvariable=self.var_ven_producto, state="readonly", width=36)
        self.combo_ven_producto.grid(row=fila_g + 1, column=0, pady=(0, 5), ipady=2)
        self.combo_ven_producto.bind("<<ComboboxSelected>>", self._actualizar_precio_producto_venta)
        fila_g += 2

        frame_cant_precio = tk.Frame(panel_izq, bg="#ffffff")
        frame_cant_precio.grid(row=fila_g, column=0, sticky="we", pady=3)
        tk.Label(frame_cant_precio, text="Cantidad:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_cant_precio, textvariable=self.var_ven_cantidad, width=14).grid(row=1, column=0, padx=(0, 12), ipady=2)
        tk.Label(frame_cant_precio, text="Precio Base (S/) [Fijo]:", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#475569").grid(row=0, column=1, sticky="w")
        ttk.Entry(frame_cant_precio, textvariable=self.var_ven_precio, width=16, state="readonly").grid(row=1, column=1, ipady=2)
        fila_g += 1

        tk.Label(panel_izq, text="Topping Adicional Opcional:", font=("Segoe UI", 8, "bold"), bg="#ffffff").grid(row=fila_g, column=0, sticky="w", pady=(4, 1))
        self.combo_ven_topping = ttk.Combobox(panel_izq, textvariable=self.var_ven_topping, state="readonly", width=36)
        self.combo_ven_topping.grid(row=fila_g + 1, column=0, pady=(0, 6), ipady=2)
        fila_g += 2

        frame_btns_carrito = tk.Frame(panel_izq, bg="#ffffff")
        frame_btns_carrito.grid(row=fila_g, column=0, pady=6)

        tk.Button(
            frame_btns_carrito,
            text="+ Agregar Producto al Pedido",
            width=30,
            bg="#2563eb",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            pady=5,
            command=self.agregar_item_carrito
        ).grid(row=0, column=0, columnspan=2, pady=(0, 5))

        tk.Button(
            frame_btns_carrito,
            text="- Quitar Línea",
            width=14,
            bg="#f59e0b",
            fg="white",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            command=self.quitar_item_carrito
        ).grid(row=1, column=0, padx=3, pady=2)

        tk.Button(
            frame_btns_carrito,
            text="Limpiar Pedido",
            width=14,
            bg="#64748b",
            fg="white",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            command=self.vaciar_carrito
        ).grid(row=1, column=1, padx=3, pady=2)

        # Panel derecho: Arriba = Detalle del Pedido Actual, Abajo = Ventas y Arqueo de la Sede
        contenedor_der = tk.Frame(self.tab_ventas, bg="#f1f5f9")
        contenedor_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 10), pady=8)

        panel_carrito = tk.LabelFrame(
            contenedor_der,
            text=" Detalle del Pedido Actual ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=10,
            pady=6
        )
        panel_carrito.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        frame_tabla_carrito = tk.Frame(panel_carrito, bg="#ffffff")
        frame_tabla_carrito.pack(fill=tk.BOTH, expand=True)

        cols_carrito = ("Cód.", "Producto", "Cant.", "Precio Base", "Topping", "Subtotal")
        self.tree_carrito = ttk.Treeview(frame_tabla_carrito, columns=cols_carrito, show="headings", height=5)
        for col, ancho in zip(cols_carrito, (55, 225, 65, 95, 165, 100)):
            self.tree_carrito.heading(col, text=col)
            self.tree_carrito.column(col, width=ancho, anchor="center" if col not in ("Producto", "Topping") else "w")

        scroll_car = ttk.Scrollbar(frame_tabla_carrito, orient=tk.VERTICAL, command=self.tree_carrito.yview)
        self.tree_carrito.configure(yscrollcommand=scroll_car.set)
        self.tree_carrito.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_car.pack(side=tk.RIGHT, fill=tk.Y)

        barra_finalizar = tk.Frame(panel_carrito, bg="#f0fdf4", pady=7, padx=12)
        barra_finalizar.pack(fill=tk.X, pady=(6, 0))

        self.var_total_carrito = tk.StringVar(value="TOTAL A COBRAR: S/ 0.00 (0 productos)")
        tk.Label(
            barra_finalizar,
            textvariable=self.var_total_carrito,
            font=("Segoe UI", 11, "bold"),
            bg="#f0fdf4",
            fg="#166534"
        ).pack(side=tk.LEFT)

        tk.Button(
            barra_finalizar,
            text="✔ Confirmar y Emitir Comprobante",
            bg="#16a34a",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            activebackground="#15803d",
            activeforeground="white",
            relief=tk.FLAT,
            padx=18,
            pady=5,
            cursor="hand2",
            command=self.guardar_venta
        ).pack(side=tk.RIGHT)

        # Panel inferior: Historial de Comprobantes y Arqueo de Caja Diaria
        titulo_hist = (
            f" Comprobantes Emitidos y Arqueo de Caja — {self.nombre_sucursal_activa} "
            if self.id_sucursal_activa else " Comprobantes Emitidos (Consolidado de Sedes) "
        )
        panel_hist = tk.LabelFrame(
            contenedor_der,
            text=titulo_hist,
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=10,
            pady=6
        )
        panel_hist.pack(fill=tk.BOTH, expand=True)

        barra_arqueo = tk.Frame(panel_hist, bg="#eff6ff", padx=10, pady=5)
        barra_arqueo.pack(fill=tk.X, pady=(0, 6))

        self.var_resumen_arqueo = tk.StringVar(value="Resumen de Caja: Calculando recaudación...")
        tk.Label(
            barra_arqueo, textvariable=self.var_resumen_arqueo,
            font=("Segoe UI", 9, "bold"), bg="#eff6ff", fg="#1e3a8a"
        ).pack(side=tk.LEFT)

        tk.Button(
            barra_arqueo,
            text="📊 Ver Arqueo por Medio de Pago",
            bg="#1d4ed8",
            fg="white",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._mostrar_ventana_arqueo
        ).pack(side=tk.RIGHT)

        frame_tabla_hist = tk.Frame(panel_hist, bg="#ffffff")
        frame_tabla_hist.pack(fill=tk.BOTH, expand=True)

        columnas = ("N° Pedido", "Comprobante", "Modalidad", "Fecha y Hora", "Cliente", "Atendido por", "Medio Pago", "Importe (S/)")
        self.tree_ventas = ttk.Treeview(frame_tabla_hist, columns=columnas, show="headings", height=6)
        for col, ancho in zip(columnas, (65, 95, 75, 115, 130, 165, 85, 85)):
            self.tree_ventas.heading(col, text=col)
            self.tree_ventas.column(
                col, width=ancho,
                anchor="center" if col in ("N° Pedido", "Comprobante", "Modalidad", "Medio Pago", "Importe (S/)") else "w"
            )

        scroll_y = ttk.Scrollbar(frame_tabla_hist, orient=tk.VERTICAL, command=self.tree_ventas.yview)
        self.tree_ventas.configure(yscrollcommand=scroll_y.set)
        self.tree_ventas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        if self.es_admin:
            barra_hist_btns = tk.Frame(panel_hist, bg="#ffffff")
            barra_hist_btns.pack(fill=tk.X, pady=(4, 0))
            tk.Button(
                barra_hist_btns, text="Anular Comprobante Seleccionado", bg="#dc2626", fg="white",
                font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=12, pady=3, cursor="hand2", command=self.borrar_venta
            ).pack(side=tk.RIGHT)

        self._refrescar_combos_venta()
        self._actualizar_correlativo_sugerido()

    def _actualizar_correlativo_sugerido(self, _event=None):
        if not hasattr(self, "var_ven_comprobante"):
            return
        correlativo = controlador.generar_correlativo_comprobante(
            self.var_ven_tipo_comp.get(), self.id_sucursal_activa
        )
        self.var_ven_comprobante.set(correlativo)

    def _refrescar_combos_venta(self):
        if not hasattr(self, "combo_ven_cliente"):
            return
        clientes, empleados, metodos, productos = controlador.obtener_catalogos_venta(
            self.id_sucursal_activa
        )

        vals_cli = [c[1] for c in clientes]
        self.combo_ven_cliente["values"] = vals_cli
        if vals_cli:
            self.var_ven_cliente.set(vals_cli[0])

        vals_emp = [e[1] for e in empleados]
        self.combo_ven_empleado["values"] = vals_emp
        if vals_emp:
            self.var_ven_empleado.set(vals_emp[0])

        vals_met = [m[1] for m in metodos]
        self.combo_ven_metodo["values"] = vals_met
        if vals_met:
            self.var_ven_metodo.set(vals_met[0])

        vals_prod = []
        self.mapa_precios_prod.clear()
        for p in productos:
            etiqueta = p[1]
            vals_prod.append(etiqueta)
            self.mapa_precios_prod[etiqueta] = f"{float(p[2]):.2f}"
        self.combo_ven_producto["values"] = vals_prod
        if vals_prod:
            self.var_ven_producto.set(vals_prod[0])
            self._actualizar_precio_producto_venta()

    def _actualizar_precio_producto_venta(self, _event=None):
        prod_sel = self.var_ven_producto.get()
        if prod_sel in self.mapa_precios_prod:
            self.var_ven_precio.set(self.mapa_precios_prod[prod_sel])
        try:
            id_prod = int(prod_sel.split(" - ", 1)[0])
            toppings = controlador.obtener_toppings_por_producto(id_prod)
            vals_top = [t[1] for t in toppings]
            self.combo_ven_topping["values"] = vals_top
            if vals_top:
                self.var_ven_topping.set(vals_top[0])
        except (ValueError, IndexError):
            pass

    def agregar_item_carrito(self):
        prod_sel = self.var_ven_producto.get()
        if not prod_sel:
            messagebox.showwarning("Producto Requerido", "Seleccione un producto del catálogo.")
            return
        try:
            id_prod = int(prod_sel.split(" - ", 1)[0])
            cantidad = int(self.var_ven_cantidad.get())
            if cantidad <= 0:
                raise ValueError
            id_top = int(self.var_ven_topping.get().split(" - ", 1)[0]) if self.var_ven_topping.get() else 0
        except ValueError:
            messagebox.showwarning("Cantidad Inválida", "Ingrese una cantidad entera mayor a cero.")
            return

        # El motor MySQL calcula el precio base, el recargo del topping y el subtotal de la línea
        linea_bd = controlador.calcular_linea_carrito_bd(id_prod, cantidad, id_top)
        if not linea_bd:
            messagebox.showerror("Error", "No se pudo calcular el importe del producto en el servidor.")
            return

        (
            id_p, nom_prod, cant_bd, precio_base,
            id_t, nom_top, precio_top, _unit_final, subtotal_bd
        ) = linea_bd

        etiqueta_top = f"{nom_top} (+S/ {float(precio_top):.2f})" if int(id_t) > 0 else "Sin topping"

        self.items_carrito.append({
            "id_prod": int(id_p),
            "nom_prod": nom_prod,
            "cantidad": int(cant_bd),
            "precio_base": float(precio_base),
            "id_top": int(id_t),
            "precio_top": float(precio_top),
            "etiqueta_top": etiqueta_top,
            "subtotal": float(subtotal_bd)
        })
        self._renderizar_carrito()

    def quitar_item_carrito(self):
        sel = self.tree_carrito.selection()
        if not sel:
            messagebox.showwarning("Selección Requerida", "Seleccione una línea del pedido para retirarla.")
            return
        idx = self.tree_carrito.index(sel[0])
        if 0 <= idx < len(self.items_carrito):
            self.items_carrito.pop(idx)
            self._renderizar_carrito()

    def vaciar_carrito(self):
        self.items_carrito.clear()
        self._renderizar_carrito()

    def _renderizar_carrito(self):
        for item in self.tree_carrito.get_children():
            self.tree_carrito.delete(item)
        payload = [
            {
                "id_producto": it["id_prod"],
                "cantidad": it["cantidad"],
                "id_topping": it["id_top"],
            }
            for it in self.items_carrito
        ]
        lineas_bd, resumen = controlador.calcular_resumen_carrito_bd(payload, 0.0)
        for lin in lineas_bd:
            nom_top = lin[6]
            etiqueta_top = f"{nom_top} (+S/ {float(lin[7]):.2f})" if int(lin[5]) > 0 else "Sin topping"
            fila_visual = (
                lin[1],
                lin[2],
                lin[3],
                f"S/ {float(lin[4]):.2f}",
                etiqueta_top,
                f"S/ {float(lin[9]):.2f}",
            )
            self.tree_carrito.insert("", tk.END, values=fila_visual)
        self.var_total_carrito.set(
            f"TOTAL A COBRAR: S/ {resumen['total_cobrar']:.2f}  ({resumen['total_lineas']} línea(s) en el pedido)"
        )

    def cargar_ventas(self):
        if not hasattr(self, "tree_ventas"):
            return
        for item in self.tree_ventas.get_children():
            self.tree_ventas.delete(item)
        registros = controlador.listar_ventas(self.id_sucursal_activa)
        for fila in registros:
            self.tree_ventas.insert("", tk.END, values=fila)
        self._actualizar_barra_arqueo()

    def _actualizar_barra_arqueo(self):
        if not hasattr(self, "var_resumen_arqueo"):
            return
        desglose, resumen = controlador.obtener_arqueo_rango(self.id_sucursal_activa or 0, None, None)
        partes = [f"{fila[1]}: S/ {float(fila[3]):.2f}" for fila in desglose]
        resumen_metodos = "  |  ".join(partes) if partes else "Sin movimientos"
        self.var_resumen_arqueo.set(f"Recaudado: S/ {resumen['total_recaudado']:.2f}   ({resumen_metodos})")

    def _mostrar_ventana_arqueo(self):
        desglose, resumen = controlador.obtener_arqueo_rango(self.id_sucursal_activa or 0, None, None)
        lineas = [f"📊 RESUMEN DE RECAUDACIÓN — {self.nombre_sucursal_activa.upper()}\n" + ("─" * 46)]
        for fila in desglose:
            lineas.append(f"• {fila[1]:<16}: {int(fila[2]):>3} venta(s)   ➔   S/ {float(fila[3]):>8.2f}")
        lineas.append("─" * 46)
        lineas.append(f"TOTAL ACUMULADO : {resumen['total_ventas']:>3} venta(s)   ➔   S/ {resumen['total_recaudado']:>8.2f}")
        messagebox.showinfo("Arqueo de Caja por Medio de Pago", "\n".join(lineas))

    def guardar_venta(self):
        if not self.items_carrito:
            messagebox.showwarning(
                "Pedido Vacío",
                "Agregue al menos un producto al pedido antes de emitir el comprobante."
            )
            return
        cli_sel = self.var_ven_cliente.get().strip()
        emp_sel = self.var_ven_empleado.get().strip()
        met_sel = self.var_ven_metodo.get().strip()
        if not cli_sel or not emp_sel or not met_sel:
            messagebox.showwarning("Datos Incompletos", "Verifique que Cliente, Cajero y Medio de Pago estén seleccionados.")
            return
        try:
            id_cli = int(cli_sel.split(" - ")[0])
            id_emp = int(emp_sel.split(" - ")[0])
            id_met = int(met_sel.split(" - ")[0])
        except (ValueError, IndexError):
            messagebox.showwarning("Datos Incompletos", "Verifique que Cliente, Cajero y Medio de Pago estén seleccionados.")
            return

        payload = [
            {
                "id_producto": it["id_prod"],
                "cantidad": it["cantidad"],
                "id_topping": it["id_top"],
            }
            for it in self.items_carrito
        ]
        ok, _datos, msg = controlador.registrar_venta_completa_bd(
            self.var_ven_tipo_comp.get(),
            self.id_sucursal_activa or 0,
            self.var_ven_canal.get(),
            id_emp,
            id_cli,
            id_met,
            payload,
        )
        if ok:
            messagebox.showinfo("Comprobante Emitido", msg)
            self.vaciar_carrito()
            self.cargar_ventas()
            self._actualizar_correlativo_sugerido()
            self.cargar_bitacora()
            self.var_estado.set(msg)
        else:
            messagebox.showerror("Error al Registrar Venta", msg)

    def borrar_venta(self):
        sel = self.tree_ventas.selection()
        if not sel:
            messagebox.showwarning("Seleccione un Comprobante", "Seleccione una venta de la tabla inferior para anularla.")
            return
        valores = self.tree_ventas.item(sel[0], "values")
        id_venta = valores[0]
        if messagebox.askyesno("Confirmar Anulación", f"¿Anular el pedido #{id_venta} ({valores[1]})?"):
            ok, msg = controlador.eliminar_venta(id_venta)
            if ok:
                messagebox.showinfo("Venta Anulada", msg)
                self.cargar_ventas()
                self._actualizar_correlativo_sugerido()
                self.cargar_bitacora()
                self.var_estado.set(msg)
            else:
                messagebox.showerror("Atención", msg)

    # =====================================================================
    # MÓDULO: PERSONAL Y SEDES (RRHH Y GESTIÓN DE ACCESOS)
    # =====================================================================

    def _armar_tab_rrhh(self):
        panel_izq = tk.LabelFrame(
            self.tab_rrhh, text=" Ficha del Colaborador ", font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg="#0f172a", padx=14, pady=10
        )
        panel_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 6), pady=10)

        roles_bd = controlador.catalogo_roles()
        roles_disp = [f"{r[0]} - {r[1]}" for r in roles_bd] if roles_bd else [
            "1 - Multifuncional (Caja)", "2 - Logística y Almacén", "3 - Recursos Humanos"
        ]

        self.var_emp_id = tk.StringVar()
        self.var_emp_nombres = tk.StringVar()
        self.var_emp_paterno = tk.StringVar()
        self.var_emp_materno = tk.StringVar()
        self.var_emp_sucursal = tk.StringVar()
        self.var_emp_rol = tk.StringVar(value=roles_disp[0])

        tk.Label(panel_izq, text="Código de Colaborador:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=0, column=0, sticky="w", pady=(2, 1))
        ttk.Entry(panel_izq, textvariable=self.var_emp_id, width=30, state="readonly").grid(row=1, column=0, pady=(0, 4), ipady=2)

        tk.Label(panel_izq, text="Nombres:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=2, column=0, sticky="w", pady=(2, 1))
        ttk.Entry(panel_izq, textvariable=self.var_emp_nombres, width=30).grid(row=3, column=0, pady=(0, 4), ipady=2)

        tk.Label(panel_izq, text="Apellido Paterno:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=4, column=0, sticky="w", pady=(2, 1))
        ttk.Entry(panel_izq, textvariable=self.var_emp_paterno, width=30).grid(row=5, column=0, pady=(0, 4), ipady=2)

        tk.Label(panel_izq, text="Apellido Materno:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=6, column=0, sticky="w", pady=(2, 1))
        ttk.Entry(panel_izq, textvariable=self.var_emp_materno, width=30).grid(row=7, column=0, pady=(0, 4), ipady=2)

        tk.Label(panel_izq, text="Sede Asignada:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=8, column=0, sticky="w", pady=(2, 1))
        lista_suc = controlador.obtener_sucursales_combo()
        if lista_suc:
            self.var_emp_sucursal.set(lista_suc[0])
        self.combo_emp_suc = ttk.Combobox(panel_izq, textvariable=self.var_emp_sucursal, values=lista_suc, state="readonly", width=28)
        self.combo_emp_suc.grid(row=9, column=0, pady=(0, 4), ipady=2)

        tk.Label(panel_izq, text="Cargo en la Empresa:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=10, column=0, sticky="w", pady=(2, 1))
        self.combo_emp_rol = ttk.Combobox(panel_izq, textvariable=self.var_emp_rol, values=roles_disp, state="readonly", width=28)
        self.combo_emp_rol.grid(row=11, column=0, pady=(0, 6), ipady=2)
        self.combo_emp_rol.bind("<<ComboboxSelected>>", self._sincronizar_estado_clave_credencial)

        frame_btns = tk.Frame(panel_izq, bg="#ffffff")
        frame_btns.grid(row=12, column=0, pady=6)

        tk.Button(frame_btns, text="Registrar Personal", width=14, bg="#16a34a", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.guardar_empleado).grid(row=0, column=0, padx=3, pady=3)
        tk.Button(frame_btns, text="Actualizar Cargo", width=14, bg="#2563eb", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.modificar_empleado).grid(row=0, column=1, padx=3, pady=3)

        if self.es_admin:
            tk.Button(frame_btns, text="Dar de Baja", width=14, bg="#dc2626", fg="white", font=("Segoe UI", 8, "bold"),
                      relief=tk.FLAT, cursor="hand2", command=self.borrar_empleado).grid(row=1, column=0, padx=3, pady=3)
            col_limp_e = 1
        else:
            col_limp_e = 0

        tk.Button(frame_btns, text="Limpiar", width=14, bg="#64748b", fg="white", font=("Segoe UI", 8, "bold"),
                  relief=tk.FLAT, cursor="hand2", command=self.limpiar_form_empleado).grid(
                      row=1, column=col_limp_e, columnspan=1 if self.es_admin else 2, padx=3, pady=3
                  )

        contenedor_der = tk.Frame(self.tab_rrhh, bg="#f1f5f9")
        contenedor_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 10), pady=10)

        panel_tabla_emp = tk.LabelFrame(
            contenedor_der,
            text=" Nómina de Colaboradores por Sucursal ",
            font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#0f172a", padx=10, pady=8
        )
        panel_tabla_emp.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 8))

        columnas = ("Código", "Nombres", "Apellido Paterno", "Apellido Materno", "Sucursal", "Cargo", "Modalidad de Acceso")
        self.tree_empleados = ttk.Treeview(panel_tabla_emp, columns=columnas, show="headings", height=8)
        for col, ancho in zip(columnas, (55, 115, 115, 115, 140, 155, 125)):
            self.tree_empleados.heading(col, text=col)
            self.tree_empleados.column(col, width=ancho, anchor="center" if col in ("Código", "Cargo", "Modalidad de Acceso") else "w")

        scroll_y = ttk.Scrollbar(panel_tabla_emp, orient=tk.VERTICAL, command=self.tree_empleados.yview)
        self.tree_empleados.configure(yscrollcommand=scroll_y.set)
        self.tree_empleados.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_empleados.bind("<<TreeviewSelect>>", self._seleccionar_fila_empleado)

        panel_cred = tk.LabelFrame(
            contenedor_der,
            text=" Asignación de Cuentas Administrativas (Gestión Interna) ",
            font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#166534" if self.es_admin else "#64748b", padx=12, pady=8
        )
        panel_cred.pack(side=tk.BOTTOM, fill=tk.X)

        self.var_cred_usuario = tk.StringVar()
        self.var_cred_pass = tk.StringVar()
        self.var_cred_pass2 = tk.StringVar()
        self.var_cred_info = tk.StringVar(
            value="Los Multifuncionales ingresan directo con la Caja Diaria de su sede. Seleccione un encargado de RRHH o Logística para asignarle cuenta."
        )

        if not self.es_admin:
            tk.Label(
                panel_cred,
                text="ℹ️ Los colaboradores Multifuncionales operan directamente desde la Caja Diaria de su sede asignada.",
                font=("Segoe UI", 9, "bold"), bg="#fef3c7", fg="#92400e", padx=10, pady=8
            ).pack(fill=tk.X)
        else:
            tk.Label(
                panel_cred, textvariable=self.var_cred_info, font=("Segoe UI", 8, "bold"),
                bg="#eff6ff", fg="#1d4ed8", pady=4
            ).pack(fill=tk.X, pady=(0, 6))

            fila_form = tk.Frame(panel_cred, bg="#ffffff")
            fila_form.pack(fill=tk.X)

            tk.Label(fila_form, text="Usuario Administrativo:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=0, column=0, sticky="w", padx=(0, 4))
            self.entry_cred_usr = ttk.Entry(fila_form, textvariable=self.var_cred_usuario, width=18)
            self.entry_cred_usr.grid(row=0, column=1, padx=(0, 12), ipady=2)

            tk.Label(fila_form, text="Contraseña:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=0, column=2, sticky="w", padx=(0, 4))
            self.entry_cred_pass = ttk.Entry(fila_form, textvariable=self.var_cred_pass, width=16, show="•")
            self.entry_cred_pass.grid(row=0, column=3, padx=(0, 12), ipady=2)

            tk.Label(fila_form, text="Confirmar:", font=("Segoe UI", 9, "bold"), bg="#ffffff").grid(row=0, column=4, sticky="w", padx=(0, 4))
            self.entry_cred_pass2 = ttk.Entry(fila_form, textvariable=self.var_cred_pass2, width=16, show="•")
            self.entry_cred_pass2.grid(row=0, column=5, padx=(0, 12), ipady=2)

            self.btn_asignar_cred = tk.Button(
                fila_form,
                text="Guardar Cuenta Administrativa",
                bg="#16a34a",
                fg="white",
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT,
                padx=10,
                pady=4,
                cursor="hand2",
                command=self.asignar_cuenta_empleado_admin
            )
            self.btn_asignar_cred.grid(row=0, column=6, padx=4)

    def _sincronizar_estado_clave_credencial(self, _event=None):
        if not self.es_admin or not hasattr(self, "entry_cred_pass"):
            return
        rol_txt = self.var_emp_rol.get()
        nom_emp = f"{self.var_emp_nombres.get()} {self.var_emp_paterno.get()}".strip() or "Colaborador"
        if "Multifuncional" in rol_txt:
            self.var_cred_usuario.set("")
            self.var_cred_pass.set("")
            self.var_cred_pass2.set("")
            self.entry_cred_usr.config(state="disabled")
            self.entry_cred_pass.config(state="disabled")
            self.entry_cred_pass2.config(state="disabled")
            self.btn_asignar_cred.config(state="disabled", bg="#94a3b8")
            self.var_cred_info.set(
                f"🏪 {nom_emp} es Multifuncional: No usa cuenta individual; inicia turno directamente con la Caja Diaria de su sede."
            )
        else:
            self.entry_cred_usr.config(state="normal")
            self.entry_cred_pass.config(state="normal")
            self.entry_cred_pass2.config(state="normal")
            self.btn_asignar_cred.config(state="normal", bg="#16a34a")
            self.var_cred_info.set(
                f"🔐 {nom_emp} ({rol_txt}) pertenece al equipo de Gestión Interna: asigne su usuario y contraseña."
            )

    def asignar_cuenta_empleado_admin(self):
        if not self.es_admin:
            return
        if not self.var_emp_id.get():
            messagebox.showwarning("Seleccione un Colaborador", "Seleccione un encargado de la nómina superior.")
            return
        ok, msg = controlador.asignar_credencial_empleado(
            self.var_emp_id.get(),
            self.var_cred_usuario.get(),
            self.var_cred_pass.get(),
            self.var_cred_pass2.get()
        )
        if ok:
            messagebox.showinfo("Acceso Asignado", msg)
            self.var_cred_pass.set("")
            self.var_cred_pass2.set("")
            self.cargar_empleados()
            self.cargar_bitacora()
            self.var_estado.set(msg)
        else:
            messagebox.showwarning("Atención", msg)

    def cargar_empleados(self):
        if not hasattr(self, "tree_empleados"):
            return
        for item in self.tree_empleados.get_children():
            self.tree_empleados.delete(item)
        for fila in controlador.listar_empleados():
            self.tree_empleados.insert("", tk.END, values=fila)

    def _seleccionar_fila_empleado(self, _event):
        sel = self.tree_empleados.selection()
        if sel:
            v = self.tree_empleados.item(sel[0], "values")
            self.var_emp_id.set(v[0])
            self.var_emp_nombres.set(v[1])
            self.var_emp_paterno.set(v[2])
            self.var_emp_materno.set(v[3])
            self.var_emp_sucursal.set(v[4])
            self.var_emp_rol.set(v[5])
            if len(v) > 6 and not str(v[6]).startswith("Caja Sede") and v[6] != "Sin cuenta":
                self.var_cred_usuario.set(v[6])
            else:
                self.var_cred_usuario.set("")
            self._sincronizar_estado_clave_credencial()

    def limpiar_form_empleado(self):
        self.var_emp_id.set("")
        self.var_emp_nombres.set("")
        self.var_emp_paterno.set("")
        self.var_emp_materno.set("")
        if hasattr(self, "var_cred_usuario"):
            self.var_cred_usuario.set("")
            self.var_cred_pass.set("")
            self.var_cred_pass2.set("")
        self.tree_empleados.selection_remove(self.tree_empleados.selection())

    def guardar_empleado(self):
        if not self.var_emp_nombres.get().strip() or not self.var_emp_paterno.get().strip():
            messagebox.showwarning("Datos Requeridos", "Complete los Nombres y Apellidos del colaborador.")
            return
        id_suc = self.var_emp_sucursal.get().split(" - ")[0]
        id_rol = self.var_emp_rol.get().split(" - ")[0]
        ok, msg = controlador.insertar_empleado(
            self.var_emp_nombres.get(), self.var_emp_paterno.get(), self.var_emp_materno.get(), id_suc, id_rol
        )
        if ok:
            messagebox.showinfo("Personal Registrado", msg)
            self.limpiar_form_empleado()
            self.cargar_empleados()
            self.cargar_bitacora()
            self._refrescar_combos_venta()
        else:
            messagebox.showerror("Atención", msg)

    def modificar_empleado(self):
        if not self.var_emp_id.get():
            messagebox.showwarning("Seleccione un Colaborador", "Seleccione un colaborador de la tabla para actualizarlo.")
            return
        id_suc = self.var_emp_sucursal.get().split(" - ")[0]
        id_rol = self.var_emp_rol.get().split(" - ")[0]
        ok, msg = controlador.actualizar_empleado(
            self.var_emp_id.get(), self.var_emp_nombres.get(), self.var_emp_paterno.get(),
            self.var_emp_materno.get(), id_suc, id_rol
        )
        if ok:
            messagebox.showinfo("Personal Actualizado", msg)
            self.limpiar_form_empleado()
            self.cargar_empleados()
            self.cargar_bitacora()
            self._refrescar_combos_venta()
        else:
            messagebox.showerror("Atención", msg)

    def borrar_empleado(self):
        if not self.var_emp_id.get():
            messagebox.showwarning("Seleccione un Colaborador", "Seleccione un colaborador para darle de baja.")
            return
        if messagebox.askyesno("Confirmar", f"¿Dar de baja al colaborador #{self.var_emp_id.get()}?"):
            ok, msg = controlador.eliminar_empleado(self.var_emp_id.get())
            if ok:
                messagebox.showinfo("Baja Registrada", msg)
                self.limpiar_form_empleado()
                self.cargar_empleados()
                self.cargar_bitacora()
                self._refrescar_combos_venta()
            else:
                messagebox.showwarning("No Permitido", msg)

    # =====================================================================
    # MÓDULO: HISTORIAL DE OPERACIONES Y AUDITORÍA (GERENCIA)
    # =====================================================================

    def _armar_tab_auditoria(self):
        panel_sup = tk.LabelFrame(
            self.tab_auditoria,
            text=" Filtros de Supervisión de Operaciones ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=14,
            pady=8
        )
        panel_sup.pack(fill=tk.X, padx=10, pady=(10, 6))

        tk.Label(panel_sup, text="Tipo de Evento:", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(side=tk.LEFT)
        self.var_aud_accion = tk.StringVar(value="Todos")
        combo_acc = ttk.Combobox(
            panel_sup,
            textvariable=self.var_aud_accion,
            values=["Todos", "Inicio de Sesión", "Registro", "Actualización", "Eliminación / Anulación", "Bloqueo Preventivo"],
            state="readonly",
            width=22
        )
        combo_acc.pack(side=tk.LEFT, padx=(6, 16))
        combo_acc.bind("<<ComboboxSelected>>", lambda _e: self.cargar_bitacora())

        tk.Label(panel_sup, text="Área / Módulo:", font=("Segoe UI", 9, "bold"), bg="#ffffff").pack(side=tk.LEFT)
        self.var_aud_tabla = tk.StringVar(value="Todos")
        combo_tab = ttk.Combobox(
            panel_sup,
            textvariable=self.var_aud_tabla,
            values=[
                "Todos",
                "Punto de Venta",
                "Seguridad y Accesos",
                "Catálogo de Productos",
                "Toppings y Adicionales",
                "Almacén e Insumos",
                "Compras y Abastecimiento",
                "Personal y Sedes",
            ],
            state="readonly",
            width=24
        )
        combo_tab.pack(side=tk.LEFT, padx=(6, 16))
        combo_tab.bind("<<ComboboxSelected>>", lambda _e: self.cargar_bitacora())

        tk.Button(
            panel_sup,
            text="Actualizar Historial",
            bg="#1e3a8a",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.cargar_bitacora
        ).pack(side=tk.LEFT, padx=4)

        tk.Label(
            panel_sup,
            text="● Auditoría Automática Activa (Ventas, Precios, Almacén, Personal y Accesos)",
            font=("Segoe UI", 8, "bold"),
            bg="#dcfce7",
            fg="#166534",
            padx=10,
            pady=4
        ).pack(side=tk.RIGHT)

        panel_tabla = tk.LabelFrame(
            self.tab_auditoria,
            text=" Registro Cronológico de Actividades ",
            font=("Segoe UI", 10, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=12,
            pady=10
        )
        panel_tabla.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columnas = ("N°", "Fecha y Hora", "Cuenta / Caja", "Área", "Evento", "Módulo", "Descripción de la Operación")
        self.tree_auditoria = ttk.Treeview(panel_tabla, columns=columnas, show="headings")
        for col, ancho in zip(columnas, (55, 135, 115, 135, 135, 155, 380)):
            self.tree_auditoria.heading(col, text=col)
            self.tree_auditoria.column(col, width=ancho, anchor="center" if col in ("N°", "Fecha y Hora", "Evento") else "w")

        scroll_y = ttk.Scrollbar(panel_tabla, orient=tk.VERTICAL, command=self.tree_auditoria.yview)
        self.tree_auditoria.configure(yscrollcommand=scroll_y.set)
        self.tree_auditoria.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

    def cargar_bitacora(self):
        if not hasattr(self, "tree_auditoria"):
            return
        for item in self.tree_auditoria.get_children():
            self.tree_auditoria.delete(item)
        registros = controlador.listar_bitacora_comercial(
            self.var_aud_accion.get(),
            self.var_aud_tabla.get()
        )
        for ev in registros:
            fila_visual = (ev[0], ev[1], ev[2], ev[3], ev[5], ev[6], ev[7])
            self.tree_auditoria.insert("", tk.END, values=fila_visual)


# =====================================================================
# PANTALLA DE INGRESO: CAJAS DIARIAS POR SEDE VS. GESTIÓN INTERNA
# =====================================================================

class VentanaAutenticacion:
    def __init__(self, root, callback_exito):
        self.root = root
        self.callback_exito = callback_exito
        self.root.title("Heladería Polo Norte — Inicio de Turno y Gestión")
        self.root.geometry("580x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#f1f5f9")

        self._centrar_ventana(580, 620)
        self._construir_banner()
        self._construir_panel_cajas_diarias()
        self._construir_panel_gestion()
        self._construir_pie()

    def _centrar_ventana(self, ancho, alto):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _construir_banner(self):
        banner = tk.Frame(self.root, bg="#0f172a", height=84)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)

        tk.Label(
            banner,
            text="🍦 HELADERÍA POLO NORTE",
            font=("Segoe UI", 15, "bold"),
            bg="#0f172a",
            fg="#ffffff"
        ).pack(pady=(14, 2))

        tk.Label(
            banner,
            text="Apertura de Caja Diaria por Sucursal y Acceso Administrativo",
            font=("Segoe UI", 9),
            bg="#0f172a",
            fg="#38bdf8"
        ).pack()

    def _construir_panel_cajas_diarias(self):
        panel_cajas = tk.LabelFrame(
            self.root,
            text=" 🏪 1. Atención en Tienda — Seleccionar Caja Diaria por Sucursal (Ingreso Directo) ",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=18,
            pady=12
        )
        panel_cajas.pack(fill=tk.X, padx=20, pady=(14, 8))

        tk.Label(
            panel_cajas,
            text="Para colaboradores Multifuncionales: elija la caja de su sede para abrir el Punto de Venta de inmediato:",
            font=("Segoe UI", 8),
            bg="#ffffff",
            fg="#475569"
        ).pack(anchor="w", pady=(0, 8))

        fila_botones_sede = tk.Frame(panel_cajas, bg="#ffffff")
        fila_botones_sede.pack(fill=tk.X)

        sedes_cajas = [
            ("📍 Sede Quintanas\n(Abrir Caja Diaria)", "caja_quintanas", "#0284c7"),
            ("📍 Sede UPAO\n(Abrir Caja Diaria)", "caja_upao", "#0d9488"),
            ("📍 Sede Mall Plaza\n(Abrir Caja Diaria)", "caja_mall", "#4f46e5"),
        ]

        for idx, (texto_btn, cuenta_caja, color_btn) in enumerate(sedes_cajas):
            fila_botones_sede.columnconfigure(idx, weight=1)
            tk.Button(
                fila_botones_sede,
                text=texto_btn,
                font=("Segoe UI", 9, "bold"),
                bg=color_btn,
                fg="#ffffff",
                activebackground="#0f172a",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                pady=10,
                cursor="hand2",
                command=lambda u=cuenta_caja: self._ingresar_caja_directa(u)
            ).grid(row=0, column=idx, sticky="we", padx=4)

    def _ingresar_caja_directa(self, cuenta_caja):
        exito, usuario_bd, rango_rol, mensaje = controlador.validar_login(cuenta_caja, "")
        if exito:
            self.callback_exito(usuario_bd, rango_rol)
        else:
            messagebox.showwarning("Atención", mensaje)

    def _construir_panel_gestion(self):
        tab_login = tk.LabelFrame(
            self.root,
            text=" 🔐 2. Administración y Gestión Interna ",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            padx=20,
            pady=14
        )
        tab_login.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4, 12))

        self.var_login_user = tk.StringVar(value="admin")
        self.var_login_pass = tk.StringVar()
        self.var_mostrar_pass_login = tk.BooleanVar(value=False)
        self.var_info_rango = tk.StringVar(value="Área: Gerencia General")
        self.var_intentos_info = tk.StringVar(value="Intentos disponibles: 3 de 3")

        tk.Label(
            tab_login,
            text="Cuenta Administrativa (Gerencia, RRHH o Logística):",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#1e293b"
        ).pack(anchor="w", pady=(2, 3))

        cuentas_bd = controlador.listar_usuarios_credenciales()
        cuentas_admin = [u[1] for u in cuentas_bd if u[3] == "Con Clave"]
        if not cuentas_admin:
            cuentas_admin = ["admin", "rrhh_etel", "log_joel"]

        self.combo_login_user = ttk.Combobox(
            tab_login, textvariable=self.var_login_user, values=cuentas_admin, font=("Segoe UI", 10)
        )
        self.combo_login_user.pack(fill=tk.X, ipady=3, pady=(0, 6))
        self.combo_login_user.bind("<<ComboboxSelected>>", self._evaluar_jerarquia_usuario)
        self.combo_login_user.bind("<KeyRelease>", self._evaluar_jerarquia_usuario)

        self.lbl_rango_detectado = tk.Label(
            tab_login,
            textvariable=self.var_info_rango,
            font=("Segoe UI", 8, "bold"),
            bg="#eff6ff",
            fg="#1d4ed8",
            pady=5
        )
        self.lbl_rango_detectado.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            tab_login,
            text="Contraseña de Acceso:",
            font=("Segoe UI", 9, "bold"),
            bg="#ffffff",
            fg="#1e293b"
        ).pack(anchor="w", pady=(2, 3))
        self.entry_login_pass = ttk.Entry(tab_login, textvariable=self.var_login_pass, font=("Segoe UI", 10), show="•")
        self.entry_login_pass.pack(fill=tk.X, ipady=4, pady=(0, 5))
        self.entry_login_pass.bind("<Return>", lambda _e: self._ejecutar_login())

        frame_opciones_login = tk.Frame(tab_login, bg="#ffffff")
        frame_opciones_login.pack(fill=tk.X, pady=(0, 10))

        tk.Checkbutton(
            frame_opciones_login,
            text="Mostrar contraseña",
            variable=self.var_mostrar_pass_login,
            bg="#ffffff",
            font=("Segoe UI", 8),
            activebackground="#ffffff",
            command=self._toggle_ver_pass_login
        ).pack(side=tk.LEFT)

        self.lbl_intentos = tk.Label(
            frame_opciones_login,
            textvariable=self.var_intentos_info,
            font=("Segoe UI", 8, "bold"),
            bg="#ffffff",
            fg="#2563eb"
        )
        self.lbl_intentos.pack(side=tk.RIGHT)

        self.btn_ingresar = tk.Button(
            tab_login,
            text="INGRESAR A ADMINISTRACIÓN",
            font=("Segoe UI", 10, "bold"),
            bg="#0f172a",
            fg="#ffffff",
            activebackground="#1e3a8a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            pady=8,
            command=self._ejecutar_login
        )
        self.btn_ingresar.pack(fill=tk.X, pady=(0, 8))

        guia_texto = (
            "Acceso restringido al equipo administrativo · Bloqueo automático preventivo al tercer intento fallido."
        )
        tk.Label(
            tab_login, text=guia_texto, font=("Segoe UI", 8), bg="#f8fafc", fg="#475569", pady=4
        ).pack(fill=tk.X, side=tk.BOTTOM)

        self._evaluar_jerarquia_usuario()

    def _evaluar_jerarquia_usuario(self, _event=None):
        info = controlador.consultar_info_usuario_web(self.var_login_user.get())
        if not info:
            self.var_info_rango.set("Cuenta no registrada en el directorio administrativo")
            self.lbl_rango_detectado.config(bg="#fef2f2", fg="#991b1b")
            self.entry_login_pass.config(state="normal")
            return

        restantes = info["intentos_restantes"]
        estado = info["estado"]
        persona = info["persona"]
        nom_suc = info["nombre_sucursal"]
        area_bonita = info["area_comercial"]

        if estado == "Bloqueado" or restantes == 0:
            self.var_info_rango.set(f"{persona} — ¡ACCESO BLOQUEADO POR SEGURIDAD!")
            self.lbl_rango_detectado.config(bg="#fee2e2", fg="#991b1b")
            self.var_intentos_info.set("¡Cuenta bloqueada (0 de 3)!")
            self.lbl_intentos.config(fg="#dc2626")
            return

        self.var_intentos_info.set(f"Intentos disponibles: {restantes} de 3")
        self.lbl_intentos.config(fg="#2563eb" if restantes == 3 else "#dc2626")

        if not info["requiere_password"]:
            self.var_info_rango.set(f"{persona} ({nom_suc}) — Apertura directa sin contraseña")
            self.lbl_rango_detectado.config(bg="#dcfce7", fg="#166534")
            self.var_login_pass.set("")
            self.entry_login_pass.config(state="disabled")
        else:
            self.var_info_rango.set(f"Responsable: {persona}   •   Área: {area_bonita}")
            self.lbl_rango_detectado.config(bg="#eff6ff", fg="#1d4ed8")
            self.entry_login_pass.config(state="normal")

    def _toggle_ver_pass_login(self):
        self.entry_login_pass.config(show="" if self.var_mostrar_pass_login.get() else "•")

    def _ejecutar_login(self):
        user = self.var_login_user.get()
        pwd = self.var_login_pass.get()

        exito, usuario_bd, rango_rol, mensaje = controlador.validar_login(user, pwd)
        if exito:
            self.callback_exito(usuario_bd, rango_rol)
        else:
            self.var_login_pass.set("")
            self._evaluar_jerarquia_usuario()
            if "BLOQUEADA" in mensaje or "BLOQUEADO" in mensaje:
                messagebox.showerror("Cuenta Bloqueada", mensaje)
            else:
                messagebox.showwarning("Acceso Denegado", mensaje)

    def _construir_pie(self):
        pie = tk.Frame(self.root, bg="#e2e8f0", height=30)
        pie.pack(fill=tk.X, side=tk.BOTTOM)
        pie.pack_propagate(False)

        tk.Label(
            pie,
            text="Heladería Polo Norte — Sedes: Las Quintanas  •  UPAO  •  Mall Plaza",
            font=("Segoe UI", 8, "bold"),
            bg="#e2e8f0",
            fg="#475569"
        ).pack(side=tk.LEFT, padx=14, pady=5)
