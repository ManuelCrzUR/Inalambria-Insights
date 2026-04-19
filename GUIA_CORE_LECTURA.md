# 📚 Guía Completa: Core + Lectura de Parquets

## Índice
1. [Qué hay en Core](#qué-hay-en-core)
2. [Módulo data_reader.py](#módulo-data_readerpy)
3. [Lectura de Parquets: Divide y Vencerás](#lectura-de-parquets-divide-y-vencerás)
4. [Módulo stats_collector.py](#módulo-stats_collectorpy)
5. [Flujo Completo](#flujo-completo)
6. [Ejemplos Prácticos](#ejemplos-prácticos)

---

# Qué hay en Core

El módulo **`pipeline/core/`** contiene la lógica pura del pipeline, sin dependencias de negocio externas.

## Estructura

```
pipeline/core/
├── __init__.py                 # Hace el módulo importable
├── models.py                   # Tipos de datos (dataclasses)
├── data_reader.py              # Lectura de parquets
└── stats_collector.py          # Acumulador de estadísticas
```

## Responsabilidades de cada archivo

### 1. **models.py** — Tipos de Datos

Define los **contratos** entre módulos usando `@dataclass`.

```python
@dataclass
class SMSMessage:
    """Mensaje SMS crudo tal como viene del parquet"""
    message: str
    phone_number: str
    status_id: int
    client_name: Optional[str]
    # ... 12 campos más

@dataclass
class NormalizedMessage:
    """Mensaje tras limpiar espacios y caracteres especiales"""
    original_message: str
    cleaned_message: str
    # ... hereda de SMSMessage

@dataclass
class Template:
    """Mensaje con placeholders reemplazados"""
    template_text: str       # "Tu saldo es [AMOUNT]"
    template_id: str         # hash(template_text)[:16]
    # ... valores específicos reemplazados

@dataclass
class TemplateStats:
    """Plantilla agregada con estadísticas"""
    template_id: str
    frequency: int           # Cuántas veces aparece
    client_names: List[str]  # Clientes que la enviaron
    # ... estadísticas

@dataclass
class PipelineStats:
    """Resumen final del pipeline"""
    total_messages: int
    unique_templates: int
    processing_time_seconds: float
    # ...
```

**¿Por qué dataclasses?**
- ✅ Type hints claros
- ✅ Validación automática en IDE
- ✅ Serialización fácil (a JSON, parquet, etc)
- ✅ Documentación clara del contrato

---

### 2. **data_reader.py** — Lectura de Parquets

Responsabilidad: **Leer archivos parquet y convertir a objetos tipados.**

#### Funciones disponibles:

| Función | Uso | Límite Memoria |
|---------|-----|---|
| `read_raw_parquet(path)` | Lee parquet sin procesar | Carga TODO |
| `filter_delivered_only(df)` | Filtra StatusId=3 | Carga TODO |
| `dataframe_to_sms_messages(df)` | Convierte a objetos | Carga TODO |
| `read_messages(path)` | Orquesta todo (simple) | Carga TODO |
| `read_messages_limited(path, limit)` | Lee hasta N filas | Configurable |
| `read_messages_streaming(path, chunk)` | Lee en chunks con pandas | Por chunk |
| **`iter_parquet_chunks(path)`** | **Lee row_groups nativos** | **~200MB** |

---

### 3. **stats_collector.py** — Acumulador de Estadísticas

Responsabilidad: **Acumular estadísticas sin cargar TODO en memoria.**

```python
class StatsAccumulator:
    def __init__(self):
        # Contadores (no guarda mensajes, solo números)
        self.total_messages = 0
        self.client_counts: Counter = Counter()      # {cliente: N}
        self.operator_counts: Counter = Counter()    # {operador: N}
        self.priority_counts: Counter = Counter()    # {prioridad: N}
        
        # Sets (para únicos)
        self.unique_phones: Set[str] = set()
        
        # Timestamps
        self.min_timestamp = None
        self.max_timestamp = None
    
    def update(self, df_chunk):
        """Procesa un chunk y acumula estadísticas"""
        # Actualiza contadores
        # Libera memoria del chunk
    
    def print_report(self):
        """Imprime reporte bonito"""
```

---

# Módulo data_reader.py

## Estructura interna

```python
# 1. CONFIGURACIÓN
REQUIRED_COLUMNS = {
    "Message": "message",
    "PhoneNumber": "phone_number",
    # ... mapeo de columnas del parquet
}

# 2. VALIDACIÓN
def validate_required_columns(df) → None
    # Verifica que existan todas las columnas

# 3. LECTURA CRUDA
def read_raw_parquet(path) → pd.DataFrame
    # Lee el parquet sin filtros

# 4. FILTRADO
def filter_delivered_only(df) → pd.DataFrame
    # Filtra StatusId=3

# 5. CONVERSIÓN
def _safe_int(value) → Optional[int]
def _safe_str(value) → Optional[str]
def _parse_timestamp(value) → Optional[datetime]
def _extract_sms_message(row) → SMSMessage
def dataframe_to_sms_messages(df) → List[SMSMessage]

# 6. API PRINCIPAL
def read_messages(path, verbose) → List[SMSMessage]
def read_messages_limited(path, limit, verbose) → List[SMSMessage]
def read_messages_streaming(path, chunk_size, verbose) → Generator

# 7. STREAMING NATIVO (DIVIDE Y VENCERÁS)
def iter_parquet_chunks(path, delivered_only, verbose) → Generator[pd.DataFrame]
```

---

# Lectura de Parquets: Divide y Vencerás

## El Problema Original

```
❌ INTENTO 1: read_messages() con 6.7M registros
├─ Lee parquet → 6.7M filas en DataFrame
├─ Filtra StatusId=3 → 6.7M objetos SMSMessage
├─ Crea 6.7M objetos Python en memoria
├─ Resultado: Killed (exit 137 - Out of Memory)
└─ Memory: Necesita ~6GB
```

## La Solución: Divide y Vencerás con PyArrow

### ¿Cómo funciona PyArrow?

Los archivos Parquet se dividen en **row_groups** — bloques de datos independientes:

```
Archivo: SmsData_2025_12_15.parquet (6.7M filas)
├─ Row_group 1: ~5k filas
├─ Row_group 2: ~5k filas
├─ Row_group 3: ~5k filas
├─ ...
└─ Row_group 1394: ~5k filas

Total: 1394 row_groups
```

### Algoritmo: Procesa uno a la vez

```python
def iter_parquet_chunks(path, delivered_only=True):
    # 1. Abre el archivo parquet
    pf = pq.ParquetFile(path)  # NO carga nada en memoria
    
    # 2. Para cada row_group
    for i in range(pf.metadata.num_row_groups):
        # 3. Lee SOLO este row_group (~5k filas)
        table = pf.read_row_group(i)
        df = table.to_pandas()  # ~5MB en memoria
        
        # 4. Filtra si es necesario
        if delivered_only:
            df = df[df["StatusId"] == 3]
        
        # 5. Devuelve el DataFrame
        yield df
        
        # 6. IMPORTANTE: Libera memoria
        del df
        del table
        # Aquí es donde está la magia: 
        # Python garbage collector limpia la RAM
```

### Flujo Visual

```
iter_parquet_chunks(parquet_path)
    ↓
Row_group 1 (5k filas)
    ↓ filter StatusId=3
    ↓ yield DataFrame
    ↓ [StatsAccumulator procesa]
    ↓ del df  ← Libera memoria
    ↓
Row_group 2 (5k filas)
    ↓ [repite...]
    ↓
Row_group 3 (5k filas)
    ↓ [repite...]
    ↓
... (1394 veces total)
    ↓
✅ Completado: 6.7M mensajes procesados
Memory peak: ~200MB (vs 6GB)
```

---

## Ejemplo Completo: Procesar 6.7M

```python
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.stats_collector import StatsAccumulator

# 1. Inicializar acumulador
stats = StatsAccumulator()

# 2. Iterar por chunks
for chunk in iter_parquet_chunks("data.parquet"):
    # chunk es un DataFrame con ~5k filas
    
    # 3. Actualizar estadísticas
    stats.update(chunk)
    
    # 4. Mostrar progreso
    stats.print_progress()
    
    # 5. El chunk se libera automáticamente al siguiente loop
    #    (Python garbage collection)

# 6. Mostrar resultados
stats.print_report()
```

### Output esperado

```
📖 Leyendo parquet por row_groups: data.parquet
   Row groups total: 1394
   → Row group 1/1394 (4,863 rows)
   → Chunk 1: 4,863 mensajes acumulados
   → Chunk 2: 9,619 mensajes acumulados
   → Chunk 3: 14,314 mensajes acumulados
   ...
   → Row group 139/1394 (5,000 rows)
   ✅ Streaming completado

📊 ESTADÍSTICAS FINALES
   Mensajes totales: 6,795,562
   Chunks procesados: 1394
   Clientes únicos: 123
   ...
```

---

## ¿Por qué pyarrow y no pandas?

| Aspecto | PyArrow | Pandas |
|---------|---------|--------|
| Lectura por chunks | ✅ Nativo (row_groups) | ❌ No existe `chunksize` |
| Memory footprint | 200MB | 6GB |
| Velocidad | 250k msg/seg | N/A |
| Granularidad | Bloques nativos | Todo o nada |
| Complejidad | Simple | Requiere Dask |

---

# Módulo stats_collector.py

## Clase StatsAccumulator

### Constructor

```python
class StatsAccumulator:
    def __init__(self):
        self.total_messages = 0
        self.client_counts: Counter = Counter()
        self.operator_counts: Counter = Counter()
        self.priority_counts: Counter = Counter()
        self.unique_phones: Set[str] = set()
        self.min_timestamp: Optional[datetime] = None
        self.max_timestamp: Optional[datetime] = None
        self.chunks_processed = 0
```

### Método: update(df_chunk)

```python
def update(self, df_chunk: pd.DataFrame) -> None:
    """Actualiza estadísticas con un chunk"""
    
    # 1. Contar mensajes
    self.total_messages += len(df_chunk)
    
    # 2. Contar clientes únicos
    client_values = df_chunk["ClientName"].value_counts()
    self.client_counts.update(client_values)
    #     ↓
    # {"BBVA": 1000, "Claro": 500, ...}
    
    # 3. Contar operadores
    op_values = df_chunk["OperatorName"].value_counts()
    self.operator_counts.update(op_values)
    
    # 4. Agregar teléfonos únicos
    phones = df_chunk["PhoneNumber"].unique()
    self.unique_phones.update(phones)
    #     ↓
    # {"+573001234567", "+573009876543", ...}
    
    # 5. Actualizar timestamps min/max
    # [código...]
    
    self.chunks_processed += 1
```

**¿Por qué no guarda mensajes individuales?**
- Para estadísticas solo necesitas números agregados
- Guardar objetos SMSMessage = mucha memoria
- Los Counters y Sets pesan mucho menos

---

## Método: print_report()

```python
def print_report(self) -> None:
    """Imprime reporte bonito formateado"""
    
    # 1. Volumen
    print(f"Mensajes: {self.total_messages:,}")
    print(f"Chunks: {self.chunks_processed}")
    
    # 2. Dimensiones
    print(f"Clientes: {len(self.client_counts)}")
    print(f"Operadores: {len(self.operator_counts)}")
    print(f"Teléfonos: {len(self.unique_phones):,}")
    
    # 3. Top clientes
    for client, count in self.client_counts.most_common(5):
        pct = (count / self.total_messages) * 100
        print(f"{client}: {count} ({pct:.1f}%)")
```

---

# Flujo Completo

## Arquitectura en capas

```
USUARIO
  ↓
test_full_parquet.py          ← Script de prueba
  ↓
iter_parquet_chunks()          ← Lee row_group por row_group
  ↓
  └─→ pyarrow.ParquetFile     ← Acceso nativo al parquet
  ↓
Row_group 1 (5k)   Row_group 2   Row_group N
  ↓                 ↓              ↓
DataFrame         DataFrame      DataFrame
  ↓                 ↓              ↓
StatsAccumulator.update()    (repite N veces)
  ↓
Counter (clientes)
Counter (operadores)
Set (teléfonos)
  ↓
StatsAccumulator.print_report()
  ↓
USUARIO (ve resultados)
```

## Número de operaciones

```
Para 6.7M registros:
├─ Row_groups leídos: 1,394
├─ Tiempo total: 27 segundos
├─ Velocidad: 250k msg/seg
├─ Memory peak: 200MB
├─ Memory vs cargar TODO: 6GB / 0.2GB = 30x menos
└─ Sin "Killed": ✅ Exitoso
```

---

# Ejemplos Prácticos

## Caso 1: Leer un parquet pequeño

```python
from pipeline.core.data_reader import read_messages

# Carga TODO en memoria (ok para < 1M)
messages = read_messages("data.parquet")

# Acceder a un mensaje
msg = messages[0]
print(msg.phone_number)
print(msg.client_name)
```

## Caso 2: Leer solo 100k mensajes

```python
from pipeline.core.data_reader import read_messages_limited

# Lee solo los primeros 100k
messages = read_messages_limited("data.parquet", limit=100000)

# Procesar normalmente
for msg in messages:
    print(msg.message)
```

## Caso 3: Procesar 6.7M sin saturar memoria ⭐

```python
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.stats_collector import StatsAccumulator

# Inicializar acumulador
stats = StatsAccumulator()

# Procesar por chunks
for chunk in iter_parquet_chunks("data.parquet"):
    stats.update(chunk)
    stats.print_progress()

# Ver resultados
stats.print_report()
```

## Caso 4: Análisis personalizado por chunk

```python
from pipeline.core.data_reader import iter_parquet_chunks
from collections import Counter

# Contar mensajes por longitud
length_distribution = Counter()

for chunk in iter_parquet_chunks("data.parquet"):
    # Procesar este chunk
    lengths = chunk["Message"].str.len()
    
    # Agrupar por rango (0-50, 50-100, 100-200, 200+)
    for length in lengths:
        if length < 50:
            length_distribution["0-50"] += 1
        elif length < 100:
            length_distribution["50-100"] += 1
        # ... etc

print(length_distribution)
```

---

# Comparación: Antes vs Después

## ANTES (problema)

```python
# ❌ Esto mata el proceso con 6.7M registros
messages = read_messages("data.parquet")
# Exit 137: Killed
```

Memory: 6GB+  
Tiempo: N/A (no termina)  
Resultado: ❌ Fracaso

## DESPUÉS (solución)

```python
# ✅ Esto funciona sin problemas
stats = StatsAccumulator()
for chunk in iter_parquet_chunks("data.parquet"):
    stats.update(chunk)
stats.print_report()
```

Memory: 200MB  
Tiempo: 27 segundos  
Resultado: ✅ Éxito + estadísticas completas

---

# Resumen: Qué tienes y cómo usarlo

## Lo que está implementado

```
pipeline/core/
├── models.py                ✅ 5 tipos de datos
├── data_reader.py           ✅ 7 funciones de lectura
│   └── iter_parquet_chunks  ✅ Divide y Vencerás con pyarrow
└── stats_collector.py       ✅ Acumulador eficiente
```

## Cómo empezar

```python
# Para procesar 6.7M mensajes:
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.stats_collector import StatsAccumulator

stats = StatsAccumulator()
for chunk in iter_parquet_chunks("path/to/data.parquet"):
    stats.update(chunk)
stats.print_report()
```

## Próximo paso

El siguiente módulo es **`text_normalizer.py`** para limpiar los mensajes.

---

**Última actualización:** 2026-04-19  
**Estado:** Core completado y testeado con 6.7M registros reales ✅
