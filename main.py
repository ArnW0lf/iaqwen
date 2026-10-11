import os
import json
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, Header, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests

import config
from prompts import build_extraction_prompt, build_formatting_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("miclub-ai-server")

app = FastAPI(
    title="MiClub AI Server",
    description="Servidor local independiente para inferencia con Qwen 2.5 y Ollama",
    version="1.0.0"
)

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
    fechaHoy: Optional[str] = None
    fechaManana: Optional[str] = None
    fechaAyer: Optional[str] = None
    diaSemana: Optional[str] = None


class AnalizarRequest(BaseModel):
    mensaje: str = Field(..., description="Pregunta del dueño en lenguaje natural")
    contexto: ContextoConsulta
    historial: Optional[list] = Field(default=[], description="Mensajes previos de la conversación en la sesión actual")


class FormatearRequest(BaseModel):
    preguntaOriginal: str
    accion: str
    datosBd: Dict[str, Any]
    contexto: ContextoConsulta
    historial: Optional[list] = Field(default=[])


@app.get("/health")
def health_check():
    """Verifica el estado del servicio y la conectividad con Ollama"""
    ollama_ok = False
    model_ok = False
    try:
        res = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=5)
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
    historial_dicts = [
        {"remitente": m.get("remitente", "usuario"), "texto": m.get("texto", "")} if isinstance(m, dict)
        else {"remitente": getattr(m, "remitente", "usuario"), "texto": getattr(m, "texto", "")}
        for m in (req.historial or [])
    ]

    system_prompt = build_extraction_prompt(
        nombre_club=req.contexto.nombreClub,
        fecha_actual_iso=req.contexto.fechaActual,
        zona_horaria=req.contexto.zonaHoraria,
        fecha_hoy=req.contexto.fechaHoy,
        fecha_manana=req.contexto.fechaManana,
        fecha_ayer=req.contexto.fechaAyer,
        dia_semana=req.contexto.diaSemana,
        historial=historial_dicts
    )

    ollama_payload = {
        "model": config.MODEL_NAME,
        "system": system_prompt,
        "prompt": req.mensaje,
        "stream": False,
        "format": "json",
        "keep_alive": "60m",
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
            timeout=60
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
    """Redacta una respuesta ejecutiva y natural en español con base en los datos de la base de datos"""
    system_prompt = build_formatting_prompt(
        nombre_club=req.contexto.nombreClub,
        pregunta_original=req.preguntaOriginal,
        accion=req.accion,
        datos_bd=req.datosBd
    )

    ollama_payload = {
        "model": config.MODEL_NAME,
        "system": system_prompt,
        "prompt": f"Redacta el informe para el dueño basado en la pregunta: '{req.preguntaOriginal}'",
        "stream": False,
        "keep_alive": "60m",
        "options": {
            "temperature": 0.3,
            "num_predict": 400
        }
    }

    try:
        logger.info(f"Formateando respuesta para acción '{req.accion}'")
        res = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json=ollama_payload,
            timeout=60
        )
        res.raise_for_status()
        texto_redactado = res.json().get("response", "").strip()
        return {
            "ok": True,
            "respuestaTexto": texto_redactado
        }
    except requests.RequestException as re:
        logger.error(f"Error comunicando con Ollama al formatear: {re}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo comunicar con el motor de inferencia Ollama al formatear respuesta: {str(re)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.AI_SERVER_HOST, port=config.AI_SERVER_PORT, reload=True)
