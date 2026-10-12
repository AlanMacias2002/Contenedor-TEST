# Ejemplos del contrato 0.1.0

Generado automáticamente por `scripts/generar_docs.py` a partir de llamadas reales al esqueleto. Las llaves se muestran como marcadores. Las fechas y tokens cambian en cada ejecución.

## Sistema

### Salud (sin llave)

`GET /health` → **HTTP 200**

**Petición**

```http
GET /health

```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-01",
  "data": {
    "estado": "ok",
    "version": "0.1.0-mock"
  },
  "avisos": []
}
```

### Preparación

`GET /ready` → **HTTP 200**

**Petición**

```http
GET /ready
X-API-Key: <llave lectura>
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-02",
  "data": {
    "estado": "listo",
    "version": "0.1.0-mock",
    "entorno": "mock",
    "odoo": {
      "alcanzable": true,
      "version": "19.0",
      "edicion": "community",
      "api_key_expira": "2027-01-08",
      "dias_para_expirar": 89
    },
    "buffer": {
      "alcanzable": true
    },
    "catalogo_sincronizado": "2026-10-11T02:14:00-07:00"
  },
  "avisos": []
}
```

## Productos y resolución

### Producto por código

`GET /v1/productos/PP-24-C6` → **HTTP 200**

**Petición**

```http
GET /v1/productos/PP-24-C6
X-API-Key: <llave lectura>
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-03",
  "data": {
    "odoo_id": 102,
    "codigo": "PP-24-C6",
    "nombre": "Patch panel 24 puertos Cat6",
    "marca": "Genérica",
    "tipo": "producto",
    "precio_unitario": 1190.0,
    "costo_unitario": 820.0,
    "moneda": "MXN",
    "stock_disponible": 6.0,
    "unidad": "Unidades",
    "origen": {
      "tipo": "odoo",
      "nombre": "BBINCO"
    },
    "activo": true,
    "actualizado": "2026-10-11T02:14:00-07:00",
    "extras": {
      "categoria": "Cableado estructurado"
    }
  },
  "avisos": []
}
```

### Producto inexistente

`GET /v1/productos/NO-EXISTE` → **HTTP 404**

**Petición**

```http
GET /v1/productos/NO-EXISTE
X-API-Key: <llave lectura>
```

**Respuesta**

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-04",
  "error": {
    "codigo": "PRODUCTO_NO_ENCONTRADO",
    "mensaje": "No existe un producto con código 'NO-EXISTE'.",
    "detalle": {
      "sugerencia": "Usa POST /v1/resolver para buscar por modelo, o POST /v1/productos/buscar."
    }
  }
}
```

### Búsqueda

`POST /v1/productos/buscar` → **HTTP 200**

**Petición**

```http
POST /v1/productos/buscar
X-API-Key: <llave lectura>

{
  "texto": "cámara",
  "solo_con_stock": true
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-05",
  "data": {
    "total": 1,
    "productos": [
      {
        "odoo_id": 3311,
        "codigo": "2CD2143G2-I",
        "nombre": "Cámara domo IP 4 MP",
        "marca": "Hikvision",
        "tipo": "producto",
        "precio_unitario": 2350.0,
        "costo_unitario": 1610.0,
        "moneda": "MXN",
        "stock_disponible": 3.0,
        "unidad": "Unidades",
        "origen": {
          "tipo": "odoo",
          "nombre": "BBINCO"
        },
        "activo": true,
        "actualizado": "2026-10-11T02:14:00-07:00",
        "extras": {
          "categoria": "Videovigilancia"
        }
      }
    ]
  },
  "avisos": []
}
```

### Resolver modelos

`POST /v1/resolver` → **HTTP 200**

Tres casos: resuelto (nivel 0), requiere confirmación (nivel 2) y no encontrado (nivel 4).

**Petición**

