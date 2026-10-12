# Guía de uso del bridge desde n8n

**Contrato 0.1.0 · esqueleto (mock)** — documento generado por `scripts/generar_guia_n8n.py` a partir de llamadas reales al esqueleto. Las respuestas son exactamente las que devuelve el mock; las fechas, tokens e ids pueden variar.

Los ejemplos siguen una conversación completa: resolver modelos, elegir productos, armar la cotización, exportarla a Odoo y modificarla después. Cada ejemplo incluye:

1. lo que diría el usuario,
2. la configuración del nodo **HTTP Request** (en un flujo) o **HTTP Request Tool** (herramienta del agente),
3. la respuesta del mock,
4. las expresiones de n8n para leer la respuesta,
5. el JSON del nodo, listo para **copiar y pegar** en el lienzo de n8n (Ctrl+V).

## Antes de usar los ejemplos

**Credenciales.** Crea en n8n tres credenciales de tipo *Header Auth* con `Name: X-API-Key`: `odoo-bridge · lectura`, `odoo-bridge · buffer` y `odoo-bridge · odoo`. 🔴 Los valores son las llaves del bridge; nunca se escriben en el nodo. Al pegar un nodo, n8n no trae la credencial: selecciónala en el campo *Header Auth*.

**URL.** `http://odoo-bridge:8000` funciona si n8n y el bridge están en la misma red Docker. Si no, cambia la parte inicial.

**Never Error.** Todos los nodos tienen *Options → Response → Never Error* activado. Así las respuestas con error (4xx, 5xx) llegan al flujo con la envoltura `{"ok": false, "error": {...}}` y puedes ramificar con un **IF** sobre `{{ $json.ok }}`.

**Herramientas del agente y `$fromAI`.** En los nodos *HTTP Request Tool*, `$fromAI("nombre", "descripción", "tipo")` marca los datos que el modelo debe llenar a partir de la conversación. La *descripción de la herramienta* es lo que el modelo lee para decidir cuándo usarla: conviene que sea precisa. `$fromAI` requiere una versión reciente de n8n; si la suya no lo reconoce, se puede usar el modo *Defined automatically by the model* de cada campo.

**Qué no conviene dar como herramienta libre.** La exportación a Odoo y la aplicación de partidas (credencial *odoo*) deben ir en el flujo **después de una confirmación explícita** de la persona, no como herramienta que el modelo decida llamar por su cuenta.

## Índice

**A. Antes de empezar una conversación**
- Verificar que el bridge está disponible

**B. Resolver modelos y elegir productos**
- Resolver modelos
- Guardar la elección del usuario
- Volver a resolver el mismo modelo
- Solicitar el alta de un producto inexistente

**C. Consultar productos y clientes**
- Producto por código
- Buscar productos
- Consultar un cliente en Odoo

**D. Armar la cotización y exportarla a Odoo**
- Crear la cotización en la DB Buffer
- Simular la exportación (preflight)
- Exportar a Odoo tras la confirmación

**E. Cotizaciones que ya están en Odoo**
- Leer una cotización de Odoo
- Simular partidas adicionales
- Aplicar las partidas tras la confirmación

**F. Sincronización bajo demanda**
- Lanzar una sincronización
- Consultar el avance

**G. Errores: cómo se ven en n8n**
- Producto inexistente
- Odoo no disponible (escenario simulado)
- Llave sin el nivel requerido

---

## A. Antes de empezar una conversación

### 1. Verificar que el bridge está disponible

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `GET` |
| URL | `http://odoo-bridge:8000/ready` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Options → Response | **Never Error** activado |

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1001",
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

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.ok }}` | `true` |
| `{{ $json.data.estado }}` | `listo` |
| `{{ $json.data.odoo.dias_para_expirar }}` | `89` |

Úsalo al inicio de un flujo, o en un flujo programado de monitoreo. Si `ok` es `false`, el agente puede avisar que el servicio no está disponible en lugar de intentar las herramientas.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "url": "http://odoo-bridge:8000/ready",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "5d1efded-043c-5a85-aee6-a2a3d9b7defa",
      "name": "Verificar que el bridge está disponible",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

## B. Resolver modelos y elegir productos

### 2. Resolver modelos

> 💬 **Usuario:** Dame los códigos de Odoo para CS-PP24-C6, DS 2CD2143G2 I y UTP6-305AZ

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/resolver` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):

