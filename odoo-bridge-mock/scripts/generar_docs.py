"""Genera docs/openapi.json y docs/ejemplos.md llamando al esqueleto de verdad.

Así los ejemplos del contrato nunca se desfasan del código:
    python scripts/generar_docs.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import CONTRATO_VERSION, Settings  # noqa: E402
from app.main import create_app  # noqa: E402

KL, KB, KO = "LLAVE_LECTURA", "LLAVE_BUFFER", "LLAVE_ODOO"
DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")

COT = {
    "cliente": {"odoo_id": 7, "nombre": "Hotel Ejemplo Los Cabos"},
    "folio_levantamiento": "L000123",
    "partidas": [
        {"seccion": "Voz y datos", "modelo_bbinco": "CS-PP24-C6", "codigo_odoo": "PP-24-C6",
         "descripcion": "Patch panel 24 puertos Cat6", "cantidad": 2, "precio_unitario": 1190.0},
        {"seccion": "Servicios", "modelo_bbinco": None, "codigo_odoo": "BBI-SERV-DATOS",
         "descripcion": "Cableado por nodo", "cantidad": 4, "precio_unitario": 350.0, "flete": 0.0},
    ],
}


def main() -> None:
    app = create_app(Settings(key_lectura=KL, key_buffer=KB, key_odoo=KO, segundos_por_lote=0.0001))
    c = TestClient(app)
    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "openapi.json"), "w", encoding="utf-8") as fh:
        json.dump(c.get("/openapi.json").json(), fh, ensure_ascii=False, indent=2)

    llaves = {KL: "<llave lectura>", KB: "<llave buffer>", KO: "<llave odoo>"}
    secciones: list[str] = []
    n = 0

    def ej(titulo, metodo, ruta, llave=None, cuerpo=None, extra=None, nota=None):
        nonlocal n
        n += 1
        h = {"X-Request-ID": f"ejemplo-{n:02d}"}
        if llave:
            h["X-API-Key"] = llave
        h.update(extra or {})
        r = c.request(metodo, ruta, headers=h, json=cuerpo)
        enc = "\n".join(f"{k}: {llaves.get(v, v)}" for k, v in h.items() if k != "X-Request-ID")
        bloque = [f"### {titulo}", "", f"`{metodo} {ruta}` → **HTTP {r.status_code}**", ""]
        if nota:
            bloque += [nota, ""]
        bloque += ["**Petición**", "", "```http", f"{metodo} {ruta}", enc]
        if cuerpo is not None:
            bloque += ["", json.dumps(cuerpo, ensure_ascii=False, indent=2)]
        bloque += ["```", "", "**Respuesta**", "", "```json", json.dumps(r.json(), ensure_ascii=False, indent=2),
                   "```", ""]
        secciones.append("\n".join(bloque))
        return r.json()

    secciones.append("## Sistema\n")
    ej("Salud (sin llave)", "GET", "/health")
    ej("Preparación", "GET", "/ready", KL)

    secciones.append("## Productos y resolución\n")
    ej("Producto por código", "GET", "/v1/productos/PP-24-C6", KL)
    ej("Producto inexistente", "GET", "/v1/productos/NO-EXISTE", KL)
    ej("Búsqueda", "POST", "/v1/productos/buscar", KL, {"texto": "cámara", "solo_con_stock": True})
    ej("Resolver modelos", "POST", "/v1/resolver", KL,
       {"modelos": ["PP-24-C6", "DS 2CD2143G2 I", "UTP6-305AZ"]},
       nota="Tres casos: resuelto (nivel 0), requiere confirmación (nivel 2) y no encontrado (nivel 4).")
    ej("Guardar equivalencia elegida por una persona", "POST", "/v1/equivalencias", KB,
       {"modelo_bbinco": "DS 2CD2143G2 I", "codigo_odoo": "2CD2143G2-I", "confirmado_por": "Vendedor"})
    ej("Solicitar alta", "POST", "/v1/altas", KB,
       {"modelo_bbinco": "UTP6-305AZ", "descripcion": "Bobina UTP Cat6 azul 305 m", "solicitado_por": "agente",
        "cotizacion_referencia": "BUF-000001"})
    ej("Consulta en lista blanca", "POST", "/v1/consultas", KL,
       {"modelo": "res.partner", "dominio": [["name", "ilike", "hotel"]], "campos": ["id", "name"]})

    secciones.append("## Cotizaciones en la DB Buffer y exportación a Odoo\n")
    ej("Crear cotización en el buffer", "POST", "/v1/cotizaciones", KB, COT)
    pf = ej("Paso 1 · Simular exportación (preflight)", "POST", "/v1/cotizaciones/BUF-000001/exportar", KL,
            {"dry_run": True})
    tok = pf["data"]["token_preflight"]
    ej("Paso 2 · Exportar a Odoo (tras confirmación humana)", "POST", "/v1/cotizaciones/BUF-000001/exportar", KO,
       {"dry_run": False, "token_preflight": tok})
    ej("Reintento: idempotente, no crea otra", "POST", "/v1/cotizaciones/BUF-000001/exportar", KO,
       {"dry_run": False})

    secciones.append("## Cotizaciones vivas en Odoo\n")
    ej("Leer cotización de Odoo", "GET", "/v1/odoo/cotizaciones/S00042", KL)
    ej("Simular inyección de partidas", "POST", "/v1/odoo/cotizaciones/S00042/partidas", KL,
       {"partidas": [{"seccion": "Voz y datos", "codigo_odoo": "JACK-C6-AZ", "descripcion": "Jack Cat6 azul",
                      "cantidad": 10, "precio_unitario": 68.0}], "dry_run": True})

    secciones.append("## Sincronización\n")
    job = ej("Lanzar sincronización", "POST", "/v1/sync/productos", KB, {"completa": True})
    ej("Consultar avance", "GET", f"/v1/jobs/{job['data']['job_id']}", KL)

    secciones.append("## Errores\n")
    ej("Sin llave", "GET", "/ready")
    ej("Llave sin el nivel requerido", "POST", "/v1/altas", KL,
       {"modelo_bbinco": "X", "descripcion": "Y", "solicitado_por": "agente"})
    ej("Entrada inválida", "POST", "/v1/resolver", KL, {"modelos": []})
    ej("Escenario simulado: Odoo caído", "GET", "/ready", KL, extra={"X-Mock-Escenario": "odoo_caido"})

    encabezado = (f"# Ejemplos del contrato {CONTRATO_VERSION}\n\n"
                  "Generado automáticamente por `scripts/generar_docs.py` a partir de llamadas reales al esqueleto. "
                  "Las llaves se muestran como marcadores. Las fechas y tokens cambian en cada ejecución.\n\n")
    with open(os.path.join(DOCS, "ejemplos.md"), "w", encoding="utf-8") as fh:
        fh.write(encabezado + "\n".join(secciones))
    print(f"docs/openapi.json y docs/ejemplos.md generados ({n} ejemplos).")


if __name__ == "__main__":
    main()
