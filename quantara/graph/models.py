from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Date, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship

# Módulo Models (Graph)
# Responsabilidad: Definición de entidades y relaciones usando SQLAlchemy ORM

Base = declarative_base()

class Proveedor(Base):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    cif = Column(String, unique=True, index=True, nullable=True)
    direccion = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    albaranes = relationship("Albaran", back_populates="proveedor")

class Albaran(Base):
    __tablename__ = "albaranes"

    id = Column(Integer, primary_key=True, index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"))
    numero_albaran = Column(String, index=True, nullable=True)
    fecha = Column(String, nullable=True)
    fecha_vencimiento = Column(String, nullable=True)
    total = Column(Float, nullable=True)
    iva_total = Column(Float, nullable=True)
    base_imponible = Column(Float, nullable=True)
    imagen_path = Column(String, nullable=True)
    procesado_ok = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    proveedor = relationship("Proveedor", back_populates="albaranes")
    productos = relationship("Producto", back_populates="albaran")
    feedback = relationship("Feedback", back_populates="albaran")

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    albaran_id = Column(Integer, ForeignKey("albaranes.id"))
    descripcion = Column(String, nullable=True)
    cantidad = Column(Float, nullable=True)
    unidad = Column(String, nullable=True)
    precio_unitario = Column(Float, nullable=True)
    iva_pct = Column(Float, nullable=True)
    total_linea = Column(Float, nullable=True)

    albaran = relationship("Albaran", back_populates="productos")

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    albaran_id = Column(Integer, ForeignKey("albaranes.id"))
    campo = Column(String, nullable=True)
    valor_ocr = Column(String, nullable=True)
    valor_correcto = Column(String, nullable=True)
    aplicado = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    albaran = relationship("Albaran", back_populates="feedback")

class CatalogoProducto(Base):
    __tablename__ = "catalogo_productos"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    nombre_normalizado = Column(String, unique=True, index=True, nullable=False)
    categoria = Column(String, nullable=True)
    unidad_medida = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class LineaAlbaran(Base):
    __tablename__ = "lineas_albaran"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    albaran_id = Column(Integer, index=True, nullable=False)
    catalogo_id = Column(Integer, ForeignKey("catalogo_productos.id"), nullable=False)
    codigo_proveedor = Column(String, nullable=True)
    descripcion_ocr = Column(String, nullable=False)
    cantidad = Column(Float, nullable=True)
    unidad = Column(String, nullable=True)
    precio_unitario = Column(Float, nullable=True)
    importe = Column(Float, nullable=True)
    iva_pct = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PrecioHistorico(Base):
    __tablename__ = "precios_historicos"
    __table_args__ = (
        Index('ix_precios_historicos_catalogo_fecha', 'catalogo_id', 'fecha'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    catalogo_id = Column(Integer, ForeignKey("catalogo_productos.id"), nullable=False)
    proveedor_id = Column(Integer, nullable=False)
    albaran_id = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    fecha = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Venta(Base):
    __tablename__ = "ventas"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    catalogo_id = Column(Integer, ForeignKey("catalogo_productos.id"), nullable=True)
    descripcion = Column(String, nullable=False)
    precio_venta = Column(Float, nullable=False)
    unidad = Column(String, nullable=True)
    fecha_desde = Column(Date, nullable=False)
    activo = Column(Boolean, default=True)
    notas = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
