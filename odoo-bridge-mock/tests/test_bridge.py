import copy
import time

from conftest import COTIZACION, KL


def _env(r, status=200):
    assert r.status_code == status, r.text
    j = r.json()
    assert j["modo"] == "mock" and j["contrato"] and j["request_id"]
    return j


# --------------------------------------------------------------- sistema / auth

def test_health_sin_llave(c):
    j = _env(c.get("/health"))
    assert j["data"]["estado"] == "ok"


def test_ready_requiere_llave(c, L):
    assert _env(c.get("/ready"), 401)["error"]["codigo"] == "API_KEY_FALTANTE"
    assert _env(c.get("/ready", headers={"X-API-Key": "x"}), 401)["error"]["codigo"] == "API_KEY_INVALIDA"
    assert _env(c.get("/ready", headers=L))["data"]["estado"] == "listo"


def test_encabezados_y_request_id(c, L):
    r = c.get("/ready", headers=L | {"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123" and r.headers["X-Bridge-Modo"] == "mock"
    assert r.json()["request_id"] == "abc123"


def test_niveles_de_llave(c, L, B):
    cuerpo = {"modelo_bbinco": "X", "descripcion": "Y", "solicitado_por": "agente"}
    assert _env(c.post("/v1/altas", json=cuerpo, headers=L), 403)["error"]["codigo"] == "ALCANCE_INSUFICIENTE"
    assert _env(c.post("/v1/altas", json=cuerpo, headers=B), 201)["data"]["id"] == "ALTA-0001"


def test_ruta_inexistente_usa_envoltura(c, L):
    assert _env(c.get("/v1/nada", headers=L), 404)["error"]["codigo"] == "RUTA_NO_ENCONTRADA"


def test_entrada_invalida(c, L):
    j = _env(c.post("/v1/resolver", json={"modelos": []}, headers=L), 422)
    assert j["error"]["codigo"] == "ENTRADA_INVALIDA" and j["error"]["detalle"][0]["campo"] == "modelos"


# --------------------------------------------------------------- escenarios

def test_escenarios(c, L):
    def esc(e):
        return c.get("/ready", headers=L | {"X-Mock-Escenario": e})
    assert _env(esc("error"), 500)["error"]["codigo"] == "ERROR_INTERNO"
    assert _env(esc("odoo_caido"), 503)["error"]["codigo"] == "ODOO_NO_DISPONIBLE"
    assert _env(esc("buffer_caido"), 503)["error"]["codigo"] == "BUFFER_NO_DISPONIBLE"
    assert _env(esc("inventado"), 400)["error"]["codigo"] == "ESCENARIO_DESCONOCIDO"
    t0 = time.perf_counter()
    _env(esc("lento"))
    assert time.perf_counter() - t0 >= 0.05


def test_escenario_no_salta_autenticacion(c):
    assert _env(c.get("/ready", headers={"X-Mock-Escenario": "error"}), 401)


def test_listado_escenarios(c, L):
    j = _env(c.get("/v1/escenarios", headers=L))
    assert "falla_job" in j["data"]["escenarios"] and "AMBIGUO" in j["data"]["palabras_clave_resolver"]


# --------------------------------------------------------------- productos / resolver

def test_producto_por_codigo(c, L):
    p = _env(c.get("/v1/productos/PP-24-C6", headers=L))["data"]
    assert p["odoo_id"] == 102 and p["origen"]["tipo"] == "odoo" and p["stock_disponible"] == 6
    assert _env(c.get("/v1/productos/NO-EXISTE", headers=L), 404)["error"]["codigo"] == "PRODUCTO_NO_ENCONTRADO"
    j = _env(c.get("/v1/productos/SYS-SW-24G", headers=L))
    assert j["data"]["odoo_id"] is None and j["avisos"]


def test_buscar(c, L):
    d = _env(c.post("/v1/productos/buscar", json={"texto": "cámara"}, headers=L))["data"]
    assert d["total"] == 2
    d = _env(c.post("/v1/productos/buscar", json={"fuente": "proveedores"}, headers=L))["data"]
    assert all(p["origen"]["tipo"] == "proveedor" for p in d["productos"]) and d["total"] == 2
    d = _env(c.post("/v1/productos/buscar", json={"fuente": "odoo", "solo_con_stock": True}, headers=L))["data"]
    assert all(p["stock_disponible"] for p in d["productos"])
    todas = _env(c.post("/v1/productos/buscar", json={}, headers=L))["data"]["productos"]
    tipos = [p["origen"]["tipo"] for p in todas]
    assert tipos == sorted(tipos, key=lambda t: t != "odoo")  # Odoo primero


def test_resolver_niveles(c, L):
    modelos = ["PP-24-C6", "pp 24 c6", "DS 2CD2143G2 I", "UTP6-305AZ", "X-NOEXISTE", "Y-AMBIGUO", "Z PROVEEDOR",
               "PP-24-C6"]
    d = _env(c.post("/v1/resolver", json={"modelos": modelos}, headers=L))
    r = {x["modelo"]: x for x in d["data"]["resultados"]}
    assert len(d["data"]["resultados"]) == 7 and "duplicados" in d["avisos"][0]
    assert r["PP-24-C6"]["estado"] == "resuelto" and r["PP-24-C6"]["nivel"] == 0 and r["PP-24-C6"]["aplicar_sin_confirmar"]
    assert r["pp 24 c6"]["nivel"] == 1 and r["pp 24 c6"]["producto"]["codigo"] == "PP-24-C6"
    cam = r["DS 2CD2143G2 I"]
    assert cam["estado"] == "requiere_confirmacion" and not cam["aplicar_sin_confirmar"]
    assert [x["producto"]["codigo"] for x in cam["candidatos"]] == ["2CD2143G2-I", "2CD2143G2-IS"]
    assert r["UTP6-305AZ"]["estado"] == "no_encontrado" and len(r["UTP6-305AZ"]["salidas_posibles"]) == 3
    assert r["X-NOEXISTE"]["estado"] == "no_encontrado"
    assert r["Y-AMBIGUO"]["estado"] == "requiere_confirmacion" and len(r["Y-AMBIGUO"]["candidatos"]) == 2
    assert r["Z PROVEEDOR"]["producto"]["origen"]["nombre"] == "Syscom"


def test_resolver_sin_proveedores(c, L):
    d = _env(c.post("/v1/resolver", json={"modelos": ["SYS-SW-24G"], "incluir_proveedores": False}, headers=L))
    assert d["data"]["resultados"][0]["estado"] == "no_encontrado"


def test_equivalencia_cambia_resolucion(c, L, B):
    antes = _env(c.post("/v1/resolver", json={"modelos": ["DS 2CD2143G2 I"]}, headers=L))["data"]["resultados"][0]
    assert antes["estado"] == "requiere_confirmacion"
    _env(c.post("/v1/equivalencias", json={"modelo_bbinco": "DS 2CD2143G2 I", "codigo_odoo": "2CD2143G2-I",
                                           "confirmado_por": "Vendedor"}, headers=B), 201)
    despues = _env(c.post("/v1/resolver", json={"modelos": ["ds-2cd2143g2-i"]}, headers=L))["data"]["resultados"][0]
    assert despues["estado"] == "resuelto" and despues["via"] == "equivalencia" and despues["nivel"] == 0
    j = _env(c.post("/v1/equivalencias", json={"modelo_bbinco": "A", "codigo_odoo": "NO-EXISTE",
                                               "confirmado_por": "x"}, headers=B), 422)
    assert j["error"]["codigo"] == "CODIGO_ODOO_INEXISTENTE"


def test_altas(c, L, B):
    a = _env(c.post("/v1/altas", json={"modelo_bbinco": "UTP6-305AZ", "descripcion": "Bobina azul",
                                       "solicitado_por": "agente"}, headers=B), 201)["data"]
    assert a["estado"] == "solicitada"
    assert _env(c.get(f"/v1/altas/{a['id']}", headers=L))["data"]["modelo_bbinco"] == "UTP6-305AZ"
    assert _env(c.get("/v1/altas/ALTA-9999", headers=L), 404)["error"]["codigo"] == "ALTA_NO_ENCONTRADA"


def test_consultas(c, L):
    d = _env(c.post("/v1/consultas", json={"modelo": "res.partner", "dominio": [["name", "ilike", "hotel"]]},
                    headers=L))["data"]
    assert d["total"] == 1 and d["registros"][0]["id"] == 7
    j = _env(c.post("/v1/consultas", json={"modelo": "res.partner", "campos": ["name", "password"]}, headers=L))
    assert "password" in j["avisos"][0] and "password" not in j["data"]["registros"][0]
    j = _env(c.post("/v1/consultas", json={"modelo": "hr.payslip"}, headers=L), 403)
    assert j["error"]["codigo"] == "MODELO_NO_PERMITIDO"


# --------------------------------------------------------------- cotizaciones

def _crear(c, B, cuerpo=None):
    return _env(c.post("/v1/cotizaciones", json=cuerpo or COTIZACION, headers=B), 201)["data"]


def test_crear_leer_reemplazar(c, L, B):
    cot = _crear(c, B)
    assert cot["referencia"] == "BUF-000001" and cot["estado"] == "borrador"
    assert cot["totales"]["subtotal"] == 2 * 1190 + 3 * 2890 + 4 * 350
    assert _env(c.get("/v1/cotizaciones/BUF-000001", headers=L))["data"]["totales"]["partidas"] == 3
    nuevo = copy.deepcopy(COTIZACION)
    nuevo["partidas"] = nuevo["partidas"][:1]
    assert _env(c.put("/v1/cotizaciones/BUF-000001", json=nuevo, headers=B))["data"]["totales"]["partidas"] == 1
    assert _env(c.get("/v1/cotizaciones/BUF-9", headers=L), 404)["error"]["codigo"] == "COTIZACION_NO_ENCONTRADA"


def test_flujo_exportacion_completo(c, L, B, O):
    _crear(c, B)
    pf = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={"dry_run": True}, headers=L))["data"]
    assert pf["listo_para_exportar"] and pf["lineas_a_crear"] == 3 + 2
    assert pf["secciones"] == ["Voz y datos", "Servicios"]
    assert any("flete en 2" in x for x in pf["no_incluye"]) and "impuestos" in pf["no_incluye"]
    tok = pf["token_preflight"]
    # La llave de buffer no alcanza para escribir en Odoo
    assert _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={"dry_run": False, "token_preflight": tok},
                       headers=B), 403)
    r = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={"dry_run": False, "token_preflight": tok},
                    headers=O))["data"]
    assert r["folio_odoo"] == "S00043" and r["estado_odoo"] == "draft" and not r["ya_existia"]
    # Idempotencia: reintento devuelve la misma
    r2 = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={"dry_run": False}, headers=O))
    assert r2["data"]["folio_odoo"] == "S00043" and r2["data"]["ya_existia"]
    cot = _env(c.get("/v1/cotizaciones/BUF-000001", headers=L))["data"]
    assert cot["estado"] == "exportada" and cot["odoo"]["folio"] == "S00043"
    od = _env(c.get("/v1/odoo/cotizaciones/S00043", headers=L))["data"]
    assert od["referencia_buffer"] == "BUF-000001" and [l["tipo"] for l in od["lineas"]].count("seccion") == 2
    j = _env(c.put("/v1/cotizaciones/BUF-000001", json=COTIZACION, headers=B), 409)
    assert j["error"]["codigo"] == "COTIZACION_EXPORTADA"


