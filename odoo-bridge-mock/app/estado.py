"""Estado en memoria del esqueleto (se pierde al reiniciar el contenedor)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Estado:
    cotizaciones: dict[str, dict] = field(default_factory=dict)
    cotizaciones_odoo: dict[str, dict] = field(default_factory=dict)
    equivalencias: list[dict] = field(default_factory=list)
    altas: dict[str, dict] = field(default_factory=dict)
    tokens: dict[str, dict] = field(default_factory=dict)
    jobs: dict[str, dict] = field(default_factory=dict)
    seq_cotizacion: int = 0
    seq_folio_odoo: int = 42
    seq_alta: int = 0
    seq_job: int = 0
    reloj: callable = time.monotonic

    def ahora(self) -> datetime:
        from .datos_ejemplo import TZ
        return datetime.now(TZ).replace(microsecond=0)
