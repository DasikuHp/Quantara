"""
Quantara OCR â€” donut_model.py  v3.0
Bugs corregidos respecto v2:
  - _normalize_date(): convierte cualquier formato a dd/mm/yy que entiende normalizer.py
  - DDI fecha: regex sin \\b (fallaba con "vto04.03.2026")
  - DDI base/IVA: restringido al bloque resumen tras "lmp.Bruto" (evita capturar EAN barcodes)
  - Levante total: anclado a "OBSERVACIONES" en vez de "TOTAL ALBARAN"
  - Panamar/Lassal: no tienen importes (delivery notes) â€” no usar fallback global
"""
import re

from quantara.config import (
    OCR_LANG, OCR_USE_ANGLE_CLS, OCR_ENABLE_MKLDNN, OCR_DROP_SCORE,
)

# numpy se importa de forma perezosa dentro de extract(): así el parser
# (_parse y helpers, Python puro) puede importarse y testearse sin numpy ni
# PaddleOCR — base del harness de evaluación offline.

# ─────────────────────────────────────────────────────────────────────
# SINGLETON DEL MOTOR OCR
# El modelo PaddleOCR (det + rec + cls) se carga UNA sola vez por proceso.
# Antes se reinstanciaba en cada /upload, recargando los pesos desde disco
# en cada petición — el mayor desperdicio de cómputo del sistema.
# ─────────────────────────────────────────────────────────────────────
_OCR_SINGLETON = None


def get_ocr():
    global _OCR_SINGLETON
    if _OCR_SINGLETON is None:
        from paddleocr import PaddleOCR
        kwargs = dict(
            use_angle_cls=OCR_USE_ANGLE_CLS,
            lang=OCR_LANG,
            show_log=False,
            drop_score=OCR_DROP_SCORE,
        )
        try:
            kwargs["enable_mkldnn"] = OCR_ENABLE_MKLDNN
        except Exception:
            pass
        try:
            _OCR_SINGLETON = PaddleOCR(**kwargs)
        except TypeError:
            # Versiones antiguas de la API no aceptan enable_mkldnn.
            kwargs.pop("enable_mkldnn", None)
            _OCR_SINGLETON = PaddleOCR(**kwargs)
    return _OCR_SINGLETON


