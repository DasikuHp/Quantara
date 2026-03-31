import os
import mlflow

# Módulo MLflow Tracker
# Responsabilidad: Registro de experimentos, métricas y modelos usando MLflow de forma local

class QuantaraTracker:
    def __init__(self, experiment_name: str = "quantara_ocr"):
        """Inicializa MLflow en un repositorio local ./mlruns para evitar dependencias remotas."""
        # Configurar tracking local explícito (directorio en raíz de donde se ejecuta)
        tracking_uri = "file://" + os.path.abspath("./mlruns")
        mlflow.set_tracking_uri(tracking_uri)
        
        self.experiment_name = experiment_name
        mlflow.set_experiment(self.experiment_name)
        self.active_run = None

    def start_run(self, run_name: str):
        """Inicia un run para agrupar métricas."""
        self.active_run = mlflow.start_run(run_name=run_name)
        return self.active_run

    def end_run(self):
        """Termina el ciclo de un run."""
        if self.active_run:
            mlflow.end_run()
            self.active_run = None

    def field_accuracy(self, extraido: str, correcto: str) -> float:
        """
        Calcula una medida de precisión entre extracción OCR y corrección.
        En esta versión simple, se basa en exact match normalizado (0.0 o 1.0).
        """
        if extraido is None and correcto is None:
            return 1.0
        if extraido is None or correcto is None:
            return 0.0
            
        str_extraido = str(extraido).strip().lower()
        str_correcto = str(correcto).strip().lower()
        
        return 1.0 if str_extraido == str_correcto else 0.0

    def log_extraction(self, albaran_id: int, campos_extraidos: dict, campos_correctos: dict):
        """
        Reporta individualmente a MLflow la certeza del OCR contrastada sobre campos verídicos.
        """
        auto_started = False
        if not mlflow.active_run():
            self.start_run(run_name=f"extraction_albaran_{albaran_id}")
            auto_started = True
            
        mlflow.log_param("albaran_id", albaran_id)
        
        total_acc = 0.0
        num_campos = 0
        
        for campo, correcto in campos_correctos.items():
            extraido = campos_extraidos.get(campo)
            acc = self.field_accuracy(extraido, correcto)
            
            # Métrica estandarizada para rastreo por campo
            mlflow.log_metric(f"acc_{campo}", acc)
            
            total_acc += acc
            num_campos += 1
            
        if num_campos > 0:
            avg_acc = total_acc / num_campos
            mlflow.log_metric("avg_extraction_accuracy", avg_acc)
            
        if auto_started:
            self.end_run()
            
    def log_model_metrics(self, precision: float, recall: float, f1: float, campo: str):
        """
        Registra el rendimiento general (P/R/F1) del modelo sobre un campo tras un ciclo de evaluación.
        """
        auto_started = False
        if not mlflow.active_run():
            self.start_run(run_name=f"metrics_{campo}")
            auto_started = True
            
        mlflow.log_metric(f"precision_{campo}", precision)
        mlflow.log_metric(f"recall_{campo}", recall)
        mlflow.log_metric(f"f1_{campo}", f1)
        
        if auto_started:
            self.end_run()
