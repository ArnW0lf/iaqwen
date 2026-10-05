import json
import logging
from typing import Any, Dict, Optional
import requests
from fastapi import FastAPI, Header, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from prompts import build_extraction_prompt, build_formatting_prompt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("miclub-ai")

app = FastAPI(
    title="MiClub AI Server (Qwen 2.5)",
    description="Servidor de IA independiente para consultas analíticas en lenguaje natural",
    version="1.0.0"
)

# Habilitar CORS para peticiones desde Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_secret_key(
    x_ai_secret_key: Optional[str] = Header(None, alias="X-AI-SECRET-KEY"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    key = x_ai_secret_key or x_api_key
    if not key or key != config.AI_API_SECRET:
        logger.warning(f"Intento de acceso no autorizado (clave inválida o ausente: '{key}')")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de autorización no válida o ausente (X-AI-SECRET-KEY)"
        )
    return key


class ContextoConsulta(BaseModel):
    clubId: str
    nombreClub: str
    fechaActual: str
    zonaHoraria: str = "America/La_Paz"


class AnalizarRequest(BaseModel):
    mensaje: str = Field(..., description="Pregunta del dueño en lenguaje natural")
    contexto: ContextoConsulta


class FormatearRequest(BaseModel):
    preguntaOriginal: str
    accion: str
    datosBd: Dict[str, Any]
    contexto: ContextoConsulta


@app.get("/health")
def health_check():
    """Verifica el estado del servicio y la conectividad con Ollama"""
    ollama_ok = False
    model_ok = False
    try:
        res = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=3)
        if res.status_code == 200:
            ollama_ok = True
            models = res.json().get("models", [])
            model_ok = any(config.MODEL_NAME in m.get("name", "") for m in models)
    except Exception as e:
        logger.error(f"Error conectando a Ollama: {e}")

    return {
        "status": "online",
        "service": "miclub-ai-server",
        "model": config.MODEL_NAME,
        "ollama_connected": ollama_ok,
        "model_available": model_ok
    }


@app.post("/api/v1/analizar")
def analizar_consulta(req: AnalizarRequest, _auth: str = Depends(verify_secret_key)):
    """Interpreta la pregunta en lenguaje natural y extrae la intención y parámetros en JSON"""
    system_prompt = build_extraction_prompt(
        nombre_club=req.contexto.nombreClub,
        fecha_actual_iso=req.contexto.fechaActual,
        zona_horaria=req.contexto.zonaHoraria
    )

    ollama_payload = {
        "model": config.MODEL_NAME,
        "system": system_prompt,
        "prompt": req.mensaje,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,  # Temperatura baja para máxima precisión en fechas y JSON
            "num_predict": 300
        }
    }

    try:
        logger.info(f"Analizando consulta para club '{req.contexto.nombreClub}': '{req.mensaje}'")
        res = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json=ollama_payload,
            timeout=30
        )
        res.raise_for_status()
        raw_response = res.json().get("response", "{}")
        parsed_json = json.loads(raw_response)
        return {
            "ok": True,
            "analisis": parsed_json
        }
    except json.JSONDecodeError as jde:
        logger.error(f"Error decodificando JSON de Qwen: {jde} -> Raw: {raw_response}")
        return {
            "ok": False,
            "error": "El modelo no generó un JSON válido",
            "raw": raw_response
        }
    except requests.RequestException as re:
        logger.error(f"Error comunicando con Ollama: {re}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo comunicar con el motor de inferencia Ollama: {str(re)}"
        )


@app.post("/api/v1/formatear-respuesta")
def formatear_respuesta(req: FormatearRequest, _auth: str = Depends(verify_secret_key)):
    """Toma los datos reales consultados de la BD y redacta una respuesta conversacional y ejecutiva"""
    system_prompt = build_formatting_prompt(
        nombre_club=req.contexto.nombreClub,
        pregunta_original=req.preguntaOriginal,
        accion=req.accion,
        datos_bd=req.datosBd
    )

    ollama_payload = {
        "model": config.MODEL_NAME,
        "system": system_prompt,
        "prompt": "Redacta el resumen ejecutivo para el dueño del club basándote estrictamente en los datos.",
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 450
        }
    }

    try:
        logger.info(f"Formateando respuesta para acción '{req.accion}'")
        res = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json=ollama_payload,
            timeout=30
        )
        res.raise_for_status()
        texto_generado = res.json().get("response", "").strip()
        return {
            "ok": True,
            "respuestaTexto": texto_generado
        }
    except requests.RequestException as re:
        logger.error(f"Error comunicando con Ollama al formatear: {re}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error en Ollama al redactar respuesta: {str(re)}"
        )


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Iniciando MiClub AI Server en http://0.0.0.0:{config.PORT} con modelo {config.MODEL_NAME}")
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=True)
