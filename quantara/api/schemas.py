from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict

# Módulo Schemas
# Responsabilidad: Definición de modelos Pydantic v2 para validación de entrada/salida de la API

class ProductoSchema(BaseModel):
    descripcion: Optional[str] = None
    cantidad: Optional[float] = None
    unidad: Optional[str] = None
    precio_unitario: Optional[float] = None
    iva_pct: Optional[float] = None
    total_linea: Optional[float] = None

class AlbaranSchema(BaseModel):
    numero_albaran: Optional[str] = None
    fecha: Optional[str] = None
    proveedor: Optional[str] = None
    productos: List[ProductoSchema] = []
    base_imponible: Optional[float] = None
    iva_total: Optional[float] = None
    total: Optional[float] = None
    procesado_ok: bool = False
    campos_fallidos: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class FeedbackSchema(BaseModel):
    albaran_id: int
    campo: str
    valor_ocr: str
    valor_correcto: str

class ResponseSchema(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