```http
POST /v1/resolver
X-API-Key: <llave lectura>

{
  "modelos": [
    "PP-24-C6",
    "DS 2CD2143G2 I",
    "UTP6-305AZ"
  ]
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-06",
  "data": {
    "catalogo_sincronizado": "2026-10-11T02:14:00-07:00",
    "resultados": [
      {
        "modelo": "PP-24-C6",
        "modelo_normalizado": "PP24C6",
        "estado": "resuelto",
        "nivel": 0,
        "via": "catalogo",
        "aplicar_sin_confirmar": true,
        "producto": {
          "odoo_id": 102,
          "codigo": "PP-24-C6",
          "nombre": "Patch panel 24 puertos Cat6",
          "marca": "Genérica",
          "tipo": "producto",
          "precio_unitario": 1190.0,
          "costo_unitario": 820.0,
          "moneda": "MXN",
          "stock_disponible": 6.0,
          "unidad": "Unidades",
          "origen": {
            "tipo": "odoo",
            "nombre": "BBINCO"
          },
          "activo": true,
          "actualizado": "2026-10-11T02:14:00-07:00",
          "extras": {
            "categoria": "Cableado estructurado"
          }
        },
        "candidatos": [],
        "salidas_posibles": []
      },
      {
        "modelo": "DS 2CD2143G2 I",
        "modelo_normalizado": "DS2CD2143G2I",
        "estado": "requiere_confirmacion",
        "nivel": 2,
        "via": "catalogo",
        "aplicar_sin_confirmar": false,
        "producto": null,
        "candidatos": [
          {
            "producto": {
              "odoo_id": 3311,
              "codigo": "2CD2143G2-I",
              "nombre": "Cámara domo IP 4 MP",
              "marca": "Hikvision",
              "tipo": "producto",
              "precio_unitario": 2350.0,
              "costo_unitario": 1610.0,
              "moneda": "MXN",
              "stock_disponible": 3.0,
              "unidad": "Unidades",
              "origen": {
                "tipo": "odoo",
                "nombre": "BBINCO"
              },
              "activo": true,
              "actualizado": "2026-10-11T02:14:00-07:00",
              "extras": {
                "categoria": "Videovigilancia"
              }
            },
            "similitud": 100
          },
          {
            "producto": {
              "odoo_id": 3312,
              "codigo": "2CD2143G2-IS",
              "nombre": "Cámara domo IP 4 MP con audio",
              "marca": "Hikvision",
              "tipo": "producto",
              "precio_unitario": 2690.0,
              "costo_unitario": 1840.0,
              "moneda": "MXN",
              "stock_disponible": 0.0,
              "unidad": "Unidades",
              "origen": {
                "tipo": "odoo",
                "nombre": "BBINCO"
              },
              "activo": true,
              "actualizado": "2026-10-11T02:14:00-07:00",
              "extras": {
                "categoria": "Videovigilancia"
              }
            },
            "similitud": 95
          }
        ],
        "salidas_posibles": []
      },
      {
        "modelo": "UTP6-305AZ",
        "modelo_normalizado": "UTP6305AZ",
        "estado": "no_encontrado",
        "nivel": 4,
        "via": "ninguna",
        "aplicar_sin_confirmar": false,
        "producto": null,
        "candidatos": [],
        "salidas_posibles": [
          "equivalente_registrado",
          "solicitar_alta",
          "sin_producto_asociado"
        ]
      }
    ]
  },
  "avisos": []
}
```

### Guardar equivalencia elegida por una persona

`POST /v1/equivalencias` → **HTTP 201**

**Petición**

```http
POST /v1/equivalencias
X-API-Key: <llave buffer>

{
  "modelo_bbinco": "DS 2CD2143G2 I",
  "codigo_odoo": "2CD2143G2-I",
  "confirmado_por": "Vendedor"
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-07",
  "data": {
    "modelo_bbinco": "DS 2CD2143G2 I",
    "codigo_odoo": "2CD2143G2-I",
    "confirmado_por": "Vendedor",
    "cotizacion_referencia": null,
    "id": 1,
    "modelo_normalizado": "DS2CD2143G2I",
    "creada": "2026-10-11T09:38:08-07:00"
  },
  "avisos": [
    "Desde ahora este modelo se resuelve solo (nivel 0, vía equivalencia)."
  ]
}
```

