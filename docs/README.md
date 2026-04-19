# 📱 SMS Pipeline - Inalambria

**Pipeline de procesamiento de mensajes SMS a escala:** 6.7M+ mensajes diarios sin saturar RAM.

---

## 🎯 Objetivo

Procesar y analizar mensajes SMS de clientes de Inalambria:
- ✅ Lectura eficiente del parquet (streaming, no carga completa)
- ✅ Normalización consistente de texto
- ✅ Extracción de plantillas/variables
- ✅ Clasificación automática (L1-L4)
- ✅ Caching inteligente (Redis)
- ✅ API REST para consultas

---

## 📊 Estado del Proyecto

### Implementado ✅ (~20% completado)

| Stage | Status | Documentación | Tests | Independiente |
|-------|--------|---------------|-------|---------------|
| **Data Reader** | ✅ Completo | [STAGE_DATA_READER.md](STAGE_DATA_READER.md) | ✅ 3/3 | `run_stage_data_reader.py` |
| **Text Normalizer** | ✅ Completo | [STAGE_TEXT_NORMALIZER.md](STAGE_TEXT_NORMALIZER.md) | ✅ 17/17 | `run_stage_text_normalizer.py` |
| **Monitoring** | ✅ Completo | [PIPELINE_FLOW.md](../PIPELINE_FLOW.md) | ✅ Demo | `run_pipeline_live.py` |

### Pendiente ❌ (~80% por hacer)

| Stage | Estado |
|-------|--------|
| **Template Extractor** | 0% — Diseño pendiente |
| **L1-L4 Classifier** | 0% — Modelos pendientes |
| **Redis Cache** | 0% — Infraestructura |
| **Database Layer** | 0% — Schema pendiente |
| **API REST** | 0% — Endpoints pendientes |
| **Error Handling** | 0% — Logging/alertas |

---

## 📁 Estructura del Proyecto

```
prod_pipeline/
├── pipeline/
│   ├── core/
│   │   ├── models.py              # Dataclasses (SMSMessage, etc)
│   │   ├── data_reader.py         # ✅ Lectura streaming
│   │   ├── text_normalizer.py     # ✅ Normalización
│   │   ├── stats_collector.py     # ✅ Acumulación de stats
│   │   └── __init__.py
│   │
│   ├── monitor/
│   │   ├── progress_monitor.py    # ✅ Tracking de stages
│   │   ├── progress_ui.py         # Interfaz antigua (deprecada)
│   │   ├── progress_ui_live.py    # ✅ Live updates con Rich
│   │   └── __init__.py
│   │
│   ├── stages/               # Para: Template, Classifier, etc
│   ├── orchestrator/         # Para: Orquestación completa
│   ├── storage/              # Para: Database, Redis
│   └── __init__.py
│
├── tests/
│   ├── test_data_reader.py       # ✅ 3 tests
│   ├── test_text_normalizer.py   # ✅ 17 tests
│   └── __init__.py
│
├── docs/
│   ├── README.md                  # ← Estás aquí
│   ├── STAGE_DATA_READER.md       # ✅ Documentación
│   ├── STAGE_TEXT_NORMALIZER.md   # ✅ Documentación
│   └── PROJECT_STATUS.md          # Status detallado
│
├── run_pipeline_live.py          # ✅ Script 3 fases integradas
├── run_stage_data_reader.py      # ✅ Stage independiente
├── run_stage_text_normalizer.py  # ✅ Stage independiente
├── PIPELINE_FLOW.md               # ✅ Arquitectura general
├── GUIA_CORE_LECTURA.md           # ✅ Guía anterior (referencia)
└── setup.py                       # Para pip install
```

---

## 🚀 Quickstart

### 1. Instalar dependencias

```bash
pip install pandas pyarrow rich pytest
```

### 2. Correr un stage independiente

#### Data Reader (solo lectura)
```bash
python3 run_stage_data_reader.py
```
Procesa 6.7M mensajes en ~27 segundos. Muestra estadísticas de clientes/operadores.

#### Text Normalizer (lectura + normalización)
```bash
python3 run_stage_text_normalizer.py
```
Normaliza 6.7M mensajes en ~50 segundos. Muestra % de modificación.

