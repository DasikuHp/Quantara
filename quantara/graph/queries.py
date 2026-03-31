from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date
from quantara.graph.models import (
    Albaran, Proveedor, Producto, Feedback,
    CatalogoProducto, LineaAlbaran, PrecioHistorico, Venta
)
# Módulo Queries (Graph)
# Responsabilidad: Definición y ejecución de consultas (SQLAlchemy)

def get_albaran_by_id(db: Session, id: int):
    return db.query(Albaran).filter(Albaran.id == id).first()

def get_albaranes_by_proveedor(db: Session, proveedor_id: int):
    return db.query(Albaran).filter(Albaran.proveedor_id == proveedor_id).all()

def get_productos_by_albaran(db: Session, albaran_id: int):
    return db.query(Producto).filter(Producto.albaran_id == albaran_id).all()

def get_gasto_por_periodo(db: Session, fecha_inicio: str, fecha_fin: str):
    return db.query(func.sum(Albaran.total)).filter(
        Albaran.fecha >= fecha_inicio,
        Albaran.fecha <= fecha_fin
    ).scalar()

def get_or_create_proveedor(db: Session, nombre: str):
    proveedor = db.query(Proveedor).filter(Proveedor.nombre == nombre).first()
    if not proveedor:
        proveedor = Proveedor(nombre=nombre)
        db.add(proveedor)
        db.commit()
        db.refresh(proveedor)
    return proveedor

def save_feedback(db: Session, albaran_id: int, campo: str, valor_ocr: str, valor_correcto: str):
    nuevo_feedback = Feedback(
        albaran_id=albaran_id,
        campo=campo,
        valor_ocr=valor_ocr,
        valor_correcto=valor_correcto,
        aplicado=False
    )
    db.add(nuevo_feedback)
    db.commit()
    db.refresh(nuevo_feedback)
    return nuevo_feedback


def gasto_por_proveedor(db: Session, fecha_desde=None, fecha_hasta=None) -> list[dict]:
    query = db.query(
        Proveedor.nombre.label("proveedor"),
        func.count(Albaran.id).label("albaranes"),
        func.sum(Albaran.total).label("total"),
        func.sum(Albaran.iva_total).label("iva")
    ).join(Albaran, Proveedor.id == Albaran.proveedor_id)

    if fecha_desde:
        query = query.filter(Albaran.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Albaran.fecha <= fecha_hasta)

    resultados = query.group_by(Proveedor.nombre).order_by(desc("total")).all()
    
    return [
        {
            "proveedor": r.proveedor,
            "albaranes": r.albaranes,
            "total": round(r.total or 0, 2),
            "iva": round(r.iva or 0, 2)
        }
        for r in resultados
    ]


def coste_producto_periodo(db: Session, nombre_producto: str, fecha_desde=None, fecha_hasta=None) -> list[dict]:
    query = db.query(
        CatalogoProducto.nombre_normalizado.label("producto"),
        func.sum(LineaAlbaran.importe).label("coste_total"),
        func.sum(LineaAlbaran.cantidad).label("cantidad_total")
    ).join(LineaAlbaran, CatalogoProducto.id == LineaAlbaran.catalogo_id)\
     .join(Albaran, LineaAlbaran.albaran_id == Albaran.id)\
     .filter(CatalogoProducto.nombre_normalizado.ilike(f"%{nombre_producto}%"))

    if fecha_desde:
        query = query.filter(Albaran.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Albaran.fecha <= fecha_hasta)

    resultados = query.group_by(CatalogoProducto.nombre_normalizado).all()

    return [
        {
            "producto": r.producto,
            "coste_total": round(r.coste_total or 0, 2),
            "cantidad_total": round(r.cantidad_total or 0, 2)
        }
        for r in resultados
    ]


def comparar_precio_proveedores(db: Session, nombre_producto: str) -> list[dict]:
    # Obtener el último precio registrado por cada proveedor para este producto
    subquery = db.query(
        PrecioHistorico.proveedor_id,
        func.max(PrecioHistorico.fecha).label("max_fecha")
    ).join(CatalogoProducto, PrecioHistorico.catalogo_id == CatalogoProducto.id)\
     .filter(CatalogoProducto.nombre_normalizado.ilike(f"%{nombre_producto}%"))\
     .group_by(PrecioHistorico.proveedor_id).subquery()

    query = db.query(
        Proveedor.nombre.label("proveedor"),
        PrecioHistorico.precio_unitario,
        PrecioHistorico.fecha.label("ultima_compra")
    ).join(subquery, (PrecioHistorico.proveedor_id == subquery.c.proveedor_id) & (PrecioHistorico.fecha == subquery.c.max_fecha))\
     .join(Proveedor, PrecioHistorico.proveedor_id == Proveedor.id)\
     .join(CatalogoProducto, PrecioHistorico.catalogo_id == CatalogoProducto.id)\
     .filter(CatalogoProducto.nombre_normalizado.ilike(f"%{nombre_producto}%"))\
     .order_by(PrecioHistorico.precio_unitario.asc())

    resultados = query.all()
    return [
        {
            "proveedor": r.proveedor,
            "precio_unitario": round(r.precio_unitario, 2),
            "ultima_compra": str(r.ultima_compra)
        }
        for r in resultados
    ]


