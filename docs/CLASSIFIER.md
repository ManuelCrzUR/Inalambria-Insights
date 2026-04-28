# Clasificador LLM: Panel Heterogéneo + Árbitro

## Overview

El clasificador es una **etapa final del pipeline** que asigna etiquetas de clasificación a plantillas de SMS usando un enfoque de **panel heterogéneo** (dos modelos LLM pequeños en paralelo) + **árbitro** (modelo grande que resuelve desacuerdos).

**Propósito:** Generar un dataset etiquetado de plantillas únicas para:
- Análisis de credit scoring en Colombia
- Entrenar modelos propios de clasificación
- Detectar patrones en mensajes comerciales/financieros

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│ Template: "Tu código es [OTP]"                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
      ┌──────────────────────────────┐
      │ HeterogeneousPanel           │
      │ (Juez 1 + Juez 2 paralelo)  │
      └──────────────────────────────┘
           │                    │
      ┌────▼──────┐        ┌───▼─────┐
      │ gpt-4o-   │        │ gpt-5-  │
      │ mini      │        │ nano    │
      │ (vote1)   │        │ (vote2) │
      └────┬──────┘        └───┬─────┘
           │                   │
           └─────────┬─────────┘
                     ▼
            ¿Labels iguales?
            AND min(conf1, conf2) ≥ 0.7?
                │         │
                │         └─── NO ──┐
                │                   │
             YES                    ▼
                │          ┌──────────────────┐
                │          │ Arbiter          │
                │          │ (gpt-5.4)       │
                │          │ Resuelve conf.   │
                │          └──────────────────┘
                │                   │
                │          ┌────────┴────────┐
                │          │                 │
                │      ┌───▼────┐       ┌───▼──────┐
                │      │ Label  │       │ ABSTAIN  │
                │      │ final  │       │ (humano) │
                │      └────────┘       └──────────┘
                │
      ┌─────────┴──────────────────────────┐
      │ ClassificationResult               │
      │ ✓ label, confidence, level_used    │
      │ ✓ panel votes (judge1, judge2)     │
      │ ✓ arbiter verdict & reasoning      │
      │ ✓ needs_human_review flag          │
      └─────────────────────────────────────┘
             ▼
      ┌──────────────────────┐
      │ Store JSONL append   │
      │ classifications.jsonl │
      └──────────────────────┘
```

---

## Componentes

### 1. **HeterogeneousPanel** (`panel.py`)

Panel de dos jueces pequeños ejecutados **en paralelo**.

```python
from pipeline.stages.classifier import HeterogeneousPanel

panel = HeterogeneousPanel(
    api_key="sk-...",
    taxonomy_data=taxonomy  # Dict con 39 etiquetas
)

# Clasificar en paralelo
vote1, vote2 = await panel.classify_parallel(
    template_text="Tu código es [OTP]",
    applied_rules=["otp"],
    client_name="Bancolombia"
)
```

**Modelos:**
- Juez 1: `gpt-4o-mini` (rápido, económico)
- Juez 2: `gpt-5-nano` (especializado)

**Output:** `PanelVote` con label, confidence, model_name.

---

### 2. **Arbiter** (`arbiter.py`)

Árbitro de alta inteligencia para resolver desacuerdos del panel.

```python
from pipeline.stages.classifier import Arbiter

arbiter = Arbiter(
    api_key="sk-...",
    taxonomy_data=taxonomy
)

# Arbitraje (solo si panel en desacuerdo)
decision = await arbiter.arbitrate(
    template_text="Tu código es [OTP]",
    applied_rules=["otp"],
    vote1=vote1,
    vote2=vote2,
    client_name="Bancolombia",
    frequency=10
)
# Output: {"label": "banking::otp_2fa", "confidence": 0.95, "reasoning": "..."}
```

**Modelo:** `gpt-5.4` (modelo grande, preciso)

**Decisiones posibles:**
- Etiqueta final válida (ej: `banking::otp_2fa`)
- **ABSTAIN**: Si el mensaje es genuinamente ambiguo → marca para revisión humana

---

### 3. **ClassifierStage** (`orchestrator.py`)

Orquestador que coordina panel + arbiter + decisión.

```python
from pipeline.stages.classifier import ClassifierStage

