"""Cotizaciones en la DB Buffer, exportación a Odoo y cotizaciones vivas en Odoo."""

from __future__ import annotations

import copy
import hashlib
import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request

from . import datos_ejemplo as ej
from .esquemas import (Cotizacion, CotizacionEntrada, CotizacionOdoo, ExportacionResultado, ExportarEntrada,
                       InyeccionEntrada, InyeccionResultado, Preflight, Respuesta)
from .nucleo import BridgeError, Nivel, exigir_nivel, ok
from .seguridad import ERRORES, acceso

router = APIRouter(prefix="/v1", responses=ERRORES)

TOKEN_VIGENCIA_S = 15 * 60
CODIGOS_ODOO = {p["codigo"] for p in ej.CATALOGO if p["origen"]["tipo"] == "odoo"}


def _estado(request: Request):
    return request.app.state.estado


def _huella(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _emitir_token(est, alcance: str, huella: str) -> tuple[str, object]:
    token = secrets.token_urlsafe(24)
    est.tokens[token] = {"alcance": alcance, "huella": huella, "vence": est.reloj() + TOKEN_VIGENCIA_S}
    return token, est.ahora() + timedelta(seconds=TOKEN_VIGENCIA_S)


def _validar_token(est, token: str | None, alcance: str, huella: str) -> None:
    if not token:
        raise BridgeError(422, "TOKEN_PREFLIGHT_REQUERIDO",
                          "Para escribir en Odoo envía dry_run=false junto con el token_preflight de la simulación.")
    t = est.tokens.get(token)
    if not t or t["alcance"] != alcance or t["vence"] < est.reloj():
        raise BridgeError(409, "TOKEN_PREFLIGHT_INVALIDO", "El token no existe, expiró o es de otra operación. "
                          "Repite la simulación (dry_run=true).")
    if t["huella"] != huella:
        raise BridgeError(409, "TOKEN_PREFLIGHT_INVALIDO",
                          "El contenido cambió después de la simulación. Repite la simulación (dry_run=true).")
    del est.tokens[token]


def _armar(entrada: CotizacionEntrada, referencia: str, creada, actualizada, estado="borrador", odoo=None) -> dict:
    partidas, subtotal = [], 0.0
    for i, p in enumerate(entrada.partidas, start=1):
        importe = round(p.cantidad * p.precio_unitario, 2) if p.precio_unitario is not None else None
        subtotal += importe or 0
        partidas.append(p.model_dump() | {"numero": i, "importe": importe})
    return {
        "referencia": referencia, "estado": estado, "cliente": entrada.cliente.model_dump(),
        "folio_levantamiento": entrada.folio_levantamiento, "moneda": entrada.moneda, "notas": entrada.notas,
        "partidas": partidas,
        "totales": {"partidas": len(partidas), "subtotal": round(subtotal, 2), "moneda": entrada.moneda},
        "odoo": odoo, "creada": creada, "actualizada": actualizada,
    }


def _avisos_contenido(cot: dict) -> list[str]:
    avisos = []
    sin_codigo = [p["numero"] for p in cot["partidas"] if not p["codigo_odoo"]]
    if sin_codigo:
        avisos.append(f"Partidas sin producto asociado (se cargarán con el modelo escrito): {sin_codigo}")
    sin_precio = [p["numero"] for p in cot["partidas"] if p["precio_unitario"] is None]
    if sin_precio:
        avisos.append(f"Partidas sin precio; bloquearán la exportación (R-03): {sin_precio}")
    return avisos


def _obtener(request: Request, referencia: str) -> dict:
    cot = _estado(request).cotizaciones.get(referencia)
    if not cot:
        raise BridgeError(404, "COTIZACION_NO_ENCONTRADA", f"No existe la cotización '{referencia}' en la DB Buffer.")
    return cot


def _contenido(cot: dict) -> dict:
    return {k: cot[k] for k in ("cliente", "moneda", "partidas")}


# ---------------------------------------------------------------------------
# Cotizaciones en la DB Buffer
# ---------------------------------------------------------------------------

@router.post("/cotizaciones", status_code=201, response_model=Respuesta[Cotizacion], tags=["Cotizaciones (Buffer)"],
             summary="Crear una cotización en la DB Buffer")
def crear(entrada: CotizacionEntrada, request: Request, _=Depends(acceso(Nivel.BUFFER))):
    est = _estado(request)
    est.seq_cotizacion += 1
    ref = f"BUF-{est.seq_cotizacion:06d}"
    ahora = est.ahora()
    cot = _armar(entrada, ref, ahora, ahora)
    est.cotizaciones[ref] = cot
    return ok(request, cot, _avisos_contenido(cot))


@router.get("/cotizaciones/{referencia}", response_model=Respuesta[Cotizacion], tags=["Cotizaciones (Buffer)"],
            summary="Leer una cotización de la DB Buffer")
def leer(referencia: str, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    cot = _obtener(request, referencia)
    return ok(request, cot, _avisos_contenido(cot))


@router.put("/cotizaciones/{referencia}", response_model=Respuesta[Cotizacion], tags=["Cotizaciones (Buffer)"],
            summary="Reemplazar el contenido de una cotización en borrador")
def reemplazar(referencia: str, entrada: CotizacionEntrada, request: Request, _=Depends(acceso(Nivel.BUFFER))):
    actual = _obtener(request, referencia)
    if actual["estado"] == "exportada":
        raise BridgeError(409, "COTIZACION_EXPORTADA",
                          "La cotización ya se exportó a Odoo. Para agregar partidas usa "
                          "POST /v1/odoo/cotizaciones/{folio}/partidas.", {"folio_odoo": actual["odoo"]["folio"]})
    cot = _armar(entrada, referencia, actual["creada"], _estado(request).ahora())
    _estado(request).cotizaciones[referencia] = cot
    return ok(request, cot, _avisos_contenido(cot))


def _preflight(est, cot: dict) -> dict:
    bloqueos = []
    for p in cot["partidas"]:
        if p["precio_unitario"] is None:
            bloqueos.append({"partida": p["numero"], "codigo": "SIN_PRECIO",
                             "mensaje": "La partida no tiene precio; no se carga en cero (R-03)."})
        if p["codigo_odoo"] and p["codigo_odoo"] not in CODIGOS_ODOO:
            bloqueos.append({"partida": p["numero"], "codigo": "CODIGO_INEXISTENTE",
                             "mensaje": f"El código '{p['codigo_odoo']}' no existe en Odoo."})
    if cot["cliente"].get("odoo_id") is None:
        bloqueos.append({"partida": None, "codigo": "CLIENTE_SIN_ODOO_ID",
                         "mensaje": "El cliente no tiene odoo_id; resuélvelo con POST /v1/consultas (res.partner)."})
    secciones = list(dict.fromkeys(p["seccion"] for p in cot["partidas"]))
    no_incluye = ["impuestos"]
    sin_flete = sum(1 for p in cot["partidas"] if p["flete"] is None)
    if sin_flete:
        no_incluye.append(f"flete en {sin_flete} partida(s) sin capturar")
    listo = not bloqueos
    token, expira = (_emitir_token(est, "exportar:" + cot["referencia"], _huella(_contenido(cot)))
                     if listo else (None, None))
    return {"dry_run": True, "listo_para_exportar": listo, "lineas_a_crear": len(cot["partidas"]) + len(secciones),
            "secciones": secciones, "subtotal": cot["totales"]["subtotal"], "moneda": cot["moneda"],
            "no_incluye": no_incluye, "bloqueos": bloqueos, "token_preflight": token, "token_expira": expira}


@router.post("/cotizaciones/{referencia}/exportar", tags=["Cotizaciones (Buffer)"],
             response_model=Respuesta[Preflight | ExportacionResultado],
             summary="Simular (dry_run) o exportar la cotización a Odoo",
             description=("Paso 1: `dry_run=true` (llave de lectura o superior) devuelve el resumen y un "
                          "`token_preflight`. Paso 2: tras confirmación humana, `dry_run=false` con ese token "
                          "(llave de nivel odoo) crea la cotización en Odoo, siempre en borrador."))
def exportar(referencia: str, entrada: ExportarEntrada, request: Request, nivel=Depends(acceso(Nivel.LECTURA))):
    est = _estado(request)
    cot = _obtener(request, referencia)

    if entrada.dry_run:
        if cot["estado"] == "exportada":
            raise BridgeError(409, "COTIZACION_EXPORTADA", "La cotización ya se exportó a Odoo.",
                              {"folio_odoo": cot["odoo"]["folio"]})
        return ok(request, _preflight(est, cot))

    exigir_nivel(nivel, Nivel.ODOO, "Exportar a Odoo")

    # Idempotencia: si ya se exportó, se devuelve la existente sin crear otra
    if cot["estado"] == "exportada":
        return ok(request, {"dry_run": False, "referencia": referencia, "folio_odoo": cot["odoo"]["folio"],
                            "odoo_id": cot["odoo"]["odoo_id"], "estado_odoo": "draft", "ya_existia": True},
                  ["La cotización ya existía en Odoo; no se creó otra."])

    _validar_token(est, entrada.token_preflight, "exportar:" + referencia, _huella(_contenido(cot)))
    if _preflight(est, cot)["bloqueos"]:
        raise BridgeError(409, "PREFLIGHT_CON_BLOQUEOS", "La cotización tiene bloqueos; no se exportó.")

    est.seq_folio_odoo += 1
    folio, odoo_id = f"S{est.seq_folio_odoo:05d}", est.seq_folio_odoo
    lineas, lid, total = [], 1000 + odoo_id * 100, 0.0
    for seccion in dict.fromkeys(p["seccion"] for p in cot["partidas"]):
        lid += 1
        lineas.append({"id": lid, "tipo": "seccion", "codigo": None, "descripcion": seccion})
        for p in (x for x in cot["partidas"] if x["seccion"] == seccion):
            lid += 1
            lineas.append({"id": lid, "tipo": "producto" if p["codigo_odoo"] else "nota", "codigo": p["codigo_odoo"],
                           "descripcion": p["descripcion"], "cantidad": p["cantidad"],
                           "precio_unitario": p["precio_unitario"], "subtotal": p["importe"]})
            total += p["importe"] or 0
    est.cotizaciones_odoo[folio] = {"folio": folio, "odoo_id": odoo_id, "estado": "draft", "cliente": cot["cliente"],
                                    "referencia_buffer": referencia, "lineas": lineas,
                                    "total_sin_impuestos": round(total, 2), "moneda": cot["moneda"], "extras": {}}
    cot["estado"] = "exportada"
    cot["odoo"] = {"folio": folio, "odoo_id": odoo_id}
    cot["actualizada"] = est.ahora()
    return ok(request, {"dry_run": False, "referencia": referencia, "folio_odoo": folio, "odoo_id": odoo_id,
                        "estado_odoo": "draft", "ya_existia": False})


# ---------------------------------------------------------------------------
# Cotizaciones vivas en Odoo
# ---------------------------------------------------------------------------

def _cot_odoo(request: Request, folio: str) -> dict:
    est = _estado(request)
    if folio in est.cotizaciones_odoo:
        return est.cotizaciones_odoo[folio]
    if folio == ej.COTIZACION_ODOO_EJEMPLO["folio"]:
        est.cotizaciones_odoo[folio] = copy.deepcopy(ej.COTIZACION_ODOO_EJEMPLO)
        return est.cotizaciones_odoo[folio]
    raise BridgeError(404, "COTIZACION_ODOO_NO_ENCONTRADA", f"No existe la cotización '{folio}' en Odoo.",
                      {"ejemplo_disponible": ej.COTIZACION_ODOO_EJEMPLO["folio"]})


@router.get("/odoo/cotizaciones/{folio}", response_model=Respuesta[CotizacionOdoo], tags=["Cotizaciones (Odoo)"],
            summary="Leer una cotización viva en Odoo")
def leer_odoo(folio: str, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    return ok(request, _cot_odoo(request, folio))


@router.post("/odoo/cotizaciones/{folio}/partidas", response_model=Respuesta[InyeccionResultado],
             tags=["Cotizaciones (Odoo)"], summary="Inyectar partidas en una cotización existente de Odoo",
             description=("Misma mecánica de dos pasos que exportar: `dry_run=true` devuelve el plan "
                          "(agregar / actualizar / solicitar_alta) y un token; `dry_run=false` con el token lo aplica."))
def inyectar(folio: str, entrada: InyeccionEntrada, request: Request, nivel=Depends(acceso(Nivel.LECTURA))):
    est = _estado(request)
    cot = _cot_odoo(request, folio)
    if cot["estado"] in ("sale", "cancel"):
        raise BridgeError(409, "COTIZACION_NO_EDITABLE", f"La cotización está en estado '{cot['estado']}'.")
    existentes = {l["codigo"]: l for l in cot["lineas"] if l["tipo"] == "producto"}
    acciones = []
    for p in entrada.partidas:
        if p.codigo_odoo and p.codigo_odoo in existentes:
            accion = "actualizar"
        elif p.codigo_odoo and p.codigo_odoo in CODIGOS_ODOO:
            accion = "agregar"
        else:
            accion = "solicitar_alta"
        acciones.append({"accion": accion, "codigo": p.codigo_odoo, "descripcion": p.descripcion,
                         "cantidad": p.cantidad, "seccion": p.seccion})
    huella = _huella({"folio": folio, "partidas": [p.model_dump() for p in entrada.partidas]})

    if entrada.dry_run:
        token, _exp = _emitir_token(est, "inyectar:" + folio, huella)
        return ok(request, {"folio": folio, "dry_run": True, "acciones": acciones, "token_preflight": token,
                            "aplicado": False})

    exigir_nivel(nivel, Nivel.ODOO, "Inyectar partidas en Odoo")
    _validar_token(est, entrada.token_preflight, "inyectar:" + folio, huella)
    lid = max((l["id"] for l in cot["lineas"]), default=0)
    for a, p in zip(acciones, entrada.partidas):
        if a["accion"] == "actualizar":
            linea = existentes[p.codigo_odoo]
            linea["cantidad"] = p.cantidad
            if p.precio_unitario is not None:
                linea["precio_unitario"] = p.precio_unitario
            linea["subtotal"] = round(linea["cantidad"] * (linea["precio_unitario"] or 0), 2)
        elif a["accion"] == "agregar":
            lid += 1
            cot["lineas"].append({"id": lid, "tipo": "producto", "codigo": p.codigo_odoo, "descripcion": p.descripcion,
                                  "cantidad": p.cantidad, "precio_unitario": p.precio_unitario,
                                  "subtotal": round(p.cantidad * (p.precio_unitario or 0), 2)})
    cot["total_sin_impuestos"] = round(sum(l.get("subtotal") or 0 for l in cot["lineas"]), 2)
    avisos = []
    if any(a["accion"] == "solicitar_alta" for a in acciones):
        avisos.append("Algunas partidas no se cargaron porque el producto no existe; regístralas con POST /v1/altas.")
    return ok(request, {"folio": folio, "dry_run": False, "acciones": acciones, "token_preflight": None,
                        "aplicado": True}, avisos)