def calcular_margen(db: Session, nombre_producto: str) -> dict:
    producto_cat = db.query(CatalogoProducto).filter(CatalogoProducto.nombre_normalizado.ilike(f"%{nombre_producto}%")).first()
    
    res = {
        "producto": nombre_producto,
        "coste_unitario": None,
        "precio_venta": None,
        "margen_euros": None,
        "margen_porcentaje": None,
        "estado": "calculado"
    }
    falta = []

    if not producto_cat:
        res["estado"] = "faltan_datos"
        res["falta"] = ["catalogo"]
        return res

    res["producto"] = producto_cat.nombre_normalizado

    # Buscar el último precio de compra (el más reciente globalmente para el producto)
    ultimo_precio = db.query(PrecioHistorico)\
        .filter(PrecioHistorico.catalogo_id == producto_cat.id)\
        .order_by(PrecioHistorico.fecha.desc(), PrecioHistorico.id.desc())\
        .first()
    
    if ultimo_precio and ultimo_precio.precio_unitario:
        res["coste_unitario"] = ultimo_precio.precio_unitario
    else:
        falta.append("coste_unitario")

    # Buscar el precio de venta activo
    venta_activa = db.query(Venta)\
        .filter(Venta.catalogo_id == producto_cat.id, Venta.activo == True)\
        .first()
    
    if venta_activa and venta_activa.precio_venta:
        res["precio_venta"] = venta_activa.precio_venta
    else:
        falta.append("precio_venta")

    if falta:
        res["estado"] = "faltan_datos"
        res["falta"] = falta
        return res

    # Cálculo
    margen_euros = res["precio_venta"] - res["coste_unitario"]
    res["margen_euros"] = round(margen_euros, 2)
    # Evitar div/0
    if res["precio_venta"] > 0:
        res["margen_porcentaje"] = round((margen_euros / res["precio_venta"]) * 100, 2)
    else:
        res["margen_porcentaje"] = 0.0

    return res


def resumen_mes_actual(db: Session) -> dict:
    import datetime
    hoy = datetime.date.today()
    inicio_mes = datetime.datetime(hoy.year, hoy.month, 1)
    fin_mes = datetime.datetime(hoy.year, hoy.month, 28, 23, 59, 59)
    
    # Gasto total y albaranes
    agg = db.query(
        func.sum(Albaran.total).label("gasto_total"),
        func.count(Albaran.id).label("num_albaranes")
    ).filter(Albaran.fecha >= inicio_mes, Albaran.fecha <= fin_mes).first()

    gasto_total = round(agg.gasto_total or 0, 2)
    num_albaranes = agg.num_albaranes or 0

    # Top Proveedores
    top_prov_query = db.query(
        Proveedor.nombre.label("proveedor"),
        func.sum(Albaran.total).label("total")
    ).join(Albaran, Proveedor.id == Albaran.proveedor_id)\
     .filter(Albaran.fecha >= inicio_mes, Albaran.fecha <= fin_mes)\
     .group_by(Proveedor.nombre)\
     .order_by(desc("total")).limit(5).all()

    top_proveedores = [{"proveedor": r.proveedor, "total": round(r.total or 0, 2)} for r in top_prov_query]

    # Top Productos (basado en importe gastado en las líneas del albarán)
    top_prod_query = db.query(
        CatalogoProducto.nombre_normalizado.label("producto"),
        func.sum(LineaAlbaran.importe).label("total")
    ).join(LineaAlbaran, CatalogoProducto.id == LineaAlbaran.catalogo_id)\
     .join(Albaran, LineaAlbaran.albaran_id == Albaran.id)\
     .filter(Albaran.fecha >= inicio_mes, Albaran.fecha <= fin_mes)\
     .group_by(CatalogoProducto.nombre_normalizado)\
     .order_by(desc("total")).limit(5).all()

    top_productos = [{"producto": r.producto, "total": round(r.total or 0, 2)} for r in top_prod_query]

    return {
        "mes": hoy.strftime("%B %Y"),
        "gasto_total": gasto_total,
        "num_albaranes": num_albaranes,
        "top_proveedores": top_proveedores,
        "top_productos": top_productos
    }


def registrar_precio_venta(db: Session, descripcion: str, precio_venta: float, unidad="ud") -> Venta:
    import datetime
    # Desactivar precio(s) anterior(es) para esa descripción
    precios_anteriores = db.query(Venta).filter(
        Venta.descripcion == descripcion,
        Venta.activo == True
    ).all()
    
    for p in precios_anteriores:
        p.activo = False
    
    # Intentar asociar con un producto de catálogo
    producto_cat = db.query(CatalogoProducto).filter(
        CatalogoProducto.nombre_normalizado.ilike(f"%{descripcion}%")
    ).first()

    nueva_venta = Venta(
        catalogo_id=producto_cat.id if producto_cat else None,
        descripcion=descripcion,
        precio_venta=precio_venta,
        unidad=unidad,
        fecha_desde=datetime.date.today(),
        activo=True
    )
    
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)
    return nueva_venta