> Resuelve modelos o números de parte de BBINCO a códigos oficiales de Odoo. Úsala siempre que el usuario mencione modelos. Nunca inventes códigos. Si un resultado tiene aplicar_sin_confirmar=false, muestra los candidatos y pide al usuario que elija.

**Cuerpo JSON en el nodo**

```
={{ JSON.stringify({ modelos: $fromAI("modelos", "Lista de modelos o números de parte tal como los escribió el usuario", "json") }) }}
```

Con los valores de este ejemplo, n8n envía:

```json
{
  "modelos": [
    "CS-PP24-C6",
    "DS 2CD2143G2 I",
    "UTP6-305AZ"
  ]
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1002",
  "data": {
    "catalogo_sincronizado": "2026-10-11T02:14:00-07:00",
    "resultados": [
      {
        "modelo": "CS-PP24-C6",
        "modelo_normalizado": "CSPP24C6",
        "estado": "requiere_confirmacion",
        "nivel": 2,
        "via": "catalogo",
        "aplicar_sin_confirmar": false,
        "producto": null,
        "candidatos": [
          {
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
            "similitud": 100
          }
        ],
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

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.resultados.length }}` | `3` |
| `{{ $json.data.resultados[0].estado }}` | `requiere_confirmacion` |
| `{{ $json.data.resultados[1].candidatos[0].producto.codigo }}` | `2CD2143G2-I` |
| `{{ $json.data.resultados[2].salidas_posibles }}` | `["equivalente_registrado", "solicitar_alta", "sin_producto_asociado"]` |

En un flujo normal (no herramienta), separa los resultados con un nodo **Split Out** sobre `data.resultados` y ramifica con un **Switch** sobre `{{ $json.estado }}`: `resuelto`, `requiere_confirmacion` y `no_encontrado`.

`$fromAI(...)` le indica al agente qué dato debe llenar. Es propio de los nodos de herramienta; en un HTTP Request normal escribe el cuerpo con datos de nodos anteriores.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "toolDescription": "Resuelve modelos o números de parte de BBINCO a códigos oficiales de Odoo. Úsala siempre que el usuario mencione modelos. Nunca inventes códigos. Si un resultado tiene aplicar_sin_confirmar=false, muestra los candidatos y pide al usuario que elija.",
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/resolver",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ modelos: $fromAI(\"modelos\", \"Lista de modelos o números de parte tal como los escribió el usuario\", \"json\") }) }}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "3b7c9dd7-2e6f-5679-a932-5539a9c8f935",
      "name": "Resolver modelos",
      "type": "n8n-nodes-base.httpRequestTool",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 3. Guardar la elección del usuario

> 💬 **Usuario:** La primera opción, la cámara sin audio.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/equivalencias` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · buffer** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):

> Guarda la equivalencia entre un modelo de BBINCO y el código de Odoo que el usuario confirmó. Úsala solo después de que el usuario elija explícitamente un candidato.

**Cuerpo JSON en el nodo**

```
={{ JSON.stringify({
  modelo_bbinco: $fromAI("modelo_bbinco", "Modelo tal como lo escribió el usuario", "string"),
  codigo_odoo: $fromAI("codigo_odoo", "Código del candidato que eligió el usuario", "string"),
  confirmado_por: "Vendedor",
  cotizacion_referencia: null
}) }}
```

Con los valores de este ejemplo, n8n envía:

```json
{
  "modelo_bbinco": "DS 2CD2143G2 I",
  "codigo_odoo": "2CD2143G2-I",
  "confirmado_por": "Vendedor",
  "cotizacion_referencia": null
}
```

**Respuesta del mock** — HTTP 201

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1003",
  "data": {
    "modelo_bbinco": "DS 2CD2143G2 I",
    "codigo_odoo": "2CD2143G2-I",
    "confirmado_por": "Vendedor",
    "cotizacion_referencia": null,
    "id": 1,
    "modelo_normalizado": "DS2CD2143G2I",
    "creada": "2026-10-11T09:49:48-07:00"
  },
  "avisos": [
    "Desde ahora este modelo se resuelve solo (nivel 0, vía equivalencia)."
  ]
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.modelo_normalizado }}` | `DS2CD2143G2I` |

