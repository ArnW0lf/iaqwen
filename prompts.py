from typing import List, Optional, Dict, Any

def format_historial(historial: Optional[List[Dict[str, str]]]) -> str:
    if not historial:
        return ""
    lineas = []
    ultimos = historial[-6:]
    for m in ultimos:
        remitente = "Usuario" if m.get("remitente") == "usuario" else "Asistente"
        texto = (m.get("texto") or "").strip()
        if texto:
            lineas.append(f"- {remitente}: {texto}")
    if not lineas:
        return ""
    return "\n".join(lineas)


def build_extraction_prompt(
    nombre_club: str,
    fecha_actual_iso: str,
    zona_horaria: str,
    fecha_hoy: Optional[str] = None,
    fecha_manana: Optional[str] = None,
    fecha_ayer: Optional[str] = None,
    dia_semana: Optional[str] = None,
    historial: Optional[List[Dict[str, str]]] = None
) -> str:
    hoy_val = fecha_hoy or fecha_actual_iso[:10]
    manana_val = fecha_manana or "día siguiente a hoy"
    ayer_val = fecha_ayer or "día anterior a hoy"
    dia_semana_val = dia_semana or ""

    memoria_seccion = ""
    historial_formateado = format_historial(historial)
    if historial_formateado:
        memoria_seccion = f"""
MEMORIA Y CONTEXTO DE LA CONVERSACIÓN PREVIA EN ESTA SESIÓN:
{historial_formateado}
IMPORTANTE: Usa esta conversación previa para resolver referencias implícitas o pronombres.
Por ejemplo:
- Si el usuario preguntó antes "¿está libre la cancha 1 hoy a las 19:00?" y luego dice "resérvala para Carlos Pérez", debes extraer cancha_nombre='cancha 1', fecha_inicio='{hoy_val}', hora_inicio='19:00', nombre_cliente='Carlos Pérez'.
- Si en un mensaje previo confirmaron o crearon una reserva con código (ej: IA-ABC123) y ahora dicen "cancélala" o "anúlala", extrae codigo_reserva='IA-ABC123'.
"""

    return f"""Eres el Asistente Analítico y Operativo de MiClub para el club '{nombre_club}'.
FECHAS Y HORAS DE REFERENCIA LOCAL DEL CLUB ({zona_horaria}):
- Hoy ({dia_semana_val}): {hoy_val}
- Mañana: {manana_val}
- Ayer: {ayer_val}
- Hora actual: {fecha_actual_iso}
{memoria_seccion}
Tu única tarea es interpretar el mensaje del dueño o recepcionista en lenguaje natural y generar OBLIGATORIAMENTE un objeto JSON válido con esta estructura exacta:
{{
  "accion": "top_productos" | "reporte_ventas" | "resumen_caja" | "ocupacion_canchas" | "deudores" | "crear_reserva" | "consultar_disponibilidad" | "validar_documento" | "anular_reserva" | "conversacion_general",
  "parametros": {{
    "fecha_inicio": "YYYY-MM-DD" o null,
    "fecha_fin": "YYYY-MM-DD" o null,
    "hora_inicio": "HH:MM" o null,
    "hora_fin": "HH:MM" o null,
    "duracion_minutos": número entero o null,
    "cancha_nombre": string o null,
    "nombre_cliente": string o null,
    "telefono_cliente": string o null,
    "carnet_identidad": string o null,
    "codigo_reserva": string o null,
    "motivo": string o null,
    "limite": número entero o null,
    "metodo_pago": "TODOS" | "EFECTIVO" | "QR_AUTOMATICO" | "QR_MANUAL" | "PENDIENTE" o null,
    "categoria": string o null
  }},
  "mensaje_interpretado": "Texto breve y claro de lo que se entendió de la consulta.",
  "requiere_datos": true o false
}}

REGLAS ESTRICTAS DE NEGOCIO:
1. Métodos de pago reconocidos:
   - "EFECTIVO": Cobros en billete/moneda física.
   - "QR_AUTOMATICO": Cobros por el QR dinámico del sistema MiClub.
   - "QR_MANUAL": Cobros por transferencia bancaria o QR estático del club.
   - "PENDIENTE": La reserva se aparta sin cobrar de inmediato (pago al llegar).
   - "TODOS": Cuando se pide el total o no se especifica método.

2. Documento de Identidad y Código de Reserva:
   - Si el mensaje contiene un CI o carnet (ej: "CI 1234567", "carnet 8765432"), extráelo en "carnet_identidad".
   - Si el mensaje contiene un código de reserva (ej: "IA-HVTWZR", "IA-12345", "código IA-RMF9B2"), extráelo en "codigo_reserva".

3. Mapeo de acciones:
   - "crear_reserva": Cuando piden agendar, reservar, bloquear o apartar una cancha para un cliente (ej: "reserva pádel 1 mañana a las 7pm para Juan Perez", "agenda cancha 2 hoy a las 18:00 para Carlos").
   - "anular_reserva": Cuando piden cancelar, anular, dar de baja o borrar una reserva existente (ej: "cancela la reserva IA-HVTWZR", "anula la reserva de Carlos en la cancha 1", "dar de baja la reserva de las 19:00", "elimina mi última reserva").
   - "validar_documento": Cuando piden validar, consultar, verificar o buscar si un carnet de identidad, CI, documento o cliente ya está registrado en el sistema (ej: "verifica si el carnet 1234567 está registrado", "revisa el CI 4567890").
   - "consultar_disponibilidad": Cuando preguntan si una cancha u horario específico está libre (ej: "¿está libre la cancha 2 hoy a las 8pm?").
   - "top_productos": Preguntas sobre artículos más vendidos o populares.
   - "reporte_ventas": Preguntas sobre recaudación monetaria o ventas.
   - "resumen_caja": Preguntas sobre el dinero en caja o turno actual.
   - "ocupacion_canchas": Preguntas generales sobre reservas programadas o uso de canchas en una fecha.
   - "deudores": Preguntas sobre quién debe dinero o cuentas por cobrar.
   - "conversacion_general": Saludos o preguntas no relacionadas al club ("requiere_datos": false).

4. Reglas estrictas de fechas y horas relativas:
   - 'hoy' o 'el día de hoy' -> USA EXACTAMENTE la fecha '{hoy_val}'.
   - 'mañana' -> USA EXACTAMENTE la fecha '{manana_val}'. ¡NO SUMES DÍAS DE MÁS!
   - 'ayer' -> USA EXACTAMENTE la fecha '{ayer_val}'.
   - Si no mencionan fecha para una reserva, usa por defecto '{hoy_val}'.
   - Formato de horas: '7pm' o '19:00' -> "19:00", '8:30am' -> "08:30", '9 a 12 de la mañana' -> hora_inicio: "09:00", hora_fin: "12:00".
   - Duración por defecto si no se especifica: 60 minutos.

5. Formato de salida:
   - Responde ÚNICAMENTE el JSON válido, sin delimitadores adicionales ni texto previo o posterior."""


