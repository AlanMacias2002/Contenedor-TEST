# Diseño del servicio `odoo-bridge`

**Proyecto:** Agente de cotización BBINCO × Cognitive
**Versión:** 0.1 — borrador para revisión
**Fecha:** 8 de octubre de 2026
**Autor:** Germán · **Revisión:** Andrea Monroy
**Estado:** diseño previo a código. Las secciones marcadas con ❓ dependen de respuestas pendientes.

---

## 0. Resumen

`odoo-bridge` es un servicio en Python, empaquetado en Docker, que concentra **toda** la comunicación entre el agente orquestador (n8n), Odoo 19 y la DB Buffer. n8n no habla con Odoo ni ejecuta lógica pesada: llama al bridge por HTTP.

Cinco decisiones de fondo:

1. **El bridge usa exclusivamente la API externa JSON-2 de Odoo.** XML-RPC y JSON-RPC están obsoletas desde Odoo 19.
2. **Toda escritura en Odoo se hace en una sola llamada atómica por operación**, porque JSON-2 no permite agrupar varias llamadas en una transacción (§6).
3. **Lo síncrono y lo asíncrono se separan.** Consultas puntuales: respuesta inmediata. Cargas masivas: trabajos que ejecuta el bridge con su propio programador; n8n solo los lanza o consulta su estado (§5).
4. **El bridge no se expone a internet** y exige una API key propia a n8n (§8).
5. **No se pone lógica Python en nodos Code de n8n.** El resolvedor de códigos y cualquier ciclo largo viven en el bridge (§11).

---

## 1. Contexto y supuestos

| Tema | Situación | Estado |
|---|---|---|
| Odoo de producción de BBINCO | Versión 19. Se asume **servidor propio** (on-premise). | ❓ Pendiente de confirmar con BBINCO |
| Servidor de pruebas de BBINCO | Odoo 19 Enterprise en odoo.com, con personalizaciones de Studio | Disponible; usuario genérico de pruebas |
| Servidor de pruebas de Cognitive | Odoo 19 Community, en Docker, sin personalizaciones de BBINCO | Disponible; aún sin catálogo cargado |
| DB Buffer | MySQL, esquema en evolución (Rev 3, soporte de proveedores) | En diseño en hilo aparte |
| Orquestador | n8n con agente de IA | ❓ Versión y lugar de despliegue en producción por confirmar |

**Nota sobre odoo.com:** Odoo indica que el acceso a datos por la API externa solo está disponible en planes *Custom* [R1]. Como el servidor de pruebas de BBINCO vive en odoo.com, lo primero es confirmar con la sonda (§12, fase 0) que su API responde.

---

## 2. Alcance

### Dentro del alcance

| # | Operación | Origen | Dirección |
|---|---|---|---|
| O1 | Exportación masiva nocturna (carga inicial y sincronización programada), lotes de máx. 2,000 registros | Programador del bridge, o n8n bajo demanda | Odoo → DB Buffer |
| O2 | Consulta puntual de productos durante el uso diario del agente | Agente (n8n) | Odoo → agente (y opcionalmente → DB Buffer) |
| O3 | Insertar en Odoo una cotización confirmada por el agente | Agente (n8n), con confirmación humana | DB Buffer → Odoo |
| O4 | Inyectar partidas a una cotización existente en Odoo | Agente (n8n) | DB Buffer → Odoo |
| O5 | Resolver modelos de BBINCO contra códigos de Odoo (resolvedor niveles 0–4, `rapidfuzz`) | Agente (n8n) | Interno del bridge |
| O6 | Consultas de lectura no previstas, sobre una lista blanca de modelos | Agente (n8n) | Odoo → agente |

### Fuera del alcance (por ahora)

- Confirmar cotizaciones (`action_confirm`), facturar o generar compras. Regla R-06 del proyecto: la cotización se crea **siempre en borrador**; confirmar es una decisión comercial.
- Obtener el PDF de la cotización (la ruta viable conocida es el token del portal; se evaluará aparte).
- Escritura en modelos personalizados (`x_*`) distintos de los que BBINCO autorice explícitamente.
- Integración con Syscom (tiene su propio flujo; el bridge podría absorberla en una versión futura).