def test_exportar_sin_token_y_token_viejo(c, L, B, O):
    _crear(c, B)
    j = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={"dry_run": False}, headers=O), 422)
    assert j["error"]["codigo"] == "TOKEN_PREFLIGHT_REQUERIDO"
    tok = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={}, headers=L))["data"]["token_preflight"]
    cambiado = copy.deepcopy(COTIZACION)
    cambiado["partidas"][0]["cantidad"] = 99
    _env(c.put("/v1/cotizaciones/BUF-000001", json=cambiado, headers=B))
    j = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={"dry_run": False, "token_preflight": tok},
                    headers=O), 409)
    assert j["error"]["codigo"] == "TOKEN_PREFLIGHT_INVALIDO"


def test_token_expira(c, L, B, O, reloj):
    _crear(c, B)
    tok = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={}, headers=L))["data"]["token_preflight"]
    reloj.t += 16 * 60
    j = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={"dry_run": False, "token_preflight": tok},
                    headers=O), 409)
    assert j["error"]["codigo"] == "TOKEN_PREFLIGHT_INVALIDO"


def test_preflight_con_bloqueos(c, L, B):
    cuerpo = copy.deepcopy(COTIZACION)
    cuerpo["cliente"] = {"nombre": "Cliente nuevo"}
    cuerpo["partidas"][0]["precio_unitario"] = None
    cuerpo["partidas"][1]["codigo_odoo"] = "INVENTADO"
    cuerpo["partidas"].append({"seccion": "Voz y datos", "modelo_bbinco": "UTP6-305AZ", "codigo_odoo": None,
                               "descripcion": "Bobina azul (sin producto)", "cantidad": 1, "precio_unitario": 3000})
    cot = _env(c.post("/v1/cotizaciones", json=cuerpo, headers=B), 201)
    assert any("sin producto" in a for a in cot["avisos"]) and any("sin precio" in a for a in cot["avisos"])
    pf = _env(c.post("/v1/cotizaciones/BUF-000001/exportar", json={}, headers=L))["data"]
    codigos = {b["codigo"] for b in pf["bloqueos"]}
    assert codigos == {"SIN_PRECIO", "CODIGO_INEXISTENTE", "CLIENTE_SIN_ODOO_ID"}
    assert not pf["listo_para_exportar"] and pf["token_preflight"] is None