Después de guardarla, ese modelo se resuelve solo (nivel 0, `via: "equivalencia"`). Requiere la credencial de nivel **buffer**.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "toolDescription": "Guarda la equivalencia entre un modelo de BBINCO y el código de Odoo que el usuario confirmó. Úsala solo después de que el usuario elija explícitamente un candidato.",
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/equivalencias",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  modelo_bbinco: $fromAI(\"modelo_bbinco\", \"Modelo tal como lo escribió el usuario\", \"string\"),\n  codigo_odoo: $fromAI(\"codigo_odoo\", \"Código del candidato que eligió el usuario\", \"string\"),\n  confirmado_por: \"Vendedor\",\n  cotizacion_referencia: null\n}) }}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "97bc98ab-be22-5ba1-bd2e-dfda17d1067c",
      "name": "Guardar la elección del usuario",
      "type": "n8n-nodes-base.httpRequestTool",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 4. Volver a resolver el mismo modelo

> 💬 **Usuario:** Agrega otras dos cámaras DS 2CD2143G2 I.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/resolver` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
{
  "modelos": [
    "DS 2CD2143G2 I"
  ]
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1004",
  "data": {
    "catalogo_sincronizado": "2026-10-11T02:14:00-07:00",
    "resultados": [
      {
        "modelo": "DS 2CD2143G2 I",
        "modelo_normalizado": "DS2CD2143G2I",
        "estado": "resuelto",
        "nivel": 0,
        "via": "equivalencia",
        "aplicar_sin_confirmar": true,
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
        "candidatos": [],
        "salidas_posibles": []
      }
    ]
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.resultados[0].estado }}` | `resuelto` |
| `{{ $json.data.resultados[0].via }}` | `equivalencia` |
| `{{ $json.data.resultados[0].aplicar_sin_confirmar }}` | `true` |

Es la misma herramienta del ejemplo 2; se muestra para ver el efecto de la equivalencia.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/resolver",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "{\n  \"modelos\": [\n    \"DS 2CD2143G2 I\"\n  ]\n}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "3cd56eaa-2eb2-588a-a3de-e225e1228c0a",
      "name": "Volver a resolver el mismo modelo",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 5. Solicitar el alta de un producto inexistente

> 💬 **Usuario:** Ese no lo tenemos; pide que lo den de alta.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/altas` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · buffer** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):

> Solicita al área responsable el alta de un producto que no existe en el catálogo. Úsala cuando la resolución devuelva no_encontrado y el usuario elija solicitar el alta.

**Cuerpo JSON en el nodo**

```
{
  "modelo_bbinco": "UTP6-305AZ",
  "descripcion": "Bobina cable UTP Cat6 azul 305 m",
  "marca": null,
  "solicitado_por": "Vendedor",
  "cotizacion_referencia": null
}
```

**Respuesta del mock** — HTTP 201

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1005",
  "data": {
    "modelo_bbinco": "UTP6-305AZ",
    "descripcion": "Bobina cable UTP Cat6 azul 305 m",
    "marca": null,
    "solicitado_por": "Vendedor",
    "cotizacion_referencia": null,
    "id": "ALTA-0001",
    "estado": "solicitada",
    "creada": "2026-10-11T09:49:48-07:00"
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.id }}` | `ALTA-0001` |
| `{{ $json.data.estado }}` | `solicitada` |

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "toolDescription": "Solicita al área responsable el alta de un producto que no existe en el catálogo. Úsala cuando la resolución devuelva no_encontrado y el usuario elija solicitar el alta.",
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/altas",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "{\n  \"modelo_bbinco\": \"UTP6-305AZ\",\n  \"descripcion\": \"Bobina cable UTP Cat6 azul 305 m\",\n  \"marca\": null,\n  \"solicitado_por\": \"Vendedor\",\n  \"cotizacion_referencia\": null\n}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "7d8b5b18-159d-5924-a444-27120579a7da",
      "name": "Solicitar el alta de un producto inexistente",
      "type": "n8n-nodes-base.httpRequestTool",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

## C. Consultar productos y clientes

### 6. Producto por código

> 💬 **Usuario:** ¿Cuántos patch panel PP-24-C6 tenemos y a qué precio?

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `GET` |
| URL | `http://odoo-bridge:8000/v1/productos/PP-24-C6` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Options → Response | **Never Error** activado |

**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):

> Consulta un producto por su código exacto de Odoo: precio, costo y existencias. Si no conoces el código exacto, usa primero resolver_modelos.

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1006",
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

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.stock_disponible }}` | `6` |
| `{{ $json.data.precio_unitario }}` | `1190` |
| `{{ $json.data.origen.tipo }}` | `odoo` |

En la herramienta, la URL lleva el código variable: `http://odoo-bridge:8000/v1/productos/{{ $fromAI("codigo", "Código exacto de Odoo", "string") }}` (escribe la URL en modo expresión, con `=` al inicio).

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "toolDescription": "Consulta un producto por su código exacto de Odoo: precio, costo y existencias. Si no conoces el código exacto, usa primero resolver_modelos.",
        "url": "http://odoo-bridge:8000/v1/productos/PP-24-C6",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "e9c733fb-6f91-5639-9d4f-d03e73b651bf",
      "name": "Producto por código",
      "type": "n8n-nodes-base.httpRequestTool",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 7. Buscar productos

