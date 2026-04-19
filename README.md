# SMS Template Extraction Pipeline

Procesamiento de mensajes SMS en escala: extrae plantillas, deduplica y clasifica en cascada L1-L4.

## 📋 Descripción

Pipeline completo para procesar parquets de SMS (~500k mensajes/día) y extraer plantillas limpias con placeholders genéricos. Flujo modular:

```
Parquet S3 (500k mensajes)
    ↓
Normalización (espacios, caracteres raros)
    ↓
Extracción de plantillas (regex → placeholders)
    ↓
Deduplicación y estadísticas
    ↓
Clasificación en cascada (L1-L4)
    ↓
Parquet+DB limpio y catalogado
```

## 🏗️ Arquitectura

```
pipeline/
├── core/                    # Lógica pura (no depende de nada)
│   ├── models.py           # Types: SMSMessage, Template, etc
│   ├── data_reader.py      # Lee parquet/CSV
│   ├── normalizer.py       # Limpia texto
│   └── template_extractor.py # Aplica regex
├── stages/                  # Pasos composables
│   ├── stage_read.py
│   ├── stage_normalize.py
│   ├── stage_extract.py
│   └── stage_deduplicate.py
├── orchestrator/            # Orquestación
│   └── pipeline.py         # Flujo principal
└── storage/                 # Persistencia
    ├── parquet_store.py
    ├── csv_store.py
    └── db_store.py
```

## 🚀 Inicio Rápido

### 1. Instalar

```bash
pip install -r requirements.txt
```

### 2. Usar

```python
from pipeline.core.models import SMSMessage
from pipeline.core.data_reader import ParquetReader
from pipeline.orchestrator.pipeline import SMSPipeline

# Leer parquet
reader = ParquetReader("data/sms_raw.parquet")
df = reader.read()

# Procesar
pipeline = SMSPipeline()
results = pipeline.run(df)

# Guardar
results.to_parquet("output/sms_templates_clean.parquet")
```

## 🧪 Testing

```bash
pytest tests/ -v
```

## 📖 Documentación

- [Arquitectura detallada](docs/ARQUITECTURA.md)
- [Guía de desarrollo](docs/DESARROLLO.md)
- [API Reference](docs/API.md)

## 📦 Producción

Este pipeline está diseñado para escalar a producción sin cambios:

- ✅ Modular: cada función es independiente y testeable
- ✅ Sin estado: funciones puras, resultado determinístico
- ✅ Configurable: parámetros externalizados
- ✅ Observable: logging y estadísticas incorporados
- ✅ Async-ready: estructura preparada para Celery/async

## 📄 Licencia

(Por definir)

## ✍️ Autores

- Manuel Cruz (desarrollo inicial)

---

**Estado:** En desarrollo | **Versión:** 0.1.0
