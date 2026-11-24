// polo_norte.js — Interactividad ligera para POS de Caja Rápida, atajos de teclado y modales
// Cero cálculos de negocio en cliente: subtotales, totales y vueltos se calculan en el servidor.

(function () {
  window.abrirModal = function (id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("open");
  };
  window.cerrarModal = function (id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("open");
  };

  function reemplazarHTMLSeguro(contenedor, htmlTexto) {
    if (!contenedor) return;
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlTexto, "text/html");
    const nodos = Array.from(doc.body.childNodes).map((n) => document.importNode(n, true));
    contenedor.replaceChildren(...nodos);
  }

  // Confirmaciones declarativas sin handlers inline (protección XSS)
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form && form.dataset && form.dataset.confirm) {
      if (!window.confirm(form.dataset.confirm)) {
        e.preventDefault();
      }
    }
  });

  // ---------------- LOGIN: Evaluación de cuenta administrativa ----------------
  const loginUser = document.getElementById("login-usuario-input");
  const loginBox = document.getElementById("login-status-box");
  if (loginUser && loginBox) {
    function pintarBadgeEstado(clase, texto) {
      loginBox.textContent = "";
      const span = document.createElement("span");
      span.className = "badge " + clase;
      span.textContent = texto;
      loginBox.appendChild(span);
    }
    async function consultarCuenta() {
      const val = (loginUser.value || "").trim();
      if (!val) {
        pintarBadgeEstado("badge-slate", "Seleccione o escriba su usuario administrativo");
        return;
      }
      try {
        const resp = await fetch("/api/login/estado?usuario=" + encodeURIComponent(val));
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.encontrado) {
          pintarBadgeEstado("badge-berry", "Cuenta no registrada en el directorio");
        } else if (data.bloqueado) {
          pintarBadgeEstado("badge-berry", "🔒 CUENTA BLOQUEADA — Solicite reactivación a Gerencia");
        } else if (!data.requiere_password) {
          pintarBadgeEstado("badge-mint", "Caja Diaria (" + data.nombre_sucursal + ") — Ingreso directo desde el panel izquierdo");
        } else {
          pintarBadgeEstado("badge-sky", data.area_comercial + " · Acceso protegido con contraseña");
        }
      } catch (_e) {
        // Silencioso en fallo de red puntual
      }
    }
    loginUser.addEventListener("change", consultarCuenta);
    loginUser.addEventListener("blur", consultarCuenta);
    if (loginUser.value) consultarCuenta();
  }

  // ---------------- POS DE CAJA RÁPIDA ----------------
  const posRoot = document.getElementById("pos-workspace");
  if (!posRoot) return;

  let selectedProdId = posRoot.dataset.defaultProd || "";
  let selectedToppingId = "0";

  const prodInput = document.getElementById("pos-id-producto");
  const topInput = document.getElementById("pos-id-topping");
  const precioReadonly = document.getElementById("pos-precio-readonly");
  const qtyInput = document.getElementById("pos-cantidad");
  const toppingsContainer = document.getElementById("pos-toppings-container");
  const cartContainer = document.getElementById("pos-cart-container");
  const metodoInput = document.getElementById("pos-id-metodo-pago");
  const qrNotice = document.getElementById("pos-qr-notice");
  const efectivoBox = document.getElementById("pos-efectivo-box");
  const montoRecibidoInput = document.getElementById("pos-monto-recibido");
  const tipoDocInput = document.getElementById("pos-tipo-comprobante");
  const correlativoSpan = document.getElementById("pos-correlativo-badge");

  async function cargarToppings(idProd) {
    if (!toppingsContainer || !idProd) return;
    try {
      const resp = await fetch("/pos/parcial/toppings/" + encodeURIComponent(idProd));
      if (resp.ok) {
        reemplazarHTMLSeguro(toppingsContainer, await resp.text());
        enlazarChipsTopping();
      }
    } catch (_e) {}
  }

  function enlazarChipsTopping() {
    selectedToppingId = "0";
    if (topInput) topInput.value = "0";
    document.querySelectorAll(".pos-chip[data-topping-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedToppingId = btn.dataset.toppingId;
        if (topInput) topInput.value = selectedToppingId;
        document.querySelectorAll(".pos-chip[data-topping-id]").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
      });
    });
  }

  window.seleccionarProductoPOS = function (btn) {
    if (!btn) return;
    selectedProdId = btn.dataset.prodId;
    if (prodInput) prodInput.value = selectedProdId;
    if (precioReadonly) precioReadonly.value = btn.dataset.prodPrecio;
    document.querySelectorAll(".pos-prod-card").forEach((c) => c.classList.remove("selected"));
    btn.classList.add("selected");
    cargarToppings(selectedProdId);
  };

  window.ajustarCantidadPOS = function (delta) {
    if (!qtyInput) return;
    const actual = parseInt(qtyInput.value || "1", 10);
    const base = Number.isNaN(actual) ? 1 : actual;
    const nuevo = Math.max(1, base + delta);
    qtyInput.value = String(nuevo);
  };

  async function actualizarCarritoDesdeServidor(url, formData) {
    try {
      const resp = await fetch(url, { method: "POST", body: formData });
      if (resp.ok && cartContainer) {
        reemplazarHTMLSeguro(cartContainer, await resp.text());
        sincronizarBotonCobro();
      }
    } catch (_e) {}
  }

  function recalcularVueltoServidor() {
    if (!montoRecibidoInput) return;
    const fd = new FormData();
    fd.append("monto_recibido", montoRecibidoInput.value || "0");
    actualizarCarritoDesdeServidor("/pos/carrito/vuelto", fd);
  }

  window.agregarItemPOS = function () {
    if (!selectedProdId) return;
    const cantNum = parseInt(qtyInput ? qtyInput.value : "1", 10);
    if (Number.isNaN(cantNum) || cantNum < 1) {
      if (qtyInput) qtyInput.value = "1";
      window.alert("Ingresa una cantidad válida mayor o igual a 1.");
      return;
    }
    const fd = new FormData();
    fd.append("id_producto", selectedProdId);
    fd.append("cantidad", String(cantNum));
    fd.append("id_topping", selectedToppingId || "0");
    if (montoRecibidoInput && montoRecibidoInput.value) {
      fd.append("monto_recibido", montoRecibidoInput.value);
    }
    actualizarCarritoDesdeServidor("/pos/carrito/agregar", fd);
    if (qtyInput) qtyInput.value = "1";
  };

  window.quitarItemPOS = function (idx) {
    const fd = new FormData();
    fd.append("indice", String(idx));
    if (montoRecibidoInput && montoRecibidoInput.value) {
      fd.append("monto_recibido", montoRecibidoInput.value);
    }
    actualizarCarritoDesdeServidor("/pos/carrito/quitar", fd);
  };

  window.vaciarCarritoPOS = function () {
    const fd = new FormData();
    if (montoRecibidoInput) montoRecibidoInput.value = "";
    actualizarCarritoDesdeServidor("/pos/carrito/vaciar", fd);
  };

  window.aplicarEfectivoPOS = function (monto) {
    if (!montoRecibidoInput) return;
    montoRecibidoInput.value = monto === "exacto" ? "" : String(monto);
    recalcularVueltoServidor();
  };

  if (montoRecibidoInput) {
    montoRecibidoInput.addEventListener("change", recalcularVueltoServidor);
    montoRecibidoInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        recalcularVueltoServidor();
      }
    });
  }

  window.seleccionarMetodoPagoPOS = function (btn) {
    if (!btn) return;
    const id = btn.dataset.metodoId;
    const nombre = (btn.dataset.metodoNombre || "").toLowerCase();
    const esEfectivo = nombre.includes("efectivo");
    if (metodoInput) metodoInput.value = id;
    document.querySelectorAll(".pos-pay-btn").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    if (qrNotice) {
      qrNotice.style.display = (nombre.includes("yape") || nombre.includes("plin")) ? "block" : "none";
    }
    if (efectivoBox) {
      efectivoBox.style.display = esEfectivo ? "block" : "none";
    }
    if (!esEfectivo && montoRecibidoInput && montoRecibidoInput.value !== "") {
      montoRecibidoInput.value = "";
      recalcularVueltoServidor();
    }
  };

  window.cambiarTipoComprobantePOS = async function (tipo) {
    if (tipoDocInput) tipoDocInput.value = tipo;
    document.querySelectorAll("[data-doc-btn]").forEach((b) => {
      b.classList.toggle("btn-navy", b.dataset.docBtn === tipo);
      b.classList.toggle("btn-outline", b.dataset.docBtn !== tipo);
    });
    if (correlativoSpan) {
      try {
        const resp = await fetch("/pos/api/correlativo?tipo=" + encodeURIComponent(tipo));
        if (resp.ok) {
          const data = await resp.json();
          correlativoSpan.textContent = data.correlativo;
        }
      } catch (_e) {}
    }
  };

  window.cambiarCanalPOS = function (canal) {
    const inp = document.getElementById("pos-canal-atencion");
    if (inp) inp.value = canal;
    document.querySelectorAll("[data-canal-btn]").forEach((b) => {
      b.classList.toggle("btn-navy", b.dataset.canalBtn === canal);
      b.classList.toggle("btn-outline", b.dataset.canalBtn !== canal);
    });
  };

  function sincronizarBotonCobro() {
    const totalEl = document.getElementById("pos-cart-total-val");
    const btnCobrar = document.getElementById("pos-btn-cobrar");
    if (totalEl && btnCobrar) {
      btnCobrar.textContent = "✓ Emitir Comprobante y Cobrar — S/ " + totalEl.dataset.total + " (F9)";
    }
  }

  enlazarChipsTopping();
  sincronizarBotonCobro();

  // Atajos de teclado comerciales para velocidad en caja: 1-9 producto, F9 cobrar, Esc cerrar modal
  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    const enInput = ["INPUT", "SELECT", "TEXTAREA"].includes(tag);
    const modalAbierto = Boolean(document.querySelector(".pn-modal-backdrop.open"));

    if (e.key === "Escape") {
      document.querySelectorAll(".pn-modal-backdrop.open").forEach((m) => m.classList.remove("open"));
      return;
    }
    if (e.key === "F9") {
      if (modalAbierto) return;
      e.preventDefault();
      const form = document.getElementById("pos-checkout-form");
      if (form) form.requestSubmit();
      return;
    }
    if (!enInput && !modalAbierto && !e.ctrlKey && !e.altKey && !e.metaKey && e.key >= "1" && e.key <= "9") {
      const idx = parseInt(e.key, 10) - 1;
      const cards = document.querySelectorAll(".pos-prod-card");
      if (cards[idx]) {
        window.seleccionarProductoPOS(cards[idx]);
      }
    }
  });
})();