---

## 3. Arquitectura

```
                         ┌──────────────────────── n8n ────────────────────────┐
                         │  AI Agent ──(HTTP Request Tool)──┐                  │
                         │  Flujos manuales / avisos ───────┤                  │
                         └──────────────────────────────────┼──────────────────┘
                                                            │ HTTP + X-API-Key
                                                            │ (red interna Docker)
┌───────────────────────────── odoo-bridge (Docker) ────────▼──────────────────┐
│  API (FastAPI)          Trabajos asíncronos         Programador interno      │
│  /v1/productos …        cola + worker               (sincronización nocturna)│
│  /v1/cotizaciones …                                                          │
│  ───────────────────────────────────────────────────────────────────────────  │
│  Cliente JSON-2 │ Mapeo Odoo ↔ Buffer │ Resolvedor │ Auditoría │ Config/entorno│
└────────┬─────────────────────────────────────────────────────────┬───────────┘
         │ HTTPS + bearer (bots de Odoo)                            │ MySQL (usuario dedicado)
         ▼                                                          ▼
     Odoo 19                                                    DB Buffer
 (pruebas Cognitive / pruebas BBINCO / producción)        (datos + tablas de control)
```

**Capas internas** (separadas para que cambios en una no toquen las demás):

| Capa | Responsabilidad |
|---|---|
| Cliente JSON-2 | Llamadas a Odoo, manejo de errores, reintentos solo en lecturas |
| Mapeo | Traducción entre modelos de Odoo y tablas de la DB Buffer. Aísla los cambios de esquema de la DB Buffer (Rev 3 en curso). |
| Perfil de entorno | Diferencias entre servidores: campos de Studio (`x_studio_*`) que existen en BBINCO y no en Cognitive, ids de impuestos, compañía, etc. |
| Resolvedor | Algoritmo de resolución de códigos (niveles 0–4) |
| Auditoría | Registro de cada operación (§7.1) |
| API y trabajos | Endpoints, autenticación, cola de trabajos, programador |

El cliente JSON-2 ya tiene un primer prototipo en la sonda `odoo-json2-probe` (§12).

---

## 4. Catálogo de operaciones (endpoints)

Versionado bajo `/v1`. Todas las respuestas en JSON con formato estable y limpio para el agente (sin tuplas `[id, nombre]` ni campos `jsonb` crudos).

| Endpoint | Tipo | Efecto | Consumidor | Fase |
|---|---|---|---|---|
| `GET /health` | Síncrono | Ninguno. ¿El proceso vive? | Docker, monitoreo | 1 |
| `GET /ready` | Síncrono | Ninguno. ¿Responden Odoo y la DB Buffer? ¿Cuándo expira la API key? | Monitoreo | 1 |
| `GET /v1/productos/{codigo}` | Síncrono | Lectura | Agente | 1 |
| `POST /v1/productos/buscar` | Síncrono | Lectura (texto, marca, categoría; máx. 50 resultados) | Agente | 1 |
| `POST /v1/consultas` | Síncrono | Lectura sobre lista blanca de modelos y campos (O6) | Agente | 1 |
| `POST /v1/resolver` | Síncrono | Ninguno sobre Odoo; resuelve modelos contra el catálogo (O5) | Agente | 2 |
| `POST /v1/sync/{entidad}` | **Asíncrono** → `202` + `job_id` | Lectura en Odoo, escritura en DB Buffer (O1) | Programador, n8n | 2 |
| `GET /v1/jobs/{job_id}` | Síncrono | Ninguno. Estado y avance del trabajo | n8n | 2 |
| `GET /v1/cotizaciones/{referencia}` | Síncrono | Lectura de una cotización viva en Odoo | Agente | 3 |
| `POST /v1/cotizaciones/exportar` | Síncrono, **`dry_run=true` por defecto** | **Escritura en Odoo** (O3) | Agente, con confirmación | 3 |
| `POST /v1/cotizaciones/{referencia}/partidas` | Síncrono, **`dry_run=true` por defecto** | **Escritura en Odoo** (O4) | Agente, con confirmación | 3 |

