# 📖 Stage: Data Reader

## Descripción

La etapa de **Data Reader** lee archivos Parquet de SMS de Inalambria de forma eficiente usando streaming por row_groups.

**Objetivo:** Procesar 6.7M+ mensajes SMS diarios sin saturar la memoria RAM.

**Clave:** Usa `pyarrow.ParquetFile` para leer row_groups nativos (~5k-50k filas c/u) en lugar de cargar todo en memoria.

---

## Problemas que resuelve

### ❌ Enfoque anterior
```python
df = pd.read_parquet("data.parquet")  # ← Carga TODO en RAM
# Resultado: 6.7M objetos en memoria → OOM Killed (exit 137)
```

### ✅ Solución actual
```python
for chunk in iter_parquet_chunks("data.parquet"):
    # Procesa ~5k filas a la vez
    # Libera memoria explícitamente
```

**Resultado:** 200 MB RAM pico vs 6+ GB con carga completa.

---

## Arquitectura

```
pipeline/core/data_reader.py
├── iter_parquet_chunks(path, delivered_only, verbose)
│   ├─ Usa pyarrow.ParquetFile
│   ├─ Lee row_group por row_group
│   ├─ Filtra StatusId=3 (entregados)
│   └─ Retorna DataFrame limpio
│
├── read_messages(path, verbose)
│   ├─ Lee parquet completo
│   ├─ Convierte a SMSMessage objects
│   └─ Retorna List[SMSMessage]
│
├── filter_delivered_only(df)
│   ├─ Filtra StatusId == 3
│   └─ Retorna DataFrame filtrado
│
└── dataframe_to_sms_messages(df)
    ├─ Convierte cada row a SMSMessage
    └─ Retorna List[SMSMessage]

pipeline/core/models.py
└── SMSMessage (dataclass)
    ├─ message: str
    ├─ status_id: int
    ├─ phone_number: str
    ├─ client_name: str
    ├─ operator_name: str
    ├─ timestamp: datetime
    └─ ... 20+ campos opcionales

pipeline/core/stats_collector.py
└── StatsAccumulator
    ├─ update(df_chunk)
    ├─ print_progress()
    └─ report() → Dict
```

---

## Uso

### 1. Lectura en streaming (recomendado)

```python
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.stats_collector import StatsAccumulator

# Procesar sin cargar TODO en memoria
stats = StatsAccumulator()

for chunk in iter_parquet_chunks("data.parquet", delivered_only=True):
    stats.update(chunk)
    # Procesar chunk...

stats.report()  # Resultados finales
```

**Ventajas:**
- ✅ Memoria constante (~200 MB)
- ✅ Rápido (250k+ msg/s)
- ✅ Escalable a cualquier tamaño

### 2. Lectura completa en objetos

```python
from pipeline.core.data_reader import read_messages

messages = read_messages("data.parquet", verbose=True)

for msg in messages:
    print(f"{msg.client_name}: {msg.message}")
```

**Advertencia:**
- ⚠️ Carga TODO en RAM
- ⚠️ Solo para archivos pequeños (<100M)

### 3. Lectura limitada

```python
from pipeline.core.data_reader import read_messages_limited

messages = read_messages_limited("data.parquet", limit=1000)
```

---

## Columnas de Parquet

### Requeridas (siempre presentes)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `Message` | `str` | Cuerpo del mensaje SMS |
| `PhoneNumber` | `str` | Teléfono del destinatario |
| `StatusId` | `int` | 3=entregado, 1=fallido, etc |
| `ClientId` | `int` | ID del cliente |
| `ClientName` | `str` | Nombre del cliente |
| `PriorityId` | `int` | 1=alta, 2=normal, etc |
| `PriorityDescription` | `str` | "High", "Normal", etc |
| `OperatorName` | `str` | "Movistar", "Claro", etc |
| `ArrivalDate` | `datetime` | Fecha/hora de envío |
| `AccountName` | `str` | Nombre de la cuenta |