> 💬 **Usuario:** ¿Qué cámaras tenemos en existencia?

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/productos/buscar` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):

> Busca productos por texto, primero en el inventario propio de BBINCO y después en catálogos de proveedores. Úsala cuando el usuario describa un producto sin dar su código.

**Cuerpo JSON en el nodo**

```
={{ JSON.stringify({
  texto: $fromAI("texto", "Palabras a buscar en código o nombre", "string"),
  solo_con_stock: $fromAI("solo_con_stock", "true si el usuario pide solo lo que hay en existencia", "boolean"),
  fuente: "todas",
  limite: 10
}) }}
```

Con los valores de este ejemplo, n8n envía:

```json
{
  "texto": "cámara",
  "solo_con_stock": true,
  "fuente": "todas",
  "limite": 10
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1007",
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

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.total }}` | `1` |
| `{{ $json.data.productos[0].nombre }}` | `Cámara domo IP 4 MP` |

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "toolDescription": "Busca productos por texto, primero en el inventario propio de BBINCO y después en catálogos de proveedores. Úsala cuando el usuario describa un producto sin dar su código.",
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/productos/buscar",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  texto: $fromAI(\"texto\", \"Palabras a buscar en código o nombre\", \"string\"),\n  solo_con_stock: $fromAI(\"solo_con_stock\", \"true si el usuario pide solo lo que hay en existencia\", \"boolean\"),\n  fuente: \"todas\",\n  limite: 10\n}) }}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "a34f7ffa-4c2d-57ac-b7ae-fd044e242081",
      "name": "Buscar productos",
      "type": "n8n-nodes-base.httpRequestTool",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 8. Consultar un cliente en Odoo

> 💬 **Usuario:** La cotización es para el Hotel Ejemplo.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/consultas` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):

> Busca un cliente en Odoo por nombre para obtener su odoo_id. Úsala antes de crear una cotización si no conoces el id del cliente.

**Cuerpo JSON en el nodo**