class DonutExtractor:

    def __init__(self):
        # Reutiliza el singleton: instanciar DonutExtractor ya no carga pesos.
        self.ocr = get_ocr()

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PUNTO DE ENTRADA
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def extract(self, image):
        try:
            import numpy as np
            img_array = np.array(image)
            result = self.ocr.ocr(img_array, cls=OCR_USE_ANGLE_CLS)
            if not result or not result[0]:
                return {}
            # full_text se mantiene IDÉNTICO al original para no alterar el
            # comportamiento de los regex por proveedor ya calibrados.
            texts = [line[1][0] for line in result[0] if line[1][1] > 0.3]
            full_text = ' '.join(texts)
            words = self._words_from_result(result[0])
            r = self._parse(texts, full_text)
            # Capa aditiva basada en geometría: solo rellena lo que falló y
            # cruza base+IVA≈total para ajustar la confianza. Nunca pisa un
            # valor ya extraído por la rama del proveedor.
            self._geometric_fallback(words, r)
            self._reconcile(r)
            return r
        except Exception as e:
            return {"error": str(e), "campos_fallidos": ["ocr"]}

    # ─────────────────────────────────────────────────────────────────
    # PRODUCTOS POR LÍNEAS (sin geometría)
    # Las fixtures/PaddleOCR conservan cada línea OCR por separado. Para los
    # proveedores cuyas líneas de producto llegan en orden secuencial
    # (código → descripción → números → terminador) esto recupera productos
    # que el regex sobre texto aplanado pierde. Se desarrolla y mide offline.
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _es_num(s):
        return bool(re.match(r'^\d{1,3}(?:[.,]\d{3})*[.,]\d{2,3}$|^\d+[.,]\d{2,3}$',
                             s.strip()))

    def _productos_lineas(self, texts, pt):
        prods = []
        n = len(texts)

        if pt in ('jasa',):
            i = 0
            while i < n:
                if re.match(r'^\d{8}$', texts[i].strip()):
                    code = texts[i].strip()
                    desc = texts[i + 1].strip() if i + 1 < n else ''
                    j, nums, unidad = i + 2, [], 'ud'
                    while j < n:
                        t = texts[j].strip()
                        if t.startswith('F.C') or re.match(r'^\d{8}$', t) \
                                or t.upper().startswith('BASE') or t == 'B.I.':
                            break
                        if t.upper() in ('CAJA', 'U', 'K', 'UD', 'KG'):
                            unidad = t.lower()
                        elif self._es_num(t):
                            nums.append(t)
                        j += 1
                    if desc and nums and not self._es_num(desc):
                        prods.append({
                            "codigo": code, "descripcion": desc,
                            "cantidad": self._f(nums[0]), "unidad": unidad,
                            "precio_unitario": None,
                            "importe": self._f(nums[-1]),
                        })
                    i = j
                    continue
                i += 1

        elif pt == 'charcuval':
            i = 0
            while i < n:
                if re.match(r'^\D?\d{11,13}$', texts[i].strip()):
                    code = texts[i].strip()
                    desc = texts[i + 1].strip() if i + 1 < n else ''
                    j, nums = i + 2, []
                    while j < n:
                        t = texts[j].strip()
                        if re.match(r'^\D?\d{11,13}$', t) or t.startswith('Imp') \
                                or t.startswith('Observ'):
                            break
                        if self._es_num(t):
                            nums.append(t)
                        j += 1
                    if desc and nums and not self._es_num(desc):
                        prods.append({
                            "codigo": code, "descripcion": desc,
                            "cantidad": self._f(nums[0]), "unidad": "ud",
                            "precio_unitario": None,
                            "importe": self._f(nums[-1]),
                        })
                    i = j
                    continue
                i += 1

        elif pt == 'divins':
            # desc viene fusionada con el código: "1807 TAMBORA 3/4(6)"
            i = 0
            while i < n:
                m = re.match(r'^(\d{3,5})\s*([A-Za-zÁÉÍÓÚÑ].{3,45})$', texts[i].strip())
                if m:
                    code, desc = m.group(1), m.group(2).strip()
                    j, nums = i + 1, []
                    while j < n and not re.match(
                            r'^(\d{3,5})\s*[A-Za-z]', texts[j].strip()) \
                            and not texts[j].strip().upper().startswith('TOTAL'):
                        if self._es_num(texts[j].strip()):
                            nums.append(texts[j].strip())
                        j += 1
                    if nums:
                        prods.append({
                            "codigo": code, "descripcion": desc,
                            "cantidad": None, "unidad": "ud",
                            "precio_unitario": None,
                            "importe": self._f(nums[-1]),
                        })
                    i = j
                    continue
                i += 1

        return prods

    def parse_from_texts(self, texts):
        """
        Parsea una lista de líneas OCR (sin imagen ni geometría).
        Punto de entrada del harness de evaluación offline: replica extract()
        salvo la inferencia y el fallback geométrico (que requiere cajas).
        Construir vía DonutExtractor.__new__ para no cargar el modelo.
        """
        full_text = ' '.join(texts)
        r = self._parse(texts, full_text)
        self._reconcile(r)
        return r

    # ─────────────────────────────────────────────────────────────────
    # GEOMETRÍA: reconstrucción de filas a partir de bounding boxes
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _words_from_result(lines):
        """Convierte el resultado crudo de PaddleOCR en tokens con posición."""
        words = []
        for ln in lines:
            try:
                box, (text, conf) = ln[0], ln[1]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                words.append({
                    "text": text, "conf": float(conf),
                    "x0": min(xs), "x1": max(xs),
                    "y0": min(ys), "y1": max(ys),
                    "cx": sum(xs) / len(xs), "cy": sum(ys) / len(ys),
                    "h": max(ys) - min(ys),
                })
            except Exception:
                continue
        return words

    @staticmethod
    def _numbers_in(text):
        """Extrae importes con decimales (1.234,56 / 1234.56 / 12,34)."""
        return re.findall(r'\d{1,3}(?:[.,]\d{3})*[.,]\d{2}(?!\d)|\d+[.,]\d{2}(?!\d)',
                          text)

    def _label_amount(self, words, etiquetas, excluir=()):
        """
        Busca una etiqueta (p.ej. 'TOTAL') y devuelve el importe más cercano:
        primero a su derecha en la misma fila, si no en la fila inmediata
        inferior alineado por X. Generaliza a proveedores sin regex dedicado.
        """
        for w in words:
            t = w["text"].upper()
            if not any(e in t for e in etiquetas):
                continue
            if any(x in t for x in excluir):
                continue
            tol = max(w["h"], 6) * 0.8
            # 1) números en la propia celda de la etiqueta (ej: "TOTAL:155,19")
            here = self._numbers_in(w["text"])
            if here:
                v = self._f(here[-1])
                if v is not None:
                    return v
            # 2) misma fila, a la derecha
            fila = [o for o in words
                    if abs(o["cy"] - w["cy"]) <= tol and o["x0"] >= w["x1"] - 2]
            fila.sort(key=lambda o: o["x0"])
            for o in fila:
                nums = self._numbers_in(o["text"])
                if nums:
                    v = self._f(nums[-1])
                    if v is not None:
                        return v
            # 3) fila inmediata inferior, alineada por X con la etiqueta
            abajo = [o for o in words
                     if 0 < (o["cy"] - w["cy"]) <= tol * 3
                     and abs(o["cx"] - w["cx"]) <= max(w["x1"] - w["x0"], 60)]
            abajo.sort(key=lambda o: o["cy"])
            for o in abajo:
                nums = self._numbers_in(o["text"])
                if nums:
                    v = self._f(nums[-1])
                    if v is not None:
                        return v
        return None

    def _geometric_fallback(self, words, r):
        """Rellena SOLO campos financieros aún vacíos usando etiquetas+posición."""
        SIN_IMPORTES = {'panamar', 'lassal', 'hielos'}
        if r.get("proveedor_tipo") in SIN_IMPORTES or not words:
            return
        if r.get("total") is None:
            r["total"] = self._label_amount(
                words, ("TOTAL",),
                excluir=("BASE", "BASES", "IMPUESTO", "IVA", "PARCIAL"))
        if r.get("base_imponible") is None:
            r["base_imponible"] = self._label_amount(
                words, ("BASE IMPONIBLE", "B.IMPONIBLE", "TOTAL BASES", "BASE"),
                excluir=("RETEN",))
        if r.get("iva_total") is None:
            r["iva_total"] = self._label_amount(
                words, ("CUOTA", "TOTAL IMPUESTOS", "I.V.A", "IVA"),
                excluir=("%", "BASE"))

    def _reconcile(self, r):
        """
        Coherencia aritmética base + IVA ≈ total.
        - Si falta el total pero hay base e IVA, lo deriva.
        - Si los tres existen pero no cuadran, baja la confianza a 'media'.
        """
        b, i, t = r.get("base_imponible"), r.get("iva_total"), r.get("total")
        if t is None and b is not None and i is not None:
            r["total"] = round(b + i, 2)
            t = r["total"]
        if b is not None and i is not None and t is not None:
            esperado = round(b + i, 2)
            if abs(esperado - t) > max(0.02, 0.01 * t):
                if r.get("confianza") == "alta":
                    r["confianza"] = "media"
                if "inconsistencia_aritmetica" not in r.get("campos_fallidos", []):
                    r.setdefault("campos_fallidos", []).append(
                        "inconsistencia_aritmetica")
        # Recalcular campos financieros que el fallback acaba de rellenar.
        SIN_IMPORTES = {'panamar', 'lassal', 'hielos'}
        if r.get("proveedor_tipo") not in SIN_IMPORTES:
            r["campos_fallidos"] = [
                c for c in r.get("campos_fallidos", [])
                if c == "inconsistencia_aritmetica" or r.get(c) in (None, [], "")
            ]

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # UTILIDADES
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _f(self, s):
        """Convierte string OCR â†’ float. Maneja coma/punto, dÃ­gito espurio, â‚¬."""
        if s is None:
            return None
        try:
            s = str(s).strip()
            s = re.sub(r'[â‚¬â‚¬E\s]', '', s)
            s = s.rstrip('.')
            if not s:
                return None
            # Separadores: si hay punto Y coma, el decimal es el Ãºltimo que
            # aparece; el otro es separador de millares.
            #   '1.234,56' â†’ '1234.56'   '1,234.56' â†’ '1234.56'
            if '.' in s and ',' in s:
                if s.rfind(',') > s.rfind('.'):
                    s = s.replace('.', '').replace(',', '.')
                else:
                    s = s.replace(',', '')
            else:
                s = s.replace(',', '.')
            # Elimina dÃ­gito extra: '238.436' â†’ '238.43' (caso JASA)
            m = re.match(r'^(\d+\.\d{2})\d+$', s)
            if m:
                s = m.group(1)
            return round(float(s), 2)
        except Exception:
            return None

    def _sum(self, lista):
        vals = [self._f(v) for v in lista if self._f(v) is not None]
        return round(sum(vals), 2) if vals else None

    def _normalize_date(self, d):
        """
        Convierte CUALQUIER formato de fecha a dd/mm/yy
        para que el normalizer.py lo entienda (solo acepta 2 dÃ­gitos de aÃ±o).
          '11/02/26'     â†’ '11/02/26'   (sin cambio)
          '04/03/2026'   â†’ '04/03/26'
          '04.03.2026'   â†’ '04/03/26'
          '2/02/2026'    â†’ '02/02/26'
          '26/02/202609:45' â†’ '26/02/26'  (Makro pegado con hora)
        """
        if not d:
            return None
        d = str(d).strip()
        # dd.mm.yyyy  o  dd.mm.yy
        m = re.match(r'^(\d{1,2})\.(\d{2})\.(20)?(\d{2})', d)
        if m:
            return f"{m.group(1).zfill(2)}/{m.group(2)}/{m.group(4)}"
        # dd/mm/yyyy  o  dd/mm/yy  (posible hora pegada al final)
        m = re.match(r'^(\d{1,2})/(\d{2})/(20)?(\d{2})', d)
        if m:
            return f"{m.group(1).zfill(2)}/{m.group(2)}/{m.group(4)}"
        return d

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # DETECCIÃ“N DE PROVEEDOR
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def detect_proveedor(self, ft):
        f = ft.lower()
        if 'charcuval' in f:                                         return 'charcuval'
        if 'jasa' in f or 'joaquin ayora' in f:                      return 'jasa'
        if 'hortofruticola' in f:                                     return 'levante'
        if 'divins' in f or 'diresa' in f:                           return 'divins'
        if 'vacum' in f:                                              return 'vacum'
        if 'europacif' in f or 'coca-cola' in f or 'cocacola' in f:  return 'cocacola'
        if 'cervecera' in f or 'ddivalencia' in f or 'ddi' in f:     return 'ddi'
        if 'makro' in f:                                              return 'makro'
        if 'panamar' in f:                                            return 'panamar'
        if 'lassal' in f:                                             return 'lassal'
        if 'hielos' in f or 'valentiae' in f:                        return 'hielos'
        return 'generico'

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # PARSER PRINCIPAL
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _parse(self, texts, ft):
        r = {
            "numero_albaran": None, "fecha": None,
            "proveedor": None,      "proveedor_tipo": None,
            "base_imponible": None, "iva_total": None,
            "total": None,          "productos": [],
            "confianza": "baja",    "campos_fallidos": []
        }
        pt = self.detect_proveedor(ft)
        r["proveedor_tipo"] = pt
        # Los proveedores sin importes no deben marcar esos campos como fallidos
        SIN_IMPORTES = {'panamar', 'lassal', 'hielos'}

        # â”€â”€ CHARCUVAL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # [04] NUM.26A/2108   [06] FECHA 11/02/26
        # final: base 0.00 0.00 total Observaciones
        if pt == 'charcuval':
            r["proveedor"] = "Exclusivas Charcuval SL"

            m = re.search(r'NUM\.(\w+/\w+)', ft)
            if m: r["numero_albaran"] = m.group(1)

            m = re.search(r'FECHA (\d{1,2}/\d{2}/\d{2,4})', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

            # base 0.00 0.00 total Observaciones
            m = re.search(
                r'([\d,\.]+)\s+0[,\.]00\s+0[,\.]00\s+([\d,\.]+)\s+Observaciones',
                ft)
            if m:
                r["base_imponible"] = self._f(m.group(1))
                r["total"] = self._f(m.group(2))

            # IVA: suma de cuotas tras 10% y 4%
            iva_vals = re.findall(r'(?:10|4)%\s*([\d\.]+)', ft)
            if iva_vals:
                r["iva_total"] = self._sum(iva_vals)

            matches = re.findall(
                r'\d{5}\s+\d{6,8}\s+\d+c\s+([A-Z@][^\d]{5,60}?)\s+(\d+)\s+([\d\.]+)\s+[\d\'\.]+ \s+([\d\.]+)',
                ft)
            for m in matches:
                prod = {
                    "descripcion": m[0].strip(),
                    "cantidad": float(m[2].replace(',', '.')),
                    "unidad": "kg",
                    "precio_unitario": None,
                    "importe": float(m[3].replace(',', '.'))
                }
                if prod.get("descripcion") and prod.get("importe"):
                    r["productos"].append(prod)

        # â”€â”€ JASA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # [09] ALV260303735   [18] 04/03/26
        # B.l./B.I. base base %IVA cuotaIVA INCOTERM
        # TOTALIMPORTE 238.436 (dÃ­gito espurio)
        elif pt == 'jasa':
            r["proveedor"] = "Jasa - Joaquin Ayora SAU"

            m = re.search(r'\b(ALV\d+)\b', ft)
            if m: r["numero_albaran"] = m.group(1)

            m = re.search(r'\b(\d{2}/\d{2}/\d{2,4})\b', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

            m = re.search(
                r'B\.[lI]\.\s*([\d,]+)\s+[\d,]+\s+\d+\s+([\d,]+)\s+INCOTERM',
                ft)
            if m:
                r["base_imponible"] = self._f(m.group(1))
                r["iva_total"] = self._f(m.group(2))

            m = re.search(r'TOTAL\s*IMPORTE[^\d]*([\d,\.]+)', ft, re.I)
            if m: r["total"] = self._f(m.group(1))

            for codigo, desc, uds_caja, precio_caja, importe in re.findall(r'(\d{8})\s+([A-Z][^\d\n]{3,60}?)\s+CAJA\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)', ft):
                r["productos"].append({
                    "codigo": codigo.strip(),
                    "descripcion": desc.strip(),
                    "cantidad": self._f(uds_caja),
                    "unidad": 'caj',
                    "precio_unitario": self._f(precio_caja),
                    "importe": self._f(importe),
                    "iva_pct": None
                })

        # â”€â”€ SH LEVANTE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # albaran1: [17] 0/2600435204/02/26  (sin espacio)
        # albaran2: [17] 0/ 26008946 07/03/26 (con espacio)
        # FIX total: Ãºltimo nÃºmero antes de OBSERVACIONES
        elif pt == 'levante':
            r["proveedor"] = "Serv. Hortofruticolas de Levante SL"

            m = re.search(r'0/\s*(\d{8})\s*(\d{2}/\d{2}/\d{2,4})', ft)
            if m:
                r["numero_albaran"] = m.group(1)
                r["fecha"] = self._normalize_date(m.group(2))

            # Bases: valor antes de 10,0 o 4,0 en tabla resumen
            # PatrÃ³n fijo: base %iva ivaval 0,00 0,00
            bases = re.findall(
                r'([\d,]+)\s+(?:10,0|4,0)\s+[\d,]+\s+0,00\s+0,00', ft)
            if bases:
                r["base_imponible"] = self._sum(bases)

            ivas = re.findall(r'(?:10,0|4,0)\s+([\d,]+)\s+0,00', ft)
            if ivas:
                r["iva_total"] = self._sum(ivas)

            # FIX: el total real estÃ¡ JUSTO ANTES de OBSERVACIONES
            # Layout: ... [18,70] OBSERVACIONES  o  ... [43,21] OBSERVACIONES
            m = re.search(r'([\d,]+)\s+OBSERVACIONES', ft)
            if m: r["total"] = self._f(m.group(1))

            matches = re.findall(
                r'([A-Za-záéíóúÁÉÍÓÚñÑ][^\d\n]{4,50}?)\s+Espa[ñn]a\s+\d{10,}[\d\-]+\s+([\d,]+)\s+0,00\s+([\d,]+)\s+([\d,]+)\s+(?:4|10),00\s+([\d,]+)',
                ft)
            for m in matches:
                prod = {
                    "descripcion": m[0].strip(),
                    "cantidad": float(m[2].replace(',', '.')),
                    "unidad": "kg",
                    "precio_unitario": float(m[3].replace(',', '.')),
                    "importe": float(m[4].replace(',', '.'))
                }
                if prod.get("descripcion") and prod.get("importe"):
                    r["productos"].append(prod)

        # â”€â”€ DIVINS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # [21] A26-0653   [25] FECHA 2/02/2026
        # [72] 154,16  [73] 21%  [74] 32,37  [75] IMPORTE TOTAL  [76] 186,53
        elif pt == 'divins':
            r["proveedor"] = "Divins Diresa SLU"

            m = re.search(r'\b(A\d{2}-\d{4})\b', ft)
            if m: r["numero_albaran"] = m.group(1)

            m = re.search(r'FECHA\s*(\d{1,2}/\d{2}/\d{2,4})', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

            m = re.search(
                r'([\d,]+)\s+21%\s+([\d,]+)\s+IMPORTE TOTAL\s+([\d,]+)', ft)
            if m:
                r["base_imponible"] = self._f(m.group(1))
                r["iva_total"] = self._f(m.group(2))
                r["total"] = self._f(m.group(3))
            else:
                m2 = re.search(r'IMPORTE TOTAL[^\d]*([\d,]+)', ft)
                if m2: r["total"] = self._f(m2.group(1))

            matches = re.findall(
                r'\b(\d{4})\s+([A-Z][A-Z0-9 /\(\)\-\.]{3,45}?)\s+(\d+)\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+([\d,]+)',
                ft)
            for m in matches:
                prod = {
                    "codigo": m[0],
                    "descripcion": m[1].strip(),
                    "cantidad": float(m[2]),
                    "unidad": "ud",
                    "precio_unitario": float(m[3].replace(',', '.')),
                    "importe": float(m[4].replace(',', '.'))
                }
                if prod.get("descripcion") and prod.get("importe"):
                    r["productos"].append(prod)

        # â”€â”€ VACUM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif pt == 'vacum':
            r["proveedor"] = "Vacum Carnes de Lujo SL"

            m = re.search(
                r'(?:ALBARAN|N[ÂºoÂ°]\.?)\s*[:\-]?\s*(\d{3,6})\b', ft, re.I)
            if m: r["numero_albaran"] = m.group(1)

            m = re.search(r'\b(\d{2}/\d{2}/\d{2,4})\b', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

            m = re.search(
                r'(?:BASE\s*IMPONIBLE|B\.?\s*IMPONIBLE)[^\d]*([\d,\.]+)',
                ft, re.I)
            if m: r["base_imponible"] = self._f(m.group(1))

            m = re.search(r'I\.?V\.?A\.?[^\d]*([\d,\.]+)', ft, re.I)
            if m: r["iva_total"] = self._f(m.group(1))

            m = re.search(r'TOTAL[^\d]*([\d,\.]+)', ft, re.I)
            if m: r["total"] = self._f(m.group(1))

        # â”€â”€ COCA-COLA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # [21] 04.03.2026   [25] 4530800844 (NOTA ENTR.)
        # [128] TOTAL BASES:128,26
        # [129] TOTAL IMPUESTOS: 26,93
        # [130] TOTAL:155,19EUROS
        # [131] NÃºm.Albaran:  [132] 4530800844
        elif pt == 'cocacola':
            r["proveedor"] = "Coca-Cola Europacific Partners"

            m = re.search(r'N.{0,5}m\.Albaran[:\s]*(\d+)', ft)
            if m: r["numero_albaran"] = m.group(1)
            else:
                m = re.search(r'NOTA ENTR\.\s*(\d{10})', ft)
                if m: r["numero_albaran"] = m.group(1)

            # FIX: sin \\b â€” el punto no es word char y confunde al engine
            m = re.search(r'(\d{2}\.\d{2}\.\d{4})', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

            m = re.search(r'TOTAL BASES:\s*([\d,]+)', ft)
            if m: r["base_imponible"] = self._f(m.group(1))

            m = re.search(r'TOTAL IMPUESTOS:\s*([\d,]+)', ft)
            if m: r["iva_total"] = self._f(m.group(1))

            m = re.search(r'TOTAL:([\d,]+)EUROS', ft)
            if m: r["total"] = self._f(m.group(1))

            matches = re.findall(
                r'\d{13}\s+\d{3,4}\s+([A-Z][A-Z0-9 /\.]{3,40}?)\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+[\d,]+\-\s+[\d,]+\s+([\d,]+)',
                ft)
            for m in matches:
                prod = {
                    "descripcion": m[0].strip(),
                    "cantidad": float(m[1].replace(',', '.')),
                    "unidad": "caj",
                    "precio_unitario": None,
                    "importe": float(m[2].replace(',', '.'))
                }
                if prod.get("descripcion") and prod.get("importe"):
                    r["productos"].append(prod)

        # â”€â”€ DDI / CERVECERA TURIA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # [40] 828097291 (albarÃ¡n)   [41] 04.03.2026
        # FIX fecha: sin \\b (fallaba con "vto04.03.2026")
        # FIX base/IVA: restringir al bloque resumen tras "lmp.Bruto"
        #   porque las lÃ­neas de producto tienen: 21,00 81658986 (EAN barcode)
        elif pt == 'ddi':
            r["proveedor"] = "Cervecera del Turia SL (DDI)"

            # NÃºmero: segundo campo numÃ©rico de 9 dÃ­gitos en la cabecera
            m = re.search(r'\d{10}\s+(\d{9})\s+\d{2}\.\d{2}\.\d{4}', ft)
            if m: r["numero_albaran"] = m.group(1)

            # FIX fecha: regex sin \\b â€” busca primera ocurrencia dd.mm.yyyy
            m = re.search(r'(\d{2}\.\d{2}\.\d{4})', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

            # FIX base/IVA: solo del bloque resumen (tras "lmp.Bruto")
            # OCR: [217] lmp.Bruto  ...  294,54 2,69 297,23 21,00 62,42
            #       133,94 133,94 10,00  ...  13,39  8,99 8,99 4,00 0,36
            m_s = re.search(r'[lI]mp\.Bruto(.+?)TOTAL', ft, re.S)
            if m_s:
                sb = m_s.group(1)
                # Base 21%: impbruto dto BASE 21,00 IVA  â†’ tercero antes de 21,00
                m21 = re.search(
                    r'([\d,]+)\s+[\d,]+\s+([\d,]+)\s+21,00\s+([\d,]+)', sb)
                # Base 10%: BASE BASE 10,00   (pueden ser iguales impbruto=base)
                m10 = re.search(
                    r'([\d,]+)\s+([\d,]+)\s+10,00', sb)
                # Base 4% y cuota: aparecen en la lÃ­nea de RE
                m4 = re.search(r'([\d,]+)\s+4,00\s+([\d,]+)', sb)

                bases, ivas = [], []
                if m21:
                    bases.append(self._f(m21.group(2)))  # base 21%
                    ivas.append(self._f(m21.group(3)))   # IVA 21%
                if m10:
                    bases.append(self._f(m10.group(2)))  # base 10%
                    # IVA 10% = base * 0.10 (no aparece explÃ­cita antes de TOTAL)
                    b10 = self._f(m10.group(2))
                    if b10: ivas.append(round(b10 * 0.10, 2))
                if m4:
                    bases.append(self._f(m4.group(1)))   # base 4%
                    ivas.append(self._f(m4.group(2)))    # IVA 4%

                if bases: r["base_imponible"] = self._sum(bases)
                if ivas:  r["iva_total"] = self._sum(ivas)

            # Total: Ãºltimo nÃºmero antes del punto final en "TOTAL 516,33."
            m = re.search(r'TOTAL\s+([\d,]+)\.?\s*$', ft)
            if not m:
                # fallback: "mporte 516,33" (OCR cortÃ³ "Importe")
                m = re.search(r'mporte\s+([\d,]+)', ft)
            if m: r["total"] = self._f(m.group(1))

            texto_productos = ft.split("lmp.Bruto")[0] if "lmp.Bruto" in ft else ft
            if texto_productos == ft:
                texto_productos = ft.split("Imp.Bruto")[0] if "Imp.Bruto" in ft else ft

            matches = re.findall(
                r'([A-Z0-9]{2,8})\s+([A-Z][A-Z0-9 \./\-,áéíóúÁÉÍÓÚ]{5,55}?)\s+(CAJ|BRL|BOT|UN|LT|PK)\s+(\d+)\s+[\d,]+\s+[\d,]+\s+(?:[\d,]+\s+)?([\d,]+)\s+(\d+),00',
                texto_productos)
            for m in matches:
                prod = {
                    "codigo": m[0],
                    "descripcion": m[1].strip(),
                    "cantidad": float(m[3]),
                    "unidad": m[2].lower(),
                    "precio_unitario": None,
                    "importe": float(m[4].replace(',', '.')),
                    "iva_pct": float(m[5])
                }
                if prod.get("descripcion") and prod.get("importe"):
                    r["productos"].append(prod)

        # â”€â”€ MAKRO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # [20] 0/0(017)0207/(2026)005540
        # [05] 26/02/202609:45   â†’ _normalize_date extrae 26/02/26
        # [231] 175,31  [232] 21,19  [233] Totalapaga  [234] 196,50
        elif pt == 'makro':
            r["proveedor"] = "Makro Distribucion Mayorista SA"
            m = re.search(r'(0/0\([^)]+\)[^\s(]+(?:\([^)]+\)[^\s]*)?)', ft)
            if m: r["numero_albaran"] = m.group(1)
            # FIX: _normalize_date maneja '26/02/202609:45' â†’ '26/02/26'
            m = re.search(r'Fecha de venta[:\s]*(\d{2}/\d{2}/\d{4}\d{2}:\d{2}|\d{2}/\d{2}/\d{4})', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))
            else:
                m = re.search(r'(\d{2}/\d{2}/\d{4})', ft)
                if m: r["fecha"] = self._normalize_date(m.group(1))

            m = re.search(r'([\d,\.]+)\s+([\d,\.]+)\s+Totalapaga', ft)
            if m:
                r["base_imponible"] = self._f(m.group(1))
                r["iva_total"] = self._f(m.group(2))

            m = re.search(r'Totalapaga\s*([\d,\.]+)', ft)
            if m: r["total"] = self._f(m.group(1))

            matches = re.findall(
                r'\d{10,14}\s+([A-Z][A-Z0-9 /\.\-,\*]{3,50}?)\s+(TA|CJ|KG|MG|BJ|BL|LT|PK|RT|GF|PQ|UD|BO|UN)\s+([\d,]+)\s+[\d,]+\s+([\d,]+)\s+(\d+)\s+([\d,]+)\s+(\d+)',
                ft)
            for m in matches:
                prod = {
                    "descripcion": m[0].strip(),
                    "cantidad": float(m[4]),
                    "unidad": m[1].lower(),
                    "precio_unitario": float(m[2].replace(',', '.')),
                    "importe": float(m[5].replace(',', '.')),
                    "iva_pct": float(m[6])
                }
                if prod.get("descripcion") and prod.get("importe"):
                    r["productos"].append(prod)

        # â”€â”€ PANAMAR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # AlbarÃ¡n de ENTREGA â€” sin importes. No marcar financieros como fallidos.
        # [23] 800406519903/03/2026  (nÃºmero 10d + fecha pegados)
        elif pt == 'panamar':
            r["proveedor"] = "Panamar Bakery Group SL"
            r["confianza"] = "alta"  # delivery note â€” completitud esperada

            m = re.search(r'(\d{10})(\d{2}/\d{2}/\d{4})', ft)
            if m:
                r["numero_albaran"] = m.group(1)
                r["fecha"] = self._normalize_date(m.group(2))
            else:
                m = re.search(r'ALBARAN\s*(\d{8,12})', ft, re.I)
                if m: r["numero_albaran"] = m.group(1)
                m = re.search(r'(\d{2}/\d{2}/\d{4})', ft)
                if m: r["fecha"] = self._normalize_date(m.group(1))

        # â”€â”€ LASSAL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Delivery Note â€” sin importes
        # [01] Delivery Note AL26001919   [02] 03/03/2026
        elif pt == 'lassal':
            r["proveedor"] = "Lassal Cooking SL"
            r["confianza"] = "alta"  # delivery note â€” completitud esperada

            m = re.search(r'Delivery Note (AL\d+)', ft)
            if m: r["numero_albaran"] = m.group(1)

            m = re.search(r'(\d{2}/\d{2}/\d{4})', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

        # â”€â”€ HIELOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        elif pt == 'hielos':
            r["proveedor"] = "Hielos Valentiae"
            r["confianza"] = "baja"

            m = re.search(r'\b(\d{4})\b', ft)
            if m: r["numero_albaran"] = m.group(1)

            m = re.search(r'(\d{1,2})\s*/\s*(\d{2})\s*/\s*(\d{2,4})', ft)
            if m:
                d, mo, y = m.group(1), m.group(2), m.group(3)
                if len(y) == 4: y = y[2:]
                r["fecha"] = f"{d.zfill(2)}/{mo}/{y}"

            m = re.search(r'(\d+)\s*â‚¬', ft)
            if m: r["total"] = self._f(m.group(1))

        # â”€â”€ GENÃ‰RICO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        else:
            r["proveedor"] = texts[0] if texts else "Desconocido"

            for pat in [r'\b(ALV\d+)\b', r'\b(AL\d{8})\b',
                        r'\b([A-Z]\d{2}-\d{4})\b', r'NUM\.(\w+/\w+)']:
                m = re.search(pat, ft)
                if m: r["numero_albaran"] = m.group(1); break

            m = re.search(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

            m = re.search(
                r'(?:BASE\s*IMPONIBLE|B\.?\s*IMPONIBLE)[^\d]*([\d,\.]+)',
                ft, re.I)
            if m: r["base_imponible"] = self._f(m.group(1))

            nums = re.findall(r'\b(\d{2,4}[.,]\d{2})\b', ft)
            if nums: r["total"] = self._f(nums[-1])

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        # FALLBACKS GLOBALES (solo si campo sigue None Y no es delivery note)
        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        if not r["numero_albaran"]:
            for pat in [r'\b(ALV\d+)\b', r'\b(AL\d{8})\b',
                        r'\b([A-Z]\d{2}-\d{4})\b', r'NUM\.(\w+/\w+)']:
                m = re.search(pat, ft)
                if m: r["numero_albaran"] = m.group(1); break

        if not r["fecha"]:
            m = re.search(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b', ft)
            if m: r["fecha"] = self._normalize_date(m.group(1))

        # FIX: NO aplicar fallback de total para Panamar y Lassal
        if not r["total"] and pt not in SIN_IMPORTES:
            nums = re.findall(r'\b(\d{2,4}[.,]\d{2})\b', ft)
            if nums: r["total"] = self._f(nums[-1])

        # Productos: fallback por lineas si el regex no extrajo ninguno.
        if not r["productos"]:
            r["productos"] = self._productos_lineas(texts, pt)

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        # NIVEL DE CONFIANZA Y CAMPOS FALLIDOS
        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        # Campos que SÃ se esperan para cada tipo
        if pt in SIN_IMPORTES:
            campos_esperados = ["numero_albaran", "fecha"]
        else:
            campos_esperados = ["numero_albaran", "fecha",
                                "base_imponible", "iva_total", "total"]

        r["campos_fallidos"] = [k for k in campos_esperados if not r.get(k)]

        criticos = ["numero_albaran", "fecha", "total"]
        fallidos_criticos = [k for k in criticos
                             if k in campos_esperados and not r.get(k)]

        if pt in ('hielos', 'generico'):
            r["confianza"] = "baja"
        elif fallidos_criticos:
            r["confianza"] = "media"
        elif pt not in SIN_IMPORTES and not r.get("total"):
            r["confianza"] = "media"
        else:
            r["confianza"] = "alta"

        return r
