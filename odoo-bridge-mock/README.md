# odoo-bridge · esqueleto (mock)

Versión simulada del servicio `odoo-bridge`. Expone **todos los endpoints del contrato** con respuestas en su forma final y datos de ejemplo, para que el agente de n8n se construya **en paralelo** al bridge real. Cuando el bridge real esté listo, se reemplaza la imagen y los flujos de n8n no cambian.

- El contrato (envoltura, llaves, endpoints, errores, estabilidad) está en **[CONTRATO.md](CONTRATO.md)**.
- Los ejemplos reales de cada petición y respuesta están en **[docs/ejemplos.md](docs/ejemplos.md)**.
- La guía para construir los flujos, con la configuración de cada nodo de n8n y nodos listos para pegar, está en **[docs/guia_n8n.md](docs/guia_n8n.md)**.
- La especificación OpenAPI está en **[docs/openapi.json](docs/openapi.json)**, y la versión interactiva en `/docs`.

> Todas las respuestas llevan `"modo": "mock"`. Los datos son de ejemplo, no de BBINCO, y lo creado vive en memoria: se pierde al reiniciar.

---

## 1. Despliegue junto al n8n del agente (servidor de Cognitive)

El bridge **no se publica a internet**. Se conecta a la misma red Docker que n8n, y n8n lo llama por su nombre de servicio: `http://odoo-bridge:8000`.

### 1.1 Averiguar la red Docker de n8n

En el servidor donde corre n8n:

```bash
docker ps --format "table {{.Names}}\t{{.Image}}"            # identifica el contenedor de n8n
docker inspect <contenedor_n8n> --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{println}}{{end}}'
```

🟢 La salida no es sensible: son nombres de contenedores y redes.

### 1.2 Configurar

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # ejecútalo 3 veces, una por llave
```

En `.env`:

- `BRIDGE_KEY_LECTURA`, `BRIDGE_KEY_BUFFER`, `BRIDGE_KEY_ODOO`: las tres llaves, distintas entre sí. 🔴 Compártelas con tu compañero por un canal privado, nunca en el repositorio ni en el chat del equipo.
- `BRIDGE_RED`: el nombre de la red del paso 1.1.

### 1.3 Levantar

```bash
docker compose up -d --build
docker compose ps                     # debe quedar "healthy" en unos segundos
docker compose logs -f odoo-bridge    # Ctrl+C para salir
```

### 1.4 Verificar desde el contenedor de n8n

```bash
docker exec <contenedor_n8n> wget -qO- http://odoo-bridge:8000/health
```

Debe responder `{"ok":true,"modo":"mock",...}`. Si dice que no resuelve el nombre, los contenedores no están en la misma red: revisa `BRIDGE_RED`.

### 1.5 Ver la documentación interactiva (`/docs`)

Como el bridge no publica puertos, para ver `/docs` desde tu navegador hay dos opciones:

- **Túnel SSH hasta la IP interna del contenedor:**

  ```bash
  docker inspect odoo-bridge --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'   # 🟢
  ssh -N -L 8000:<IP_interna>:8000 <usuario>@<IP_PUBLICA_SERVIDOR>                               # 🔴 no compartir
  ```

  Después abre `http://localhost:8000/docs`.

- **Sin tocar el servidor:** importa `docs/openapi.json` en Postman o Insomnia, o lee `docs/ejemplos.md`.

---

## 2. Configuración en n8n

### Credenciales

Crea tres credenciales de tipo **Header Auth**:

| Nombre sugerido | Name | Value |
|---|---|---|
| `odoo-bridge · lectura` | `X-API-Key` | llave de lectura 🔴 |
| `odoo-bridge · buffer` | `X-API-Key` | llave de buffer 🔴 |
| `odoo-bridge · odoo` | `X-API-Key` | llave de odoo 🔴 (solo para la herramienta de exportar) |

### Nodo HTTP Request / HTTP Request Tool

