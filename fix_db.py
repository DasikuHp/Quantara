import sqlite3
import os
from quantara.config import DB_PATH   # usar la misma ruta que el sistema

db_path = DB_PATH
os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = None

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Crear tablas
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        cif TEXT,
        direccion TEXT,
        telefono TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS albaranes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id INTEGER REFERENCES proveedores(id),
        numero_albaran TEXT,
        fecha DATE,
        fecha_vencimiento DATE,
        total REAL,
        iva_total REAL,
        base_imponible REAL,
        imagen_path TEXT,
        procesado_ok BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        albaran_id INTEGER REFERENCES albaranes(id),
        descripcion TEXT,
        cantidad REAL,
        unidad TEXT,
        precio_unitario REAL,
        iva_pct REAL,
        total_linea REAL
    );

    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        albaran_id INTEGER REFERENCES albaranes(id),
        campo TEXT NOT NULL,
        valor_ocr TEXT,
        valor_correcto TEXT,
        aplicado BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()

    # Mostrar tablas creadas
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("Tablas creadas:")
    for row in cur.fetchall():
        print(" -", row[0])

    # Mostrar proveedores
    cur.execute("SELECT * FROM proveedores")
    print("\nProveedores:")
    for row in cur.fetchall():
        print(" ", row)

    # Mostrar albaranes
    cur.execute("SELECT id, numero_albaran, fecha, total FROM albaranes")
    print("\nAlbaranes:")
    for row in cur.fetchall():
        print(" ", row)

except sqlite3.Error as e:
    print(f"Error en la base de datos: {e}")

finally:
    if conn:
        conn.close()