### Solicitar alta

`POST /v1/altas` → **HTTP 201**

**Petición**

```http
POST /v1/altas
X-API-Key: <llave buffer>

{
  "modelo_bbinco": "UTP6-305AZ",
  "descripcion": "Bobina UTP Cat6 azul 305 m",
  "solicitado_por": "agente",
  "cotizacion_referencia": "BUF-000001"
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-08",
  "data": {
    "modelo_bbinco": "UTP6-305AZ",
    "descripcion": "Bobina UTP Cat6 azul 305 m",
    "marca": null,
    "solicitado_por": "agente",
    "cotizacion_referencia": "BUF-000001",
    "id": "ALTA-0001",
    "estado": "solicitada",
    "creada": "2026-10-11T09:38:08-07:00"
  },
  "avisos": []
}
```

### Consulta en lista blanca

`POST /v1/consultas` → **HTTP 200**

**Petición**

```http
POST /v1/consultas
X-API-Key: <llave lectura>

{
  "modelo": "res.partner",
  "dominio": [
    [
      "name",
      "ilike",
      "hotel"
    ]
  ],
  "campos": [
    "id",
    "name"
  ]
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-09",
  "data": {
    "modelo": "res.partner",
    "total": 1,
    "registros": [
      {
        "id": 7,
        "name": "Hotel Ejemplo Los Cabos"
      }
    ]
  },
  "avisos": []
}
```

## Cotizaciones en la DB Buffer y exportación a Odoo

### Crear cotización en el buffer

`POST /v1/cotizaciones` → **HTTP 201**

**Petición**

```http
POST /v1/cotizaciones
X-API-Key: <llave buffer>

{
  "cliente": {
    "odoo_id": 7,
    "nombre": "Hotel Ejemplo Los Cabos"
  },
  "folio_levantamiento": "L000123",
  "partidas": [
    {
      "seccion": "Voz y datos",
      "modelo_bbinco": "CS-PP24-C6",
      "codigo_odoo": "PP-24-C6",
      "descripcion": "Patch panel 24 puertos Cat6",
      "cantidad": 2,
      "precio_unitario": 1190.0
    },
    {
      "seccion": "Servicios",
      "modelo_bbinco": null,
      "codigo_odoo": "BBI-SERV-DATOS",
      "descripcion": "Cableado por nodo",
      "cantidad": 4,
      "precio_unitario": 350.0,
      "flete": 0.0
    }
  ]
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-10",
  "data": {
    "referencia": "BUF-000001",
    "estado": "borrador",
    "cliente": {
      "odoo_id": 7,
      "nombre": "Hotel Ejemplo Los Cabos"
    },
    "folio_levantamiento": "L000123",
    "moneda": "MXN",
    "notas": null,
    "partidas": [
      {
        "seccion": "Voz y datos",
        "modelo_bbinco": "CS-PP24-C6",
        "codigo_odoo": "PP-24-C6",
        "descripcion": "Patch panel 24 puertos Cat6",
        "cantidad": 2.0,
        "precio_unitario": 1190.0,
        "flete": null,
        "numero": 1,
        "importe": 2380.0
      },
      {
        "seccion": "Servicios",
        "modelo_bbinco": null,
        "codigo_odoo": "BBI-SERV-DATOS",
        "descripcion": "Cableado por nodo",
        "cantidad": 4.0,
        "precio_unitario": 350.0,
        "flete": 0.0,
        "numero": 2,
        "importe": 1400.0
      }
    ],
    "totales": {
      "partidas": 2,
      "subtotal": 3780.0,
      "moneda": "MXN"
    },
    "odoo": null,
    "creada": "2026-10-11T09:38:08-07:00",
    "actualizada": "2026-10-11T09:38:08-07:00"
  },
  "avisos": []
}
```

### Paso 1 · Simular exportación (preflight)

`POST /v1/cotizaciones/BUF-000001/exportar` → **HTTP 200**

**Petición**

