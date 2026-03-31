import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from quantara.api.schemas import AlbaranSchema, FeedbackSchema, ResponseSchema, ProductoSchema
from quantara.graph.database import get_db
from quantara.graph import queries, models
from quantara.config import UPLOAD_DIR
from quantara.core.normalizer import parse_linea_producto, normalize_proveedor

# Módulo Routes
# Responsabilidad: Definición de los endpoints de la API REST

router = APIRouter()

@router.post("/upload")
def process_document(
    file: UploadFile = File(...),
):
    from quantara.graph.database import SessionLocal
    from quantara.graph.models import Albaran, Proveedor
    from quantara.ocr.donut_model import DonutExtractor
    from quantara.ocr.preprocessor import pdf_to_image, load_image
    from quantara.core.validator import validate_albaran_completo
    from quantara.core.normalizer import normalize_proveedor
    import tempfile, os

    db = SessionLocal()
    try:
        contents = file.file.read()
        suffix = ".pdf" if "pdf" in file.content_type else ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        if suffix == ".pdf":
            images = pdf_to_image(tmp_path)
            image = images[0] if images else None
        else:
            image = load_image(tmp_path)

        os.unlink(tmp_path)

        if not image:
            raise HTTPException(status_code=400, detail="No se pudo procesar el archivo")

        extractor = DonutExtractor()
        raw = extractor.extract(image)
        validated = validate_albaran_completo(raw)

        nombre_proveedor = normalize_proveedor(
            raw.get("proveedor") or "Proveedor Desconocido"
        )

        proveedor = db.query(Proveedor).filter_by(nombre=nombre_proveedor).first()
        if not proveedor:
            proveedor = Proveedor(nombre=nombre_proveedor)
            db.add(proveedor)
            db.flush()

        albaran = Albaran(
            proveedor_id=proveedor.id,
            numero_albaran=raw.get("numero_albaran"),
            fecha=validated["validos"].get("fecha"),
            total=validated["validos"].get("total"),
            iva_total=validated["validos"].get("iva_total"),
            base_imponible=validated["validos"].get("base_imponible"),
            procesado_ok=len(validated["fallidos"]) == 0,
        )
        db.add(albaran)
        db.commit()
        db.refresh(albaran)

        for prod in (raw.get("productos") or []):
            desc = prod.get("descripcion")
            if not desc:
                continue
            from quantara.graph.models import Producto
            producto_db = Producto(
                albaran_id=albaran.id,
                descripcion=str(desc).strip(),
                cantidad=prod.get("cantidad") or prod.get("kilos"),
                unidad=prod.get("unidad", "ud"),
                precio_unitario=prod.get("precio_unitario") or prod.get("precio_kg"),
                iva_pct=prod.get("iva_pct"),
                total_linea=prod.get("importe") or prod.get("importe_neto"),
            )
            db.add(producto_db)
        if raw.get("productos"):
            db.commit()

        return {
            "success": True,
            "message": "Documento procesado con éxito",
            "data": {
                "numero_albaran": albaran.numero_albaran,
                "fecha": str(albaran.fecha) if albaran.fecha else None,
                "proveedor": proveedor.nombre,
                "productos": [{"descripcion": p.get("descripcion"), "cantidad": p.get("cantidad"),
                               "importe": p.get("importe")} for p in (raw.get("productos") or [])],
                "base_imponible": albaran.base_imponible,
                "iva_total": albaran.iva_total,
                "total": albaran.total,
                "procesado_ok": albaran.procesado_ok,
                "campos_fallidos": validated["fallidos"],
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        db.close()


@router.get("/albaran/{id}", response_model=ResponseSchema)
def get_albaran(id: int, db: Session = Depends(get_db)):
    try:
        albaran = queries.get_albaran_by_id(db, id)
        if not albaran:
            raise HTTPException(status_code=404, detail="Albarán no encontrado")

        productos_db = queries.get_productos_by_albaran(db, id)

        res_data = AlbaranSchema(
            numero_albaran=albaran.numero_albaran,
            fecha=albaran.fecha,
            proveedor=albaran.proveedor.nombre if albaran.proveedor else None,
            productos=[ProductoSchema(
                descripcion=p.descripcion,
                cantidad=p.cantidad,
                unidad=p.unidad,
                precio_unitario=p.precio_unitario,
                iva_pct=p.iva_pct,
                total_linea=p.total_linea
            ) for p in productos_db],
            base_imponible=albaran.base_imponible,
            iva_total=albaran.iva_total,
            total=albaran.total,
            procesado_ok=albaran.procesado_ok,
            campos_fallidos=[]
        )
        return ResponseSchema(success=True, message="Albarán recuperado", data=res_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/albaranes", response_model=ResponseSchema)
def list_albaranes(
    proveedor: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db)
):
    try:
        q = db.query(models.Albaran)

        if proveedor:
            q = q.join(models.Proveedor).filter(models.Proveedor.nombre.ilike(f"%{proveedor}%"))
        if fecha_inicio:
            q = q.filter(models.Albaran.fecha >= fecha_inicio)
        if fecha_fin:
            q = q.filter(models.Albaran.fecha <= fecha_fin)

        albaranes = q.offset(skip).limit(limit).all()

        data_list = []
        for alb in albaranes:
            data_list.append(AlbaranSchema(
                numero_albaran=alb.numero_albaran,
                fecha=alb.fecha,
                proveedor=alb.proveedor.nombre if alb.proveedor else None,
                productos=[],
                base_imponible=alb.base_imponible,
                iva_total=alb.iva_total,
                total=alb.total,
                procesado_ok=alb.procesado_ok,
                campos_fallidos=[]
            ).model_dump())

        return ResponseSchema(success=True, message="Albaranes listados", data=data_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback", response_model=ResponseSchema)
def submit_feedback(feedback: FeedbackSchema, db: Session = Depends(get_db)):
    try:
        alb = queries.get_albaran_by_id(db, feedback.albaran_id)
        if not alb:
            raise HTTPException(status_code=404, detail="Albarán no encontrado para registrar feedback")

        queries.save_feedback(
            db,
            albaran_id=feedback.albaran_id,
            campo=feedback.campo,
            valor_ocr=feedback.valor_ocr,
            valor_correcto=feedback.valor_correcto
        )
        return ResponseSchema(success=True, message="Feedback almacenado correctamente")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ResponseSchema)
def get_stats(db: Session = Depends(get_db)):
    try:
        total_gasto = db.query(func.sum(models.Albaran.total)).scalar() or 0.0

        gasto_prov_query = db.query(
            models.Proveedor.nombre,
            func.sum(models.Albaran.total)
        ).join(models.Albaran).group_by(models.Proveedor.id).all()

        top_productos = db.query(
            models.Producto.descripcion,
            func.sum(models.Producto.cantidad)
        ).group_by(models.Producto.descripcion)\
         .order_by(func.sum(models.Producto.cantidad).desc()).limit(5).all()

        stats = {
            "gasto_total": total_gasto,
            "gasto_por_proveedor": [{"proveedor": row[0], "total": row[1]} for row in gasto_prov_query if row[0]],
            "top_productos": [{"producto": row[0], "cantidad": row[1]} for row in top_productos if row[0]]
        }
        return ResponseSchema(success=True, message="Estadísticas de facturación", data=stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from datetime import date
from pydantic import BaseModel

class PrecioVentaRequest(BaseModel):
    descripcion: str
    precio_venta: float
    unidad: str = "ud"

@router.get("/resumen")
def get_resumen():
    from quantara.graph.database import SessionLocal
    from quantara.graph.queries import resumen_mes_actual
    
    db = SessionLocal()
    try:
        resultado = resumen_mes_actual(db)
        return {"success": True, "data": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/gasto-proveedores")
def get_gasto_proveedores(desde: str = None, hasta: str = None):
    from quantara.graph.database import SessionLocal
    from quantara.graph.queries import gasto_por_proveedor
    
    db = SessionLocal()
    try:
        f_desde = date.fromisoformat(desde) if desde else None
        f_hasta = date.fromisoformat(hasta) if hasta else None
        
        lista = gasto_por_proveedor(db, f_desde, f_hasta)
        total_periodo = sum(item.get("total", 0) for item in lista)
        
        return {"success": True, "data": lista, "total_periodo": total_periodo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/producto/{nombre}/coste")
def get_producto_coste(nombre: str, desde: str = None, hasta: str = None):
    from quantara.graph.database import SessionLocal
    from quantara.graph.queries import coste_producto_periodo
    
    db = SessionLocal()
    try:
        f_desde = date.fromisoformat(desde) if desde else None
        f_hasta = date.fromisoformat(hasta) if hasta else None
        
        lista = coste_producto_periodo(db, nombre, f_desde, f_hasta)
        return {"success": True, "data": lista}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/producto/{nombre}/comparar")
def get_producto_comparar(nombre: str):
    from quantara.graph.database import SessionLocal
    from quantara.graph.queries import comparar_precio_proveedores
    
    db = SessionLocal()
    try:
        lista = comparar_precio_proveedores(db, nombre)
        return {"success": True, "data": lista}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/margen/{producto}")
def get_margen(producto: str):
    from quantara.graph.database import SessionLocal
    from quantara.graph.queries import calcular_margen
    
    db = SessionLocal()
    try:
        resultado = calcular_margen(db, producto)
        return {"success": True, "data": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/precio-venta")
def post_precio_venta(body: PrecioVentaRequest):
    from quantara.graph.database import SessionLocal
    from quantara.graph.queries import registrar_precio_venta
    
    db = SessionLocal()
    try:
        v = registrar_precio_venta(db, body.descripcion, body.precio_venta, body.unidad)
        return {
            "success": True,
            "message": f"{body.descripcion} → {body.precio_venta}€",
            "data": {"id": v.id}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
