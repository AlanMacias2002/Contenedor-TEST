"""Productos, resolución de modelos, consultas, equivalencias y altas."""

from __future__ import annotations

import copy
import difflib

from fastapi import APIRouter, Depends, Request

from . import datos_ejemplo as ej
from .esquemas import (Alta, AltaEntrada, BuscarEntrada, BuscarSalida, ConsultaEntrada, ConsultaSalida,
                       Equivalencia, EquivalenciaEntrada, Producto, Respuesta, ResolverEntrada, ResolverSalida)
from .nucleo import BridgeError, Nivel, normalizar, ok
from .seguridad import ERRORES, acceso

router = APIRouter(prefix="/v1", responses=ERRORES)

UMBRAL_PARCIAL = 85


def _estado(request: Request):
    return request.app.state.estado


def _catalogo(incluir_proveedores: bool = True) -> list[dict]:
    """Inventario propio primero, luego proveedores."""
    odoo = [p for p in ej.CATALOGO if p["origen"]["tipo"] == "odoo"]
    prov = [p for p in ej.CATALOGO if p["origen"]["tipo"] == "proveedor"]
    return [copy.deepcopy(p) for p in odoo + (prov if incluir_proveedores else [])]


def _sin_prefijo(clave: str) -> str:
    for pref in ej.PREFIJOS_DISTRIBUIDOR:
        if clave.startswith(pref) and len(clave) > len(pref) + 2:
            return clave[len(pref):]
    return clave


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------

@router.get("/productos/{codigo}", response_model=Respuesta[Producto], tags=["Productos"],
            summary="Producto por código exacto")