**`dry_run`:** el bridge hace todas las validaciones y resoluciones, y devuelve exactamente lo que crearía (cabecera, número de líneas, totales y qué no incluye), sin escribir. Cumple las reglas de *preflight* del proyecto (R-01 a R-04). La escritura real exige `dry_run=false` **y** el `token_preflight` devuelto por la simulación, para que no se escriba algo distinto a lo que se mostró.

---

## 5. Síncrono vs. asíncrono

### Regla

| Tipo | Criterio | Ejemplos |
|---|---|---|
| **Síncrono** | Termina en pocos segundos (objetivo < 10 s, tope 30 s) y devuelve el resultado completo | Consulta de producto, resolvedor, *preflight* y exportación de una cotización |
| **Asíncrono** | Puede tardar minutos u horas, o procesa más de un lote | Carga inicial, sincronización nocturna, recargas masivas |

n8n **nunca espera** un trabajo asíncrono con una petición abierta. Esto evita los cortes por tiempo y que n8n acumule miles de registros en el historial de cada ejecución.

### ¿Quién dispara la sincronización nocturna?

| Opción | A favor | En contra |
|---|---|---|
| **A. Programador propio del bridge** (recomendada) | No depende de que n8n esté arriba. Más simple de operar. La carga corre aunque el agente esté en mantenimiento. | El horario se configura en el bridge, no en n8n |
| B. n8n lo lanza (Schedule Trigger → `POST /v1/sync/...`) y consulta `GET /v1/jobs/{id}` | El horario se ve en n8n junto al resto de flujos | Dos piezas deben estar sanas para que ocurra; requiere un ciclo de consulta en n8n |

**Recomendación:** opción A para lo programado, y además exponer `POST /v1/sync/...` para que el agente (o una persona desde n8n) pueda lanzar una sincronización bajo demanda y consultar su estado. Al terminar, el bridge puede **avisar** a un webhook de n8n con el resumen, en lugar de que n8n pregunte.

### Diseño de los trabajos de sincronización

- **Lotes de máx. 2,000 registros**, paginando por llave (`id > último_id`, orden por `id`), no por `offset`. Así una edición concurrente en Odoo no provoca registros saltados ni duplicados.
- **Incremental por `write_date`:** cada entidad guarda su marca de última sincronización exitosa en la tabla de control. La carga inicial es la misma operación con la marca vacía.
- **Punto de control por lote:** si el trabajo falla en el lote 18 de 35 (≈ 70,000 registros), se reanuda en el 18.
- **Escritura idempotente en la DB Buffer:** `INSERT … ON DUPLICATE KEY UPDATE` por id de Odoo, una transacción por lote.
- **Candado por entidad:** no pueden correr dos sincronizaciones de la misma entidad a la vez.
- **Bajas:** los registros archivados en Odoo (`active = false`) se sincronizan como inactivos, no se borran de la DB Buffer.

### Cola de trabajos

Para el volumen previsto basta una cola sencilla persistida en la DB Buffer (tabla `bridge_jobs`) y un worker dentro del mismo contenedor. No se necesita Celery ni Redis en la primera versión. Si más adelante hay varios workers, se reevalúa.

---

## 6. Escritura en Odoo con JSON-2: transacciones

### Lo que confirma la documentación oficial [R2]

- **Cada llamada a JSON-2 corre en su propia transacción SQL:** se confirma si tiene éxito y se descarta si hay error.
- **No es posible encadenar varias llamadas dentro de una misma transacción.** Entre una llamada y la siguiente, otros usuarios pueden modificar la base.
- La solución que propone Odoo es **llamar a un solo método que haga todas las operaciones relacionadas**, de modo que se haga todo o nada. Si no existe tal método, se puede crear uno en un módulo propio.
- Todos los argumentos van **nombrados** en el cuerpo JSON (`ids`, `context` y los parámetros del método); no hay argumentos posicionales.
- La API aplica los permisos, reglas de registro y accesos a campos del usuario dueño de la API key.

### Cómo se aplica a cabecera + líneas

Odoo permite crear la cabecera **y** sus líneas en una sola llamada a `create`, usando los *comandos* de los campos uno-a-muchos [R3]. Un solo `create` es una sola transacción:

```json
POST /json/2/sale.order/create
{
  "vals_list": [{
    "partner_id": 42,
    "client_order_ref": "<referencia>",
    "order_line": [
      [0, 0, {"display_type": "line_section", "name": "Cableado estructurado", "sequence": 10}],
      [0, 0, {"product_id": 101, "product_uom_qty": 3, "price_unit": 2890.0, "sequence": 20}],
      [0, 0, {"product_id": 102, "product_uom_qty": 1, "price_unit": 1190.0, "sequence": 30}]
    ]
  }]
}
```

| Comando | Forma | Uso en el bridge |
|---|---|---|
| CREATE | `[0, 0, {valores}]` | Crear líneas nuevas (O3 y O4) |
| UPDATE | `[1, id, {valores}]` | Actualizar una línea existente (O4) |
| DELETE | `[2, id, 0]` | No previsto en la primera versión |

Para la **inyección incremental** (O4), un solo `write` sobre `sale.order` con una mezcla de comandos `[1, …]` y `[0, …]` también es atómico.

Se respetan las restricciones ya conocidas del proyecto: secciones con `display_type = 'line_section'`, `sequence` de diez en diez, impuestos en `tax_ids` (cuidando no arrastrar los de todas las compañías), y creación siempre en borrador.

### Lo que sigue sin ser atómico, y cómo se maneja

Una exportación completa implica varios pasos que **no** caben en una sola llamada:

```
1. Leer la cotización de la DB Buffer
2. Resolver ids en Odoo (cliente, productos, unidad, impuestos)      ← lecturas
3. Crear sale.order con todas sus líneas                            ← UNA escritura atómica
4. Leer el folio que asignó Odoo (S000xx)                           ← lectura
5. Marcar en la DB Buffer: exportada, id y folio de Odoo             ← escritura en MySQL
```

| Riesgo | Mitigación |
|---|---|
| Entre el paso 2 y el 3 alguien archiva un producto | El `create` falla completo (rollback) y el bridge reporta qué producto falló. No queda nada a medias en Odoo. |
| El paso 3 se ejecutó, pero la respuesta se perdió (corte de red) y n8n reintenta | **Idempotencia:** antes de crear, el bridge busca si ya existe una cotización con la referencia de la DB Buffer. Si existe, la devuelve en lugar de crear otra. ❓ Falta decidir **qué campo** guarda esa referencia (ver §13). |
| El paso 3 tuvo éxito pero el 5 falló | La tabla de auditoría registra la operación como "creada en Odoo, pendiente de marcar". Un proceso de conciliación la completa usando la misma búsqueda por referencia. |

**Opción futura (solo con servidor propio):** si una operación necesitara atomicidad entre varios modelos de Odoo, se puede crear un módulo con un método dedicado (por ejemplo, `x_bridge_exportar_cotizacion`), como recomienda Odoo. Requiere instalar código en el Odoo de BBINCO y no es posible en Odoo Online. **No se propone para la primera versión.**

---

## 7. Qué registra el bridge y qué se activa en Odoo

### 7.1 Lo que registra el bridge

| Registro | Dónde | Contenido |
|---|---|---|
| `bridge_jobs` | DB Buffer | Trabajos asíncronos: tipo, estado, avance por lote, punto de control, errores, inicio y fin |
| `bridge_sync_state` | DB Buffer | Por entidad: marca `write_date` de la última sincronización exitosa |
| `bridge_audit` | DB Buffer | **Cada escritura en Odoo**: quién la pidió (consumidor), cuándo, entorno, operación, referencia de la DB Buffer, *hash* del contenido, id y folio resultantes, resultado y error |
| Logs | Salida estándar del contenedor (JSON) | Cada petición: endpoint, duración, código de respuesta, `job_id` o `request_id` |

**Nunca se registran** API keys, contraseñas ni el cuerpo completo de datos de clientes en los logs. El detalle de negocio queda solo en las tablas de la DB Buffer, que ya lo contienen.

### 7.2 ❓ Lo que se activa en Odoo cuando el bridge escribe

Este es el punto ciego principal. Al crear una `sale.order` pueden dispararse, entre otros:

- **Secuencias:** Odoo asigna el folio (regla R-07: el folio lo emite Odoo).
- **Acciones automatizadas** de Studio o de módulos (`base.automation`): por ejemplo, notificar a un vendedor, cambiar etapa o llenar campos.
- **Acciones de servidor** (`ir.actions.server`) y **tareas programadas** (`ir.cron`) que actúan sobre cotizaciones.
- **Seguidores y notificaciones** del chatter (correos internos o al cliente).
- **Cálculos automáticos:** lista de precios, impuestos por posición fiscal, descuentos, márgenes.
- **Campos obligatorios de Studio** que hagan fallar el `create` si no se envían.
- **Validaciones o aprobaciones** personalizadas.

Antes de diseñar el detalle de O3 y O4 hay que **inventariarlas**. Dos vías complementarias:

1. **Preguntar a BBINCO** (cuestionario en §13).
2. **Revisarlo técnicamente** en el servidor de pruebas de BBINCO, leyendo con un usuario administrador los modelos `base.automation`, `ir.actions.server`, `ir.cron` y `mail.template` filtrados por `sale.order`, `sale.order.line` y `res.partner`, y los campos obligatorios con `fields_get`. La sonda puede extenderse para hacerlo en solo lectura.

Con esa información se decide, por cada automatización, si el bridge la deja actuar, la evita (por ejemplo, con claves de contexto como `mail_create_nosubscribe`, si BBINCO está de acuerdo) o la replica en su lógica.

---

## 8. Seguridad y autenticación

### 8.1 n8n → bridge

| Medida | Detalle |
|---|---|
| **Sin exposición a internet** | El bridge corre en la misma red Docker que n8n y **no publica puertos**. n8n lo alcanza por nombre de servicio (`http://odoo-bridge:8000`). Si se necesita acceso desde el host, solo en `127.0.0.1`. |
| **API key obligatoria** | Encabezado `X-API-Key` en todas las rutas excepto `/health`. En n8n se guarda como credencial *Header Auth*, nunca escrita en el flujo. |
| **Llaves por consumidor y alcance** | Una llave de **lectura** (consultas, resolvedor, estado de trabajos) y otra de **escritura** (exportar cotización, lanzar sincronización). Si la llave del agente se filtrara, no podría escribir en Odoo. |
| **Comparación segura y rotación** | Comparación en tiempo constante; las llaves se pueden rotar sin reconstruir la imagen (variables de entorno o *Docker secrets*). |
| **Si n8n y el bridge quedan en hosts distintos** | Proxy inverso con HTTPS y lista de IPs permitidas, además de la API key. |
| **Límite de peticiones** | Tope por llave para que un ciclo del agente no sature Odoo. |

### 8.2 Bridge → Odoo

| Medida | Detalle |
|---|---|
| **Usuarios bot dedicados** | Odoo recomienda usuarios bot con permisos mínimos para integraciones automatizadas [R2]: uno de **solo lectura** y otro con permisos limitados a **Ventas** para O3/O4. Así Odoo mismo bloquea lo que el bridge no deba hacer. |
| **Caducidad de API keys** | Odoo no permite llaves de más de **tres meses** [R2]. El bridge debe conocer la fecha de expiración, reportarla en `/ready` y alertar con anticipación. Se documenta un procedimiento de rotación. |
| **Llave solo donde se necesita** | El encabezado `Authorization` se envía únicamente en las rutas `/json/2/…`. Los endpoints públicos, como `/web/version`, se llaman sin API key ni `X-Odoo-Database`. |
| **Solo HTTPS** | Contra producción y BBINCO. Contra el servidor de Cognitive, por túnel SSH mientras siga en HTTP. |
| **Un perfil por entorno** | Las llaves y URL de pruebas nunca se mezclan con las de producción; el entorno activo aparece en cada respuesta y en la auditoría. |

### 8.3 Bridge → DB Buffer

Usuario MySQL propio del bridge con permisos solo sobre las tablas que lee y escribe (no `DROP`, no `GRANT`).

---

## 9. Despliegue y operación

### 9.1 ❓ Dónde se aloja