def test_cantidad_invalida(c, B):
    cuerpo = copy.deepcopy(COTIZACION)
    cuerpo["partidas"][0]["cantidad"] = 0
    assert _env(c.post("/v1/cotizaciones", json=cuerpo, headers=B), 422)["error"]["codigo"] == "ENTRADA_INVALIDA"


def test_cotizacion_odoo_e_inyeccion(c, L, O):
    od = _env(c.get("/v1/odoo/cotizaciones/S00042", headers=L))["data"]
    assert od["estado"] == "draft" and od["total_sin_impuestos"] == 12450.0
    assert _env(c.get("/v1/odoo/cotizaciones/S99999", headers=L), 404)
    partidas = [
        {"seccion": "Voz y datos", "codigo_odoo": "PP-24-C6", "descripcion": "Patch panel", "cantidad": 5},
        {"seccion": "Voz y datos", "codigo_odoo": "JACK-C6-AZ", "descripcion": "Jack azul", "cantidad": 10,
         "precio_unitario": 68.0},
        {"seccion": "Voz y datos", "codigo_odoo": None, "modelo_bbinco": "UTP6-305AZ", "descripcion": "Bobina azul",
         "cantidad": 1},
    ]
    plan = _env(c.post("/v1/odoo/cotizaciones/S00042/partidas", json={"partidas": partidas}, headers=L))["data"]
    assert [a["accion"] for a in plan["acciones"]] == ["actualizar", "agregar", "solicitar_alta"]
    assert _env(c.post("/v1/odoo/cotizaciones/S00042/partidas",
                       json={"partidas": partidas, "dry_run": False, "token_preflight": plan["token_preflight"]},
                       headers=L), 403)
    res = _env(c.post("/v1/odoo/cotizaciones/S00042/partidas",
                      json={"partidas": partidas, "dry_run": False, "token_preflight": plan["token_preflight"]},
                      headers=O))
    assert res["data"]["aplicado"] and res["avisos"]
    od = _env(c.get("/v1/odoo/cotizaciones/S00042", headers=L))["data"]
    assert od["total_sin_impuestos"] == 12450.0 - 2380.0 + 5 * 1190.0 + 680.0