stage = ClassifierStage(
    panel=panel,
    arbiter=arbiter,
    store=store,
    agreement_threshold=0.7,  # Min confidence para acuerdo
    concurrency=10            # LLM calls paralelas
)

# Clasificar un template individual
result = await stage.classify_template(
    template_id="abc123",
    template_text="Tu código es [OTP]",
    applied_rules=["otp"],
    client_name="Bancolombia",
    frequency=10
)

# O clasificar un stream (con persistencia automática)
async for result in stage.classify_stream(templates_iterator):
    print(f"Clasificado: {result.label}")
```

**Lógica de decisión:**
1. Panel vota en paralelo → vote1, vote2
2. ¿Labels iguales AND min(conf1, conf2) ≥ threshold?
   - **SÍ** → `level_used="panel_agreement"`, fin
   - **NO** → Arbiter resuelve
3. ¿Arbiter dice ABSTAIN?
   - **SÍ** → `needs_human_review=True`, `level_used="human_review"`
   - **NO** → `level_used="arbiter"`, usa label del arbiter

---

### 4. **ClassificationStore** (`storage.py`)

Persistencia JSONL con soporte para **resume**.

```python
from pipeline.stages.classifier import ClassificationStore

store = ClassificationStore("output/classifications.jsonl")
store.ensure_parent_exists()

# Append resultados
await store.append(result)

# Resume: cargar IDs ya procesados
processed_ids = await store.load_processed_ids()  # Set[str]

# Iterar resultados persistidos
for result_dict in store.iter_classifications():
    print(result_dict["label"])
```

**Características:**
- **Append-only**: nuevos resultados al final del archivo
- **asyncio.Lock**: escrituras concurrentes seguras
- **Resume**: `load_processed_ids()` salta templates ya procesados
- **Robusto**: skipea líneas JSON corruptas con warning

---

## Taxonomía

39 etiquetas compuestas organizadas en categorías:

```json
{
  "version": "1.0.0",
  "labels": [
    {
      "label": "banking::otp_2fa",
      "description": "Contraseñas de un solo uso..."
    },
    {
      "label": "banking::transaction_alerts",
      "description": "Confirmaciones en tiempo real de débitos..."
    },
    {
      "label": "collections::extrajudicial_notice",
      "description": "Intentos de cobro pre-legal..."
    },
    // ... 36 más
  ]
}
```

**Categorías principales:**
- `banking::*` — Transacciones, OTP, alertas, fraude
- `collections::*` — Cobro, legal, burós
- `lending_and_credit::*` — Préstamos, ofertas, pagos
- `telecom::*` — Recargas, ofertas
- `utilities::*` — Servicios públicos, facturación
- (y más)

---

## Uso: Modo Standalone (Data Sintética)

Clasificar un JSONL de plantillas únicas y generar dataset etiquetado.

### Setup

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar API key
export OPENAI_API_KEY=sk-...
```

### Ejecución

```bash
python scripts/run_stage_classifier.py \
    --input output/2026-04-24/unique_templates.jsonl \
    --output output/2026-04-24/classifications.jsonl \
    --limit 100 \
    --concurrency 5 \
    --threshold 0.7
```

**Opciones:**
- `--input`: path a `unique_templates.jsonl` (requerido)
- `--output`: path a salida (default: mismo dir, nombre `classifications.jsonl`)
- `--limit N`: máximo templates a clasificar (default: sin límite)
- `--concurrency N`: LLM calls paralelas simultáneas (default: 10)
- `--threshold F`: confidence mínima para acuerdo panel (default: 0.7)

### Output

```jsonl
{"template_id":"8d62ce6caa968828","template_text":"Tu código es [OTP]","label":"banking::otp_2fa","confidence":0.95,"level_used":"panel_agreement",...}
{"template_id":"5f7a8b9c2d1e3f4a","template_text":"Saldo: [AMOUNT]","label":"banking::balance_alerts","confidence":0.88,"level_used":"arbiter",...}
```

### Resume

Si la clasificación se interrumpe, puedes reanudarla:

```bash
python scripts/run_stage_classifier.py \
    --input output/2026-04-24/unique_templates.jsonl \
    --output output/2026-04-24/classifications.jsonl \
    --limit 1000
```

El script cargará los template_ids ya procesados y solo clasificará los nuevos.

### Estadísticas Finales

```
╭────────────────────────────────────────────────────────╮
│          Clasificación Completa                         │
├────────────────────────────────────────────────────────┤
│ Templates clasificados          1,000                   │
│ Acuerdo panel                   750 (75.0%)            │
│ Árbitro intervino              200 (20.0%)            │
│ Revisión humana                 50 (5.0%)             │
│ Errores                          0 (0.0%)             │
├────────────────────────────────────────────────────────┤
│ Top 10 Etiquetas Más Frecuentes                        │
├────────────────────────────────────────────────────────┤
│ banking::otp_2fa               320                     │
│ banking::transaction_alerts    180                     │
│ banking::balance_alerts         95                     │
│ ... (7 más)                                           │
╰────────────────────────────────────────────────────────╯
```

---

## Uso: Modo Pipeline (Producción)

Integrar el clasificador como etapa final del pipeline streaming.

### Ejecución

```bash
# Sin clasificación (pipeline normal)
python scripts/run_pipeline_live.py

# Con clasificación LLM
python scripts/run_pipeline_live.py --classify

# Con concurrencia personalizada
python scripts/run_pipeline_live.py --classify --concurrency 5 --threshold 0.75
```

**Opciones:**
- `--classify`: activar etapa de clasificación (default: off)
- `--concurrency N`: LLM calls paralelas (default: 10)
- `--threshold F`: confidence mínima para acuerdo (default: 0.7)

### Output

En el mismo directorio de salida (`output/<fecha>/`):

```
output/2026-04-28/
├── templates_with_placeholders.jsonl      (streaming)
├── templates_pure_messages.jsonl          (streaming)
├── unique_templates.jsonl                 (deduplicado)
├── classifications.jsonl                  (LLM)   ← NUEVO
└── metadata.json                          (stats)
```

### UI en Vivo

Durante la ejecución, muestra progreso por etapa:

```
┌─ 📖 Lectura del Parquet ────────────────────────────────┐
│ 1394 / 1394  [████████████████████████████] 100% | Done │
└────────────────────────────────────────────────────────┘

┌─ 🔧 Normalización de Texto ─────────────────────────────┐
│ 65M / 65M    [████████████████████████████] 100% | Done │
└────────────────────────────────────────────────────────┘

┌─ 🎯 Extracción de Plantillas ───────────────────────────┐
│ 65M / 65M    [████████████████████████████] 100% | Done │
└────────────────────────────────────────────────────────┘

┌─ 🤖 Clasificación LLM ──────────────────────────────────┐
│ 15K / 15K    [████████████████████████████] 100% | Done │
│ Panel acuerdo: 11K | Árbitro: 3K | Humano: 1K          │
└────────────────────────────────────────────────────────┘
```

---

## Configuración

### Variables de Entorno

```bash
# API de OpenAI
OPENAI_API_KEY=sk-...

# Modelos (pueden overridearse)
MODEL_PANEL_1=gpt-4o-mini              # Juez 1
MODEL_PANEL_2=gpt-5-nano               # Juez 2
MODEL_ARBITER=gpt-5.4                  # Árbitro

# Comportamiento
CLASSIFIER_AGREEMENT_THRESHOLD=0.7     # Min confidence para acuerdo
CLASSIFIER_CONCURRENCY=10              # LLM calls paralelas
TAXONOMY_PATH=config/taxonomy.json     # Path a taxonomía
CLASSIFICATIONS_OUTPUT_FILENAME=classifications.jsonl
```

### En `config/settings.py`

```python
from config import settings

print(settings.OPENAI_API_KEY)
print(settings.MODEL_PANEL_1)
print(settings.CLASSIFIER_AGREEMENT_THRESHOLD)
```

---

## Formato del Output JSONL

Cada línea es un `ClassificationResult` serializado:

```json
{
  "template_id": "8d62ce6caa968828",
  "template_text": "Tu código es [OTP]",
  "applied_rules": ["otp"],
  "frequency": 10,
  "label": "banking::otp_2fa",
  "category": "banking",
  "subcategory": "otp_2fa",
  "confidence": 0.95,
  "level_used": "panel_agreement",
  "agreement": true,
  "panel_judge_1": "banking::otp_2fa",
  "panel_judge_1_conf": 0.95,
  "panel_judge_2": "banking::otp_2fa",
  "panel_judge_2_conf": 0.92,
  "arbiter_label": null,
  "arbiter_abstained": false,
  "arbiter_reasoning": null,
  "needs_human_review": false,
  "is_synthetic": true,
  "classified_at": "2026-04-28T15:30:45.123456",
  "metadata": {}
}
```

**Campos críticos:**
- `level_used`: "panel_agreement" | "arbiter" | "human_review" | "error"
- `needs_human_review`: true si ABSTAIN o error
- `panel_judge_1/2`: votos individuales del panel
- `arbiter_reasoning`: justificación del árbitro (si intervino)

---

## Costos API

**Estimación por template:**

| Escenario | Modelos | Costo |
|-----------|---------|-------|
| Panel acuerdo | 1x mini + 1x nano | ~0.00015 USD |
| Árbitro interviene | + 1x gpt-5.4 | ~0.0005 USD |

**Para 1 millón de templates:**
- Panel acuerdo (75%): 750k × $0.00015 = $112.50
- Árbitro (25%): 250k × $0.0005 = $125
- **Total: ~$237.50**

---

## Testing

### Unitarios

```bash
pytest tests/test_classifier_orchestrator.py tests/test_classifier_storage.py -v
```

Cubre:
- Acuerdo del panel con confidences altas
- Desacuerdo y arbitraje
- Threshold bajo activando árbitro
- ABSTAIN marcando para revisión humana
- Exception handling sin romper stream
- Resume de templates ya procesados
- Concurrencia segura (asyncio.Lock)
- Tolerancia a JSON corrupto

### Manual (Smoke Test)

```bash
python scripts/run_stage_classifier.py \
    --input output/2026-04-24/unique_templates.jsonl \
    --output /tmp/test_classifications.jsonl \
    --limit 5
```

Verificar:
- 5 líneas en `/tmp/test_classifications.jsonl`
- Cada línea tiene todos los campos (label, confidence, level_used, etc.)
- Resumen final muestra % acuerdo vs árbitro

---

## Troubleshooting

### Error: `OPENAI_API_KEY no está definida`

```bash
export OPENAI_API_KEY=sk-...
python scripts/run_stage_classifier.py --input ...
```

### Error: `Línea N es JSON inválido`

Normal. El store salta líneas corruptas con warning. Si muchas líneas fallan:
1. Verificar que el JSONL input es válido: `jq . input.jsonl > /dev/null`
2. Revisar logs para ver qué líneas fallaron

### Lentitud: pocas LLM calls paralelas

Aumentar concurrencia (cuidado con rate limits de OpenAI):

```bash
python scripts/run_stage_classifier.py --input ... --concurrency 20
```

### Budget: costos altos inesperados

Si el 100% fueron al árbitro (threshold muy alto), revisar:
```bash
jq '.level_used' output/*/classifications.jsonl | sort | uniq -c
```

Reducir threshold:
```bash
python scripts/run_stage_classifier.py --input ... --threshold 0.5
```

---

## Próximos Pasos

1. **Entrenar modelos propios** usando el dataset etiquetado generado
2. **Fine-tune** de modelos pequeños (DistilBERT, etc.) con las 39 etiquetas
3. **Evaluación**: comparar precisión de modelos propios vs panel LLM
4. **Automatización**: reemplazar panel LLM con modelo propio en producción

---

## Referencias

- Taxonomía: `config/taxonomy.json`
- Modelos de datos: `pipeline/core/models.py::ClassificationResult`
- Componentes: `pipeline/stages/classifier/`
- Scripts: `scripts/run_stage_classifier.py`, `scripts/run_pipeline_live.py`
- Tests: `tests/test_classifier_*.py`