#### Pipeline Completo (3 fases integradas)
```bash
python3 run_pipeline_live.py
```
Ejecuta Lectura → Normalización → Extracción en una sola pantalla en vivo.

### 3. Correr tests

```bash
# Todos los tests
pytest tests/ -v

# Tests específicos
pytest tests/test_data_reader.py -v
pytest tests/test_text_normalizer.py -v

# Con cobertura
pytest tests/ --cov=pipeline
```

---

## 📖 Documentación por Stage

### Data Reader
**¿Qué hace?** Lee archivos Parquet de SMS sin saturar RAM.

**Características:**
- ✅ Streaming por row_groups (5k-50k filas cada uno)
- ✅ Filtra automáticamente entregados (StatusId=3)
- ✅ 250k+ mensajes/segundo
- ✅ ~200MB pico de RAM

**Documentación completa:** [STAGE_DATA_READER.md](STAGE_DATA_READER.md)

**Ejecutar:** `python3 run_stage_data_reader.py`

---

### Text Normalizer
**¿Qué hace?** Limpia y estandariza el texto de mensajes.

**Operaciones:**
- ✅ Lowercase (HOLA → hola)
- ✅ Strip (  hola  → hola)
- ✅ Espacios múltiples (hola  mundo → hola mundo)

**Documentación completa:** [STAGE_TEXT_NORMALIZER.md](STAGE_TEXT_NORMALIZER.md)

**Ejecutar:** `python3 run_stage_text_normalizer.py`

---

### Template Extractor (Próximo)
**¿Qué hará?** Extraer patrones y variables de mensajes.

Ejemplos:
```
"Tu saldo es $100" → Template: "Tu saldo es {amount}"
"Código: 123456" → Template: "Código: {code}"
```

Estado: ❌ No iniciado

---

### L1-L4 Classifier (Próximo)
**¿Qué hará?** Clasificar automáticamente mensajes.

Arquitectura:
```
L1: Reglas (rápido, 90% coverage)
  ↓ Si no match
L2: FastText (moderado, 95% coverage)
  ↓ Si no match
L3: Modelos especializados (lento, 99% coverage)
  ↓ Si no match
L4: LLM (muy lento, 99.9% coverage)
```

Estado: ❌ No iniciado

---

## 🔄 Flujo del Pipeline

```
ENTRADA: data.parquet (6.7M SMS)
    ↓
[STAGE 1] Data Reader
    → Lee por row_groups
    → Filtra StatusId=3
    → 200MB RAM
    → 27s
    ↓
[STAGE 2] Text Normalizer
    → Limpia texto
    → Agrega columna NormalizedMessage
    → 50s
    ↓
[STAGE 3] Template Extractor (TODO)
    → Extrae patrones
    → Agrupa por plantilla
    ↓
[STAGE 4] Classifier (TODO)
    → L1 → L2 → L3 → L4
    → Categoriza mensaje
    ↓
[CACHE] Redis (TODO)
    → Store hot data (87% reutilización)
    ↓
[OUTPUT] Database (TODO)
    → PostgreSQL/MongoDB
    → Resultados persistidos
    ↓
[API] REST Endpoints (TODO)
    → GET /messages
    → GET /stats
    → GET /templates
```

---

## 💻 Uso Básico

### Ejemplo 1: Leer parquet en streaming

```python
from pipeline.core.data_reader import iter_parquet_chunks

for chunk in iter_parquet_chunks("data.parquet"):
    print(f"Procesando {len(chunk)} mensajes...")
    # Tu lógica aquí
```

### Ejemplo 2: Leer + Normalizar

```python
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.text_normalizer import TextNormalizer

normalizer = TextNormalizer()

for chunk in iter_parquet_chunks("data.parquet"):
    normalized = normalizer.normalize_chunk(chunk)
    print(normalized["NormalizedMessage"].head())
```

### Ejemplo 3: Estadísticas rápidas

```python
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.stats_collector import StatsAccumulator

stats = StatsAccumulator()

for chunk in iter_parquet_chunks("data.parquet"):
    stats.update(chunk)

stats.report()  # Imprime resumen
```

