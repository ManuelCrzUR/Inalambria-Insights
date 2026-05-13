# Implementación: Módulo s3_query

**Status**: ✅ Completo

## Archivos creados

```
s3_query/
├── __init__.py                      Exports principales
├── TEMP_s3_scanner.py               [Foco principal] DuckDB + S3 queries
├── TEMP_template_lookup.py          Carga CSV de clasificaciones
├── TEMP_aggregator.py               Agrega mensajes → patrones + categorías
├── TEMP_phone_scorer.py             Orquesta todo → API simple/avanzada
├── README.md                        Guía de uso y API
└── AWS_SETUP.md                     Setup paso a paso + verificación

scripts/
└── TEMP_score_phones.py             CLI para scoring

requirements.txt                     [ACTUALIZADO] +duckdb>=0.10.0
```

## Qué hace cada módulo

### `TEMP_s3_scanner.py` (foco principal)

**Propósito**: Consultar S3 sin descargas masivas

**Componentes**:
- `_get_duckdb_conn()` — Crea conexión DuckDB in-memory con httpfs
- `_build_partition_filter()` — Calcula filtros hive para pushdown (year >= start_year)
- `scan_messages()` — Query principal, retorna DataFrame filtrado
- `scan_messages_batch()` — Versión por lotes para muchos teléfonos

**Características**:
- DuckDB in-memory (no disco)
- Pushdown de filtros hive (year partition)
- Row group filtering (StatusId=3, ArrivalDate, PhoneNumber)
- Memory limit: 3GB (configurable)
- Usa credential_chain (IAM role) en EC2
- Manejo de errores: FileNotFoundError si bucket no existe, ValueError si lista vacía

**Uso**:
```python
from s3_query.TEMP_s3_scanner import scan_messages
df = scan_messages(["573001234567"], lookback_days=365)
# Retorna: DataFrame con PhoneNumber, Message, ArrivalDate
```

### `TEMP_template_lookup.py`

**Propósito**: Carga CSV de clasificaciones una sola vez

**Componentes**:
- `load_classifications()` — Lee CSV → dict {template_id: {categoria, subcategoria, label}}
- `get_category_info()` — Lookup seguro con defaults

**Características**:
- Maneja variaciones de nombres de columnas (ID Plantilla vs id_plantilla)
- ~45MB en RAM (300k filas × 150 bytes)
- Fallback a defaults si template_id no está en lookup

**Uso**:
```python
from s3_query.TEMP_template_lookup import load_classifications
lookup = load_classifications("config/all_rule_classifications.csv")
info = lookup.get("template_id_123")
# Retorna: {categoria: "banking", subcategoria: "transaction_alerts", ...}
```

### `TEMP_aggregator.py`

**Propósito**: Transforma mensajes → JSON de scoring

**Componentes**:
- `PhoneScoreAggregator` class
  - `aggregate()` — Método principal
  - `_build_temporal_patterns()` — Hourly (24), dayparts (4), weekdays (7)
  - `_build_categories()` — Array con subcategorías
  - `_build_message_types()` — Mapeo a 5 tipos: otp_2fa, transactional, billing, marketing, service_notifications
  - `_build_metadata()` — Timestamp, version, request_reference
  - `_empty_score()` — Estructura vacía si no hay mensajes

**Reutiliza**:
- `TextNormalizer` del pipeline existente (normaliza mensajes)
- `TemplateExtractor` del pipeline existente (extrae template_id)

**Características**:
- Maneja teléfonos sin mensajes (retorna estructura válida, no error)
- Calcula shares (fracciones) correctamente
- ISO 8601 timestamps con "Z"
- Sorted por frecuencia (descendente)

**Uso**:
```python
from s3_query.TEMP_aggregator import PhoneScoreAggregator
agg = PhoneScoreAggregator()
result = agg.aggregate("573001234567", df, lookup)
# Retorna: JSON dict completo
```

### `TEMP_phone_scorer.py`

**Propósito**: Orquesta TODOS los componentes (API principal)

**Componentes**:
- `PhoneScorer` class — API avanzada
  - `__init__()` — Carga lookup una sola vez
  - `score_phones()` — Scoring single o batch
  - `score_phones_batch()` — Múltiples teléfonos en lotes (memory-safe)
- `score_phones()` function — API simple

**Características**:
- Carga lookup UNA sola vez en `__init__` (no por cada teléfono)
- Detecta CSV en `config/` por default
- Batch size configurable (default 100)
- Retorna Dict o List[Dict] según input