```
{
  "modelo": "res.partner",
  "dominio": [
    [
      "name",
      "ilike",
      "hotel ejemplo"
    ]
  ],
  "campos": [
    "id",
    "name",
    "email"
  ],
  "limite": 5
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1008",
  "data": {
    "modelo": "res.partner",
    "total": 1,
    "registros": [
      {
        "id": 7,
        "name": "Hotel Ejemplo Los Cabos",
        "email": "compras@hotel-ejemplo.mx"
      }
    ]
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.registros[0].id }}` | `7` → se usa como `cliente.odoo_id` |

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "toolDescription": "Busca un cliente en Odoo por nombre para obtener su odoo_id. Úsala antes de crear una cotización si no conoces el id del cliente.",
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/consultas",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "{\n  \"modelo\": \"res.partner\",\n  \"dominio\": [\n    [\n      \"name\",\n      \"ilike\",\n      \"hotel ejemplo\"\n    ]\n  ],\n  \"campos\": [\n    \"id\",\n    \"name\",\n    \"email\"\n  ],\n  \"limite\": 5\n}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "eea7342b-e951-58e3-866b-5c80690ea5a2",
      "name": "Consultar un cliente en Odoo",
      "type": "n8n-nodes-base.httpRequestTool",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

## D. Armar la cotización y exportarla a Odoo

### 9. Crear la cotización en la DB Buffer

> 💬 **Usuario:** Listo, arma la cotización con eso.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/cotizaciones` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · buffer** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
={{ JSON.stringify({
  cliente: { odoo_id: $("Consultar cliente").item.json.data.registros[0].id,
             nombre: $("Consultar cliente").item.json.data.registros[0].name },
  folio_levantamiento: $json.folio_levantamiento,
  moneda: "MXN",
  notas: null,
  partidas: $json.partidas
}) }}
```

Con los valores de este ejemplo, n8n envía:

```json
{
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
      "cantidad": 2,
      "precio_unitario": 1190.0,
      "flete": null
    },
    {
      "seccion": "Videovigilancia",
      "modelo_bbinco": "DS 2CD2143G2 I",
      "codigo_odoo": "2CD2143G2-I",
      "descripcion": "Cámara domo IP 4 MP",
      "cantidad": 2,
      "precio_unitario": 2350.0,
      "flete": 120.0
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

**Respuesta del mock** — HTTP 201

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1009",
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
        "seccion": "Videovigilancia",
        "modelo_bbinco": "DS 2CD2143G2 I",
        "codigo_odoo": "2CD2143G2-I",
        "descripcion": "Cámara domo IP 4 MP",
        "cantidad": 2.0,
        "precio_unitario": 2350.0,
        "flete": 120.0,
        "numero": 2,
        "importe": 4700.0
      },
      {
        "seccion": "Servicios",
        "modelo_bbinco": null,
        "codigo_odoo": "BBI-SERV-DATOS",
        "descripcion": "Cableado por nodo",
        "cantidad": 4.0,
        "precio_unitario": 350.0,
        "flete": 0.0,
        "numero": 3,
        "importe": 1400.0
      }
    ],
    "totales": {
      "partidas": 3,
      "subtotal": 8480.0,
      "moneda": "MXN"
    },
    "odoo": null,
    "creada": "2026-10-11T09:49:48-07:00",
    "actualizada": "2026-10-11T09:49:48-07:00"
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.referencia }}` | `BUF-000001` → guárdala; la usan los pasos siguientes |
| `{{ $json.data.totales.subtotal }}` | `8480` |
| `{{ $json.avisos }}` | `[]` |

Aquí el cuerpo se arma con datos de nodos anteriores: el cliente de la consulta y las partidas que el agente fue reuniendo (por ejemplo, en un nodo **Code** o **Set** que construye el arreglo `partidas`). Para modificarla más tarde se usa `PUT /v1/cotizaciones/{referencia}` con el mismo cuerpo.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/cotizaciones",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  cliente: { odoo_id: $(\"Consultar cliente\").item.json.data.registros[0].id,\n             nombre: $(\"Consultar cliente\").item.json.data.registros[0].name },\n  folio_levantamiento: $json.folio_levantamiento,\n  moneda: \"MXN\",\n  notas: null,\n  partidas: $json.partidas\n}) }}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "fc88a49d-deb2-56f0-8f51-b0154fb40cc1",
      "name": "Crear la cotización en la DB Buffer",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 10. Simular la exportación (preflight)

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/cotizaciones/BUF-000001/exportar` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
{
  "dry_run": true
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1010",
  "data": {
    "dry_run": true,
    "listo_para_exportar": true,
    "lineas_a_crear": 6,
    "secciones": [
      "Voz y datos",
      "Videovigilancia",
      "Servicios"
    ],
    "subtotal": 8480.0,
    "moneda": "MXN",
    "no_incluye": [
      "impuestos",
      "flete en 1 partida(s) sin capturar"
    ],
    "bloqueos": [],
    "token_preflight": "Vs7otCFofa9jfpgCfq761oEnmYJ-EYId",
    "token_expira": "2026-10-11T10:04:48-07:00"
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.listo_para_exportar }}` | `true` |
| `{{ $json.data.lineas_a_crear }}` | `6` (3 partidas + 3 secciones) |
| `{{ $json.data.no_incluye }}` | `["impuestos", "flete en 1 partida(s) sin capturar"]` |
| `{{ $json.data.token_preflight }}` | token de un solo uso, válido 15 min |

En la URL real la referencia va como expresión: `=http://odoo-bridge:8000/v1/cotizaciones/{{ $("Crear cotización").item.json.data.referencia }}/exportar`.

El resumen (líneas, subtotal, qué no incluye, bloqueos) es lo que el agente le muestra a la persona para que confirme. Si `listo_para_exportar` es `false`, lista `data.bloqueos` y no continúa.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/cotizaciones/BUF-000001/exportar",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "{\n  \"dry_run\": true\n}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "618e6bd2-f0a5-540c-8bc5-431aa4ab4ada",
      "name": "Simular la exportación (preflight)",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 11. Exportar a Odoo tras la confirmación

> 💬 **Usuario:** Sí, confirmo. Súbela a Odoo.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/cotizaciones/BUF-000001/exportar` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · odoo** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
={{ JSON.stringify({
  dry_run: false,
  token_preflight: $("Simular exportación").item.json.data.token_preflight
}) }}
```

Con los valores de este ejemplo, n8n envía:

```json
{
  "dry_run": false,
  "token_preflight": "Vs7otCFofa9jfpgCfq761oEnmYJ-EYId"
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1011",
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

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.folio_odoo }}` | `S00043` |
| `{{ $json.data.estado_odoo }}` | `draft` |
| `{{ $json.data.ya_existia }}` | `false` |

⚠️ Es el único nodo que lleva la credencial **odoo-bridge · odoo**. Conviene que **no** sea una herramienta que el agente pueda llamar libremente: colócalo en el flujo después de un paso de aprobación explícita (por ejemplo, la respuesta "sí" del usuario en Telegram o un nodo de espera de aprobación).

Si n8n reintenta este nodo, el bridge responde con la misma cotización y `ya_existia: true`; no se duplica en Odoo.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/cotizaciones/BUF-000001/exportar",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  dry_run: false,\n  token_preflight: $(\"Simular exportación\").item.json.data.token_preflight\n}) }}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "efc29206-4d8f-50e7-a986-9b4f3f48d9c5",
      "name": "Exportar a Odoo tras la confirmación",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

## E. Cotizaciones que ya están en Odoo

### 12. Leer una cotización de Odoo

> 💬 **Usuario:** ¿Qué lleva la cotización S00042?

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `GET` |
| URL | `http://odoo-bridge:8000/v1/odoo/cotizaciones/S00042` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Options → Response | **Never Error** activado |

**Descripción de la herramienta** (lo que lee el modelo para decidir cuándo usarla):

> Lee una cotización existente en Odoo por su folio (por ejemplo S00042): líneas, cantidades y total.

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1012",
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

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.estado }}` | `draft` |
| `{{ $json.data.total_sin_impuestos }}` | `12450` |
| `{{ $json.data.lineas.filter(l => l.tipo === 'producto').length }}` | `3` |

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "toolDescription": "Lee una cotización existente en Odoo por su folio (por ejemplo S00042): líneas, cantidades y total.",
        "url": "http://odoo-bridge:8000/v1/odoo/cotizaciones/S00042",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "b6f6bd26-8ae6-5964-85af-640aab187fef",
      "name": "Leer una cotización de Odoo",
      "type": "n8n-nodes-base.httpRequestTool",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 13. Simular partidas adicionales

> 💬 **Usuario:** Al S00042 agrégale 10 jacks azules y sube los patch panel a 5.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/odoo/cotizaciones/S00042/partidas` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
={{ JSON.stringify({
  dry_run: true,
  partidas: $("Partidas a inyectar").item.json.partidas
}) }}
```

Con los valores de este ejemplo, n8n envía:

```json
{
  "dry_run": true,
  "partidas": [
    {
      "seccion": "Voz y datos",
      "codigo_odoo": "PP-24-C6",
      "descripcion": "Patch panel 24 puertos Cat6",
      "cantidad": 5,
      "precio_unitario": 1190.0
    },
    {
      "seccion": "Voz y datos",
      "codigo_odoo": "JACK-C6-AZ",
      "descripcion": "Jack Cat6 color azul",
      "cantidad": 10,
      "precio_unitario": 68.0
    }
  ]
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1013",
  "data": {
    "folio": "S00042",
    "dry_run": true,
    "acciones": [
      {
        "accion": "actualizar",
        "codigo": "PP-24-C6",
        "descripcion": "Patch panel 24 puertos Cat6",
        "cantidad": 5.0,
        "seccion": "Voz y datos"
      },
      {
        "accion": "agregar",
        "codigo": "JACK-C6-AZ",
        "descripcion": "Jack Cat6 color azul",
        "cantidad": 10.0,
        "seccion": "Voz y datos"
      }
    ],
    "token_preflight": "uo-_iCJ525FOzC3oPaUELBfgt1Cr8Fz5",
    "aplicado": false
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.acciones.map(a => a.accion) }}` | `["actualizar", "agregar"]` |

`Partidas a inyectar` es un nodo **Set** previo donde el agente deja el arreglo de partidas. Así la simulación y la aplicación envían exactamente el mismo contenido.

Igual que la exportación: se muestra el plan, la persona confirma y después se llama con `dry_run: false`, el `token_preflight` y la credencial **odoo**.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/odoo/cotizaciones/S00042/partidas",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  dry_run: true,\n  partidas: $(\"Partidas a inyectar\").item.json.partidas\n}) }}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "6e50ffd2-12f1-5f60-b172-d1f1bd187a5d",
      "name": "Simular partidas adicionales",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 14. Aplicar las partidas tras la confirmación

> 💬 **Usuario:** Confirmo.

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/odoo/cotizaciones/S00042/partidas` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · odoo** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
={{ JSON.stringify({
  dry_run: false,
  token_preflight: $("Simular partidas").item.json.data.token_preflight,
  partidas: $("Partidas a inyectar").item.json.partidas
}) }}
```

Con los valores de este ejemplo, n8n envía:

```json
{
  "dry_run": false,
  "token_preflight": "uo-_iCJ525FOzC3oPaUELBfgt1Cr8Fz5",
  "partidas": [
    {
      "seccion": "Voz y datos",
      "codigo_odoo": "PP-24-C6",
      "descripcion": "Patch panel 24 puertos Cat6",
      "cantidad": 5,
      "precio_unitario": 1190.0
    },
    {
      "seccion": "Voz y datos",
      "codigo_odoo": "JACK-C6-AZ",
      "descripcion": "Jack Cat6 color azul",
      "cantidad": 10,
      "precio_unitario": 68.0
    }
  ]
}
```

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1014",
  "data": {
    "folio": "S00042",
    "dry_run": false,
    "acciones": [
      {
        "accion": "actualizar",
        "codigo": "PP-24-C6",
        "descripcion": "Patch panel 24 puertos Cat6",
        "cantidad": 5.0,
        "seccion": "Voz y datos"
      },
      {
        "accion": "agregar",
        "codigo": "JACK-C6-AZ",
        "descripcion": "Jack Cat6 color azul",
        "cantidad": 10.0,
        "seccion": "Voz y datos"
      }
    ],
    "token_preflight": null,
    "aplicado": true
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.aplicado }}` | `true` |

