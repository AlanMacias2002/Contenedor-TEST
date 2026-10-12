"""Contrato del bridge: esquemas de entrada y salida.

Estos modelos son el contrato entre el agente (n8n) y el bridge. El bridge real
reutilizará estos mismos esquemas, así que el esqueleto y el bridge responden igual.

Regla de estabilidad
--------------------
* Los campos declarados aquí forman el NÚCLEO ESTABLE. Cambiar o quitar uno es un
  cambio de contrato (sube la versión y se avisa).
* Los datos que todavía pueden cambiar (sobre todo los que vienen de Odoo) viajan
  en el objeto ``extras``. El agente puede leerlos, pero no debe depender de ellos.
* Agregar un campo nuevo opcional no rompe a nadie.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Envoltura común
# ---------------------------------------------------------------------------

class Respuesta(BaseModel, Generic[T]):
    """Toda respuesta exitosa llega dentro de esta envoltura."""
    ok: bool = True
    modo: Literal["mock", "real"] = Field(description="'mock' = datos de ejemplo del esqueleto")
    contrato: str = Field(description="Versión del contrato de la API")
    request_id: str
    data: T
    avisos: list[str] = Field(default_factory=list, description="Mensajes para el agente que no son errores")


class ErrorDetalle(BaseModel):
    codigo: str = Field(description="Código estable, p. ej. PRODUCTO_NO_ENCONTRADO")
    mensaje: str = Field(description="Explicación legible, en español")
    detalle: Any = None


class RespuestaError(BaseModel):
    """Toda respuesta con error llega dentro de esta envoltura."""
    ok: bool = False
    modo: Literal["mock", "real"]
    contrato: str
    request_id: str
    error: ErrorDetalle


# ---------------------------------------------------------------------------
# Productos (núcleo estable)
# ---------------------------------------------------------------------------

class Origen(BaseModel):
    tipo: Literal["odoo", "proveedor"] = Field(description="'odoo' = inventario propio de BBINCO")
    nombre: str = Field(description="'BBINCO' o el nombre del proveedor, p. ej. 'Syscom'")


class Producto(BaseModel):
    odoo_id: Optional[int] = Field(None, description="id de product.product; null si solo existe en un proveedor")
    codigo: str = Field(description="Código oficial (default_code en Odoo o SKU del proveedor)")
    nombre: str
    marca: Optional[str] = None
    tipo: Literal["producto", "servicio"]
    precio_unitario: Optional[float] = Field(None, description="Precio de venta de lista; null si no hay dato")
    costo_unitario: Optional[float] = Field(None, description="Costo; null si no hay dato")
    moneda: Literal["MXN", "USD"] = "MXN"
    stock_disponible: Optional[float] = Field(None, description="null en servicios o si no se conoce")
    unidad: str = "Unidades"
    origen: Origen
    activo: bool = True
    actualizado: Optional[datetime] = Field(None, description="Última sincronización de este dato")
    extras: dict[str, Any] = Field(default_factory=dict, description="Campos aún no estables")


# ---------------------------------------------------------------------------
# Resolución de modelos
# ---------------------------------------------------------------------------

class ResolverEntrada(BaseModel):
    modelos: list[str] = Field(min_length=1, max_length=50, examples=[["CS-PP24-C6", "DS 2CD2143G2 I", "UTP6-305AZ"]])
    incluir_proveedores: bool = Field(True, description="Buscar también en catálogos de proveedores si no hay coincidencia en Odoo")


class Candidato(BaseModel):
    producto: Producto
    similitud: int = Field(ge=0, le=100)


EstadoResolucion = Literal["resuelto", "requiere_confirmacion", "no_encontrado"]


class ResultadoResolucion(BaseModel):
    modelo: str = Field(description="Modelo tal como lo envió el agente")
    modelo_normalizado: str
    estado: EstadoResolucion
    nivel: int = Field(ge=0, le=4, description="0 exacta · 1 normalizada · 2 sin prefijo · 3 parcial · 4 no encontrado")
    via: Literal["equivalencia", "catalogo", "ninguna"]
    aplicar_sin_confirmar: bool = Field(description="True solo en niveles 0 y 1 con un único resultado (regla R-05)")
    producto: Optional[Producto] = None
    candidatos: list[Candidato] = Field(default_factory=list)
    salidas_posibles: list[Literal["equivalente_registrado", "solicitar_alta", "sin_producto_asociado"]] = Field(default_factory=list)


class ResolverSalida(BaseModel):
    catalogo_sincronizado: datetime
    resultados: list[ResultadoResolucion]


# ---------------------------------------------------------------------------
# Búsqueda
# ---------------------------------------------------------------------------

class BuscarEntrada(BaseModel):
    texto: Optional[str] = Field(None, description="Busca en código y nombre")
    marca: Optional[str] = None
    fuente: Literal["odoo", "proveedores", "todas"] = "todas"
    solo_con_stock: bool = False
    limite: int = Field(20, ge=1, le=50)


class BuscarSalida(BaseModel):
    total: int
    productos: list[Producto] = Field(description="Primero inventario propio (Odoo) y después proveedores")


# ---------------------------------------------------------------------------
# Consultas genéricas (lista blanca)
# ---------------------------------------------------------------------------

class ConsultaEntrada(BaseModel):
    modelo: str = Field(examples=["res.partner"])
    dominio: list[Any] = Field(default_factory=list, examples=[[["name", "ilike", "hotel"]]])
    campos: list[str] = Field(default_factory=list)
    limite: int = Field(20, ge=1, le=50)


class ConsultaSalida(BaseModel):
    modelo: str
    total: int
    registros: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Equivalencias y altas
# ---------------------------------------------------------------------------

class EquivalenciaEntrada(BaseModel):
    modelo_bbinco: str
    codigo_odoo: str
    confirmado_por: str = Field(description="Persona que eligió el candidato")
    cotizacion_referencia: Optional[str] = None


class Equivalencia(EquivalenciaEntrada):
    id: int
    modelo_normalizado: str
    creada: datetime


class AltaEntrada(BaseModel):
    modelo_bbinco: str
    descripcion: str
    marca: Optional[str] = None
    solicitado_por: str
    cotizacion_referencia: Optional[str] = None


class Alta(AltaEntrada):
    id: str
    estado: Literal["solicitada", "dada_de_alta", "rechazada"]
    creada: datetime


# ---------------------------------------------------------------------------
# Cotizaciones en la DB Buffer
# ---------------------------------------------------------------------------

class Cliente(BaseModel):
    odoo_id: Optional[int] = Field(None, description="id de res.partner si ya se conoce")
    nombre: str


class PartidaEntrada(BaseModel):
    seccion: str = Field(description="Especialidad o sección, p. ej. 'Voz y datos'")
    modelo_bbinco: Optional[str] = None
    codigo_odoo: Optional[str] = Field(None, description="null = sin producto asociado; se cargará con el modelo escrito")
    descripcion: str
    cantidad: float = Field(gt=0)
    precio_unitario: Optional[float] = Field(None, ge=0, description="null bloquea la exportación (regla R-03)")
    flete: Optional[float] = Field(None, ge=0, description="Nace vacío, nunca en cero (regla ⑧)")


class Partida(PartidaEntrada):
    numero: int
    importe: Optional[float] = None


class CotizacionEntrada(BaseModel):
    cliente: Cliente
    folio_levantamiento: Optional[str] = Field(None, examples=["L000123"])
    moneda: Literal["MXN", "USD"] = "MXN"
    notas: Optional[str] = None
    partidas: list[PartidaEntrada] = Field(min_length=1, max_length=500)


EstadoCotizacion = Literal["borrador", "exportada"]


class Totales(BaseModel):
    partidas: int
    subtotal: float = Field(description="Suma de partidas con precio; sin impuestos ni flete")
    moneda: str


class Cotizacion(BaseModel):
    referencia: str = Field(description="Referencia del buffer, p. ej. BUF-000001")
    estado: EstadoCotizacion
    cliente: Cliente
    folio_levantamiento: Optional[str] = None
    moneda: str
    notas: Optional[str] = None
    partidas: list[Partida]
    totales: Totales
    odoo: Optional[dict[str, Any]] = Field(None, description="Folio e id en Odoo cuando ya se exportó")
    creada: datetime
    actualizada: datetime


class ExportarEntrada(BaseModel):
    dry_run: bool = Field(True, description="True = solo simula (preflight). La escritura real exige False + token_preflight")
    token_preflight: Optional[str] = None


class Bloqueo(BaseModel):
    partida: Optional[int] = None
    codigo: str
    mensaje: str


class Preflight(BaseModel):
    dry_run: Literal[True] = True
    listo_para_exportar: bool
    lineas_a_crear: int = Field(description="Partidas + líneas de sección (regla R-01)")
    secciones: list[str]
    subtotal: float
    moneda: str
    no_incluye: list[str] = Field(description="Lo que el total no contempla (regla R-04)")
    bloqueos: list[Bloqueo]
    token_preflight: Optional[str] = Field(None, description="Solo si listo_para_exportar")
    token_expira: Optional[datetime] = None


class ExportacionResultado(BaseModel):
    dry_run: Literal[False] = False
    referencia: str
    folio_odoo: str
    odoo_id: int
    estado_odoo: Literal["draft"] = Field("draft", description="Siempre borrador (regla R-06)")
    ya_existia: bool = Field(description="True si la cotización ya se había exportado (idempotencia)")


# ---------------------------------------------------------------------------
# Cotizaciones vivas en Odoo
# ---------------------------------------------------------------------------

class LineaOdoo(BaseModel):
    id: int
    tipo: Literal["seccion", "producto", "nota"]
    codigo: Optional[str] = None
    descripcion: str
    cantidad: Optional[float] = None
    precio_unitario: Optional[float] = None
    subtotal: Optional[float] = None
    extras: dict[str, Any] = Field(default_factory=dict)


class CotizacionOdoo(BaseModel):
    folio: str
    odoo_id: int
    estado: Literal["draft", "sent", "sale", "cancel"]
    cliente: Cliente
    referencia_buffer: Optional[str] = None
    lineas: list[LineaOdoo]
    total_sin_impuestos: float
    moneda: str
    extras: dict[str, Any] = Field(default_factory=dict)


class InyeccionEntrada(BaseModel):
    partidas: list[PartidaEntrada] = Field(min_length=1, max_length=200)
    dry_run: bool = True
    token_preflight: Optional[str] = None


class AccionInyeccion(BaseModel):
    accion: Literal["agregar", "actualizar", "solicitar_alta"]
    codigo: Optional[str]
    descripcion: str
    cantidad: float
    seccion: str


class InyeccionResultado(BaseModel):
    folio: str
    dry_run: bool
    acciones: list[AccionInyeccion]
    token_preflight: Optional[str] = None
    aplicado: bool = False


# ---------------------------------------------------------------------------
# Sincronización y trabajos
# ---------------------------------------------------------------------------

Entidad = Literal["productos", "clientes", "cotizaciones"]
EstadoJob = Literal["en_cola", "corriendo", "completado", "fallido"]


class SyncEntrada(BaseModel):
    completa: bool = Field(False, description="True = recarga todo; False = solo cambios desde la última sincronización")


class Job(BaseModel):
    job_id: str
    entidad: Entidad
    tipo: Literal["incremental", "completa"]
    estado: EstadoJob
    lote_actual: int
    lotes_totales: int
    registros_procesados: int
    registros_totales: int
    iniciado: datetime
    terminado: Optional[datetime] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Sistema
# ---------------------------------------------------------------------------

class Salud(BaseModel):
    estado: Literal["ok"] = "ok"
    version: str


class Preparacion(BaseModel):
    estado: Literal["listo", "degradado"]
    version: str
    entorno: str
    odoo: dict[str, Any]
    buffer: dict[str, Any]
    catalogo_sincronizado: datetime