def producto_por_codigo(codigo: str, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    for p in _catalogo():
        if p["codigo"] == codigo:
            avisos = []
            if p["origen"]["tipo"] == "proveedor":
                avisos.append("Producto solo disponible con proveedor; no existe en el inventario de Odoo.")
            return ok(request, p, avisos)
    raise BridgeError(404, "PRODUCTO_NO_ENCONTRADO", f"No existe un producto con código '{codigo}'.",
                      {"sugerencia": "Usa POST /v1/resolver para buscar por modelo, o POST /v1/productos/buscar."})


@router.post("/productos/buscar", response_model=Respuesta[BuscarSalida], tags=["Productos"],
             summary="Buscar productos por texto, marca u origen")
def buscar(entrada: BuscarEntrada, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    res = []
    for p in _catalogo(entrada.fuente != "odoo"):
        if entrada.fuente == "proveedores" and p["origen"]["tipo"] != "proveedor":
            continue
        if entrada.texto:
            t = entrada.texto.lower()
            if t not in p["nombre"].lower() and t not in p["codigo"].lower():
                continue
        if entrada.marca and (p["marca"] or "").lower() != entrada.marca.lower():
            continue
        if entrada.solo_con_stock and not (p["stock_disponible"] or 0) > 0:
            continue
        res.append(p)
    return ok(request, {"total": len(res), "productos": res[: entrada.limite]})


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def _resultado(modelo, norm, estado, nivel, via, producto=None, candidatos=None):
    return {
        "modelo": modelo, "modelo_normalizado": norm, "estado": estado, "nivel": nivel, "via": via,
        "aplicar_sin_confirmar": estado == "resuelto" and nivel <= 1,
        "producto": producto, "candidatos": candidatos or [],
        "salidas_posibles": (["equivalente_registrado", "solicitar_alta", "sin_producto_asociado"]
                             if estado == "no_encontrado" else []),
    }


def _resolver_uno(modelo: str, catalogo: list[dict], equivalencias: list[dict]) -> dict:
    literal = modelo.strip()
    norm = normalizar(modelo)
    upper = modelo.upper()

    # Escenarios forzados por palabra clave (solo en el esqueleto)
    if "NOEXISTE" in upper:
        return _resultado(modelo, norm, "no_encontrado", 4, "ninguna")
    if "AMBIGUO" in upper:
        cands = [{"producto": p, "similitud": s} for p, s in
                 zip([p for p in catalogo if p["codigo"].startswith("2CD2143G2")], (91, 88))]
        return _resultado(modelo, norm, "requiere_confirmacion", 3, "catalogo", candidatos=cands)
    if "PROVEEDOR" in upper:
        prov = next((p for p in catalogo if p["origen"]["tipo"] == "proveedor"), None)
        if prov:
            return _resultado(modelo, norm, "resuelto", 1, "catalogo", producto=prov)

    # Equivalencia confirmada previamente por una persona
    for eq in equivalencias:
        if eq["modelo_normalizado"] == norm:
            prod = next((p for p in catalogo if p["codigo"] == eq["codigo_odoo"]), None)
            if prod:
                return _resultado(modelo, norm, "resuelto", 0, "equivalencia", producto=prod)

    # Nivel 0 · literal
    for p in catalogo:
        if p["codigo"] == literal:
            return _resultado(modelo, norm, "resuelto", 0, "catalogo", producto=p)

    # Nivel 1 · normalizada
    n1 = [p for p in catalogo if normalizar(p["codigo"]) == norm]
    if len(n1) == 1:
        return _resultado(modelo, norm, "resuelto", 1, "catalogo", producto=n1[0])
    if len(n1) > 1:
        return _resultado(modelo, norm, "requiere_confirmacion", 1, "catalogo",
                          candidatos=[{"producto": p, "similitud": 100} for p in n1])

    # Nivel 2 · sin prefijo del distribuidor (+ vecinos parecidos)
    clave = _sin_prefijo(norm)
    n2 = [p for p in catalogo if _sin_prefijo(normalizar(p["codigo"])) == clave] if clave != norm else []
    if n2:
        cands = [{"producto": p, "similitud": 100} for p in n2]
        vistos = {p["codigo"] for p in n2}
        for p in catalogo:
            if p["codigo"] in vistos:
                continue
            s = round(difflib.SequenceMatcher(None, clave, _sin_prefijo(normalizar(p["codigo"]))).ratio() * 100)
            if s >= UMBRAL_PARCIAL:
                cands.append({"producto": p, "similitud": s})
        cands.sort(key=lambda c: -c["similitud"])
        return _resultado(modelo, norm, "requiere_confirmacion", 2, "catalogo", candidatos=cands[:3])

    # Nivel 3 · parcial
    puntajes = []
    for p in catalogo:
        s = round(difflib.SequenceMatcher(None, clave, _sin_prefijo(normalizar(p["codigo"]))).ratio() * 100)
        if s >= UMBRAL_PARCIAL:
            puntajes.append({"producto": p, "similitud": s})
    if puntajes:
        puntajes.sort(key=lambda c: -c["similitud"])
        return _resultado(modelo, norm, "requiere_confirmacion", 3, "catalogo", candidatos=puntajes[:3])

    return _resultado(modelo, norm, "no_encontrado", 4, "ninguna")


@router.post("/resolver", response_model=Respuesta[ResolverSalida], tags=["Resolución"],
             summary="Resolver modelos de BBINCO contra el catálogo",
             description=("Palabras clave del esqueleto: un modelo que contenga **NOEXISTE** devuelve "
                          "no_encontrado; **AMBIGUO** devuelve candidatos; **PROVEEDOR** se resuelve con un "
                          "producto de proveedor. El resto se busca en el catálogo de ejemplo."))
def resolver(entrada: ResolverEntrada, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    catalogo = _catalogo(entrada.incluir_proveedores)
    vistos, modelos = set(), []
    for m in entrada.modelos:
        if m not in vistos:
            vistos.add(m)
            modelos.append(m)
    resultados = [_resolver_uno(m, catalogo, _estado(request).equivalencias) for m in modelos]
    avisos = []
    if len(modelos) < len(entrada.modelos):
        avisos.append("Se quitaron modelos duplicados.")
    for r in resultados:
        if r["producto"] and r["producto"]["origen"]["tipo"] == "proveedor":
            avisos.append(f"'{r['modelo']}' solo existe con proveedor ({r['producto']['origen']['nombre']}).")
    return ok(request, {"catalogo_sincronizado": ej.CATALOGO_SINCRONIZADO, "resultados": resultados}, avisos)


# ---------------------------------------------------------------------------
# Consultas en lista blanca
# ---------------------------------------------------------------------------

def _cumple(reg: dict, dominio: list) -> bool:
    for cond in dominio:
        if not (isinstance(cond, list) and len(cond) == 3):
            continue
        campo, op, valor = cond
        v = reg.get(campo)
        if op == "=" and v != valor:
            return False
        if op == "ilike" and str(valor).lower().strip("%") not in str(v).lower():
            return False
    return True


@router.post("/consultas", response_model=Respuesta[ConsultaSalida], tags=["Consultas"],
             summary="Lectura genérica sobre modelos permitidos",
             description="Modelos permitidos en el esqueleto: " + ", ".join(sorted(ej.MODELOS_PERMITIDOS)))
def consultar(entrada: ConsultaEntrada, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    conf = ej.MODELOS_PERMITIDOS.get(entrada.modelo)
    if conf is None:
        raise BridgeError(403, "MODELO_NO_PERMITIDO", f"El modelo '{entrada.modelo}' no está en la lista blanca.",
                          {"permitidos": sorted(ej.MODELOS_PERMITIDOS)})
    avisos = []
    campos = entrada.campos or conf["campos"]
    fuera = [c for c in campos if c not in conf["campos"]]
    if fuera:
        avisos.append("Campos omitidos por no estar permitidos: " + ", ".join(fuera))
    campos = [c for c in campos if c in conf["campos"]]
    if any(isinstance(c, list) and len(c) == 3 and c[1] not in ("=", "ilike") for c in entrada.dominio):
        avisos.append("El esqueleto solo filtra con '=' e 'ilike'; las demás condiciones se ignoraron.")
    regs = [{c: r.get(c) for c in campos} for r in conf["registros"] if _cumple(r, entrada.dominio)]
    return ok(request, {"modelo": entrada.modelo, "total": len(regs), "registros": regs[: entrada.limite]}, avisos)


# ---------------------------------------------------------------------------
# Equivalencias y altas
# ---------------------------------------------------------------------------

@router.post("/equivalencias", status_code=201, response_model=Respuesta[Equivalencia], tags=["Resolución"],
             summary="Guardar la elección de una persona (modelo BBINCO → código Odoo)")
def crear_equivalencia(entrada: EquivalenciaEntrada, request: Request, _=Depends(acceso(Nivel.BUFFER))):
    if not any(p["codigo"] == entrada.codigo_odoo and p["origen"]["tipo"] == "odoo" for p in ej.CATALOGO):
        raise BridgeError(422, "CODIGO_ODOO_INEXISTENTE",
                          f"El código '{entrada.codigo_odoo}' no existe en el catálogo de Odoo.")
    est = _estado(request)
    norm = normalizar(entrada.modelo_bbinco)
    est.equivalencias = [e for e in est.equivalencias if e["modelo_normalizado"] != norm]
    eq = entrada.model_dump() | {"id": len(est.equivalencias) + 1, "modelo_normalizado": norm, "creada": est.ahora()}
    est.equivalencias.append(eq)
    return ok(request, eq, ["Desde ahora este modelo se resuelve solo (nivel 0, vía equivalencia)."])


@router.post("/altas", status_code=201, response_model=Respuesta[Alta], tags=["Altas"],
             summary="Solicitar el alta de un producto que no existe en el catálogo")
def crear_alta(entrada: AltaEntrada, request: Request, _=Depends(acceso(Nivel.BUFFER))):
    est = _estado(request)
    est.seq_alta += 1
    alta = entrada.model_dump() | {"id": f"ALTA-{est.seq_alta:04d}", "estado": "solicitada", "creada": est.ahora()}
    est.altas[alta["id"]] = alta
    return ok(request, alta)


@router.get("/altas/{alta_id}", response_model=Respuesta[Alta], tags=["Altas"], summary="Estado de una solicitud de alta")
def ver_alta(alta_id: str, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    alta = _estado(request).altas.get(alta_id)
    if not alta:
        raise BridgeError(404, "ALTA_NO_ENCONTRADA", f"No existe la solicitud '{alta_id}'.")
    return ok(request, alta)
