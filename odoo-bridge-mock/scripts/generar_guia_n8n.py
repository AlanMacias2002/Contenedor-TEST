"""Genera docs/guia_n8n.md: ejemplos de uso del bridge desde nodos de n8n.

Cada ejemplo ejecuta la petición contra el esqueleto, así la respuesta mostrada
es exactamente la que devuelve el mock:
    python scripts/generar_guia_n8n.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import CONTRATO_VERSION, Settings  # noqa: E402
from app.main import create_app  # noqa: E402

BASE = "http://odoo-bridge:8000"
LLAVES = {"lectura": "LLAVE_LECTURA", "buffer": "LLAVE_BUFFER", "odoo": "LLAVE_ODOO"}
CRED = {"lectura": "odoo-bridge · lectura", "buffer": "odoo-bridge · buffer", "odoo": "odoo-bridge · odoo"}
DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")


def nodo(nombre: str, metodo: str, ruta: str, nivel: str, cuerpo_n8n: str | None, herramienta: str | None,
         escenario: str | None = None) -> dict:
    """JSON de un nodo de n8n listo para pegar en el lienzo."""
    params: dict = {}
    if metodo != "GET":
        params["method"] = metodo
    params["url"] = BASE + ruta
    params["authentication"] = "genericCredentialType"
    params["genericAuthType"] = "httpHeaderAuth"
    headers = [{"name": "X-Request-ID", "value": "={{ $execution.id }}"}]
    if escenario:
        headers.append({"name": "X-Mock-Escenario", "value": escenario})
    params["sendHeaders"] = True
    params["headerParameters"] = {"parameters": headers}
    if cuerpo_n8n is not None:
        params["sendBody"] = True
        params["specifyBody"] = "json"
        params["jsonBody"] = cuerpo_n8n
    params["options"] = {"response": {"response": {"neverError": True}}, "timeout": 30000}
    if herramienta:
        params = {"toolDescription": herramienta, **params}
    n = {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, nombre)), "name": nombre,
         "type": "n8n-nodes-base.httpRequestTool" if herramienta else "n8n-nodes-base.httpRequest",
         "typeVersion": 4.2, "position": [0, 0]}
    return {"nodes": [n], "connections": {}}


def main() -> None:
    app = create_app(Settings(key_lectura=LLAVES["lectura"], key_buffer=LLAVES["buffer"], key_odoo=LLAVES["odoo"],
                              segundos_por_lote=0.0001, lento_segundos=0))
    c = TestClient(app)
    partes: list[str] = []
    n = 0

    def ejemplo(titulo: str, *, usuario: str | None, tipo: str, metodo: str, ruta: str, nivel: str,
                cuerpo: dict | None = None, cuerpo_n8n: str | None = None, herramienta: str | None = None,
                escenario: str | None = None, lectura: list[tuple[str, str]] | None = None,
                notas: list[str] | None = None, mostrar=None) -> dict:
        nonlocal n
        n += 1
        h = {"X-API-Key": LLAVES[nivel], "X-Request-ID": f"ejecucion-{1000 + n}"}
        if escenario:
            h["X-Mock-Escenario"] = escenario
        r = c.request(metodo, ruta, headers=h, json=cuerpo)
        resp = r.json()
        nombre = titulo
        if cuerpo_n8n is None and cuerpo is not None:
            cuerpo_n8n = json.dumps(cuerpo, ensure_ascii=False, indent=2)
        nd = nodo(nombre, metodo, ruta, nivel, cuerpo_n8n, herramienta, escenario)

        b = [f"### {n}. {titulo}", ""]
        if usuario:
            b += [f"> 💬 **Usuario:** {usuario}", ""]
        b += ["| Campo del nodo | Valor |", "|---|---|",
              f"| Tipo de nodo | **{tipo}** |",
              f"| Method | `{metodo}` |",
              f"| URL | `{BASE}{ruta}` |",
              f"| Authentication | Generic Credential Type → Header Auth → **{CRED[nivel]}** |",
              "| Send Headers | `X-Request-ID` = `{{ $execution.id }}`" +
              (f"; `X-Mock-Escenario` = `{escenario}`" if escenario else "") + " |"]
        if cuerpo_n8n is not None:
            b.append("| Send Body | JSON (ver abajo) |")
        b += ["| Options → Response | **Never Error** activado |", ""]
        if herramienta:
            b += [f"**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):", "",
                  f"> {herramienta}", ""]
        if cuerpo_n8n is not None:
            b += ["**Cuerpo JSON en el nodo**", "", "```", cuerpo_n8n, "```", ""]
            if cuerpo is not None and cuerpo_n8n != json.dumps(cuerpo, ensure_ascii=False, indent=2):
                b += ["Con los valores de este ejemplo, n8n envía:", "", "```json",
                      json.dumps(cuerpo, ensure_ascii=False, indent=2), "```", ""]
        b += [f"**Respuesta del mock** — HTTP {r.status_code}", "", "```json",
              json.dumps(mostrar(resp) if mostrar else resp, ensure_ascii=False, indent=2), "```", ""]
        if lectura:
            b += ["**Cómo leer la respuesta en n8n**", "", "| Expresión | Valor en este ejemplo |", "|---|---|"]
            for expr, valor in lectura:
                b.append(f"| `{expr}` | {valor} |")
            b.append("")
        for nota in notas or []:
            b += [nota, ""]
        b += ["<details><summary>JSON del nodo para pegar en n8n</summary>", "", "```json",
              json.dumps(nd, ensure_ascii=False, indent=2), "```", "", "</details>", "", "---", ""]
        partes.append("\n".join(b))
        return resp

    # ------------------------------------------------------------------ guion
    partes.append("## A. Antes de empezar una conversación\n")
    ejemplo("Verificar que el bridge está disponible", usuario=None, tipo="HTTP Request (flujo)",
            metodo="GET", ruta="/ready", nivel="lectura",
            lectura=[("{{ $json.ok }}", "`true`"), ("{{ $json.data.estado }}", "`listo`"),
                     ("{{ $json.data.odoo.dias_para_expirar }}", "`89`")],
            notas=["Úsalo al inicio de un flujo, o en un flujo programado de monitoreo. "
                   "Si `ok` es `false`, el agente puede avisar que el servicio no está disponible "
                   "en lugar de intentar las herramientas."])

    partes.append("## B. Resolver modelos y elegir productos\n")
    res = ejemplo(
        "Resolver modelos", tipo="HTTP Request Tool (herramienta del agente)",
        usuario="Dame los códigos de Odoo para CS-PP24-C6, DS 2CD2143G2 I y UTP6-305AZ",
        metodo="POST", ruta="/v1/resolver", nivel="lectura",
        cuerpo={"modelos": ["CS-PP24-C6", "DS 2CD2143G2 I", "UTP6-305AZ"]},
        cuerpo_n8n='={{ JSON.stringify({ modelos: $fromAI("modelos", "Lista de modelos o números de parte '
                   'tal como los escribió el usuario", "json") }) }}',
        herramienta=("Resuelve modelos o números de parte de BBINCO a códigos oficiales de Odoo. Úsala siempre que "
                     "el usuario mencione modelos. Nunca inventes códigos. Si un resultado tiene "
                     "aplicar_sin_confirmar=false, muestra los candidatos y pide al usuario que elija."),
        lectura=[("{{ $json.data.resultados.length }}", "`3`"),
                 ("{{ $json.data.resultados[0].estado }}", "`requiere_confirmacion`"),
                 ("{{ $json.data.resultados[1].candidatos[0].producto.codigo }}", "`2CD2143G2-I`"),
                 ("{{ $json.data.resultados[2].salidas_posibles }}",
                  "`[\"equivalente_registrado\", \"solicitar_alta\", \"sin_producto_asociado\"]`")],
        notas=["En un flujo normal (no herramienta), separa los resultados con un nodo **Split Out** sobre "
               "`data.resultados` y ramifica con un **Switch** sobre `{{ $json.estado }}`: `resuelto`, "
               "`requiere_confirmacion` y `no_encontrado`.",
               "`$fromAI(...)` le indica al agente qué dato debe llenar. Es propio de los nodos de herramienta; "
               "en un HTTP Request normal escribe el cuerpo con datos de nodos anteriores."])

    ejemplo("Guardar la elección del usuario", tipo="HTTP Request Tool (herramienta del agente)",
            usuario="La primera opción, la cámara sin audio.",
            metodo="POST", ruta="/v1/equivalencias", nivel="buffer",
            cuerpo={"modelo_bbinco": "DS 2CD2143G2 I", "codigo_odoo": "2CD2143G2-I",
                    "confirmado_por": "Vendedor", "cotizacion_referencia": None},
            cuerpo_n8n=('={{ JSON.stringify({\n  modelo_bbinco: $fromAI("modelo_bbinco", "Modelo tal como lo '
                        'escribió el usuario", "string"),\n  codigo_odoo: $fromAI("codigo_odoo", "Código del '
                        'candidato que eligió el usuario", "string"),\n  confirmado_por: "Vendedor",\n  '
                        'cotizacion_referencia: null\n}) }}'),
            herramienta=("Guarda la equivalencia entre un modelo de BBINCO y el código de Odoo que el usuario "
                         "confirmó. Úsala solo después de que el usuario elija explícitamente un candidato."),
            lectura=[("{{ $json.data.modelo_normalizado }}", "`DS2CD2143G2I`")],
            notas=["Después de guardarla, ese modelo se resuelve solo (nivel 0, `via: \"equivalencia\"`). "
                   "Requiere la credencial de nivel **buffer**."])

    ejemplo("Volver a resolver el mismo modelo", tipo="HTTP Request Tool (herramienta del agente)",
            usuario="Agrega otras dos cámaras DS 2CD2143G2 I.",
            metodo="POST", ruta="/v1/resolver", nivel="lectura", cuerpo={"modelos": ["DS 2CD2143G2 I"]},
            lectura=[("{{ $json.data.resultados[0].estado }}", "`resuelto`"),
                     ("{{ $json.data.resultados[0].via }}", "`equivalencia`"),
                     ("{{ $json.data.resultados[0].aplicar_sin_confirmar }}", "`true`")],
            notas=["Es la misma herramienta del ejemplo 2; se muestra para ver el efecto de la equivalencia."])

    ejemplo("Solicitar el alta de un producto inexistente", tipo="HTTP Request Tool (herramienta del agente)",
            usuario="Ese no lo tenemos; pide que lo den de alta.",
            metodo="POST", ruta="/v1/altas", nivel="buffer",
            cuerpo={"modelo_bbinco": "UTP6-305AZ", "descripcion": "Bobina cable UTP Cat6 azul 305 m",
                    "marca": None, "solicitado_por": "Vendedor", "cotizacion_referencia": None},
            herramienta=("Solicita al área responsable el alta de un producto que no existe en el catálogo. "
                         "Úsala cuando la resolución devuelva no_encontrado y el usuario elija solicitar el alta."),
            lectura=[("{{ $json.data.id }}", "`ALTA-0001`"), ("{{ $json.data.estado }}", "`solicitada`")])

    partes.append("## C. Consultar productos y clientes\n")
    ejemplo("Producto por código", tipo="HTTP Request Tool (herramienta del agente)",
            usuario="¿Cuántos patch panel PP-24-C6 tenemos y a qué precio?",
            metodo="GET", ruta="/v1/productos/PP-24-C6", nivel="lectura",
            herramienta=("Consulta un producto por su código exacto de Odoo: precio, costo y existencias. "
                         "Si no conoces el código exacto, usa primero resolver_modelos."),
            lectura=[("{{ $json.data.stock_disponible }}", "`6`"), ("{{ $json.data.precio_unitario }}", "`1190`"),
                     ("{{ $json.data.origen.tipo }}", "`odoo`")],
            notas=["En la herramienta, la URL lleva el código variable: "
                   "`http://odoo-bridge:8000/v1/productos/{{ $fromAI(\"codigo\", \"Código exacto de Odoo\", "
                   "\"string\") }}` (escribe la URL en modo expresión, con `=` al inicio)."])

    ejemplo("Buscar productos", tipo="HTTP Request Tool (herramienta del agente)",
            usuario="¿Qué cámaras tenemos en existencia?",
            metodo="POST", ruta="/v1/productos/buscar", nivel="lectura",
            cuerpo={"texto": "cámara", "solo_con_stock": True, "fuente": "todas", "limite": 10},
            cuerpo_n8n=('={{ JSON.stringify({\n  texto: $fromAI("texto", "Palabras a buscar en código o nombre", '
                        '"string"),\n  solo_con_stock: $fromAI("solo_con_stock", "true si el usuario pide solo lo '
                        'que hay en existencia", "boolean"),\n  fuente: "todas",\n  limite: 10\n}) }}'),
            herramienta=("Busca productos por texto, primero en el inventario propio de BBINCO y después en "
                         "catálogos de proveedores. Úsala cuando el usuario describa un producto sin dar su código."),
            lectura=[("{{ $json.data.total }}", "`1`"), ("{{ $json.data.productos[0].nombre }}", "`Cámara domo IP 4 MP`")])

    ejemplo("Consultar un cliente en Odoo", tipo="HTTP Request Tool (herramienta del agente)",
            usuario="La cotización es para el Hotel Ejemplo.",
            metodo="POST", ruta="/v1/consultas", nivel="lectura",
            cuerpo={"modelo": "res.partner", "dominio": [["name", "ilike", "hotel ejemplo"]], "campos": ["id", "name", "email"],
                    "limite": 5},
            herramienta=("Busca un cliente en Odoo por nombre para obtener su odoo_id. Úsala antes de crear una "
                         "cotización si no conoces el id del cliente."),
            lectura=[("{{ $json.data.registros[0].id }}", "`7` → se usa como `cliente.odoo_id`")])

    partes.append("## D. Armar la cotización y exportarla a Odoo\n")
    cot = {"cliente": {"odoo_id": 7, "nombre": "Hotel Ejemplo Los Cabos"}, "folio_levantamiento": "L000123",
           "moneda": "MXN", "notas": None,
           "partidas": [
               {"seccion": "Voz y datos", "modelo_bbinco": "CS-PP24-C6", "codigo_odoo": "PP-24-C6",
                "descripcion": "Patch panel 24 puertos Cat6", "cantidad": 2, "precio_unitario": 1190.0, "flete": None},
               {"seccion": "Videovigilancia", "modelo_bbinco": "DS 2CD2143G2 I", "codigo_odoo": "2CD2143G2-I",
                "descripcion": "Cámara domo IP 4 MP", "cantidad": 2, "precio_unitario": 2350.0, "flete": 120.0},
               {"seccion": "Servicios", "modelo_bbinco": None, "codigo_odoo": "BBI-SERV-DATOS",
                "descripcion": "Cableado por nodo", "cantidad": 4, "precio_unitario": 350.0, "flete": 0.0}]}
    ejemplo("Crear la cotización en la DB Buffer", tipo="HTTP Request (flujo)",
            usuario="Listo, arma la cotización con eso.",
            metodo="POST", ruta="/v1/cotizaciones", nivel="buffer", cuerpo=cot,
            cuerpo_n8n=('={{ JSON.stringify({\n  cliente: { odoo_id: $("Consultar cliente").item.json.data.registros[0].id,\n'
                        '             nombre: $("Consultar cliente").item.json.data.registros[0].name },\n'
                        '  folio_levantamiento: $json.folio_levantamiento,\n  moneda: "MXN",\n  notas: null,\n'
                        '  partidas: $json.partidas\n}) }}'),
            lectura=[("{{ $json.data.referencia }}", "`BUF-000001` → guárdala; la usan los pasos siguientes"),
                     ("{{ $json.data.totales.subtotal }}", "`8480`"), ("{{ $json.avisos }}", "`[]`")],
            notas=["Aquí el cuerpo se arma con datos de nodos anteriores: el cliente de la consulta y las partidas "
                   "que el agente fue reuniendo (por ejemplo, en un nodo **Code** o **Set** que construye el arreglo "
                   "`partidas`). Para modificarla más tarde se usa `PUT /v1/cotizaciones/{referencia}` con el mismo cuerpo."])

    pf = ejemplo("Simular la exportación (preflight)", tipo="HTTP Request (flujo)", usuario=None,
                 metodo="POST", ruta="/v1/cotizaciones/BUF-000001/exportar", nivel="lectura",
                 cuerpo={"dry_run": True}, cuerpo_n8n='{\n  "dry_run": true\n}',
                 lectura=[("{{ $json.data.listo_para_exportar }}", "`true`"),
                          ("{{ $json.data.lineas_a_crear }}", "`6` (3 partidas + 3 secciones)"),
                          ("{{ $json.data.no_incluye }}", "`[\"impuestos\", \"flete en 1 partida(s) sin capturar\"]`"),
                          ("{{ $json.data.token_preflight }}", "token de un solo uso, válido 15 min")],
                 notas=["En la URL real la referencia va como expresión: "
                        "`=http://odoo-bridge:8000/v1/cotizaciones/{{ $(\"Crear cotización\").item.json.data.referencia }}/exportar`.",
                        "El resumen (líneas, subtotal, qué no incluye, bloqueos) es lo que el agente le muestra a la "
                        "persona para que confirme. Si `listo_para_exportar` es `false`, lista `data.bloqueos` y no "
                        "continúa."])
    tok = pf["data"]["token_preflight"]

    ejemplo("Exportar a Odoo tras la confirmación", tipo="HTTP Request (flujo)",
            usuario="Sí, confirmo. Súbela a Odoo.",
            metodo="POST", ruta="/v1/cotizaciones/BUF-000001/exportar", nivel="odoo",
            cuerpo={"dry_run": False, "token_preflight": tok},
            cuerpo_n8n=('={{ JSON.stringify({\n  dry_run: false,\n  token_preflight: '
                        '$("Simular exportación").item.json.data.token_preflight\n}) }}'),
            lectura=[("{{ $json.data.folio_odoo }}", "`S00043`"), ("{{ $json.data.estado_odoo }}", "`draft`"),
                     ("{{ $json.data.ya_existia }}", "`false`")],
            notas=["⚠️ Es el único nodo que lleva la credencial **odoo-bridge · odoo**. Conviene que **no** sea una "
                   "herramienta que el agente pueda llamar libremente: colócalo en el flujo después de un paso de "
                   "aprobación explícita (por ejemplo, la respuesta \"sí\" del usuario en Telegram o un nodo de espera "
                   "de aprobación).",
                   "Si n8n reintenta este nodo, el bridge responde con la misma cotización y `ya_existia: true`; no "
                   "se duplica en Odoo."])

    partes.append("## E. Cotizaciones que ya están en Odoo\n")
    ejemplo("Leer una cotización de Odoo", tipo="HTTP Request Tool (herramienta del agente)",
            usuario="¿Qué lleva la cotización S00042?",
            metodo="GET", ruta="/v1/odoo/cotizaciones/S00042", nivel="lectura",
            herramienta="Lee una cotización existente en Odoo por su folio (por ejemplo S00042): líneas, cantidades y total.",
            lectura=[("{{ $json.data.estado }}", "`draft`"), ("{{ $json.data.total_sin_impuestos }}", "`12450`"),
                     ("{{ $json.data.lineas.filter(l => l.tipo === 'producto').length }}", "`3`")])

    plan = ejemplo("Simular partidas adicionales", tipo="HTTP Request (flujo)",
                   usuario="Al S00042 agrégale 10 jacks azules y sube los patch panel a 5.",
                   metodo="POST", ruta="/v1/odoo/cotizaciones/S00042/partidas", nivel="lectura",
                   cuerpo={"dry_run": True, "partidas": [
                       {"seccion": "Voz y datos", "codigo_odoo": "PP-24-C6", "descripcion": "Patch panel 24 puertos Cat6",
                        "cantidad": 5, "precio_unitario": 1190.0},
                       {"seccion": "Voz y datos", "codigo_odoo": "JACK-C6-AZ", "descripcion": "Jack Cat6 color azul",
                        "cantidad": 10, "precio_unitario": 68.0}]},
                   lectura=[("{{ $json.data.acciones.map(a => a.accion) }}", "`[\"actualizar\", \"agregar\"]`")],
                   cuerpo_n8n=('={{ JSON.stringify({\n  dry_run: true,\n  partidas: '
                               '$("Partidas a inyectar").item.json.partidas\n}) }}'),
                   notas=["`Partidas a inyectar` es un nodo **Set** previo donde el agente deja el arreglo de partidas. "
                          "Así la simulación y la aplicación envían exactamente el mismo contenido.",
                          "Igual que la exportación: se muestra el plan, la persona confirma y después se llama con "
                          "`dry_run: false`, el `token_preflight` y la credencial **odoo**."])
    ejemplo("Aplicar las partidas tras la confirmación", tipo="HTTP Request (flujo)", usuario="Confirmo.",
            metodo="POST", ruta="/v1/odoo/cotizaciones/S00042/partidas", nivel="odoo",
            cuerpo={"dry_run": False, "token_preflight": plan["data"]["token_preflight"], "partidas": [
                {"seccion": "Voz y datos", "codigo_odoo": "PP-24-C6", "descripcion": "Patch panel 24 puertos Cat6",
                 "cantidad": 5, "precio_unitario": 1190.0},
                {"seccion": "Voz y datos", "codigo_odoo": "JACK-C6-AZ", "descripcion": "Jack Cat6 color azul",
                 "cantidad": 10, "precio_unitario": 68.0}]},
            cuerpo_n8n=('={{ JSON.stringify({\n  dry_run: false,\n  token_preflight: '
                        '$("Simular partidas").item.json.data.token_preflight,\n  partidas: '
                        '$("Partidas a inyectar").item.json.partidas\n}) }}'),
            lectura=[("{{ $json.data.aplicado }}", "`true`")],
            notas=["⚠️ Las `partidas` deben ser **exactamente las mismas** que en la simulación; si cambian, el "
                   "bridge rechaza el token con `TOKEN_PREFLIGHT_INVALIDO`. Por eso ambos nodos leen el arreglo del mismo "
                   "nodo **Set** (`Partidas a inyectar`)."])

    partes.append("## F. Sincronización bajo demanda\n")
    job = ejemplo("Lanzar una sincronización", tipo="HTTP Request (flujo)", usuario=None,
                  metodo="POST", ruta="/v1/sync/productos", nivel="buffer", cuerpo={"completa": False},
                  lectura=[("{{ $json.data.job_id }}", "id para consultar el avance"),
                           ("{{ $json.data.estado }}", "`en_cola` o `corriendo`")],
                  notas=["Responde **202** de inmediato. La sincronización nocturna la ejecuta el propio bridge; "
                         "esto es solo para lanzarla a mano."])
    ejemplo("Consultar el avance", tipo="HTTP Request (flujo)", usuario=None,
            metodo="GET", ruta=f"/v1/jobs/{job['data']['job_id']}", nivel="lectura",
            lectura=[("{{ $json.data.estado }}", "`completado`"),
                     ("{{ $json.data.lote_actual }} / {{ $json.data.lotes_totales }}", "`1 / 1`")],
            notas=["Patrón en n8n: **Wait** (por ejemplo, 30 s) → este nodo → **IF** `{{ $json.data.estado }}` es "
                   "`completado` o `fallido` → si no, regresa al Wait. Pon un límite de vueltas."])

    partes.append("## G. Errores: cómo se ven en n8n\n")
    ejemplo("Producto inexistente", tipo="HTTP Request Tool (herramienta del agente)", usuario="¿Tienes el XYZ-999?",
            metodo="GET", ruta="/v1/productos/XYZ-999", nivel="lectura",
            lectura=[("{{ $json.ok }}", "`false`"), ("{{ $json.error.codigo }}", "`PRODUCTO_NO_ENCONTRADO`"),
                     ("{{ $json.error.detalle.sugerencia }}", "qué hacer a continuación")],
            notas=["Gracias a **Never Error**, la respuesta 404 llega al flujo como cualquier otra. En una herramienta, "
                   "el agente lee `error.mensaje` y puede intentar otra vía."])
    ejemplo("Odoo no disponible (escenario simulado)", tipo="HTTP Request (flujo)", usuario=None,
            metodo="GET", ruta="/ready", nivel="lectura", escenario="odoo_caido",
            lectura=[("{{ $json.error.codigo }}", "`ODOO_NO_DISPONIBLE`")],
            notas=["El encabezado `X-Mock-Escenario` solo existe en el esqueleto; quítalo al pasar al bridge real."])
    ejemplo("Llave sin el nivel requerido", tipo="HTTP Request (flujo)", usuario=None,
            metodo="POST", ruta="/v1/altas", nivel="lectura",
            cuerpo={"modelo_bbinco": "X", "descripcion": "Y", "solicitado_por": "agente"},
            lectura=[("{{ $json.error.codigo }}", "`ALCANCE_INSUFICIENTE`")],
            notas=["Indica que el nodo usa una credencial de nivel menor al necesario (aquí, lectura en lugar de buffer)."])

    # ------------------------------------------------------------------ documento
    indice = "\n".join(
        f"- {l.split('. ', 1)[1]}" if l.startswith("### ") else f"\n**{l[3:]}**"
        for p in partes for l in p.splitlines() if l.startswith("### ") or l.startswith("## ")
    )
    cabecera = f"""# Guía de uso del bridge desde n8n