⚠️ Las `partidas` deben ser **exactamente las mismas** que en la simulación; si cambian, el bridge rechaza el token con `TOKEN_PREFLIGHT_INVALIDO`. Por eso ambos nodos leen el arreglo del mismo nodo **Set** (`Partidas a inyectar`).

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/odoo/cotizaciones/S00042/partidas",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  dry_run: false,\n  token_preflight: $(\"Simular partidas\").item.json.data.token_preflight,\n  partidas: $(\"Partidas a inyectar\").item.json.partidas\n}) }}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "0c5b9874-0192-5645-b54c-afc2e5752052",
      "name": "Aplicar las partidas tras la confirmación",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

## F. Sincronización bajo demanda

### 15. Lanzar una sincronización

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/sync/productos` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · buffer** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
{
  "completa": false
}
```

**Respuesta del mock** — HTTP 202

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1015",
  "data": {
    "job_id": "sync-productos-0001",
    "entidad": "productos",
    "tipo": "incremental",
    "estado": "en_cola",
    "lote_actual": 0,
    "lotes_totales": 1,
    "registros_procesados": 0,
    "registros_totales": 44,
    "iniciado": "2026-10-11T09:49:48-07:00",
    "terminado": null,
    "error": null
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.job_id }}` | id para consultar el avance |
| `{{ $json.data.estado }}` | `en_cola` o `corriendo` |

Responde **202** de inmediato. La sincronización nocturna la ejecuta el propio bridge; esto es solo para lanzarla a mano.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/sync/productos",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "{\n  \"completa\": false\n}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "4a35ea3f-8705-52c2-abfe-b8543a97d515",
      "name": "Lanzar una sincronización",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 16. Consultar el avance

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `GET` |
| URL | `http://odoo-bridge:8000/v1/jobs/sync-productos-0001` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Options → Response | **Never Error** activado |

