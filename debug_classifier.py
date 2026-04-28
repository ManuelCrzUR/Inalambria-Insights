#!/usr/bin/env python3
"""
debug_classifier.py - Debug de un clasificador con 1 sola plantilla
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from pipeline.stages.classifier import HeterogeneousPanel, Arbiter
from pipeline.core.models import NormalizedMessage

async def test_single_template():
    """Test con una sola plantilla para debug"""

    # Validar API key
    if not settings.OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY no está configurada")
        return

    print("=" * 70)
    print("DEBUG: Clasificador con 1 plantilla")
    print("=" * 70)
    print(f"Modelos configurados:")
    print(f"  Panel 1: {settings.MODEL_PANEL_1}")
    print(f"  Panel 2: {settings.MODEL_PANEL_2}")
    print(f"  Arbiter: {settings.MODEL_ARBITER}")
    print()

    # Cargar taxonomía
    try:
        with open(settings.TAXONOMY_PATH, 'r', encoding='utf-8') as f:
            taxonomy = json.load(f)
        print(f"✓ Taxonomía cargada: {len(taxonomy['labels'])} etiquetas")
    except Exception as e:
        print(f"✗ Error cargando taxonomía: {e}")
        return

    # Template de prueba
    template_text = "tu código otp es [OTP] válido por [NUM] minutos"
    applied_rules = ["otp", "number"]
    client_name = "Banking Test"

    print(f"\nTemplate a clasificar:")
    print(f"  Texto: {template_text}")
    print(f"  Reglas: {applied_rules}")
    print(f"  Cliente: {client_name}")
    print()

    # Test Panel
    print("-" * 70)
    print("FASE 1: Llamando al Panel (Juez 1 + Juez 2 en paralelo)")
    print("-" * 70)

    try:
        panel = HeterogeneousPanel(api_key=settings.OPENAI_API_KEY, taxonomy_data=taxonomy)
        print(f"✓ Panel inicializado")

        vote1, vote2 = await panel.classify_parallel(
            template_text=template_text,
            applied_rules=applied_rules,
            client_name=client_name
        )

        print(f"\n✓ Respuesta del Panel:")
        print(f"  Juez 1 ({settings.MODEL_PANEL_1}):")
        print(f"    - Label: {vote1.label}")
        print(f"    - Confidence: {vote1.confidence}")
        if vote1.label == "error":
            print(f"    - ERROR: {vote1.raw_response}")

        print(f"  Juez 2 ({settings.MODEL_PANEL_2}):")
        print(f"    - Label: {vote2.label}")
        print(f"    - Confidence: {vote2.confidence}")
        if vote2.label == "error":
            print(f"    - ERROR: {vote2.raw_response}")

        # Verificar acuerdo
        agreement = vote1.label == vote2.label
        min_conf = min(vote1.confidence, vote2.confidence)
        threshold = settings.CLASSIFIER_AGREEMENT_THRESHOLD

        print(f"\n  Análisis de acuerdo:")
        print(f"    - Labels iguales: {agreement}")
        print(f"    - Confianza mínima: {min_conf}")
        print(f"    - Threshold: {threshold}")
        print(f"    - ¿ACUERDO?: {agreement and min_conf >= threshold}")

    except Exception as e:
        print(f"✗ Error en Panel: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test Arbiter (si no hay acuerdo)
    print("\n" + "-" * 70)
    print("FASE 2: Arbiter (solo si hay desacuerdo)")
    print("-" * 70)

    if not (agreement and min_conf >= threshold):
        print("→ Hay desacuerdo o baja confianza, llamando al Arbiter...")
        try:
            arbiter = Arbiter(api_key=settings.OPENAI_API_KEY, taxonomy_data=taxonomy)
            print(f"✓ Arbiter inicializado")

            arbiter_result = await arbiter.arbitrate(
                template_text=template_text,
                applied_rules=applied_rules,
                vote1=vote1,
                vote2=vote2,
                client_name=client_name,
                frequency=24
            )

            print(f"\n✓ Respuesta del Arbiter ({settings.MODEL_ARBITER}):")
            if arbiter_result is None:
                print(f"  - RESULT IS NONE (crítico)")
            else:
                print(f"  - Label: {arbiter_result.label}")
                print(f"  - Confidence: {arbiter_result.confidence}")
                print(f"  - Reasoning: {arbiter_result.reasoning}")

        except Exception as e:
            print(f"✗ Error en Arbiter: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return
    else:
        print("→ Hay acuerdo, NO se necesita Arbiter")

    print("\n" + "=" * 70)
    print("✓ DEBUG COMPLETADO EXITOSAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_single_template())