**Contrato {CONTRATO_VERSION} · esqueleto (mock)** — documento generado por `scripts/generar_guia_n8n.py` a partir de llamadas reales al esqueleto. Las respuestas son exactamente las que devuelve el mock; las fechas, tokens e ids pueden variar.

Los ejemplos siguen una conversación completa: resolver modelos, elegir productos, armar la cotización, exportarla a Odoo y modificarla después. Cada ejemplo incluye:

1. lo que diría el usuario,
2. la configuración del nodo **HTTP Request** (en un flujo) o **HTTP Request Tool** (herramienta del agente),
3. la respuesta del mock,
4. las expresiones de n8n para leer la respuesta,
5. el JSON del nodo, listo para **copiar y pegar** en el lienzo de n8n (Ctrl+V).

## Antes de usar los ejemplos

**Credenciales.** Crea en n8n tres credenciales de tipo *Header Auth* con `Name: X-API-Key`: `odoo-bridge · lectura`, `odoo-bridge · buffer` y `odoo-bridge · odoo`. 🔴 Los valores son las llaves del bridge; nunca se escriben en el nodo. Al pegar un nodo, n8n no trae la credencial: selecciónala en el campo *Header Auth*.

**URL.** `{BASE}` funciona si n8n y el bridge están en la misma red Docker. Si no, cambia la parte inicial.

