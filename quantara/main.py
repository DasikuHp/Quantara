from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from quantara.api.routes import router as api_router
from quantara.graph.database import init_db

# Punto de entrada principal de Quantara
# Responsabilidad: Inicialización de la aplicación FastAPI y arranque del servidor

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Evento Startup: Iniciar Base de Datos SQLite/Grafos
    init_db()
    yield
    # Eventos de Shutdown / Limpieza podrían ir aquí

# Instancia FastAPI con título y versión específica
app = FastAPI(title="Quantara API", version="0.1.0", lifespan=lifespan)

# CORS abierto para entorno de desarrollo ágil
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Integración del router de las operaciones de negocio
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
from fastapi.staticfiles import StaticFiles
import os
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