```http
POST /v1/cotizaciones/BUF-000001/exportar
X-API-Key: <llave lectura>

{
  "dry_run": true
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-11",
  "data": {
    "dry_run": true,
    "listo_para_exportar": true,
    "lineas_a_crear": 4,
    "secciones": [
      "Voz y datos",
      "Servicios"
    ],
    "subtotal": 3780.0,
    "moneda": "MXN",
    "no_incluye": [
      "impuestos",
      "flete en 1 partida(s) sin capturar"
    ],
    "bloqueos": [],
    "token_preflight": "Lt7iNdhZ71-9Tq3wXCwP6DBpRJz3VvM-",
    "token_expira": "2026-10-11T09:53:08-07:00"
  },
  "avisos": []
}
```

### Paso 2 · Exportar a Odoo (tras confirmación humana)

`POST /v1/cotizaciones/BUF-000001/exportar` → **HTTP 200**

**Petición**

```http
POST /v1/cotizaciones/BUF-000001/exportar
X-API-Key: <llave odoo>

{
  "dry_run": false,
  "token_preflight": "Lt7iNdhZ71-9Tq3wXCwP6DBpRJz3VvM-"
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-12",
  "data": {
    "dry_run": false,
    "referencia": "BUF-000001",
    "folio_odoo": "S00043",
    "odoo_id": 43,
    "estado_odoo": "draft",
    "ya_existia": false
  },
  "avisos": []
}
```

### Reintento: idempotente, no crea otra

`POST /v1/cotizaciones/BUF-000001/exportar` → **HTTP 200**

**Petición**

```http
POST /v1/cotizaciones/BUF-000001/exportar
X-API-Key: <llave odoo>

{
  "dry_run": false
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-13",
  "data": {
    "dry_run": false,
    "referencia": "BUF-000001",
    "folio_odoo": "S00043",
    "odoo_id": 43,
    "estado_odoo": "draft",
    "ya_existia": true
  },
  "avisos": [
    "La cotización ya existía en Odoo; no se creó otra."
  ]
}
```

## Cotizaciones vivas en Odoo

### Leer cotización de Odoo

`GET /v1/odoo/cotizaciones/S00042` → **HTTP 200**

**Petición**

```http
GET /v1/odoo/cotizaciones/S00042
X-API-Key: <llave lectura>
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-14",
  "data": {
    "folio": "S00042",
    "odoo_id": 42,
    "estado": "draft",
    "cliente": {
      "odoo_id": 7,
      "nombre": "Hotel Ejemplo Los Cabos"
    },
    "referencia_buffer": null,
    "lineas": [
      {
        "id": 501,
        "tipo": "seccion",
        "codigo": null,
        "descripcion": "Voz y datos",
        "cantidad": null,
        "precio_unitario": null,
        "subtotal": null,
        "extras": {}
      },
      {
        "id": 502,
        "tipo": "producto",
        "codigo": "PP-24-C6",
        "descripcion": "Patch panel 24 puertos Cat6",
        "cantidad": 2.0,
        "precio_unitario": 1190.0,
        "subtotal": 2380.0,
        "extras": {}
      },
      {
        "id": 503,
        "tipo": "producto",
        "codigo": "CAB-UTP6-305",
        "descripcion": "Bobina cable UTP Cat6 305 m",
        "cantidad": 3.0,
        "precio_unitario": 2890.0,
        "subtotal": 8670.0,
        "extras": {}
      },
      {
        "id": 504,
        "tipo": "seccion",
        "codigo": null,
        "descripcion": "Servicios",
        "cantidad": null,
        "precio_unitario": null,
        "subtotal": null,
        "extras": {}
      },
      {
        "id": 505,
        "tipo": "producto",
        "codigo": "BBI-SERV-DATOS",
        "descripcion": "Servicio de cableado para video, datos y voz",
        "cantidad": 4.0,
        "precio_unitario": 350.0,
        "subtotal": 1400.0,
        "extras": {}
      }
    ],
    "total_sin_impuestos": 12450.0,
    "moneda": "MXN",
    "extras": {
      "pricelist": "Lista pública (MXN)"
    }
  },
  "avisos": []
}
```

### Simular inyección de partidas

