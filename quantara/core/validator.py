"""
Quantara Core — validator.py  v2.2
COMPATIBLE CON routes.py ORIGINAL:
  validate_albaran_completo(raw) devuelve:
    {
      "validos":  {"fecha": ..., "total": ..., "iva_total": ..., "base_imponible": ...},
      "fallidos": ["campo1", ...]
    }

NUEVA API (para uso futuro):
  validate_albaran(data) devuelve el dict con procesado_ok y campos_fallidos.
"""
from datetime import datetime

DELIVERY_NOTE_PROVIDERS = {'panamar', 'lassal', 'hielos'}

_FORMATOS_FECHA = [
    "%d/%m/%y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%d-%m-%y",
    "%Y-%m-%d %H:%M:%S",   # formato que devuelve normalize_albaran
]


def normalize_fecha(fecha_str: str):
    """Convierte cualquier string de fecha a datetime."""
    if not fecha_str:
        return None
    for fmt in _FORMATOS_FECHA:
        try:
            return datetime.strptime(str(fecha_str).strip(), fmt)
        except ValueError:
            continue
    return None


def validate_albaran_completo(raw: dict) -> dict:
    """
    API ORIGINAL — usada por routes.py.
    Recibe el dict crudo de DonutExtractor.
    Devuelve {"validos": {...}, "fallidos": [...]}
    """
    if not raw or not isinstance(raw, dict):
        return {"validos": {}, "fallidos": ["ocr_error"]}

    proveedor_tipo   = (raw.get("proveedor_tipo") or "").lower()
    es_delivery_note = proveedor_tipo in DELIVERY_NOTE_PROVIDERS

    # ── Parsear fecha ─────────────────────────────────────────────
    fecha_dt = normalize_fecha(raw.get("fecha"))

    # ── Campos validados ──────────────────────────────────────────
    validos = {
        "fecha":          fecha_dt,
        "total":          raw.get("total"),
        "iva_total":      raw.get("iva_total"),
        "base_imponible": raw.get("base_imponible"),
    }

    # ── Determinar fallidos ───────────────────────────────────────
    fallidos = []

    if not raw.get("numero_albaran"):
        fallidos.append("numero_albaran")

    if not validos["fecha"]:
        fallidos.append("fecha")

    if not es_delivery_note:
        if validos["total"] is None:
            fallidos.append("total")
        if validos["base_imponible"] is None:
            fallidos.append("base_imponible")
        if validos["iva_total"] is None:
            fallidos.append("iva_total")

    return {"validos": validos, "fallidos": fallidos}


# ── Nueva API (validate_albaran) ──────────────────────────────────
def validate_albaran(data: dict) -> dict:
    """
    Nueva API — devuelve el dict con procesado_ok y campos_fallidos.
    Usada por el nuevo routes.py y las queries.
    """
    proveedor_tipo   = (data.get("proveedor_tipo") or "").lower()
    es_delivery_note = proveedor_tipo in DELIVERY_NOTE_PROVIDERS

    campos_criticos    = ["numero_albaran", "fecha"]
    campos_financieros = [] if es_delivery_note else ["total"]
    campos_deseables   = [] if es_delivery_note else ["base_imponible", "iva_total"]

    fallidos = []
    for c in campos_criticos:
        if not data.get(c):
            fallidos.append(c)
    for c in campos_financieros:
        if data.get(c) is None:
            fallidos.append(c)
    for c in campos_deseables:
        if data.get(c) is None and c not in fallidos:
            fallidos.append(c)

    bloqueantes = [c for c in fallidos if c in campos_criticos + campos_financieros]
    data["procesado_ok"]    = len(bloqueantes) == 0
    data["campos_fallidos"] = fallidos
    return data