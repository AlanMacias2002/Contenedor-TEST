# Contrato de la API del `odoo-bridge` · versión 0.1.0

Este documento es el acuerdo entre quien construye el **agente en n8n** y quien construye el **bridge**. El esqueleto (mock) y el bridge real responden con este mismo contrato. Así, los flujos de n8n no cambian cuando se sustituye uno por otro.

- **Referencia interactiva:** `GET /docs` en el bridge, o `docs/openapi.json` (se puede importar en Postman o Insomnia).
- **Ejemplos reales de petición y respuesta:** `docs/ejemplos.md`, generado automáticamente a partir del esqueleto.

> ⚠️ **Contrato en evolución.** Pueden aparecer endpoints nuevos y cambiar algunos campos, sobre todo los de consulta y escritura en Odoo. Las reglas de la sección 4 indican qué es estable y cómo se avisan los cambios.

---

## 1. Envoltura de las respuestas

Todas las respuestas, exitosas o con error, comparten la misma forma.

**Éxito**

```json
{
  "ok": true,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "3f9a1c2b7d4e5f60",
  "data": { "...": "contenido del endpoint" },
  "avisos": ["Mensajes para el agente que no son errores"]
}
```

**Error**

```json
{
  "ok": false,
  "modo": "mock",
  "contrato": "0.1.0",
  "request_id": "3f9a1c2b7d4e5f60",
  "error": {
    "codigo": "PRODUCTO_NO_ENCONTRADO",
    "mensaje": "No existe un producto con código 'XYZ'.",
    "detalle": { "...": "opcional" }
  }
}
```

| Campo | Para qué sirve en n8n |
|---|---|
| `ok` | Decidir la rama del flujo sin revisar el código HTTP |
| `modo` | `"mock"` en el esqueleto, `"real"` en el bridge. Nunca tomes decisiones de negocio con datos `mock`. |
| `contrato` | Detectar si el bridge cambió de versión |
| `request_id` | Rastrear una petición en los logs del bridge. Puedes enviar el tuyo en el encabezado `X-Request-ID`, por ejemplo el id de la ejecución de n8n. |
| `avisos` | Información útil para que el agente se la explique al usuario |
| `error.codigo` | **Estable**: úsalo para ramificar. El `mensaje` puede cambiar de redacción. |

---

## 2. Autenticación

Encabezado `X-API-Key` en todas las rutas excepto `/health`. Hay tres llaves, y cada nivel incluye los permisos de los anteriores:

| Nivel | Permite | Quién la usa en n8n |
|---|---|---|
| `lectura` | Consultar, resolver, simular exportaciones (`dry_run`), ver estado de trabajos | Herramientas de consulta del agente |
| `buffer` | Lo anterior + escribir en la DB Buffer: cotizaciones, equivalencias, altas, sincronización | Herramientas que guardan la cotización |
| `odoo` | Lo anterior + **escribir en Odoo**: exportar cotizaciones, inyectar partidas | Solo la herramienta que exporta **tras confirmación humana** |

🔴 Guarda cada llave como credencial **Header Auth** de n8n (nombre `X-API-Key`), nunca escrita en el flujo.

---

## 3. Endpoints

