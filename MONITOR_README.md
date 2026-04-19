# 📊 Monitor del Pipeline - Interfaz Visual

## Descripción

Sistema de monitoreo en tiempo real para el pipeline SMS. Muestra:

- ✅ **Progreso general** (% completado)
- ✅ **Estado de cada stage** (Data Reader, Normalizer, etc.)
- ✅ **Velocidad de procesamiento** (items/segundo)
- ✅ **ETA** (tiempo estimado de finalización)
- ✅ **Estadísticas en vivo** (clientes, operadores, etc.)
- ✅ **Errores** (si hay problemas)

## Arquitectura

```
pipeline/monitor/
├── progress_monitor.py    # Lógica de tracking
├── progress_ui.py         # Interfaz visual con Rich
└── __init__.py

Uso típico:
  Stage (Data Reader)
    ↓ emite progreso
  Monitor (captura eventos)
    ↓ actualiza estado
  UI (renderiza en terminal)
    ↓ muestra al usuario
```

## Componentes

### 1. PipelineMonitor

Clase central que trackea todos los stages:

```python
from pipeline.monitor.progress_monitor import PipelineMonitor

monitor = PipelineMonitor()

# Agregar stages
reader_stage = monitor.add_stage("Data Reader")
normalizer_stage = monitor.add_stage("Text Normalizer")

# Usar stages
reader_stage.start(total_items=1394)
reader_stage.increment(1)
reader_stage.complete()
```

#### Métodos principales:

```python
# Agregar un nuevo stage
stage = monitor.add_stage("Mi Stage")

# Obtener un stage
stage = monitor.get_stage("Mi Stage")

# Obtener todos
all_stages = monitor.get_all_stages()

# Resumen
summary = monitor.get_summary()
```

### 2. StageProgress

Representa el progreso de un stage individual:

```python
@dataclass
class StageProgress:
    name: str
    status: StageStatus         # PENDING, RUNNING, COMPLETED, ERROR
    total_items: int
    processed_items: int
    start_time: datetime
    end_time: datetime
    
    @property
    def percentage: float       # % completado (0-100)
    
    @property
    def items_per_second: float # Velocidad
    
    @property
    def eta_seconds: float      # Segundos hasta terminar
    
    def start(total_items)      # Iniciar
    def update(processed)       # Actualizar contador
    def increment(amount)       # Incrementar +1, +5, etc
    def complete()              # Marcar como completo
    def error(message)          # Marcar como error
```

### 3. PipelineUI

Interfaz visual con Rich que renderiza el progreso:

```python
from pipeline.monitor.progress_ui import PipelineUI

monitor = PipelineMonitor()
ui = PipelineUI(monitor)

# Mostrar la UI
ui.display()

# Mostrar resumen final
ui.display_summary()
```

## Ejemplo de Uso Completo

```python
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.monitor.progress_monitor import PipelineMonitor
from pipeline.monitor.progress_ui import PipelineUI

# 1. Crear monitor
monitor = PipelineMonitor()
ui = PipelineUI(monitor)

# 2. Agregar stages
reader = monitor.add_stage("Data Reader")
normalizer = monitor.add_stage("Text Normalizer")

# 3. Iniciar
reader.start(total_items=1394)  # 1394 row_groups

# 4. Procesar
for chunk_num, chunk in enumerate(iter_parquet_chunks("data.parquet"), 1):
    # Actualizar progreso
    reader.increment(1, chunk_rows=len(chunk))
    
    # Mostrar UI cada N iteraciones
    if chunk_num % 50 == 0:
        ui.display()

# 5. Completar
reader.complete()

# 6. Mostrar resumen
ui.display_summary()
```

## Salida Visual

```
══════════════════════════════════════════════════════════════════════════════
                   🚀 Pipeline SMS - Monitor en Tiempo Real
══════════════════════════════════════════════════════════════════════════════

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Progreso General ━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ [████████░░░░░░░░░░░░░░░░░░░░░░] 35.7%                                 ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━ Stages del Pipeline ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Stage                      Estado         Progreso       Velocidad   ETA ┃
┠─────────────────────────────────────────────────────────────────────────┨
┃ 📖 Data Reader             ⏳ Ejecutándose [███████░░░░░░] 50%  250k  1.4s┃
┃ 🔧 Text Normalizer        ⏳ Ejecutándose [██████░░░░░░░] 45%  240k  1.8s┃
┃ 📊 Stats Collector        ✅ Completado   [████████████] 100% 250k  0.2s┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━ Info en Tiempo Real ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Data Reader → chunk_rows: 4863, total_rows: 240_000                     ┃
┃ Text Normalizer → speed: 240,000 msg/s                                  ┃
┃ Stats Collector → unique_clients: 45, unique_operators: 12              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━ Errores ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ✅ Sin errores                                                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Cómo Ejecutar la Demo

```bash
# Instalar Rich (si no está instalado)
pip install rich

# Ejecutar demo
python3 test_pipeline_monitor.py
```

### Funcionalidades de la Demo:

1. **Data Reader** - Lee el parquet por row_groups
   - Muestra % de progreso
   - Velocidad en items/segundo
   - ETA de finalización

2. **Text Normalizer** - Simula normalización (en paralelo)
   - Procesa cada chunk leído
   - Muestra velocidad de normalización

3. **Stats Collector** - Acumula estadísticas (en paralelo)
   - Cuenta clientes únicos
   - Cuenta operadores únicos

## Integración con Text Normalizer (próximo)

Cuando construyas `text_normalizer.py`, puedes integrarlo así:

```python
from pipeline.core.text_normalizer import TextNormalizer
from pipeline.monitor.progress_monitor import PipelineMonitor

monitor = PipelineMonitor()
normalizer_stage = monitor.add_stage("Text Normalizer")

normalizer_stage.start(total_items=len(messages))

normalizer = TextNormalizer()

for i, msg in enumerate(messages):
    normalized = normalizer.clean(msg.message)
    normalizer_stage.increment(1, speed=f"{normalizer_stage.items_per_second:,.0f}")
    
    if i % 10000 == 0:
        ui.display()

normalizer_stage.complete()
```

## Archivos Creados

```
pipeline/monitor/
├── __init__.py                  # Inicializa el módulo
├── progress_monitor.py          # Lógica de tracking (150 líneas)
└── progress_ui.py               # Interfaz visual con Rich (250 líneas)

test_pipeline_monitor.py          # Demo completa (150 líneas)
MONITOR_README.md                 # Esta documentación
```

## Ventajas de esta Interfaz

✅ **Terminal nativa** - No requiere navegador  
✅ **Actualización en tiempo real** - Repinta cada N iteraciones  
✅ **Múltiples stages** - Monitorea varios procesos en paralelo  
✅ **Información rica** - Porcentaje, velocidad, ETA  
✅ **Visual atractivo** - Colores, emojis, barras  
✅ **Fácil de integrar** - Solo 3 líneas de código  

## Próximos Pasos

1. **Terminar `text_normalizer.py`** con integración de monitor
2. **Crear `template_extractor.py`** con su propio stage
3. **Agregar más stages** según el pipeline completo

---

**Versión:** 1.0.0  
**Dependencias:** rich  
**Estado:** ✅ Completado y demostrado