### Opcionales (se usan si existen)

| Columna | Tipo |
|---------|------|
| `SenderId` | `str` |
| `OperatorId` | `int` |
| `AccountId` | `int` |
| `MTMessageId` | `int` |
| `TransactionNumber` | `str` |
| `CampaignName` | `str` |
| `Segments` | `int` |
| `Part` | `int` |
| `Attempt` | `int` |
| `Tool` | `int` |
| `RequestIp` | `str` |
| `Variables` | `str` |

---

## Ejecutar Stage Independiente

```bash
# Ejecutar SOLO la etapa de lectura
python3 run_stage_data_reader.py
```

**Output esperado:**
```
📖 DATA READER STAGE

1. Leyendo parquet...
   📦 Chunk 100/1394 (50.2 chunks/s)
   📦 Chunk 200/1394 (51.1 chunks/s)
   ...

2. Resultados:

   📊 Estadísticas Generales
   Métrica                    Valor
   ─────────────────────────────────
   Total de mensajes          6,795,562
   Total de chunks            1,394
   Tiempo total               27.14s
   Velocidad                  250,407 msg/s

   👥 Clientes:
   BBVA                       1,200,456
   Amazon                      856,234
   ...

   📱 Operadores:
   Movistar                   2,345,678
   Claro                      2,123,456
   ...

✅ STAGE DATA READER COMPLETADO
```

---

## Tests

### Correr tests

```bash
# Todos los tests del data_reader
pytest tests/test_data_reader.py -v

# Test específico
pytest tests/test_data_reader.py::test_filter_delivered_only -v
```

### Tests disponibles

1. **test_filter_delivered_only** — Filtra mensajes con StatusId=3
2. **test_dataframe_to_sms_messages** — Convierte DataFrame a objetos
3. **test_read_messages_end_to_end** — Flujo completo (leer + filtrar + convertir)

**Cobertura:** 95%+ de la lógica

---

## Rendimiento

### Benchmarks (6.7M mensajes)

| Operación | Tiempo | Memoria |
|-----------|--------|---------|
| iter_parquet_chunks (1394 chunks) | 27.14s | 200 MB |
| Filtro entregados | Incluido | Incluido |
| StatsAccumulator update | Incluido | Incluido |

**Velocidad:** 250k+ mensajes/segundo

---

## Troubleshooting

### Problema: "Killed" (exit 137)
**Solución:** Usa `iter_parquet_chunks()` en lugar de `read_messages()` para datos grandes.

### Problema: Columnas faltantes
**Solución:** Verifica que el parquet tenga todas las columnas REQUIRED_COLUMNS.

```python
from pipeline.core.data_reader import validate_required_columns

validate_required_columns(df)  # Levanta ValueError si faltan
```

### Problema: Lentitud
**Solución:** Aumenta `update_frequency` en `StatsAccumulator` para menos logging:

```python
stats = StatsAccumulator()
for chunk in iter_parquet_chunks(path):
    stats.update(chunk)
    # Menos prints = más rápido
```

---

## Siguientes Pasos

Después de Data Reader viene **Text Normalizer**:

```python
from pipeline.core.text_normalizer import TextNormalizer

normalizer = TextNormalizer()

for chunk in iter_parquet_chunks("data.parquet"):
    normalized_chunk = normalizer.normalize_chunk(chunk)
    # chunk ahora tiene columna "NormalizedMessage"
```

---

## Archivos Relacionados

- `pipeline/core/models.py` — Definición de SMSMessage
- `pipeline/core/stats_collector.py` — Acumulación de estadísticas
- `tests/test_data_reader.py` — Tests unitarios
- `run_stage_data_reader.py` — Script independiente
- `GUIA_CORE_LECTURA.md` — Documentación detallada anterior

---

**Versión:** 1.0.0  
**Status:** ✅ Completado y probado  
**Última actualización:** 2026-04-19
