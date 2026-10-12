"""odoo-bridge · ESQUELETO (mock).

Expone el contrato completo del bridge con datos de ejemplo, para que el agente
de n8n se construya en paralelo al bridge real.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import BRIDGE_VERSION, CONTRATO_VERSION, Settings
from .estado import Estado
from .nucleo import MODO, BridgeError, cuerpo_error, request_id
from .rutas_cotizaciones import router as r_cot
from .rutas_productos import router as r_prod
from .rutas_sistema import router as r_sis

log = logging.getLogger("odoo-bridge")

DESCRIPCION = f"""
**Esqueleto (mock)** del servicio `odoo-bridge` · contrato **{CONTRATO_VERSION}**.

Todas las respuestas usan la misma envoltura (`ok`, `modo`, `contrato`, `request_id`, `data` o `error`, `avisos`).
Los datos son **de ejemplo**: `modo` siempre vale `"mock"`.

**Autenticación:** encabezado `X-API-Key`. Tres niveles: `lectura` < `buffer` < `odoo`.
Cada nivel incluye los permisos de los anteriores.

**Escenarios:** encabezado `X-Mock-Escenario` (`error`, `odoo_caido`, `buffer_caido`, `lento`, `falla_job`)
para probar el manejo de errores del agente. Ver `GET /v1/escenarios`.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.desde_entorno()
    app = FastAPI(
        title="odoo-bridge (esqueleto)", version=BRIDGE_VERSION, description=DESCRIPCION,
        docs_url="/docs" if settings.docs else None, redoc_url=None,
        openapi_url="/openapi.json" if settings.docs else None,
    )
    app.state.settings = settings
    app.state.estado = Estado()

    @app.middleware("http")
    async def encabezados(request: Request, call_next):
        rid = request_id(request)
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        resp.headers["X-Bridge-Modo"] = MODO
        resp.headers["X-Bridge-Contrato"] = CONTRATO_VERSION
        return resp

    @app.exception_handler(BridgeError)
    async def _bridge_error(request: Request, exc: BridgeError):
        log.info("%s %s -> %s %s", request.method, request.url.path, exc.status, exc.codigo)
        return JSONResponse(cuerpo_error(request, exc.codigo, exc.mensaje, exc.detalle), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError):
        detalle = [{"campo": ".".join(str(x) for x in e["loc"][1:]) or e["loc"][0], "problema": e["msg"]}
                   for e in exc.errors()]
        return JSONResponse(cuerpo_error(request, "ENTRADA_INVALIDA", "La petición no cumple el contrato.", detalle),
                            status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codigos = {404: "RUTA_NO_ENCONTRADA", 405: "METODO_NO_PERMITIDO"}
        return JSONResponse(cuerpo_error(request, codigos.get(exc.status_code, "ERROR_HTTP"), str(exc.detail)),
                            status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):
        log.exception("Error no controlado")
        return JSONResponse(cuerpo_error(request, "ERROR_INTERNO", "Error interno del bridge."), status_code=500)

    app.include_router(r_sis)
    app.include_router(r_prod)
    app.include_router(r_cot)
    return app


def app_factory() -> FastAPI:  # uvicorn --factory
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app()
