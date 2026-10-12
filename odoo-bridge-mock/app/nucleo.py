"""Piezas comunes: envoltura de respuesta, errores, autenticación y escenarios."""

from __future__ import annotations

import asyncio
import hmac
import uuid
from enum import IntEnum

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader

from .config import CONTRATO_VERSION

MODO = "mock"


# ---------------------------------------------------------------------------
# Envoltura
# ---------------------------------------------------------------------------

def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
    return rid


def ok(request: Request, data, avisos: list[str] | None = None) -> dict:
    return {"ok": True, "modo": MODO, "contrato": CONTRATO_VERSION,
            "request_id": request_id(request), "data": data, "avisos": avisos or []}


def cuerpo_error(request: Request, codigo: str, mensaje: str, detalle=None) -> dict:
    return {"ok": False, "modo": MODO, "contrato": CONTRATO_VERSION,
            "request_id": request_id(request),
            "error": {"codigo": codigo, "mensaje": mensaje, "detalle": detalle}}


class BridgeError(Exception):
    """Error de negocio con código estable; se convierte en la envoltura de error."""

    def __init__(self, status: int, codigo: str, mensaje: str, detalle=None):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje, self.detalle = status, codigo, mensaje, detalle


# ---------------------------------------------------------------------------
# Autenticación por niveles
# ---------------------------------------------------------------------------

class Nivel(IntEnum):
    LECTURA = 1   # consultar, resolver, preflight, estado de trabajos
    BUFFER = 2    # además: escribir en la DB Buffer (cotizaciones, equivalencias, altas, sync)
    ODOO = 3      # además: escribir en Odoo (exportar, inyectar partidas)


_ESQUEMA_LLAVE = APIKeyHeader(name="X-API-Key", auto_error=False,
                              description="Llave del bridge: lectura, buffer u odoo")


def nivel_de_llave(request: Request, llave: str | None = Security(_ESQUEMA_LLAVE)) -> Nivel:
    s = request.app.state.settings
    llave = llave or ""
    if not llave:
        raise BridgeError(401, "API_KEY_FALTANTE", "Falta el encabezado X-API-Key.")
    # Comparación en tiempo constante; se revisan las tres siempre.
    nivel = None
    for valor, n in ((s.key_odoo, Nivel.ODOO), (s.key_buffer, Nivel.BUFFER), (s.key_lectura, Nivel.LECTURA)):
        if hmac.compare_digest(llave.encode(), valor.encode()) and nivel is None:
            nivel = n
    if nivel is None:
        raise BridgeError(401, "API_KEY_INVALIDA", "La API key no es válida.")
    request.state.nivel = nivel
    return nivel


def requiere(minimo: Nivel):
    def _dep(request: Request, nivel: Nivel = Depends(nivel_de_llave)) -> Nivel:
        if nivel < minimo:
            raise BridgeError(403, "ALCANCE_INSUFICIENTE",
                              f"Esta operación requiere la llave de nivel '{minimo.name.lower()}'.")
        return nivel
    return _dep


def exigir_nivel(nivel: Nivel, minimo: Nivel, operacion: str) -> None:
    if nivel < minimo:
        raise BridgeError(403, "ALCANCE_INSUFICIENTE",
                          f"{operacion} requiere la llave de nivel '{minimo.name.lower()}'.")


# ---------------------------------------------------------------------------
# Escenarios simulados (encabezado X-Mock-Escenario)
# ---------------------------------------------------------------------------

ESCENARIOS = {
    "error": "Simula un error interno del bridge (500).",
    "odoo_caido": "Simula que Odoo no responde (503).",
    "buffer_caido": "Simula que la DB Buffer no responde (503).",
    "lento": "Retrasa la respuesta BRIDGE_MOCK_LENTO_SEGUNDOS segundos.",
    "falla_job": "Solo en POST /v1/sync: el trabajo falla a la mitad.",
}


async def escenario(request: Request) -> str | None:
    esc = (request.headers.get("X-Mock-Escenario") or "").strip().lower() or None
    if esc is None:
        return None
    if esc not in ESCENARIOS:
        raise BridgeError(400, "ESCENARIO_DESCONOCIDO", f"Escenario '{esc}' no existe.",
                          {"disponibles": sorted(ESCENARIOS)})
    if esc == "lento":
        await asyncio.sleep(request.app.state.settings.lento_segundos)
    elif esc == "error":
        raise BridgeError(500, "ERROR_INTERNO", "Error interno simulado (escenario 'error').")
    elif esc == "odoo_caido":
        raise BridgeError(503, "ODOO_NO_DISPONIBLE", "Odoo no respondió (simulado). Reintenta más tarde.")
    elif esc == "buffer_caido":
        raise BridgeError(503, "BUFFER_NO_DISPONIBLE", "La DB Buffer no respondió (simulado). Reintenta más tarde.")
    return esc


def normalizar(texto: str) -> str:
    """Mayúsculas, sin espacios, guiones, puntos ni diagonales."""
    return "".join(c for c in texto.upper() if c not in " -./\\_")
