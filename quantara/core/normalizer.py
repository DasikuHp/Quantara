"""
Quantara Core — normalizer.py  v2.1
Compatible con routes.py original — exporta:
  - normalize_proveedor(nombre) → str
  - parse_linea_producto(texto) → dict
  - normalize_albaran(raw)      → dict limpio
"""
import re
from datetime import datetime

# ── Mapa de normalización de nombres de proveedor ─────────────────
_PROVEEDOR_MAP = {
    "charcuval":    "Exclusivas Charcuval",
    "jasa":         "Jasa - Joaquin Ayora Sau",
    "hortofruticola": "Serv. Hortofruticolas De Levante",
    "levante":      "Serv. Hortofruticolas De Levante",
    "divins":       "Divins Diresa",
    "diresa":       "Divins Diresa",
    "europacif":    "Coca-Cola Europacific Partners",
    "coca":         "Coca-Cola Europacific Partners",
    "cervecera":    "Cervecera Del Turia Sl (Ddi)",
    "ddi":          "Cervecera Del Turia Sl (Ddi)",
    "makro":        "Makro Distribucion Mayorista",
    "panamar":      "Panamar Bakery Group",
    "lassal":       "Lassal Cooking",
    "vacum":        "Vacum Carnes De Lujo",
    "hielos":       "Hielos Valentiae",
}


def normalize_proveedor(nombre: str) -> str:
    """
    Normaliza el nombre de un proveedor a su forma canónica.
    Requerido por routes.py original.
    """
    if not nombre:
        return "Proveedor Desconocido"
    nombre_lower = nombre.lower()
    for clave, nombre_norm in _PROVEEDOR_MAP.items():
        if clave in nombre_lower:
            return nombre_norm
    # Si no hay match, capitalizar el nombre como viene
    return nombre.strip().title()


def parse_linea_producto(texto: str) -> dict:
    """
    Intenta parsear una línea de texto OCR como línea de producto.
    Requerido por routes.py original (stub — se completa en fase productos).
    Devuelve dict con claves estándar o vacío si no reconoce el formato.
    """
    if not texto or not isinstance(texto, str):
        return {}
    texto = texto.strip()
    # Patrón básico: descripción + cantidad + precio
    m = re.search(
        r'([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-/\.]{3,40})\s+'
        r'([\d]+(?:[,\.]\d+)?)\s+'
        r'([\d]+(?:[,\.]\d+)?)',
        texto
    )
    if m:
        return {
            "descripcion":    m.group(1).strip(),
            "cantidad":       _safe_float(m.group(2)),
            "precio_unitario": _safe_float(m.group(3)),
        }
    return {}


# ── Formatos de fecha ─────────────────────────────────────────────
_FORMATOS_FECHA = [
    "%d/%m/%y",   # 04/03/26
    "%d/%m/%Y",   # 04/03/2026
    "%d.%m.%Y",   # 04.03.2026
    "%d-%m-%Y",   # 04-03-2026
    "%d-%m-%y",   # 04-03-26
]


def _parse_fecha(valor: str):
    if not valor:
        return None
    valor = str(valor).strip()
    for fmt in _FORMATOS_FECHA:
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            continue
    return None


def _safe_float(valor) -> float | None:
    if valor is None:
        return None
    try:
        return round(float(str(valor).replace(',', '.').strip()), 2)
    except (ValueError, TypeError):
        return None


def normalize_albaran(raw: dict) -> dict:
    """
    Recibe el dict crudo de DonutExtractor y devuelve un dict normalizado
    sin la clave 'validos' interna (esa la añade el validator).
    """
    if not raw or not isinstance(raw, dict):
        return _empty_result()

    numero    = str(raw.get("numero_albaran") or "").strip() or None
    proveedor = raw.get("proveedor") or "Desconocido"
    prov_tipo = raw.get("proveedor_tipo") or "generico"
    fecha_dt  = _parse_fecha(raw.get("fecha"))

    base  = _safe_float(raw.get("base_imponible"))
    iva   = _safe_float(raw.get("iva_total"))
    total = _safe_float(raw.get("total"))

    if base is not None and iva is not None and total is None:
        total = round(base + iva, 2)

    productos = raw.get("productos") or []
    if not isinstance(productos, list):
        productos = []

    campos_fallidos = raw.get("campos_fallidos") or []
    if not isinstance(campos_fallidos, list):
        campos_fallidos = []

    confianza = raw.get("confianza", "baja")

    return {
        "numero_albaran":  numero,
        "fecha":           str(fecha_dt) if fecha_dt else raw.get("fecha"),
        "proveedor":       proveedor,
        "proveedor_tipo":  prov_tipo,
        "base_imponible":  base,
        "iva_total":       iva,
        "total":           total,
        "productos":       productos,
        "confianza":       confianza,
        "campos_fallidos": campos_fallidos,
        "procesado_ok":    False,
    }


def _empty_result() -> dict:
    return {
        "numero_albaran":  None,
        "fecha":           None,
        "proveedor":       "Desconocido",
        "proveedor_tipo":  "generico",
        "base_imponible":  None,
        "iva_total":       None,
        "total":           None,
        "productos":       [],
        "confianza":       "baja",
        "campos_fallidos": ["ocr_error"],
        "procesado_ok":    False,
    }