| Campo | Valor |
|---|---|
| URL | `http://odoo-bridge:8000/v1/...` |
| Authentication | *Generic Credential Type → Header Auth* → la credencial del nivel necesario |
| Body | JSON |
| Options → Response → **Never Error** | Activado. Así las respuestas 4xx y 5xx llegan al flujo con su envoltura `{"ok": false, "error": {...}}` y puedes ramificar por `{{ $json.ok }}` y `{{ $json.error.codigo }}`. |
| Options → Timeout | 30000 ms |

Opcional: envía `X-Request-ID: {{ $execution.id }}` para rastrear la ejecución de n8n en los logs del bridge.

### Flujo de prueba de humo

`n8n/prueba_humo.json` es un ejemplo: *Inicio manual → GET /ready → POST /v1/resolver → un ítem por modelo*. En n8n: **Workflows → Import from File**. Luego asigna la credencial `odoo-bridge · lectura` a los dos nodos HTTP y ejecútalo. Deberías obtener tres ítems: uno resuelto, uno que requiere confirmación y uno no encontrado.

---

## 3. Desarrollo local

```bash
python -m venv .venv
.venv\Scripts\activate                 # Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt

# Llaves de prueba en la sesión (CMD); en Linux/Mac usa export
set BRIDGE_KEY_LECTURA=dev-lectura-123
set BRIDGE_KEY_BUFFER=dev-buffer-123
set BRIDGE_KEY_ODOO=dev-odoo-123

uvicorn app.main:app_factory --factory --reload --port 8000
```

Abre `http://localhost:8000/docs`, presiona **Authorize**, pega una llave y usa *Try it out* en cualquier endpoint. También desde curl:

```bash
curl -s -X POST http://localhost:8000/v1/resolver -H "X-API-Key: dev-lectura-123" -H "Content-Type: application/json" -d "{\"modelos\": [\"DS 2CD2143G2 I\"]}"
```

Con Docker y el puerto publicado solo en tu máquina:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

En ese caso, crea antes la red si no existe: `docker network create bbinco-net`.

### Pruebas

```bash
python -m pytest -q tests
```

28 pruebas cubren cada endpoint, los tres niveles de llave, los escenarios simulados, el flujo de exportación en dos pasos (token, expiración, idempotencia) y la sincronización asíncrona.

### Regenerar la documentación

Después de cambiar el contrato:

```bash
python scripts/generar_docs.py      # actualiza docs/openapi.json y docs/ejemplos.md
python scripts/generar_guia_n8n.py  # actualiza docs/guia_n8n.md
```

---

## 4. Estructura

```
app/
  main.py               aplicación, manejo de errores, encabezados
  config.py             variables de entorno y versión del contrato
  esquemas.py           ★ el contrato: todos los modelos de entrada y salida
  nucleo.py             envoltura, autenticación por niveles, escenarios
  seguridad.py          dependencia de acceso (llave + escenario)
  rutas_sistema.py      /health, /ready, /v1/escenarios, /v1/sync, /v1/jobs
  rutas_productos.py    productos, resolver, consultas, equivalencias, altas
  rutas_cotizaciones.py cotizaciones en buffer, exportación y cotizaciones de Odoo
  datos_ejemplo.py      catálogo y registros de ejemplo
  estado.py             estado en memoria
tests/                  pruebas
scripts/generar_docs.py genera docs/ a partir del esqueleto
n8n/prueba_humo.json    flujo de ejemplo para importar en n8n
```

## 5. Del esqueleto al bridge real

`esquemas.py` y la envoltura de `nucleo.py` **se conservan tal cual** en el bridge real: son el contrato. Lo que se reemplaza es el interior de cada ruta, los datos de ejemplo por consultas a Odoo (JSON-2) y a la DB Buffer (MySQL), y el estado en memoria por las tablas `bridge_*`. Cada endpoint puede pasar de simulado a real de forma independiente; mientras convivan, conviene marcar en `avisos` cuáles ya son reales.