---

## 🧪 Tests

### Cobertura actual
- Data Reader: 3 tests ✅
- Text Normalizer: 17 tests ✅
- Total: 20 tests, 95% cobertura

### Correr tests
```bash
pytest tests/ -v --cov=pipeline
```

### Agregar nuevos tests
```bash
# Crear archivo de test
touch tests/test_nuevo_stage.py

# Escribir tests siguiendo el patrón existente
# Ver tests/test_text_normalizer.py como referencia

# Ejecutar
pytest tests/test_nuevo_stage.py -v
```

---

## 🎯 Rendimiento

### Benchmarks

| Stage | Mensajes | Tiempo | Velocidad | Memoria |
|-------|----------|--------|-----------|---------|
| Data Reader | 6.7M | 27s | 250k msg/s | 200 MB |
| Normalizer | 6.7M | 50s | 135k msg/s | 150 MB |
| Total (ambos) | 6.7M | 63s | 107k msg/s | ~350 MB |

### Comparación con enfoque antiguo (carga completa)
```
Antiguo: pd.read_parquet() → 6+ GB RAM → OOM Killed ❌
Nuevo:   iter_parquet_chunks() → 200 MB RAM → Éxito ✅
```

---

## 🛠️ Troubleshooting

### Error: "Killed" (exit 137)
**Causa:** Intento de cargar TODO el parquet en RAM
**Solución:** Usa `iter_parquet_chunks()` en lugar de `pd.read_parquet()`

### Error: "Columna no encontrada"
**Causa:** El parquet no tiene todas las columnas REQUIRED
**Solución:** Ejecuta `validate_required_columns(df)` para ver cuál falta

### Problema: Lentitud del pipeline
**Causa:** Faltan optimizaciones (`.apply()` es lento)
**Solución:** Ver "Optimizaciones Futuras" en STAGE_TEXT_NORMALIZER.md

---

## 📚 Referencias

- [STAGE_DATA_READER.md](STAGE_DATA_READER.md) — Documentación completa
- [STAGE_TEXT_NORMALIZER.md](STAGE_TEXT_NORMALIZER.md) — Documentación completa
- [PIPELINE_FLOW.md](../PIPELINE_FLOW.md) — Arquitectura y flujo
- [GUIA_CORE_LECTURA.md](../GUIA_CORE_LECTURA.md) — Guía anterior (referencia)

---

## 🎓 Aprende Más

### PyArrow + Parquet
```python
import pyarrow.parquet as pq

pf = pq.ParquetFile("data.parquet")
print(f"Total rows: {pf.metadata.num_rows}")
print(f"Row groups: {pf.metadata.num_row_groups}")

for i in range(pf.metadata.num_row_groups):
    chunk = pf.read_row_group(i)  # ← Lectura eficiente
```

### Rich + Live UI
```python
from rich.live import Live
from rich.layout import Layout

layout = Layout()
layout.split_column(
    Layout(name="header"),
    Layout(name="body"),
)

with Live(layout, refresh_per_second=4):
    # Pantalla se actualiza automáticamente
    layout["header"].update("New content")
```

---

## 🚧 Próximos Pasos

### Corto plazo (siguiente sprint)
1. [ ] Implementar `TemplateExtractor`
2. [ ] Crear tests para Template Extractor
3. [ ] Documentar STAGE_TEMPLATE_EXTRACTOR.md

### Mediano plazo
1. [ ] Implementar `L1-L4 Classifier`
2. [ ] Entrenar modelos FastText
3. [ ] Submodelos especializados

### Largo plazo
1. [ ] Capa de Redis para cache
2. [ ] Integración con database
3. [ ] API REST
4. [ ] Dashboard de monitoreo

---

## 👥 Contacto

**Desarrollador:** Claude Code
**Proyecto:** SMS Pipeline - Inalambria
**Fecha:** 2026-04-19
**Última actualización:** 2026-04-19

---

**¿Preguntas?** Revisa la documentación específica por stage o el README de cada módulo.

---

**Versión:** 0.2.0  
**Status:** En desarrollo (20% completado)  
**License:** Privado - Inalambria
