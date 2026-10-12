"""Dependencia de acceso: autenticación + escenario simulado, en ese orden."""

from __future__ import annotations

from fastapi import Depends, Request

from .esquemas import RespuestaError
from .nucleo import Nivel, escenario, requiere

ERRORES = {
    401: {"model": RespuestaError, "description": "Falta la API key o no es válida"},
    403: {"model": RespuestaError, "description": "La llave no tiene el nivel requerido, o el recurso no está permitido"},
    422: {"model": RespuestaError, "description": "Entrada inválida"},
    503: {"model": RespuestaError, "description": "Odoo o la DB Buffer no disponibles"},
}


def acceso(minimo: Nivel):
    async def _dep(request: Request, nivel: Nivel = Depends(requiere(minimo))) -> Nivel:
        request.state.escenario = await escenario(request)
        return nivel
    return _dep
