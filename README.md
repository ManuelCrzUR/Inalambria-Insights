# Inalambria Insights — SMS Pipeline

Procesamiento diario de mensajes SMS a escala: normalización, extracción de plantillas, deduplicación y clasificación en cascada L1–L4.

**Estado:** En desarrollo &nbsp;|&nbsp; **Versión:** 0.1.0 &nbsp;|&nbsp; **Python:** 3.10+

---

## 📋 Descripción

Pipeline modular para procesar parquets de SMS (~500k mensajes/día) desde S3, construir un perfil por número de teléfono y clasificar plantillas deduplicadas sin saturar RAM.

```
Parquet S3 (~500k mensajes/día)
        ↓
   Normalización de texto
   (números, fechas, montos → tokens)
        ↓
   Generación de ID único por plantilla (sha256[:16])
        ↓
   ┌─────────────────────────────────────┐
   │     REGISTRAR      │   CLASIFICAR   │
   │  (todos los msgs)  │ (solo únicas)  │
   └─────────────────────────────────────┘
                             ↓
                  Cascada L1–L4
                  (reglas → FastText → LLM)
                             ↓
                  Perfil por número en DB
```

> Ver diseño completo en [docs/stages/pipeline_inalambria_v2.md](docs/stages/pipeline_inalambria_v2.md)

---

## 🏗️ Estructura del proyecto

```
Inalambria-Insights/
├── pipeline/               ← Código principal
│   ├── core/               ← Lógica pura (data_reader, text_normalizer, models)
│   ├── monitor/            ← Interfaz visual del progreso (rich)
│   ├── stages/             ← Pasos composables del pipeline
│   ├── orchestrator/       ← Orquestación del flujo completo
│   └── storage/            ← Persistencia (parquet, DB, Redis)
│
├── tests/                  ← Tests automatizados
├── scripts/                ← Scripts ejecutables (ver scripts/README.md)
├── docs/                   ← Toda la documentación
│   └── stages/             ← Documentación por etapa del pipeline
│
├── config/                 ← Configuración centralizada
├── data/                   ← Datos locales (en .gitignore)
├── output/                 ← Resultados (en .gitignore)
└── .github/workflows/      ← CI automático
```

---

## 🚀 Inicio rápido

### 1. Clonar e instalar

```bash
git clone https://github.com/ManuelCrzUR/Inalambria-Insights.git
cd Inalambria-Insights
pip install -r requirements.txt
```

### 2. Configurar entorno

```bash
cp .env.example .env
# Editar .env con la ruta real al archivo .parquet
```

### 3. Ejecutar el pipeline

```bash
# Pipeline completo con interfaz visual en vivo
python scripts/run_pipeline_live.py

# Solo etapa de lectura (para validar el parquet)
python scripts/run_stage_data_reader.py

# Solo etapa de normalización
python scripts/run_stage_text_normalizer.py
```

> Ver descripción completa de cada script en [scripts/README.md](scripts/README.md)

---

## 🧪 Tests

```bash
pytest tests/ -v
```

---

## 📖 Documentación

### Diseño del pipeline

| Documento | Descripción |
|---|---|
| [pipeline_inalambria_v2.md](docs/stages/pipeline_inalambria_v2.md) | Diseño completo: flujo principal, cascada L1–L4, Redis, perfil por número |
| [pipeline_inalambria.md](docs/stages/pipeline_inalambria.md) | Versión inicial del diseño |
| [PIPELINE_FLOW.md](docs/PIPELINE_FLOW.md) | Arquitectura mejorada del flujo |
| [ARQUITECTURA_CORE.md](docs/ARQUITECTURA_CORE.md) | Arquitectura interna del módulo core |

### Stages implementados

| Documento | Descripción |
|---|---|
| [STAGE_DATA_READER.md](docs/STAGE_DATA_READER.md) | Stage de lectura de parquet |
| [STAGE_TEXT_NORMALIZER.md](docs/STAGE_TEXT_NORMALIZER.md) | Stage de normalización de texto |
| [GUIA_CORE_LECTURA.md](docs/stages/GUIA_CORE_LECTURA.md) | Guía completa: core + lectura de parquets |
| [MONITOR_README.md](docs/stages/MONITOR_README.md) | Monitor del pipeline — interfaz visual |

### Referencia

| Documento | Descripción |
|---|---|
| [METADATA_SCHEMA.md](docs/METADATA_SCHEMA.md) | Schema de metadata de los SMS |
| [EJEMPLOS_USAGE.md](docs/EJEMPLOS_USAGE.md) | Ejemplos de uso del core |
| [PROJECT_STATUS.md](docs/PROJECT_STATUS.md) | Estado actual del proyecto |
| [docs/README.md](docs/README.md) | Índice completo de la documentación |

---

## 📦 Principios de diseño

- **Modular:** cada función es independiente y testeable por separado
- **Sin estado:** funciones puras, resultado determinístico
- **Memory-safe:** procesamiento en chunks — nunca carga el parquet completo
- **Configurable:** parámetros externalizados en `config/settings.py` y `.env`
- **Observable:** interfaz visual en tiempo real con `rich`
- **Escalable:** estructura preparada para Celery/async y clasificación L1–L4

---

## ✍️ Autores

- Manuel Cruz — desarrollo inicial