**Respuesta del mock** — HTTP 200

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1016",
  "data": {
    "job_id": "sync-productos-0001",
    "entidad": "productos",
    "tipo": "incremental",
    "estado": "completado",
    "lote_actual": 1,
    "lotes_totales": 1,
    "registros_procesados": 44,
    "registros_totales": 44,
    "iniciado": "2026-10-11T09:49:48-07:00",
    "terminado": "2026-10-11T09:49:48-07:00",
    "error": null
  },
  "avisos": []
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.data.estado }}` | `completado` |
| `{{ $json.data.lote_actual }} / {{ $json.data.lotes_totales }}` | `1 / 1` |

Patrón en n8n: **Wait** (por ejemplo, 30 s) → este nodo → **IF** `{{ $json.data.estado }}` es `completado` o `fallido` → si no, regresa al Wait. Pon un límite de vueltas.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "url": "http://odoo-bridge:8000/v1/jobs/sync-productos-0001",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "f490471d-ad01-5f16-9ae3-7a7044f39c23",
      "name": "Consultar el avance",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

## G. Errores: cómo se ven en n8n

### 17. Producto inexistente

> 💬 **Usuario:** ¿Tienes el XYZ-999?

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request Tool (herramienta del agente)** |
| Method | `GET` |
| URL | `http://odoo-bridge:8000/v1/productos/XYZ-999` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Options → Response | **Never Error** activado |

