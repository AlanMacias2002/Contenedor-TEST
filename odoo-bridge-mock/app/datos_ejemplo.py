"""Datos de EJEMPLO del esqueleto. No son datos reales de BBINCO.

Nombres, códigos y precios inventados con la forma del catálogo real, para que
el agente tenga algo realista con qué trabajar mientras se construye el bridge.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=-7))  # America/Mazatlan
CATALOGO_SINCRONIZADO = datetime(2026, 10, 11, 2, 14, tzinfo=TZ)

_ODOO = {"tipo": "odoo", "nombre": "BBINCO"}
_SYSCOM = {"tipo": "proveedor", "nombre": "Syscom"}


def _p(odoo_id, codigo, nombre, marca, tipo, precio, costo, stock, origen=_ODOO, extras=None, moneda="MXN"):
    return {
        "odoo_id": odoo_id, "codigo": codigo, "nombre": nombre, "marca": marca, "tipo": tipo,
        "precio_unitario": precio, "costo_unitario": costo, "moneda": moneda,
        "stock_disponible": stock, "unidad": "Unidades", "origen": origen, "activo": True,
        "actualizado": CATALOGO_SINCRONIZADO, "extras": extras or {},
    }


CATALOGO = [
    # --- Inventario propio (Odoo) ---
    _p(29, "BBI-SERV-DATOS", "Servicio de cableado para video, datos y voz", "BBINCO", "servicio", 350.0, None, None,
       extras={"categoria": "Servicios"}),
    _p(32, "BBI-SERV-INSTAL", "Servicio de instalación de sistemas", "BBINCO", "servicio", 480.0, None, None,
       extras={"categoria": "Servicios"}),
    _p(102, "PP-24-C6", "Patch panel 24 puertos Cat6", "Genérica", "producto", 1190.0, 820.0, 6,
       extras={"categoria": "Cableado estructurado"}),
    _p(101, "CAB-UTP6-305", "Bobina cable UTP Cat6 305 m", "Genérica", "producto", 2890.0, 2150.0, 14,
       extras={"categoria": "Cableado estructurado"}),
    _p(140, "JACK-C6-AZ", "Jack Cat6 color azul", "Genérica", "producto", 68.0, 41.0, 230,
       extras={"categoria": "Cableado estructurado", "color": "azul"}),
    _p(141, "FACEPLATE-2", "Placa de pared 2 puertos", "Genérica", "producto", 45.0, 22.0, 120,
       extras={"categoria": "Cableado estructurado"}),
    _p(3311, "2CD2143G2-I", "Cámara domo IP 4 MP", "Hikvision", "producto", 2350.0, 1610.0, 3,
       extras={"categoria": "Videovigilancia"}),
    _p(3312, "2CD2143G2-IS", "Cámara domo IP 4 MP con audio", "Hikvision", "producto", 2690.0, 1840.0, 0,
       extras={"categoria": "Videovigilancia"}),
    # --- Catálogo de proveedor (Syscom) ---
    _p(None, "SYS-SW-24G", "Switch administrable 24 puertos Gigabit", "TP-Link", "producto", None, 312.5, 57,
       origen=_SYSCOM, moneda="USD", extras={"sku_proveedor": "TL-SG3428"}),
    _p(None, "SYS-UPS-1500", "UPS 1500 VA línea interactiva", "APC", "producto", None, 268.0, 12,
       origen=_SYSCOM, moneda="USD", extras={"sku_proveedor": "BX1500M-LM60"}),
]

PREFIJOS_DISTRIBUIDOR = ("DS", "CS", "TL", "SYS")

CLIENTES = [
    {"id": 7, "name": "Hotel Ejemplo Los Cabos", "vat": "XAXX010101000", "email": "compras@hotel-ejemplo.mx"},
    {"id": 8, "name": "Residencial Demo", "vat": "XAXX010101000", "email": "admin@residencial-demo.mx"},
]

MODELOS_PERMITIDOS = {
    "res.partner": {"campos": ["id", "name", "vat", "email"], "registros": CLIENTES},
    "product.category": {"campos": ["id", "name", "complete_name"], "registros": [
        {"id": 3, "name": "Cableado estructurado", "complete_name": "All / Cableado estructurado"},
        {"id": 5, "name": "Servicios", "complete_name": "All / Servicios"},
        {"id": 6, "name": "Videovigilancia", "complete_name": "All / Videovigilancia"},
    ]},
    "uom.uom": {"campos": ["id", "name"], "registros": [{"id": 1, "name": "Unidades"}, {"id": 8, "name": "m"}]},
    "sale.order": {"campos": ["id", "name", "partner_id", "state", "amount_untaxed"], "registros": [
        {"id": 42, "name": "S00042", "partner_id": [7, "Hotel Ejemplo Los Cabos"], "state": "draft", "amount_untaxed": 12580.0},
    ]},
}

COTIZACION_ODOO_EJEMPLO = {
    "folio": "S00042", "odoo_id": 42, "estado": "draft",
    "cliente": {"odoo_id": 7, "nombre": "Hotel Ejemplo Los Cabos"},
    "referencia_buffer": None, "moneda": "MXN",
    "lineas": [
        {"id": 501, "tipo": "seccion", "codigo": None, "descripcion": "Voz y datos"},
        {"id": 502, "tipo": "producto", "codigo": "PP-24-C6", "descripcion": "Patch panel 24 puertos Cat6",
         "cantidad": 2, "precio_unitario": 1190.0, "subtotal": 2380.0},
        {"id": 503, "tipo": "producto", "codigo": "CAB-UTP6-305", "descripcion": "Bobina cable UTP Cat6 305 m",
         "cantidad": 3, "precio_unitario": 2890.0, "subtotal": 8670.0},
        {"id": 504, "tipo": "seccion", "codigo": None, "descripcion": "Servicios"},
        {"id": 505, "tipo": "producto", "codigo": "BBI-SERV-DATOS", "descripcion": "Servicio de cableado para video, datos y voz",
         "cantidad": 4, "precio_unitario": 350.0, "subtotal": 1400.0},
    ],
    "total_sin_impuestos": 12450.0,
    "extras": {"pricelist": "Lista pública (MXN)"},
}

ENTIDADES_SYNC = {
    # entidad: (lotes, registros)
    "productos": (5, 8877),
    "clientes": (2, 2410),
    "cotizaciones": (35, 70000),
}