| Método | Ruta | Nivel | Qué hace |
|---|---|---|---|
| GET | `/health` | — | ¿El proceso está vivo? |
| GET | `/ready` | lectura | ¿Responden Odoo y la DB Buffer? ¿Cuándo expira la API key de Odoo? |
| GET | `/v1/escenarios` | lectura | *(Solo esqueleto)* escenarios y datos de ejemplo disponibles |
| GET | `/v1/productos/{codigo}` | lectura | Producto por código exacto |
| POST | `/v1/productos/buscar` | lectura | Búsqueda por texto, marca u origen (Odoo primero, luego proveedores) |
| POST | `/v1/resolver` | lectura | Resolver modelos de BBINCO contra el catálogo (hasta 50 por petición) |
| POST | `/v1/consultas` | lectura | Lectura sobre modelos de una lista blanca |
| POST | `/v1/equivalencias` | buffer | Guardar la elección de una persona (modelo → código), para que se resuelva sola la próxima vez |
| POST | `/v1/altas` | buffer | Solicitar el alta de un producto inexistente |
| GET | `/v1/altas/{id}` | lectura | Estado de una solicitud de alta |
| POST | `/v1/cotizaciones` | buffer | Crear una cotización en la DB Buffer |
| GET | `/v1/cotizaciones/{referencia}` | lectura | Leer una cotización del buffer |
| PUT | `/v1/cotizaciones/{referencia}` | buffer | Reemplazar una cotización en borrador |
| POST | `/v1/cotizaciones/{referencia}/exportar` | lectura (`dry_run`) / **odoo** (real) | Simular o crear la cotización en Odoo |
| GET | `/v1/odoo/cotizaciones/{folio}` | lectura | Leer una cotización viva en Odoo |
| POST | `/v1/odoo/cotizaciones/{folio}/partidas` | lectura (`dry_run`) / **odoo** (real) | Agregar o actualizar partidas en una cotización de Odoo |
| POST | `/v1/sync/{entidad}` | buffer | Lanzar una sincronización Odoo → buffer (asíncrona, responde 202) |
| GET | `/v1/jobs/{job_id}` | lectura | Avance de una sincronización |

Entidades sincronizables: `productos`, `clientes`, `cotizaciones`.

### Escritura en Odoo: siempre en dos pasos

```
1. POST …/exportar  {"dry_run": true}                       → resumen + token_preflight
2. Una persona revisa el resumen y confirma
3. POST …/exportar  {"dry_run": false, "token_preflight": …} → folio en Odoo
```

- El token dura **15 minutos** y es válido solo para ese contenido. Si la cotización cambia, hay que repetir el paso 1.
- **Idempotencia:** si el paso 3 se repite (por ejemplo, n8n reintenta tras un corte de red), el bridge devuelve la cotización ya creada con `"ya_existia": true` y no crea otra.
- La cotización se crea **siempre en borrador** (regla R-06).

---

## 4. Estabilidad de los campos

| Tipo | Regla |
|---|---|
| **Núcleo estable** | Los campos documentados en el esquema. Cambiarlos o quitarlos es un cambio de contrato: sube la versión y se avisa antes. |
| **`extras`** | Objeto libre dentro de productos y cotizaciones de Odoo. Contiene datos que todavía pueden cambiar, como los campos de Studio de BBINCO. Se puede leer, pero **no conviene construir lógica que dependa de él**. |
| **Campos nuevos** | Se pueden agregar campos opcionales en cualquier momento. El flujo de n8n debe ignorar los campos que no conoce. |

**Núcleo del producto:** `odoo_id`, `codigo`, `nombre`, `marca`, `tipo`, `precio_unitario`, `costo_unitario`, `moneda`, `stock_disponible`, `unidad`, `origen` (`tipo`: `odoo` | `proveedor`, y `nombre`), `activo`, `actualizado`.

**Núcleo de la resolución:** `modelo`, `modelo_normalizado`, `estado` (`resuelto` | `requiere_confirmacion` | `no_encontrado`), `nivel` (0–4), `via`, `aplicar_sin_confirmar`, `producto`, `candidatos[]` (`producto`, `similitud`), `salidas_posibles[]`.

**Núcleo de la partida:** `seccion`, `modelo_bbinco`, `codigo_odoo`, `descripcion`, `cantidad`, `precio_unitario`, `flete`.

**Versionado:** `0.x.y`. Mientras la versión mayor sea `0`, un cambio en la versión menor (`0.2.0`) puede romper algo y se anuncia antes. Un cambio de revisión (`0.1.1`) solo agrega.

---

## 5. Reglas de negocio reflejadas en el contrato

| Regla | Dónde se ve |
|---|---|
| R-05: no sustituir una pieza sin confirmación | `aplicar_sin_confirmar` es `true` solo en niveles 0 y 1 con un único resultado |
| R-01: las líneas mostradas son las que se crean | `lineas_a_crear` del preflight = partidas + líneas de sección |
| R-03: una pieza sin precio bloquea la carga | `precio_unitario: null` → bloqueo `SIN_PRECIO` |
| R-04: el total declara qué no incluye | `no_incluye` del preflight |
| R-06: crear siempre en borrador | `estado_odoo: "draft"` |
| Regla ⑤: producto ausente | `salidas_posibles`: equivalente registrado, solicitar alta o sin producto asociado |
| Regla ⑧: el flete nace vacío, nunca en cero | `flete: null` = no capturado; `0` = sí capturado como cero |

