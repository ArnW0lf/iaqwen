import requests
import json
import time

SERVER_URL = "http://localhost:8000"
SECRET_KEY = "miclub_secreto_super_seguro_2026"

def test_health():
    print("Testing /health...")
    res = requests.get(f"{SERVER_URL}/health")
    print(f"Status: {res.status_code}, Body: {res.json()}")
    assert res.status_code == 200

def test_analizar():
    print("\nTesting /api/v1/analizar...")
    payload = {
        "mensaje": "cuales son los 3 productos mas vendidos de este fin de semana?",
        "contexto": {
            "clubId": "cmlis9w8300031hel4tto9dq2",
            "nombreClub": "Club de arnulfo velasquez paz",
            "fechaActual": "2026-10-04T21:00:00",
            "zonaHoraria": "America/La_Paz"
        }
    }
    headers = {
        "X-AI-SECRET-KEY": SECRET_KEY
    }
    t0 = time.time()
    res = requests.post(f"{SERVER_URL}/api/v1/analizar", json=payload, headers=headers)
    t1 = time.time()
    print(f"Status: {res.status_code} in {t1 - t0:.2f}s")
    print(f"Response: {json.dumps(res.json(), indent=2, ensure_ascii=False)}")
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True

def test_formatear():
    print("\nTesting /api/v1/formatear-respuesta...")
    payload = {
        "preguntaOriginal": "cuales son los 3 productos mas vendidos de este fin de semana?",
        "accion": "top_productos",
        "datosBd": {
            "fecha_inicio": "2026-10-03",
            "fecha_fin": "2026-10-04",
            "total_unidades": 18,
            "productos": [
                {"nombre": "Gatorade 500ml", "cantidad": 7, "totalRecaudado": 70.0},
                {"nombre": "Empanada de Carne", "cantidad": 6, "totalRecaudado": 36.0},
                {"nombre": "Agua Mineral 600ml", "cantidad": 5, "totalRecaudado": 25.0}
            ]
        },
        "contexto": {
            "clubId": "cmlis9w8300031hel4tto9dq2",
            "nombreClub": "Club de arnulfo velasquez paz",
            "fechaActual": "2026-10-04T21:00:00",
            "zonaHoraria": "America/La_Paz"
        }
    }
    headers = {
        "X-AI-SECRET-KEY": SECRET_KEY
    }
    t0 = time.time()
    res = requests.post(f"{SERVER_URL}/api/v1/formatear-respuesta", json=payload, headers=headers)
    t1 = time.time()
    print(f"Status: {res.status_code} in {t1 - t0:.2f}s")
    print(f"Response: {json.dumps(res.json(), indent=2, ensure_ascii=False)}")
    assert res.status_code == 200

if __name__ == "__main__":
    test_health()
    test_analizar()
    test_formatear()
    print("\nAll tests passed successfully!")
