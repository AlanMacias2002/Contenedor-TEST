"""Salud, preparación, sincronización y trabajos asíncronos."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request

from . import datos_ejemplo as ej
from .config import BRIDGE_VERSION
from .esquemas import Entidad, Job, Preparacion, Respuesta, Salud, SyncEntrada
from .nucleo import ESCENARIOS, BridgeError, Nivel, ok
from .seguridad import ERRORES, acceso

router = APIRouter()


@router.get("/health", response_model=Respuesta[Salud], tags=["Sistema"], summary="¿El proceso está vivo? (sin API key)")
def health(request: Request):
    return ok(request, {"estado": "ok", "version": BRIDGE_VERSION})


@router.get("/ready", response_model=Respuesta[Preparacion], tags=["Sistema"], responses=ERRORES,
            summary="¿Responden Odoo y la DB Buffer?")
def ready(request: Request, _=Depends(acceso(Nivel.LECTURA))):
    return ok(request, {
        "estado": "listo", "version": BRIDGE_VERSION, "entorno": "mock",
        "odoo": {"alcanzable": True, "version": "19.0", "edicion": "community", "api_key_expira": "2027-01-08",
                 "dias_para_expirar": 89},
        "buffer": {"alcanzable": True},
        "catalogo_sincronizado": ej.CATALOGO_SINCRONIZADO,
    })


@router.get("/v1/escenarios", tags=["Sistema"], responses=ERRORES,
            summary="Escenarios simulados disponibles en el esqueleto")
def escenarios(request: Request, _=Depends(acceso(Nivel.LECTURA))):
    return ok(request, {
        "encabezado": "X-Mock-Escenario",
        "escenarios": ESCENARIOS,
        "palabras_clave_resolver": {"NOEXISTE": "no_encontrado", "AMBIGUO": "requiere_confirmacion",
                                    "PROVEEDOR": "resuelto con producto de proveedor"},
        "datos_de_ejemplo": {"codigos": [p["codigo"] for p in ej.CATALOGO],
                             "cotizacion_odoo": ej.COTIZACION_ODOO_EJEMPLO["folio"],
                             "clientes": [{"odoo_id": c["id"], "nombre": c["name"]} for c in ej.CLIENTES]},
    })


# ---------------------------------------------------------------------------
# Sincronización
# ---------------------------------------------------------------------------

def _vista(est, job: dict, seg_lote: float) -> dict:
    transcurrido = est.reloj() - job["t0"]
    lotes, regs = job["lotes_totales"], job["registros_totales"]
    lote = min(lotes, int(transcurrido / seg_lote))
    estado, terminado, error = "corriendo", None, None
    if job["falla_en"] is not None and lote >= job["falla_en"]:
        lote, estado = job["falla_en"], "fallido"
        error = f"Odoo devolvió 503 al leer el lote {lote + 1} (simulado). El trabajo puede reanudarse desde ese lote."
    elif lote >= lotes:
        estado = "completado"
    elif transcurrido < seg_lote * 0.25:
        estado = "en_cola"
    if estado in ("completado", "fallido"):
        terminado = job["iniciado"] + timedelta(seconds=round(min(transcurrido, (lote + 1) * seg_lote)))
    return {"job_id": job["job_id"], "entidad": job["entidad"], "tipo": job["tipo"], "estado": estado,
            "lote_actual": lote, "lotes_totales": lotes, "registros_procesados": round(regs * lote / lotes),
            "registros_totales": regs, "iniciado": job["iniciado"], "terminado": terminado, "error": error}


@router.post("/v1/sync/{entidad}", status_code=202, response_model=Respuesta[Job], tags=["Sincronización"],
             responses=ERRORES, summary="Lanzar una sincronización Odoo → DB Buffer (asíncrona)",
             description="Responde de inmediato con un job_id. Consulta el avance con GET /v1/jobs/{job_id}.")
def lanzar_sync(entidad: Entidad, request: Request, entrada: SyncEntrada | None = None,
                _=Depends(acceso(Nivel.BUFFER))):
    est = request.app.state.estado
    seg = request.app.state.settings.segundos_por_lote
    for job in est.jobs.values():
        if job["entidad"] == entidad and _vista(est, job, seg)["estado"] in ("en_cola", "corriendo"):
            raise BridgeError(409, "SYNC_EN_CURSO", f"Ya hay una sincronización de '{entidad}' en curso.",
                              {"job_id": job["job_id"]})
    lotes, regs = ej.ENTIDADES_SYNC[entidad]
    completa = bool(entrada and entrada.completa)
    if not completa:
        lotes, regs = 1, max(1, regs // 200)
    est.seq_job += 1
    job = {"job_id": f"sync-{entidad}-{est.seq_job:04d}", "entidad": entidad,
           "tipo": "completa" if completa else "incremental", "lotes_totales": lotes, "registros_totales": regs,
           "iniciado": est.ahora(), "t0": est.reloj(),
           "falla_en": max(1, lotes // 2) if getattr(request.state, "escenario", None) == "falla_job" else None}
    if job["falla_en"] is not None and lotes == 1:
        job["falla_en"] = 0
    est.jobs[job["job_id"]] = job
    return ok(request, _vista(est, job, seg))


@router.get("/v1/jobs/{job_id}", response_model=Respuesta[Job], tags=["Sincronización"], responses=ERRORES,
            summary="Estado y avance de un trabajo")
def ver_job(job_id: str, request: Request, _=Depends(acceso(Nivel.LECTURA))):
    est = request.app.state.estado
    job = est.jobs.get(job_id)
    if not job:
        raise BridgeError(404, "JOB_NO_ENCONTRADO", f"No existe el trabajo '{job_id}'.")
    return ok(request, _vista(est, job, request.app.state.settings.segundos_por_lote))
