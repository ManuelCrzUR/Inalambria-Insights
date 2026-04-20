# 📊 Flujo del Pipeline - Arquitectura Mejorada

## Cambio Importante: De Paralelo a Secuencial

### ❌ ANTES (Problema)

```
Data Reader ────→ Text Normalizer ────→ Stats (todo en paralelo)
    ↓
[Múltiples pantallas se actualizan]
[Scroll infinito]
[Confuso qué está pasando]
```

### ✅ AHORA (Solución)

```
FASE 1: Leer Parquet
├─ Carga TODO el parquet en memoria
├─ Acumula en lista de DataFrames
└─ Muestra % en UNA pantalla que se actualiza

      ↓ (datos cargados)

FASE 2: Normalizar
├─ Procesa los DataFrames cargados
├─ Limpia texto
└─ Muestra % en UNA pantalla que se actualiza

      ↓ (datos normalizados)

FASE 3: Extraer Plantillas
├─ Procesa los datos normalizados
├─ Extrae placeholders
└─ Muestra % en UNA pantalla que se actualiza
```

---

## Ventajas del Nuevo Flujo

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| **Pantallas** | ❌ Múltiples (scroll) | ✅ UNA (se actualiza) |
| **Claridad** | ❌ Confuso | ✅ Claro (fase por fase) |
| **Memoria** | ❌ Picos | ✅ Predecible |
| **Complejidad** | ❌ Sincronización | ✅ Simple secuencial |
| **Debugging** | ❌ Difícil | ✅ Fácil (UNA pantalla) |

---

## Arquitectura del Nuevo Sistema

```
pipeline/monitor/
├── progress_monitor.py       (antigua - lógica de tracking)
├── progress_ui.py            (antigua - interfaz con updates)
└── progress_ui_live.py       (NUEVA - interfaz con Live sin scroll)

test_pipeline_monitor.py       (antigua - demo paralela)
test_pipeline_clean.py         (NUEVA - demo secuencial)
```

---

## Cómo Funciona PipelineLiveUI

### 1. Crear instancia

```python
from pipeline.monitor.progress_ui_live import PipelineLiveUI

ui = PipelineLiveUI()
```

### 2. Actualizar durante procesamiento

```python
ui.update_phase(
    phase_name="📖 Lectura del Parquet",
    processed=50,           # Procesados hasta ahora
    total=1394,             # Total a procesar
    **{
        "Rows/chunk": 4863,
        "Total rows": 240000,
    }
)
```

### 3. Marcar fase como completada

```python
ui.complete_phase()
```

### 4. Mostrar resumen final

```python
ui.show_summary()
```

---

## Ejemplo Real: Flujo Completo

```python
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.monitor.progress_ui_live import PipelineLiveUI

ui = PipelineLiveUI()

# ============================================================
# FASE 1: LEER
# ============================================================

chunks = []
for i, chunk in enumerate(iter_parquet_chunks(parquet_path), 1):
    chunks.append(chunk)
    
    ui.update_phase(
        "📖 Lectura del Parquet",
        processed=i,
        total=1394
    )

ui.complete_phase()

# ============================================================
# FASE 2: NORMALIZAR
# ============================================================

total_messages = sum(len(c) for c in chunks)
processed = 0

for chunk in chunks:
    for msg in chunk["Message"]:
        normalized = msg.lower().strip()
        processed += 1
        
        if processed % 10000 == 0:
            ui.update_phase(
                "🔧 Normalización de Texto",
                processed=processed,
                total=total_messages
            )

ui.complete_phase()

# ============================================================
# FASE 3: EXTRAER
# ============================================================

extracted = 0
for chunk in chunks:
    for msg in chunk["Message"]:
        # Extraer placeholders
        extracted += 1
        
        if extracted % 10000 == 0:
            ui.update_phase(
                "🎯 Extracción de Plantillas",
                processed=extracted,
                total=total_messages
            )

ui.complete_phase()

# ============================================================
# RESUMEN
# ============================================================

ui.show_summary()
```

---

## Pantalla Resultante

### Fase 1: Leyendo

```
🚀 Pipeline SMS
⏱️  12.3s

📖 Lectura del Parquet
[████████░░░░░░░░░░░░░] 35.7%
350 / 1394

Completadas
✅ —
```

### Fase 2: Normalizando

```
🚀 Pipeline SMS
⏱️  45.6s

🔧 Normalización de Texto
[██████████░░░░░░░░░░░░] 45.5%
1,500,000 / 3,300,000

Completadas
✅ 📖 Lectura del Parquet
```

### Fase 3: Extrayendo

```
🚀 Pipeline SMS
⏱️  67.8s

🎯 Extracción de Plantillas
[███████████████░░░░░░░░] 67.3%
2,200,000 / 3,300,000

Completadas
✅ 📖 Lectura del Parquet
✅ 🔧 Normalización de Texto
```

### Final: Resumen

```
✅ PIPELINE COMPLETADO

Resumen:
  Tiempo total: 89.45s
  Fases: 3

Fases completadas:
  ✅ 📖 Lectura del Parquet
  ✅ 🔧 Normalización de Texto
  ✅ 🎯 Extracción de Plantillas
```

---

## Beneficios vs Complejidad Anterior

### ✅ Beneficio 1: UNA Pantalla
- No hay scroll
- Todo cabe en terminal
- Fácil de ver qué está pasando

### ✅ Beneficio 2: Fases Claras
- Sabemos exactamente en qué fase estamos
- No hay confusión de múltiples procesos
- Debugging más fácil

### ✅ Beneficio 3: Mejor Manejo de Memoria
- **Fase 1**: Cargamos datos
- **Fase 2**: Procesamos datos cargados
- No hay picos de memoria impredecibles

### ✅ Beneficio 4: Simplicidad
- Sin sincronización de threads
- Sin manejo de múltiples estados
- Código más limpio

---

## Comparación: test_pipeline_monitor.py vs test_pipeline_clean.py

| Script | Patrón | Pantallas | Complejidad |
|--------|--------|-----------|-------------|
| `test_pipeline_monitor.py` | Paralelo | ❌ Múltiples | Alta |
| `test_pipeline_clean.py` | Secuencial | ✅ UNA | Baja |

---

## Próximas Implementaciones

Cuando hagas `text_normalizer.py`, usa este patrón:

```python
from pipeline.monitor.progress_ui_live import PipelineLiveUI

class TextNormalizer:
    def __init__(self, ui: PipelineLiveUI):
        self.ui = ui
    
    def normalize_batch(self, messages):
        total = len(messages)
        
        for i, msg in enumerate(messages):
            normalized = self._clean(msg)
            
            if i % 1000 == 0:
                self.ui.update_phase(
                    "🔧 Text Normalizer",
                    processed=i,
                    total=total
                )
        
        self.ui.complete_phase()
```

---

## Archivos

```
pipeline/monitor/
├── progress_monitor.py          (base: tracking de datos)
├── progress_ui.py               (antigua: updates múltiples)
└── progress_ui_live.py          (NUEVA: live sin scroll)

test_pipeline_monitor.py          (antigua: paralelo)
test_pipeline_clean.py            (NUEVA: secuencial)

PIPELINE_FLOW.md                  (esta documentación)
```

---

**Conclusión:** El nuevo sistema es más simple, más claro y mejor para UX. ✅

Una pantalla que se actualiza en vivo es mucho mejor que múltiples pantallas scrolleando.
