# main.py
# Punto de entrada principal: Autenticación Jerárquica por Roles (RBAC) y Tabla Hash

import sys
sys.dont_write_bytecode = True

import tkinter as tk
from interfaz import VentanaAutenticacion, HeladeriaApp


def iniciar_sistema():
    ventana_login = tk.Tk()

    def acceso_concedido(usuario_autenticado, rango_rol):
        ventana_login.destroy()
        abrir_ventana_principal(usuario_autenticado, rango_rol)

    VentanaAutenticacion(ventana_login, callback_exito=acceso_concedido)
    ventana_login.mainloop()


def abrir_ventana_principal(usuario_autenticado, rango_rol):
    ventana_principal = tk.Tk()

    def volver_al_login():
        ventana_principal.destroy()
        iniciar_sistema()

    HeladeriaApp(
        ventana_principal,
        usuario_autenticado=usuario_autenticado,
        rango_rol=rango_rol,
        callback_logout=volver_al_login
    )
    ventana_principal.mainloop()


if __name__ == "__main__":
    iniciar_sistema()
