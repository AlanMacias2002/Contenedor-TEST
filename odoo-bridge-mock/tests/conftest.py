import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

KL, KB, KO = "llave-lectura-pruebas-0001", "llave-buffer-pruebas-0002", "llave-odoo-pruebas-0003"


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def app(reloj):
    s = Settings(key_lectura=KL, key_buffer=KB, key_odoo=KO, segundos_por_lote=2.0, lento_segundos=0.05)
    a = create_app(s)
    a.state.estado.reloj = reloj
    return a


@pytest.fixture
def c(app):
    return TestClient(app)


@pytest.fixture
def L():
    return {"X-API-Key": KL}


@pytest.fixture
def B():
    return {"X-API-Key": KB}


@pytest.fixture
def O():
    return {"X-API-Key": KO}


COTIZACION = {
    "cliente": {"odoo_id": 7, "nombre": "Hotel Ejemplo Los Cabos"},
    "folio_levantamiento": "L000123",
    "partidas": [
        {"seccion": "Voz y datos", "modelo_bbinco": "CS-PP24-C6", "codigo_odoo": "PP-24-C6",
         "descripcion": "Patch panel 24 puertos Cat6", "cantidad": 2, "precio_unitario": 1190.0},
        {"seccion": "Voz y datos", "modelo_bbinco": "UTP6-305", "codigo_odoo": "CAB-UTP6-305",
         "descripcion": "Bobina UTP Cat6", "cantidad": 3, "precio_unitario": 2890.0, "flete": 150.0},
        {"seccion": "Servicios", "modelo_bbinco": None, "codigo_odoo": "BBI-SERV-DATOS",
         "descripcion": "Cableado por nodo", "cantidad": 4, "precio_unitario": 350.0},
    ],
}
