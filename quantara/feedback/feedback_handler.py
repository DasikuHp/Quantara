import json
from sqlalchemy.orm import Session
from quantara.graph import models, queries

# Módulo Feedback Handler
# Responsabilidad: Procesar correcciones de usuarios para reentrenar/ajustar el sistema

def process_feedback(db: Session, albaran_id: int, campo: str, valor_ocr: str, valor_correcto: str) -> dict:
    """Guarda una corrección en la tabla de feedback y retorna confirmación."""
    nuevo_feedback = queries.save_feedback(
        db=db,
        albaran_id=albaran_id,
        campo=campo,
        valor_ocr=valor_ocr,
        valor_correcto=valor_correcto
    )
    return {
        "success": True,
        "message": f"Feedback registrado exitosamente para el campo '{campo}'",
        "feedback_id": nuevo_feedback.id
    }

def get_pending_feedback(db: Session) -> list:
    """Lista las correcciones que aún no han sido aplicadas a un ciclo de fine-tuning."""
    return db.query(models.Feedback).filter(models.Feedback.aplicado == False).all()

def mark_feedback_applied(db: Session, feedback_id: int) -> bool:
    """Marca un registro específico de feedback como ya aplicado."""
    feedback = db.query(models.Feedback).filter(models.Feedback.id == feedback_id).first()
    if feedback:
        feedback.aplicado = True
        db.commit()
        return True
    return False

def export_feedback_for_training(db: Session, output_path: str) -> int:
    """
    Exporta el feedback pendiente a JSONL para uso futuro en entrenamiento.
    No borra el feedback de la DB, solo lo marca como aplicado.
    """
    pending = get_pending_feedback(db)
    if not pending:
        return 0

    records_exported = 0
    with open(output_path, 'a', encoding='utf-8') as f:
        for fb in pending:
            # Recuperar referencia de la imagen origen desde el Albarán
            albaran = db.query(models.Albaran).filter(models.Albaran.id == fb.albaran_id).first()
            imagen_path = albaran.imagen_path if albaran else None
            
            record = {
                "feedback_id": fb.id,
                "albaran_id": fb.albaran_id,
                "imagen_path": imagen_path,
                "campo": fb.campo,
                "valor_ocr": fb.valor_ocr,
                "valor_correcto": fb.valor_correcto
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
            # Mantener persistencia marcándolo en vez de eliminarlo
            fb.aplicado = True
            records_exported += 1
            
    db.commit()
    return records_exported