# --------------------------------------------------------------- sincronización

def test_sync_avanza_y_termina(c, L, B, reloj):
    job = _env(c.post("/v1/sync/productos", json={"completa": True}, headers=B), 202)["data"]
    assert job["estado"] == "en_cola" and job["lotes_totales"] == 5
    jid = job["job_id"]
    reloj.t += 4.5
    v = _env(c.get(f"/v1/jobs/{jid}", headers=L))["data"]
    assert v["estado"] == "corriendo" and v["lote_actual"] == 2
    assert _env(c.post("/v1/sync/productos", headers=B), 409)["error"]["codigo"] == "SYNC_EN_CURSO"
    reloj.t += 10
    v = _env(c.get(f"/v1/jobs/{jid}", headers=L))["data"]
    assert v["estado"] == "completado" and v["registros_procesados"] == v["registros_totales"] and v["terminado"]
    assert _env(c.post("/v1/sync/productos", headers=B), 202)["data"]["tipo"] == "incremental"


def test_sync_falla(c, L, B, reloj):
    jid = _env(c.post("/v1/sync/cotizaciones", json={"completa": True},
                      headers=B | {"X-Mock-Escenario": "falla_job"}), 202)["data"]["job_id"]
    reloj.t += 200
    v = _env(c.get(f"/v1/jobs/{jid}", headers=L))["data"]
    assert v["estado"] == "fallido" and v["lote_actual"] == 17 and "lote 18" in v["error"]


def test_sync_validaciones(c, L, B):
    assert _env(c.post("/v1/sync/nominas", headers=B), 422)
    assert _env(c.post("/v1/sync/productos", headers=L), 403)
    assert _env(c.get("/v1/jobs/sync-x", headers=L), 404)["error"]["codigo"] == "JOB_NO_ENCONTRADO"


def test_openapi_lista_todos_los_endpoints(c):
    rutas = c.get("/openapi.json").json()["paths"]
    esperadas = {"/health", "/ready", "/v1/escenarios", "/v1/productos/{codigo}", "/v1/productos/buscar",
                 "/v1/resolver", "/v1/consultas", "/v1/equivalencias", "/v1/altas", "/v1/altas/{alta_id}",
                 "/v1/cotizaciones", "/v1/cotizaciones/{referencia}", "/v1/cotizaciones/{referencia}/exportar",
                 "/v1/odoo/cotizaciones/{folio}", "/v1/odoo/cotizaciones/{folio}/partidas",
                 "/v1/sync/{entidad}", "/v1/jobs/{job_id}"}
    assert esperadas <= set(rutas)


def test_llave_nunca_en_respuesta(c, L):
    r = c.get("/ready", headers=L)
    assert KL not in r.text