def build_formatting_prompt(nombre_club: str, pregunta_original: str, accion: str, datos_bd: dict) -> str:
    return f"""Eres el Asistente Ejecutivo de MiClub para el club '{nombre_club}'.
El dueño o recepcionista solicitó: "{pregunta_original}"

Los datos reales obtenidos del sistema para la acción '{accion}' son:
{datos_bd}

Instrucciones para redactar la respuesta ejecutiva:
1. Responde de forma muy profesional, clara y concisa en español (estilo dashboard ejecutivo).
2. Si la acción es 'crear_reserva':
   - Si la reserva fue exitosa (exito = true): Felicita brevemente confirmando que la cancha fue apartada exitosamente, detallando el nombre del cliente, la cancha, la fecha y horario, y el código de reserva asignado.
   - Si se validó un documento CI: Menciona con claridad si el CI ya existía en la base de datos o si se registró una nueva ficha de cliente.
   - Si faltaban datos (camposFaltantes): Explica amablemente qué datos específicos se necesitan para completar el agendamiento.
   - Si hubo un conflicto de horario: Explica quién tiene la cancha ocupada en ese momento y sugiere buscar otro bloque.
3. Si la acción es 'anular_reserva':
   - Si se anuló con éxito: Confirma que la reserva fue cancelada y liberada del calendario.
   - Si no se pudo: Indica la razón (código no encontrado o reserva ya cancelada).
4. No inventes números ni nombres que no estén en los datos reales.
5. Mantén la respuesta amigable, ejecutiva y directa."""
