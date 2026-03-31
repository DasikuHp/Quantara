import sys

def test_startup():
    print("--- Test de inicialización de módulos Quantara ---")
    
    # 1. Database Init
    try:
        from quantara.graph.database import init_db
        init_db()
        print("✅ graph.database (init_db ejecutado) OK")
    except Exception as e:
        print(f"❌ graph.database FAILED: {str(e)}")

    # 2. OCR Model (Sin instanciar)
    try:
        from quantara.ocr.donut_model import DonutExtractor
        print("✅ ocr.donut_model (DonutExtractor importado) OK")
    except Exception as e:
        print(f"❌ ocr.donut_model FAILED: {str(e)}")

    # 3. FastAPI App import
    try:
        from quantara.main import app
        print("✅ main (app importada) OK")
    except Exception as e:
        print(f"❌ main FAILED: {str(e)}")

    # 4. MLflow Tracker import (Sin instanciar)
    try:
        from quantara.evaluation.mlflow_tracker import QuantaraTracker
        print("✅ evaluation.mlflow_tracker (QuantaraTracker importado) OK")
    except Exception as e:
        print(f"❌ evaluation.mlflow_tracker FAILED: {str(e)}")

if __name__ == "__main__":
    test_startup()