**Uso**:
```python
# Simple
from s3_query.TEMP_phone_scorer import score_phones
result = score_phones("573001234567")

# Avanzada
from s3_query.TEMP_phone_scorer import PhoneScorer
scorer = PhoneScorer("config/all_rule_classifications.csv")
results = scorer.score_phones_batch(
    phones_list,
    batch_size=50  # Menos memoria
)
```

### `TEMP_score_phones.py` (CLI)

**Uso**:
```bash
# Un teléfono
python scripts/TEMP_score_phones.py 573001234567

# Múltiples
python scripts/TEMP_score_phones.py 573001234567 573009876543

# Desde archivo
python scripts/TEMP_score_phones.py --file phones.txt --output resultado.json

# Con opciones
python scripts/TEMP_score_phones.py 573001234567 \
    --lookback-days 180 \
    --ref loan_app_123 \
    --s3-region us-east-2
```

**Flags**:
- `phones`: Posicionales (0+ teléfonos)
- `--file`: Leer desde archivo (uno por línea)
- `--output`: Guardar a archivo (default: stdout)
- `--lookback-days`: Días (default 365)
- `--ref`: Request reference ID
- `--csv`: Path a CSV (default: config/all_rule_classifications.csv)
- `--s3-bucket`: Bucket S3 (default: s3://inalambria-db-sms/imp3)
- `--s3-region`: AWS region (default: us-east-2)

## Decisiones arquitectónicas

### ✅ DuckDB in-memory (no disco)
- **Ventaja**: Seguro para instancia 8GB (límite 3GB)
- **Desventaja**: Cada query consulta S3 (latencia)
- **Mitigación**: Para múltiples teléfonos, usar `score_phones_batch()` que agrupa queries

### ✅ Pushdown de filtros hive (year >= start_year)
- **Ventaja**: DuckDB poda particiones antes de leerlas
- **Desventaja**: No puede podar por mes/día (no son partition keys)
- **Mitigación**: ArrivalDate >= start_date filtra exactamente después de descargar

### ✅ CSV lookup (no DB)
- **Ventaja**: Trivial de desplegar (un archivo)
- **Desventaja**: ~45MB en RAM
- **Mitigación**: Cargar una sola vez en `PhoneScorer.__init__()`

### ✅ Reutilizar TextNormalizer + TemplateExtractor
- Reutiliza código existente del pipeline
- Consistencia con clasificación principal

## Testing en local (sin S3)

Para desarrollar/testear SIN acceso a S3, mockear `scan_messages()`:

```python
import pandas as pd
from datetime import datetime
from s3_query.TEMP_aggregator import PhoneScoreAggregator

# Mock data
df = pd.DataFrame({
    "PhoneNumber": ["573001234567"] * 100,
    "Message": [
        "tu código otp es 1234",
        "tu pago de $100 fue confirmado",
        "recarga tu saldo"
    ] * 33 + ["..." ] ,
    "ArrivalDate": pd.date_range("2025-05-01", periods=100, freq="D")
})

# Mock lookup
lookup = {
    "abcd1234": {"categoria": "banking", "subcategoria": "otp_2fa"},
    "efgh5678": {"categoria": "banking", "subcategoria": "transaction_alerts"},
    "ijkl9012": {"categoria": "utility", "subcategoria": "billing"},
}

# Test aggregator
agg = PhoneScoreAggregator()
result = agg.aggregate("573001234567", df, lookup)
print(result)
```

## Verificación completada

✅ Sintaxis Python: `python3 -m py_compile` → sin errores

✅ Imports: Todos los módulos importables (sin errores de path)

✅ Estructura: Archivos en lugar correcto

✅ Requirements: `duckdb>=0.10.0` agregado a requirements.txt

## Próximos pasos en AWS

1. **SSH a instancia**: Conectarse a EC2
2. **Instalar DuckDB**: `pip install "duckdb>=0.10.0"`
3. **Copiar CSV**: Via SCP desde máquina local
4. **Seguir AWS_SETUP.md**: Tests paso a paso
5. **Integrar**: Usar PhoneScorer en aplicación principal

## Documentación

- `README.md`: Guía de uso, ejemplos, troubleshooting
- `AWS_SETUP.md`: Setup completo + 9 tests de verificación
- Inline docstrings: Todos los métodos tienen tipos + documentación

---

**Implementación completada el**: 2026-05-13  
**Modularización**: ✅ Carpeta separada `s3_query/` (no dentro de `pipeline/`)  
**Region S3**: us-east-2 (configurado por default)
