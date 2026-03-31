PID: Sistema Quantara para Gestión Inteligente de Albaranes

1. Objetivos del Proyecto


Chatbot ligero con OCR:

Analizar albaranes y crear resúmenes.
Crear una base de datos estructurada e interconectada que posibilite su uso posterior.


OCR con razonamiento incluido:

Entender los campos de los albaranes.
Optimizar cómo se guarda y utiliza la información.


2. Herramientas

OCR: Donut-base (end-to-end).
Base de Datos: SQLite (ligero y local).
Evaluación: MLflow (métricas por campo).
Alternativas consideradas:

PaddleOCR (para documentos estructurados).
LayoutLMv3 (para albaranes con tablas o secciones fijas).


3. Alcance
Tipos de Albaranes:

Cada albarán es diferente dependiendo del proveedor.
Usuarios Concurrentes:

1-3 usuarios.

4. Decisión sobre OCR
Elige Donut-base si:

Tus albaranes son muy variados (cada proveedor usa un formato distinto).
Quieres simplificar el pipeline (1 modelo en lugar de OCR + NLP).
No tienes recursos para etiquetar miles de ejemplos (Donut funciona bien con pocos datos).
Elige LayoutLMv3 si:

Tus albaranes tienen tablas o secciones fijas (ej: siempre hay una tabla de productos con columnas "Cantidad", "Descripción", "Precio").
Puedes invertir tiempo en etiquetar datos para fine-tuning.

5. Evaluación

Probar el modelo con un conjunto de prueba (albaranes no usados en el entrenamiento).
Métricas de precisión (ej: % de campos correctos) para medir la mejora.
Herramientas: Weights & Biases o TensorBoard.
Almacenamiento de feedback: Guardar las correcciones en una tabla feedback con los campos:

albaran_id, campo, valor_extraido, valor_correcto, fecha_correccion.


6. Necesidades

Dataset de entrenamiento: Colección de albaranes históricos (PDFs, imágenes) con sus campos etiquetados manualmente.
Modelo base: Un modelo preentrenado de NLP (ej: bert-base-multilingual-cased o roberta-base).
Herramientas: Librerías como transformers de Hugging Face, spaCy, o plataformas como Label Studio para etiquetar datos.
Entrenar con transformers o spaCy usando los datos etiquetados.

7. Módulos del Sistema

Quantara Core: Motor de razonamiento documental.
Quantara Graph: Base de datos interconectada.
Quantara OCR: Módulo de lectura inteligente.