| Opción | A favor | En contra |
|---|---|---|
| **Junto a n8n, en el mismo `docker compose`** (recomendada) | Red interna sin exposición; un solo lugar que operar; latencia mínima | Depende de dónde viva n8n en producción |
| En la infraestructura de BBINCO, junto a su Odoo | Cercanía a Odoo; los datos no salen de BBINCO | Requiere acceso y acuerdos de operación con su TI; n8n tendría que alcanzarlo por red |
| VPS de Cognitive separado | Control total | Un servidor más que mantener; exige HTTPS y filtrado entre hosts |

La decisión depende de **dónde correrá n8n en producción**, que también está pendiente.

### 9.2 Cómo se despliega

- Imagen Docker con **etiquetas de versión** (`odoo-bridge:0.3.1`), nunca solo `latest`.
- `docker compose` con un archivo de variables por entorno: `cognitive-pruebas`, `bbinco-pruebas`, `produccion`.
- Migraciones de las tablas de control (`bridge_*`) versionadas junto al código.
- Promoción por etapas: estable contra Cognitive → validado contra pruebas de BBINCO → producción, igual que el plan general del proyecto.

### 9.3 Cómo se monitorea

| Mecanismo | Qué detecta |
|---|---|
| `HEALTHCHECK` de Docker sobre `/health` | Proceso caído o colgado (Docker lo reinicia) |
| `/ready` | Odoo o DB Buffer inalcanzables, API key por expirar, versión de Odoo distinta a la esperada |
| Estado de trabajos en `bridge_jobs` | Sincronización nocturna fallida o incompleta |
| Aviso al terminar cada trabajo nocturno (webhook a n8n → correo o mensaje) | Que el equipo se entere sin revisar logs |
| Logs JSON del contenedor | Diagnóstico de errores y tiempos |

El bridge es **sin estado** en memoria: todo su estado vive en la DB Buffer, así que reiniciarlo o reemplazarlo no pierde nada (los trabajos se reanudan desde su punto de control).

---

## 10. Integración con el agente en n8n

| Necesidad | Cómo en n8n |
|---|---|
| El agente consulta o resuelve | Herramientas del *AI Agent* con **HTTP Request Tool** apuntando al bridge, con descripciones claras para el modelo |
| El agente exporta una cotización | Herramienta en **dos pasos**: `preflight` (dry-run) → el resumen se muestra a una persona → solo con su confirmación se llama con `dry_run=false` y el `token_preflight` |
| Sincronización nocturna | La ejecuta el programador del bridge; n8n solo recibe el aviso final |
| Sincronización bajo demanda | `POST /v1/sync/...` y consulta con `GET /v1/jobs/{id}` |
| Credenciales | Credencial *Header Auth* de n8n con la API key del bridge; una por alcance |

Herramientas propuestas para el agente:

| Herramienta | Endpoint | Escribe |
|---|---|---|
| `buscar_producto` | `GET /v1/productos/{codigo}`, `POST /v1/productos/buscar` | No |
| `resolver_modelos` | `POST /v1/resolver` | No |
| `consultar_odoo` | `POST /v1/consultas` (lista blanca) | No |
| `consultar_cotizacion` | `GET /v1/cotizaciones/{referencia}` | No |
| `previsualizar_exportacion` | `POST /v1/cotizaciones/exportar` (`dry_run=true`) | No |
| `exportar_cotizacion` | `POST /v1/cotizaciones/exportar` (`dry_run=false`) | **Sí**, solo tras confirmación humana |
| `estado_sincronizacion` | `GET /v1/jobs/{id}` | No |

El agente decide **cuándo** y **qué**; el **cómo** queda en código determinista, probado y auditado.

---

## 11. Restricciones de n8n que refuerzan el diseño

Observaciones de Andrea, verificadas contra la documentación oficial de n8n:

| Observación | Confirmación | Fuente |
|---|---|---|
| El nodo **Execute Command** viene desactivado por defecto desde n8n 2.0 | Confirmado: n8n 2.0 desactiva por defecto Execute Command y Local File Trigger por riesgo de seguridad; se reactivan quitándolos de la variable `NODES_EXCLUDE` | [R4] |
| Python en el nodo **Code** bloquea la biblioteca estándar y paquetes externos | Confirmado: `N8N_RUNNERS_STDLIB_ALLOW` y `N8N_RUNNERS_EXTERNAL_ALLOW` vienen vacías (todo bloqueado); los paquetes externos deben estar **instalados en la imagen `n8nio/runners`** | [R5] |
| Se bloquean `open`, `exec`, `eval` y el acceso a variables de entorno | Confirmado: la lista por defecto de `N8N_RUNNERS_BUILTINS_DENY` incluye `eval`, `exec`, `compile`, `open`, `getattr`, `type`, entre otros; `N8N_BLOCK_RUNNER_ENV_ACCESS` es `true` por defecto | [R5] |
| El resolvedor con `rapidfuzz` no se puede pegar tal cual en un nodo Code | Consecuencia directa de lo anterior: requeriría permitir el paquete y reconstruir la imagen de runners | [R5] |
| Cada tarea del nodo Code tiene un límite de 300 s | Confirmado: `N8N_RUNNERS_TASK_TIMEOUT` = 300 s por defecto; al excederlo, el runner detiene la tarea y se reinicia | [R5] |

Dato adicional: el modo `internal` de los task runners está marcado como obsoleto y se eliminará en una versión futura [R5], así que cualquier configuración de runners debería planearse en modo `external`.

❓ **Por verificar:** la versión exacta de n8n que corre en el entorno del proyecto (`n8n --version` o la pantalla *Acerca de*). Las conclusiones aplican a n8n 2.x.

**Conclusiones de diseño:**

1. **No reactivar Execute Command.** No hace falta: n8n llama al bridge por HTTP.
2. **El resolvedor vive en el bridge** como endpoint (`POST /v1/resolver`), con `rapidfuzz` instalado normalmente en su imagen.
3. **Ningún ciclo largo vive en un nodo Code.** La carga de ≈ 70,000 líneas por lotes es un trabajo asíncrono del bridge.
4. Los nodos Code quedan, si acaso, para transformaciones ligeras en JavaScript (dar formato a una respuesta para el agente).

---

## 12. Plan de trabajo

| Fase | Contenido | Entregable | Toca Odoo |
|---|---|---|---|
| **0. Prerrequisitos** | Usuario bot de solo lectura y su API key en cada servidor de pruebas; ejecutar la sonda; catálogo cargado en el servidor de Cognitive | Reporte de la sonda por entorno | Lectura |
| **0.5 Sonda JSON-2** ✅ | Script de solo lectura que demuestra la comunicación (versión, usuario, campos disponibles, productos) | `odoo-json2-probe` | Lectura |
| **1. Lectura** | Cliente JSON-2, perfiles de entorno, `/health`, `/ready`, productos, consultas en lista blanca, autenticación por API key | Bridge v0.1 | Lectura |
| **1.5 Prueba de humo en n8n** | Flujo manual → HTTP Request → bridge; primera herramienta del agente | Flujo de n8n | Lectura |
| **2. Sincronización y resolvedor** | Trabajos asíncronos, tablas de control, programador, incremental por `write_date`, resolvedor | Bridge v0.2 | Lectura |
| **3. Escritura** | *Preflight*, exportación de cotización, inyección de partidas, idempotencia, auditoría, bot de escritura | Bridge v0.3 | **Escritura, solo en pruebas** |
| **4. Integración completa** | Herramientas del agente, confirmación humana, avisos, monitoreo | Flujos de n8n | — |
| **5. Producción** | Ensayos en vivo con BBINCO | — | Escritura en producción |

**Bloqueos:** la fase 3 no inicia sin las respuestas de §7.2 y §13 sobre automatizaciones y campo de idempotencia. La fase 5 no inicia sin la confirmación del tipo de alojamiento de producción.

---

## 13. Decisiones y preguntas pendientes

### Para Andrea / Cognitive

| # | Pregunta | Afecta a |
|---|---|---|
| D1 | ¿Dónde correrá n8n en producción? (Define dónde se aloja el bridge.) | §9 |
| D2 | ¿Qué versión de n8n usa el proyecto? | §11 |
| D3 | ¿Disparador de la sincronización nocturna: programador del bridge (recomendado) o n8n? | §5 |
| D4 | ¿Cola de trabajos en la DB Buffer (recomendado) o infraestructura dedicada (Redis)? | §5 |
| D5 | ¿Aprobación del flujo de dos pasos (preflight + confirmación humana) para escribir en Odoo? | §4, §10 |