---

## 6. Códigos de error

| HTTP | `error.codigo` | Qué hacer en el agente |
|---|---|---|
| 400 | `ESCENARIO_DESCONOCIDO` | *(Solo esqueleto)* revisar `X-Mock-Escenario` |
| 401 | `API_KEY_FALTANTE`, `API_KEY_INVALIDA` | Error de configuración; avisar al equipo |
| 403 | `ALCANCE_INSUFICIENTE` | La herramienta usa una llave de nivel menor al necesario |
| 403 | `MODELO_NO_PERMITIDO` | El modelo no está en la lista blanca de `/v1/consultas` |
| 404 | `PRODUCTO_NO_ENCONTRADO`, `COTIZACION_NO_ENCONTRADA`, `COTIZACION_ODOO_NO_ENCONTRADA`, `ALTA_NO_ENCONTRADA`, `JOB_NO_ENCONTRADO`, `RUTA_NO_ENCONTRADA` | Informar al usuario o probar otra vía (por ejemplo, `/v1/resolver`) |
| 405 | `METODO_NO_PERMITIDO` | Error de configuración del nodo |
| 409 | `COTIZACION_EXPORTADA` | Ya está en Odoo; para agregar partidas usar `/v1/odoo/cotizaciones/{folio}/partidas` |
| 409 | `TOKEN_PREFLIGHT_INVALIDO` | Repetir el preflight y volver a pedir confirmación |
| 409 | `PREFLIGHT_CON_BLOQUEOS` | Resolver los bloqueos antes de exportar |
| 409 | `SYNC_EN_CURSO`, `COTIZACION_NO_EDITABLE` | Esperar o informar al usuario |
| 422 | `ENTRADA_INVALIDA` | `error.detalle` lista cada campo con problema |
| 422 | `CODIGO_ODOO_INEXISTENTE`, `TOKEN_PREFLIGHT_REQUERIDO` | Corregir la petición |
| 500 | `ERROR_INTERNO` | Reintentar una vez; si persiste, avisar |
| 503 | `ODOO_NO_DISPONIBLE`, `BUFFER_NO_DISPONIBLE` | Reintentar más tarde e informar al usuario |

---

## 7. Solo en el esqueleto

**Palabras clave en `/v1/resolver`** para forzar cada rama del agente:

| Si el modelo contiene… | Resultado |
|---|---|
| `NOEXISTE` | `no_encontrado` |
| `AMBIGUO` | `requiere_confirmacion` con dos candidatos |
| `PROVEEDOR` | `resuelto` con un producto de Syscom |

Además, el esqueleto resuelve de verdad contra un pequeño catálogo de ejemplo. Por ejemplo, `PP-24-C6` → nivel 0, `pp 24 c6` → nivel 1, `DS 2CD2143G2 I` → nivel 2 con dos candidatos, `UTP6-305AZ` → no encontrado.

**Encabezado `X-Mock-Escenario`**, para probar el manejo de errores del agente:

| Valor | Efecto |
|---|---|
| `error` | 500 `ERROR_INTERNO` |
| `odoo_caido` | 503 `ODOO_NO_DISPONIBLE` |
| `buffer_caido` | 503 `BUFFER_NO_DISPONIBLE` |
| `lento` | Responde con 5 s de retraso, para probar timeouts |
| `falla_job` | En `POST /v1/sync`, el trabajo falla a la mitad |

**Datos de ejemplo:** códigos `BBI-SERV-DATOS`, `BBI-SERV-INSTAL`, `PP-24-C6`, `CAB-UTP6-305`, `JACK-C6-AZ`, `FACEPLATE-2`, `2CD2143G2-I`, `2CD2143G2-IS` (Odoo) y `SYS-SW-24G`, `SYS-UPS-1500` (Syscom); clientes con `odoo_id` 7 y 8; cotización de Odoo `S00042`.

**Memoria:** las cotizaciones, altas, equivalencias y trabajos creados viven en memoria y **se pierden al reiniciar** el contenedor.
