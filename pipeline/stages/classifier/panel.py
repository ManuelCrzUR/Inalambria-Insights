import asyncio
import json
from typing import List, Tuple, Optional
from openai import AsyncOpenAI
from pipeline.stages.classifier.base import PanelVote
from config import settings

# --- Prompts ---

PANEL_SYSTEM_PROMPT = """
Eres un clasificador experto de mensajes SMS comerciales en Colombia, especializado en Credit Scoring e Insights Financieros.
Tu tarea es clasificar la plantilla de mensaje proporcionada en EXACTAMENTE una de las categorías definidas.

REGLAS CRÍTICAS:
1. Debes usar SOLO los identificadores de etiqueta proporcionados (ej: 'banking::otp_2fa').
2. Guíate por la descripción de cada etiqueta para asegurar la precisión.
3. Los 'applied_rules' indican qué datos variables se encontraron:
   - ['amount'] -> Alta probabilidad de transacciones, créditos o servicios públicos.
   - ['otp'] -> Casi siempre banking::otp_2fa.
   - ['date', 'url'] -> Notificaciones, recordatorios o seguimiento.
4. Sé honesto con la confianza (0.0 a 1.0). No exageres si el mensaje es ambiguo.
"""

PANEL_USER_PROMPT = """
TAXONOMÍA DISPONIBLE:
{taxonomy_context}

DATOS DEL MENSAJE:
Plantilla: "{template_text}"
Reglas aplicadas: {applied_rules}
Cliente/Sender: {client_name}

Clasifica esta plantilla.
"""

class HeterogeneousPanel:
    """
    Gestiona el panel de jueces heterogéneo (gpt-4o-mini + gpt-5-nano).
    Ejecuta las peticiones de forma asíncrona y paralela.
    """

    def __init__(self, api_key: str, taxonomy_data: dict):
        self.client = AsyncOpenAI(api_key=api_key)
        self.taxonomy = taxonomy_data
        self.labels = [item["label"] for item in taxonomy_data["labels"]]
        
        # Generar contexto de taxonomía para el prompt
        self.taxonomy_context = "\n".join([
            f"- {item['label']}: {item['description']}" 
            for item in taxonomy_data["labels"]
        ])

    def _get_schema(self):
        """Define el esquema de Structured Output para OpenAI."""
        return {
            "name": "classification_response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "enum": self.labels
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Nivel de confianza de 0.0 a 1.0"
                    }
                },
                "required": ["label", "confidence"],
                "additionalProperties": False
            }
        }

    async def _call_judge(self, model: str, template_text: str, applied_rules: List[str], client_name: str) -> PanelVote:
        """Realiza una llamada individual a un modelo."""
        try:
            response = await self.client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": PANEL_SYSTEM_PROMPT},
                    {"role": "user", "content": PANEL_USER_PROMPT.format(
                        taxonomy_context=self.taxonomy_context,
                        template_text=template_text,
                        applied_rules=applied_rules,
                        client_name=client_name or "Desconocido"
                    )}
                ],
                response_format=self._get_schema(),
                temperature=0.0 # Garantizar determinismo
            )
            
            result = response.choices[0].message.parsed
            return PanelVote(
                label=result.label,
                confidence=result.confidence,
                model_name=model
            )
        except Exception as e:
            # En caso de error, devolvemos un voto nulo para que el árbitro decida
            return PanelVote(
                label="error",
                confidence=0.0,
                model_name=model,
                raw_response={"error": str(e)}
            )

    async def classify_parallel(self, template_text: str, applied_rules: List[str], client_name: Optional[str] = None) -> Tuple[PanelVote, PanelVote]:
        """
        Ejecuta Juez 1 (Mini) y Juez 2 (Nano) en paralelo.
        """
        # settings.MODEL_PANEL_1 y settings.MODEL_PANEL_2 deben estar definidos
        vote1, vote2 = await asyncio.gather(
            self._call_judge(settings.MODEL_PANEL_1, template_text, applied_rules, client_name),
            self._call_judge(settings.MODEL_PANEL_2, template_text, applied_rules, client_name)
        )
        return vote1, vote2