**Never Error.** Todos los nodos tienen *Options → Response → Never Error* activado. Así las respuestas con error (4xx, 5xx) llegan al flujo con la envoltura `{{"ok": false, "error": {{...}}}}` y puedes ramificar con un **IF** sobre `{{{{ $json.ok }}}}`.

**Herramientas del agente y `$fromAI`.** En los nodos *HTTP Request Tool*, `$fromAI("nombre", "descripción", "tipo")` marca los datos que el modelo debe llenar a partir de la conversación. La *descripción de la herramienta* es lo que el modelo lee para decidir cuándo usarla: conviene que sea precisa. `$fromAI` requiere una versión reciente de n8n; si la suya no lo reconoce, se puede usar el modo *Defined automatically by the model* de cada campo.

**Qué no conviene dar como herramienta libre.** La exportación a Odoo y la aplicación de partidas (credencial *odoo*) deben ir en el flujo **después de una confirmación explícita** de la persona, no como herramienta que el modelo decida llamar por su cuenta.

## Índice
{indice}

---

"""
    with open(os.path.join(DOCS, "guia_n8n.md"), "w", encoding="utf-8") as fh:
        fh.write(cabecera + "\n".join(partes))
    print(f"docs/guia_n8n.md generado ({n} ejemplos).")


if __name__ == "__main__":
    main()
