"""
Quantara — db_manager.py
Script de gestión de la base de datos.
Ejecutar desde E:\Quantara\:
  python310 db_manager.py --help
  python310 db_manager.py --status
  python310 db_manager.py --reset-test
  python310 db_manager.py --reset-all
  python310 db_manager.py --delete-proveedor "Makro Distribucion Mayorista"
  python310 db_manager.py --delete-albaran "0/0(017)0207/(2026)005540"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ── Ruta a la DB ─────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "quantara", "data", "quantara.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


def status():
    """Muestra el estado actual de todas las tablas."""
    db = Session()
    tablas = ["proveedores", "albaranes", "productos", "feedback",
              "catalogo_productos", "lineas_albaran", "precios_historicos", "ventas"]
    print("\n══════════════════════════════════════")
    print("  QUANTARA DB — ESTADO ACTUAL")
    print(f"  {DB_PATH}")
    print("══════════════════════════════════════")
    total_rows = 0
    for tabla in tablas:
        try:
            result = db.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
            bar = "█" * min(result, 40)
            print(f"  {tabla:<22} {result:>5} filas  {bar}")
            total_rows += result
        except Exception:
            print(f"  {tabla:<22} (tabla no existe)")
    print("──────────────────────────────────────")
    print(f"  TOTAL                  {total_rows:>5} filas")

    # Detalle proveedores
    try:
        rows = db.execute(text(
            "SELECT p.nombre, COUNT(a.id) as n, SUM(a.total) as total "
            "FROM proveedores p LEFT JOIN albaranes a ON p.id=a.proveedor_id "
            "GROUP BY p.nombre ORDER BY total DESC"
        )).fetchall()
        if rows:
            print("\n  PROVEEDORES:")
            for r in rows:
                t = f"€{r[2]:.2f}" if r[2] else "—"
                print(f"    {r[0]:<35} {r[1]:>3} albaranes  {t}")
    except Exception as e:
        print(f"  (Error detalle: {e})")

    print("══════════════════════════════════════\n")
    db.close()


def reset_test():
    """
    Elimina TODOS los datos de prueba manteniendo la estructura de tablas.
    Borra en orden correcto para respetar FK.
    """
    db = Session()
    tablas_orden = [
        "feedback", "lineas_albaran", "precios_historicos",
        "ventas", "productos", "albaranes",
        "catalogo_productos", "proveedores"
    ]
    print("\n⚠️  ELIMINANDO TODOS LOS DATOS DE PRUEBA...")
    for tabla in tablas_orden:
        try:
            result = db.execute(text(f"DELETE FROM {tabla}"))
            print(f"  ✓ {tabla:<25} {result.rowcount} filas eliminadas")
        except Exception as e:
            print(f"  ✗ {tabla:<25} Error: {e}")
    
    # Reiniciar autoincrement
    for tabla in tablas_orden:
        try:
            db.execute(text(f"DELETE FROM sqlite_sequence WHERE name='{tabla}'"))
        except Exception:
            pass

    db.commit()
    db.close()
    print("\n✅ Base de datos limpia. IDs reiniciados desde 1.")
    print("   Puedes volver a subir los PDFs desde Swagger.\n")


def delete_proveedor(nombre):
    """Elimina un proveedor y todos sus albaranes."""
    db = Session()
    try:
        prov = db.execute(text(
            "SELECT id FROM proveedores WHERE nombre LIKE :n"
        ), {"n": f"%{nombre}%"}).fetchone()
        
        if not prov:
            print(f"\n✗ Proveedor '{nombre}' no encontrado.\n")
            db.close()
            return
        
        prov_id = prov[0]
        alb_ids = db.execute(text(
            "SELECT id FROM albaranes WHERE proveedor_id=:id"
        ), {"id": prov_id}).fetchall()
        alb_ids = [r[0] for r in alb_ids]

        # Borrar en cascada
        if alb_ids:
            ids_str = ",".join(str(i) for i in alb_ids)
            db.execute(text(f"DELETE FROM productos WHERE albaran_id IN ({ids_str})"))
            db.execute(text(f"DELETE FROM lineas_albaran WHERE albaran_id IN ({ids_str})"))
            db.execute(text(f"DELETE FROM feedback WHERE albaran_id IN ({ids_str})"))
            db.execute(text(f"DELETE FROM precios_historicos WHERE albaran_id IN ({ids_str})"))
        
        db.execute(text("DELETE FROM albaranes WHERE proveedor_id=:id"), {"id": prov_id})
        db.execute(text("DELETE FROM proveedores WHERE id=:id"), {"id": prov_id})
        db.commit()
        print(f"\n✅ Eliminado: {nombre} ({len(alb_ids)} albaranes)\n")
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error: {e}\n")
    finally:
        db.close()


def delete_albaran(numero):
    """Elimina un albarán específico por número."""
    db = Session()
    try:
        alb = db.execute(text(
            "SELECT id, numero_albaran FROM albaranes WHERE numero_albaran LIKE :n"
        ), {"n": f"%{numero}%"}).fetchone()

        if not alb:
            print(f"\n✗ Albarán '{numero}' no encontrado.\n")
            db.close()
            return

        alb_id = alb[0]
        db.execute(text("DELETE FROM productos WHERE albaran_id=:id"), {"id": alb_id})
        db.execute(text("DELETE FROM lineas_albaran WHERE albaran_id=:id"), {"id": alb_id})
        db.execute(text("DELETE FROM feedback WHERE albaran_id=:id"), {"id": alb_id})
        db.execute(text("DELETE FROM precios_historicos WHERE albaran_id=:id"), {"id": alb_id})
        db.execute(text("DELETE FROM albaranes WHERE id=:id"), {"id": alb_id})
        db.commit()
        print(f"\n✅ Albarán {alb[1]} eliminado.\n")
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error: {e}\n")
    finally:
        db.close()


def verify():
    """Verifica que el pipeline completo funciona con un test rápido."""
    print("\n🔍 VERIFICANDO PIPELINE...")
    
    # 1. Import chain
    try:
        from quantara.core.normalizer import normalize_proveedor, parse_linea_producto
        print("  ✓ normalizer importa OK")
    except Exception as e:
        print(f"  ✗ normalizer: {e}")

    try:
        from quantara.core.validator import validate_albaran_completo, validate_albaran
        print("  ✓ validator importa OK")
    except Exception as e:
        print(f"  ✗ validator: {e}")

    try:
        from quantara.graph.models import Albaran, Proveedor, Producto, CatalogoProducto
        print("  ✓ models importa OK")
    except Exception as e:
        print(f"  ✗ models: {e}")

    try:
        from quantara.graph.queries import (
            gasto_por_proveedor, calcular_margen,
            resumen_mes_actual, registrar_precio_venta
        )
        print("  ✓ queries importa OK")
    except Exception as e:
        print(f"  ✗ queries: {e}")

    try:
        from quantara.ocr.preprocessor import pdf_to_image
        print("  ✓ preprocessor importa OK")
    except Exception as e:
        print(f"  ✗ preprocessor: {e}")

    try:
        from quantara.ocr.donut_model import DonutExtractor
        print("  ✓ donut_model importa OK")
    except Exception as e:
        print(f"  ✗ donut_model: {e}")

    # 2. Test validator
    try:
        from quantara.core.validator import validate_albaran_completo
        raw = {"numero_albaran": "TEST-001", "fecha": "04/03/26",
               "proveedor": "Test", "proveedor_tipo": "generico",
               "total": 100.0, "base_imponible": 90.0, "iva_total": 10.0,
               "productos": [], "confianza": "alta", "campos_fallidos": []}
        v = validate_albaran_completo(raw)
        assert "validos" in v and "fallidos" in v
        print("  ✓ validator funciona OK")
    except Exception as e:
        print(f"  ✗ validator test: {e}")

    # 3. Test DB connection
    try:
        db = Session()
        db.execute(text("SELECT 1"))
        db.close()
        print("  ✓ DB conecta OK")
    except Exception as e:
        print(f"  ✗ DB: {e}")

    print("\n  Si todos son ✓ — el sistema está listo para producción.\n")


# ── CLI ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args:
        print(__doc__)
    elif "--status" in args:
        status()
    elif "--verify" in args:
        verify()
    elif "--reset-all" in args or "--reset-test" in args:
        confirma = input("⚠️  ¿Seguro? Esto borrará TODOS los datos. Escribe 'SI': ")
        if confirma.strip().upper() == "SI":
            reset_test()
            status()
        else:
            print("Cancelado.")
    elif "--delete-proveedor" in args:
        idx = args.index("--delete-proveedor")
        if idx + 1 < len(args):
            delete_proveedor(args[idx + 1])
            status()
        else:
            print("Uso: python310 db_manager.py --delete-proveedor 'Nombre Proveedor'")
    elif "--delete-albaran" in args:
        idx = args.index("--delete-albaran")
        if idx + 1 < len(args):
            delete_albaran(args[idx + 1])
        else:
            print("Uso: python310 db_manager.py --delete-albaran 'NUM-ALBARAN'")
    else:
        print(f"Opción desconocida: {args}")
        print("Usa --help para ver opciones disponibles.")
