"""Configuración del esqueleto, leída de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

CONTRATO_VERSION = "0.1.0"
BRIDGE_VERSION = "0.1.0-mock"


@dataclass
class Settings:
    key_lectura: str = ""
    key_buffer: str = ""
    key_odoo: str = ""
    docs: bool = True
    segundos_por_lote: float = 2.0
    lento_segundos: float = 5.0
    extra: dict = field(default_factory=dict)

    @classmethod
    def desde_entorno(cls) -> "Settings":
        s = cls(
            key_lectura=os.environ.get("BRIDGE_KEY_LECTURA", ""),
            key_buffer=os.environ.get("BRIDGE_KEY_BUFFER", ""),
            key_odoo=os.environ.get("BRIDGE_KEY_ODOO", ""),
            docs=os.environ.get("BRIDGE_DOCS", "true").lower() != "false",
            segundos_por_lote=float(os.environ.get("BRIDGE_MOCK_SEGUNDOS_POR_LOTE", "2")),
            lento_segundos=float(os.environ.get("BRIDGE_MOCK_LENTO_SEGUNDOS", "5")),
        )
        faltan = [n for n, v in (("BRIDGE_KEY_LECTURA", s.key_lectura),
                                 ("BRIDGE_KEY_BUFFER", s.key_buffer),
                                 ("BRIDGE_KEY_ODOO", s.key_odoo)) if not v]
        if faltan:
            raise RuntimeError(
                "Faltan variables obligatorias: " + ", ".join(faltan)
                + ". Copia .env.example a .env y define las tres llaves."
            )
        if len({s.key_lectura, s.key_buffer, s.key_odoo}) < 3:
            raise RuntimeError("Las tres llaves (lectura, buffer, odoo) deben ser distintas.")
        return s