`POST /v1/odoo/cotizaciones/S00042/partidas` → **HTTP 200**

**Petición**

```http
POST /v1/odoo/cotizaciones/S00042/partidas
X-API-Key: <llave lectura>

{
  "partidas": [
    {
      "seccion": "Voz y datos",
      "codigo_odoo": "JACK-C6-AZ",
      "descripcion": "Jack Cat6 azul",
      "cantidad": 10,
      "precio_unitario": 68.0
    }
  ],
  "dry_run": true
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-15",
  "data": {
    "folio": "S00042",
    "dry_run": true,
    "acciones": [
      {
        "accion": "agregar",
        "codigo": "JACK-C6-AZ",
        "descripcion": "Jack Cat6 azul",
        "cantidad": 10.0,
        "seccion": "Voz y datos"
      }
    ],
    "token_preflight": "LNmJtSwAjJc1cjMBewxAZg44_XKeqlc5",
    "aplicado": false
  },
  "avisos": []
}
```

## Sincronización

### Lanzar sincronización

`POST /v1/sync/productos` → **HTTP 202**

**Petición**

```http
POST /v1/sync/productos
X-API-Key: <llave buffer>

{
  "completa": true
}
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-16",
  "data": {
    "job_id": "sync-productos-0001",
    "entidad": "productos",
    "tipo": "completa",
    "estado": "en_cola",
    "lote_actual": 0,
    "lotes_totales": 5,
    "registros_procesados": 0,
    "registros_totales": 8877,
    "iniciado": "2026-10-11T09:38:08-07:00",
    "terminado": null,
    "error": null
  },
  "avisos": []
}
```

### Consultar avance

`GET /v1/jobs/sync-productos-0001` → **HTTP 200**

**Petición**

```http
GET /v1/jobs/sync-productos-0001
X-API-Key: <llave lectura>
```

**Respuesta**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-17",
  "data": {
    "job_id": "sync-productos-0001",
    "entidad": "productos",
    "tipo": "completa",
    "estado": "completado",
    "lote_actual": 5,
    "lotes_totales": 5,
    "registros_procesados": 8877,
    "registros_totales": 8877,
    "iniciado": "2026-10-11T09:38:08-07:00",
    "terminado": "2026-10-11T09:38:08-07:00",
    "error": null
  },
  "avisos": []
}
```

## Errores

### Sin llave

`GET /ready` → **HTTP 401**

**Petición**

```http
GET /ready

```

**Respuesta**

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-18",
  "error": {
    "codigo": "API_KEY_FALTANTE",
    "mensaje": "Falta el encabezado X-API-Key.",
    "detalle": null
  }
}
```

### Llave sin el nivel requerido

`POST /v1/altas` → **HTTP 403**

**Petición**

```http
POST /v1/altas
X-API-Key: <llave lectura>

{
  "modelo_bbinco": "X",
  "descripcion": "Y",
  "solicitado_por": "agente"
}
```

**Respuesta**

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-19",
  "error": {
    "codigo": "ALCANCE_INSUFICIENTE",
    "mensaje": "Esta operación requiere la llave de nivel 'buffer'.",
    "detalle": null
  }
}
```

### Entrada inválida

`POST /v1/resolver` → **HTTP 422**

**Petición**

```http
POST /v1/resolver
X-API-Key: <llave lectura>

{
  "modelos": []
}
```

**Respuesta**

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-20",
  "error": {
    "codigo": "ENTRADA_INVALIDA",
    "mensaje": "La petición no cumple el contrato.",
    "detalle": [
      {
        "campo": "modelos",
        "problema": "List should have at least 1 item after validation, not 0"
      }
    ]
  }
}
```

### Escenario simulado: Odoo caído

`GET /ready` → **HTTP 503**

**Petición**

```http
GET /ready
X-API-Key: <llave lectura>
X-Mock-Escenario: odoo_caido
```

**Respuesta**

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejemplo-21",
  "error": {
    "codigo": "ODOO_NO_DISPONIBLE",
    "mensaje": "Odoo no respondió (simulado). Reintenta más tarde.",
    "detalle": null
  }
}
```
