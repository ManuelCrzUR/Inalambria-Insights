import asyncio
from typing import List, Optional
from openai import AsyncOpenAI
from pipeline.stages.classifier.base import PanelVote
from config import settings

ARBITER_SYSTEM_PROMPT = """
Eres el Árbitro Supremo de un sistema de clasificación de SMS en Colombia.
Tu función es entrar en acción cuando dos modelos previos (Mini y Nano) no logran ponerse de acuerdo o tienen baja confianza.

TU MISIÓN:
1. Analizar el mensaje original y el contexto del cliente.
2. Evaluar los votos de los dos jueces previos (Juez 1: gpt-4o-mini, Juez 2: gpt-5-nano).
3. Dar un veredicto definitivo basado en la taxonomía proporcionada.

REGLAS DE ARBITRAJE:
- Si un juez tiene una etiqueta más precisa según la descripción -> Elógela.
- Si ambos fallaron pero el mensaje es claro según la descripción -> Corrígelos con la etiqueta correcta.
- Si el mensaje es GENUINAMENTE AMBIGUO y no hay suficiente contexto para clasificar -> Elige 'ABSTAIN'.
- Debes justificar brevemente tu decisión en el campo 'reasoning'.
"""

ARBITER_USER_PROMPT = """
TAXONOMÍA DISPONIBLE:
{taxonomy_context}

DATOS DEL MENSAJE:
Plantilla: "{template_text}"
Reglas aplicadas: {applied_rules}
Cliente/Sender: {client_name}
Frecuencia: {frequency}

--- VOTOS DEL PANEL (DESACUERDO) ---
Juez 1 (Mini): {label1} (Confianza: {conf1})
Juez 2 (Nano): {label2} (Confianza: {conf2})

Veredicto final:
"""

class Arbiter:
    """
    Componente de mediación de alta inteligencia (gpt-5.4).
    Analiza conflictos en el panel y decide la etiqueta final o se abstiene.
    """

    def __init__(self, api_key: str, taxonomy_data: dict):
        self.client = AsyncOpenAI(api_key=api_key)
        self.taxonomy = taxonomy_data
        # Añadimos ABSTAIN a las etiquetas posibles para el árbitro
        self.labels = [item["label"] for item in taxonomy_data["labels"]] + ["ABSTAIN"]
        
        self.taxonomy_context = "\n".join([
            f"- {item['label']}: {item['description']}" 
            for item in taxonomy_data["labels"]
        ])

    def _get_schema(self):
        return {
            "name": "arbiter_response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "enum": self.labels,
                        "description": "Etiqueta final de la taxonomía o ABSTAIN si es imposible clasificar."
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Nivel de confianza del veredicto final"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Explicación breve de por qué se eligió esta etiqueta sobre las del panel."
                    }
                },
                "required": ["label", "confidence", "reasoning"],
                "additionalProperties": False
            }
        }

    async def arbitrate(
        self, 
        template_text: str, 
        applied_rules: List[str], 
        vote1: PanelVote, 
        vote2: PanelVote,
        client_name: Optional[str] = None,
        frequency: int = 1
    ) -> dict:
        """
        Ejecuta la mediación usando el modelo arbiter configurado.
        """
        try:
            response = await self.client.beta.chat.completions.parse(
                model=settings.MODEL_ARBITER,
                messages=[
                    {"role": "system", "content": ARBITER_SYSTEM_PROMPT},
                    {"role": "user", "content": ARBITER_USER_PROMPT.format(
                        taxonomy_context=self.taxonomy_context,
                        template_text=template_text,
                        applied_rules=applied_rules,
                        client_name=client_name or "Desconocido",
                        frequency=frequency,
                        label1=vote1.label,
                        conf1=vote1.confidence,
                        label2=vote2.label,
                        conf2=vote2.confidence
                    )}
                ],
                response_format=self._get_schema(),
                temperature=0.0
            )
            
            # Devolvemos el objeto real de la respuesta parseada
            return response.choices[0].message.parsed
        except Exception as e:
            # Fallback crítico
            return {
                "label": "ABSTAIN",
                "confidence": 0.0,
                "reasoning": f"Error técnico en el árbitro: {str(e)}"
            }