**Respuesta del mock** — HTTP 404

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1017",
  "error": {
    "codigo": "PRODUCTO_NO_ENCONTRADO",
    "mensaje": "No existe un producto con código 'XYZ-999'.",
    "detalle": {
      "sugerencia": "Usa POST /v1/resolver para buscar por modelo, o POST /v1/productos/buscar."
    }
  }
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.ok }}` | `false` |
| `{{ $json.error.codigo }}` | `PRODUCTO_NO_ENCONTRADO` |
| `{{ $json.error.detalle.sugerencia }}` | qué hacer a continuación |

Gracias a **Never Error**, la respuesta 404 llega al flujo como cualquier otra. En una herramienta, el agente lee `error.mensaje` y puede intentar otra vía.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "url": "http://odoo-bridge:8000/v1/productos/XYZ-999",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "44abaa90-726e-591c-ab70-b9f20c1c6f75",
      "name": "Producto inexistente",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 18. Odoo no disponible (escenario simulado)

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `GET` |
| URL | `http://odoo-bridge:8000/ready` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}`; `X-Mock-Escenario` = `odoo_caido` |
| Options → Response | **Never Error** activado |

**Respuesta del mock** — HTTP 503

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1018",
  "error": {
    "codigo": "ODOO_NO_DISPONIBLE",
    "mensaje": "Odoo no respondió (simulado). Reintenta más tarde.",
    "detalle": null
  }
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.error.codigo }}` | `ODOO_NO_DISPONIBLE` |

El encabezado `X-Mock-Escenario` solo existe en el esqueleto; quítalo al pasar al bridge real.

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "url": "http://odoo-bridge:8000/ready",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            },
            {
              "name": "X-Mock-Escenario",
              "value": "odoo_caido"
            }
          ]
        },
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "ee9c0f3a-1630-51af-a60d-2916fa37142e",
      "name": "Odoo no disponible (escenario simulado)",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---

### 19. Llave sin el nivel requerido

| Campo del nodo | Valor |
|---|---|
| Tipo de nodo | **HTTP Request (flujo)** |
| Method | `POST` |
| URL | `http://odoo-bridge:8000/v1/altas` |
| Authentication | Generic Credential Type → Header Auth → **odoo-bridge · lectura** |
| Send Headers | `X-Request-ID` = `{{ $execution.id }}` |
| Send Body | JSON (ver abajo) |
| Options → Response | **Never Error** activado |

**Cuerpo JSON en el nodo**

```
{
  "modelo_bbinco": "X",
  "descripcion": "Y",
  "solicitado_por": "agente"
}
```

**Respuesta del mock** — HTTP 403

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "ejecucion-1019",
  "error": {
    "codigo": "ALCANCE_INSUFICIENTE",
    "mensaje": "Esta operación requiere la llave de nivel 'buffer'.",
    "detalle": null
  }
}
```

**Cómo leer la respuesta en n8n**

| Expresión | Valor en este ejemplo |
|---|---|
| `{{ $json.error.codigo }}` | `ALCANCE_INSUFICIENTE` |

Indica que el nodo usa una credencial de nivel menor al necesario (aquí, lectura en lugar de buffer).

<details><summary>JSON del nodo para pegar en n8n</summary>

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://odoo-bridge:8000/v1/altas",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Request-ID",
              "value": "={{ $execution.id }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "{\n  \"modelo_bbinco\": \"X\",\n  \"descripcion\": \"Y\",\n  \"solicitado_por\": \"agente\"\n}",
        "options": {
          "response": {
            "response": {
              "neverError": true
            }
          },
          "timeout": 30000
        }
      },
      "id": "761a74b9-1bea-53db-b4f1-093c57a4b1d3",
      "name": "Llave sin el nivel requerido",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [
        0,
        0
      ]
    }
  ],
  "connections": {}
}
```

</details>

---