### Para BBINCO

| # | Pregunta | Afecta a |
|---|---|---|
| B1 | ¿Su Odoo de producción está en servidor propio, Odoo.sh u Odoo Online? ¿Qué plan? | Viabilidad de la API y de módulos propios |
| B2 | ¿Qué modelos debe **leer** el agente y cuáles **escribir**? | Lista blanca (§4) y permisos de los bots |
| B3 | ¿Qué acciones automatizadas, notificaciones, secuencias o aprobaciones se disparan al crear o modificar una cotización? ¿Alguna debe evitarse cuando escribe el agente? | §7.2 |
| B4 | ¿Qué campos obligatorios (incluidos los de Studio) tiene una cotización? | §6 |
| B5 | ¿Qué campo puede guardar la referencia de la DB Buffer para idempotencia? (`client_order_ref` puede estar en uso para la orden de compra del cliente; alternativa: un campo de Studio dedicado) | §6 |
| B6 | ¿Aceptan crear dos usuarios bot (lectura y ventas) con API keys rotadas cada tres meses? ¿Quién las rota? | §8.2 |
| B7 | ¿Lista de precios, compañía y política de impuestos que deben usar las cotizaciones creadas por el agente? | §6 |
| B8 | ¿Horario permitido para cargas masivas y algún límite de peticiones a respetar? | §5 |

---

## 14. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Automatizaciones desconocidas en Odoo al escribir | Correos al cliente, datos inconsistentes | Inventario previo (§7.2); escritura solo en pruebas hasta validar |
| Expiración de API keys (máx. 3 meses) | El bridge deja de funcionar sin aviso | `/ready` reporta la fecha; alerta anticipada; procedimiento de rotación |
| Diferencias entre servidores (Community vs. Enterprise con Studio) | Algo que funciona en pruebas de Cognitive falla en BBINCO | Perfiles de entorno; detección de campos con `fields_get`; validar en pruebas de BBINCO antes de producción |
| Obsolescencia de APIs | Integraciones rotas al actualizar Odoo | Solo JSON-2. Odoo programa la eliminación de los servicios de objetos de XML-RPC/JSON-RPC para Odoo 22 (otoño de 2028) [R1] |
| El esquema de la DB Buffer sigue cambiando (Rev 3) | Retrabajo en el mapeo | Capa de mapeo aislada; empezar por productos |
| El bridge es un servicio más que operar | Carga operativa | Contenedor sin estado, healthchecks, avisos automáticos, despliegue con compose |

---

## 15. Referencias

- **[R1]** Odoo — *External RPC API* (obsolescencia de XML-RPC/JSON-RPC, calendario de eliminación y planes con acceso a la API). https://www.odoo.com/documentation/saas-19.4/developer/reference/external_rpc_api.html
- **[R2]** Odoo 19 — *External JSON-2 API* (formato de petición, API keys, usuarios bot, transacciones). https://www.odoo.com/documentation/19.0/developer/reference/external_api.html
- **[R3]** Odoo 19 — *ORM API*, clase `Command` y `create(vals_list)`. https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
- **[R4]** n8n — *v2.0 breaking changes*. https://docs.n8n.io/2-0-breaking-changes
- **[R5]** n8n — *Task runners environment variables*. https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/task-runners
- Documentos del proyecto: `01_SPEC_Captura_Levantamiento.md` (reglas R-01 a R-11, escritura e inyección incremental), `05_Catalogo_Reglas_Negocio.md` (restricciones técnicas de Odoo 19), `Cognitive_Del_Levantamiento_a_la_Cotizacion.md`.

> Nota: la página de Odoo 19.0 sobre JSON-2 menciona la eliminación de XML-RPC/JSON-RPC en "Odoo 20", mientras que la documentación más reciente (saas-19.4) precisa que en Odoo 20 se eliminó el servicio `db` y que los servicios de objetos se eliminarán en Odoo 22. En cualquier caso, la conclusión es la misma: construir sobre JSON-2.
