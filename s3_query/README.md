# s3_query - Scoring de Teléfonos vía DuckDB + S3

Módulo para consultar datos de SMS desde S3 directamente usando DuckDB, sin descargas masivas ni reventamientos de RAM.

## Arquitectura

```
TEMP_s3_scanner.py      → DuckDB + httpfs → consulta S3, retorna DataFrame
TEMP_template_lookup.py → Carga CSV de clasificaciones
TEMP_aggregator.py      → Agrega mensajes → patrones temporales + categorías
TEMP_phone_scorer.py    → Orquesta todo → JSON final
```

## Instalación (en AWS instance)

### Con `uv` (recomendado)

```bash
# 1. Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# 2. Instalar dependencias (incluyendo duckdb)
cd /home/ec2-user/prod_pipeline
uv sync

# 3. Activar venv
source .venv/bin/activate

# 4. Verificar acceso S3 (confirmar región)
aws s3api get-bucket-location --bucket inalambria-db-sms
# Respuesta esperada: us-east-2

# 5. Copiar CSV de clasificaciones (desde máquina local)
scp -i <key.pem> ~/Downloads/all_rule_classifications.csv \
    ec2-user@<ip>:/home/ec2-user/prod_pipeline/config/all_rule_classifications.csv
```

### Con pip (alternativa)

```bash
# 1. Instalar DuckDB
pip install "duckdb>=0.10.0"

# 2-5. Igual que arriba (pasos 4-5)
```

## Uso

### Python API (simple)

```python
from s3_query.TEMP_phone_scorer import score_phones

# Un teléfono
result = score_phones("573001234567")
print(result)

# Lista de teléfonos
results = score_phones(["573001234567", "573009876543"])
for r in results:
    print(f"{r['phone_number']}: {r['message_types']['counts_last_365d']}")

# Con opciones
result = score_phones(
    "573001234567",
    lookback_days=180,
    request_reference="loan_app_12345",
    s3_region="us-east-2"
)
```

### Python API (avanzada)

```python
from s3_query.TEMP_phone_scorer import PhoneScorer

scorer = PhoneScorer(
    classifications_csv="config/all_rule_classifications.csv",
    s3_bucket="s3://inalambria-db-sms/imp3",
    s3_region="us-east-2"
)

# Scoring individual
result = scorer.score_phones("573001234567")

# Lotes grandes (menos memoria)
results = scorer.score_phones_batch(
    ["573001234567", "573009876543", ...],
    batch_size=100  # 100 teléfonos por query a S3
)
```

### CLI

```bash
# Un teléfono
python scripts/TEMP_score_phones.py 573001234567

# Múltiples teléfonos
python scripts/TEMP_score_phones.py 573001234567 573009876543

# Desde archivo
python scripts/TEMP_score_phones.py --file phones.txt

# Con opciones
python scripts/TEMP_score_phones.py 573001234567 \
    --lookback-days 180 \
    --ref loan_app_12345 \
    --output result.json

# Help
python scripts/TEMP_score_phones.py --help
```

## Output JSON

```json
{
  "phone_number": "573001234567",
  "temporal_patterns": {
    "hourly_distribution": [
      { "hour": 0, "messages_last_365d": 5 },
      { "hour": 18, "messages_last_365d": 29 }
    ],
    "daypart_distribution": {
      "night_00_06_share_last_365d": 0.02,
      "morning_06_12_share_last_365d": 0.34,
      "afternoon_12_18_share_last_365d": 0.42,
      "evening_18_24_share_last_365d": 0.22
    },
    "weekday_distribution": [
      { "weekday": "MON", "messages_last_365d": 78 },
      { "weekday": "SUN", "messages_last_365d": 22 }
    ]
  },
  "categories": [
    {
      "category": "banking",
      "messages_last_365d": 124,
      "share_last_365d": 0.30,
      "first_seen_at": "2020-01-15T10:00:00Z",
      "last_seen_at": "2025-11-29T13:00:00Z",
      "subcategories": [
        {
          "subcategory": "transaction_alerts",
          "messages_last_365d": 38,
          "share_within_category": 0.31
        }
      ]
    }
  ],
  "message_types": {
    "lookback_days": 365,
    "counts_last_365d": {
      "otp_2fa": 52,
      "transactional": 96,
      "billing": 58,
      "marketing_promotional": 113,
      "service_notifications": 74
    }
  },
  "metadata": {
    "generated_at": "2025-12-04T22:15:00Z",
    "request_reference": "loan_app_12345",
    "granularity": "standard",
    "data_lookback_days": 365,
    "version": "1.0.0"
  }
}
```

## Memoria & Rendimiento

- **DuckDB memory limit**: 3GB (configurable en `TEMP_s3_scanner.py`)
- **CSV clasificaciones**: ~45MB en RAM (cargar una sola vez)
- **Por consulta**: 1-10 teléfonos = pocos cientos de KB resultado
- **Seguro para 8GB instance**: No hay descarga masiva a disco

## Configuración (variables de entorno)

```bash
export S3_REGION=us-east-2              # AWS region (default)
export AWS_ACCESS_KEY_ID=...            # Si no tiene IAM role (opcional)
export AWS_SECRET_ACCESS_KEY=...        # Si no tiene IAM role (opcional)
```

En EC2 con IAM role: no se necesitan credenciales explícitas. DuckDB usa `credential_chain` (IMDS).

## Componentes internos

### `TEMP_s3_scanner.py`

- `scan_messages(phones, lookback_days=365)` → DataFrame
- `scan_messages_batch(phones, batch_size=100)` → Dict[phone: DataFrame]

Consulta S3 directamente con DuckDB. Pushdown de filtros hive (year). Sin escrituras a disco.

### `TEMP_template_lookup.py`

- `load_classifications(csv_path)` → Dict
- `get_category_info(template_id, lookup)`

Carga CSV una sola vez → dict {template_id: {categoria, subcategoria, label}}.

### `TEMP_aggregator.py`

- `PhoneScoreAggregator` class
  - `.aggregate(phone, df, lookup)` → JSON dict

Normaliza mensajes (reutiliza `TextNormalizer` del pipeline existente).
Extrae templates (reutiliza `TemplateExtractor`).
Construye patrones temporales, categorías, tipos de mensaje.

### `TEMP_phone_scorer.py`

- `PhoneScorer` class - API avanzada
- `score_phones(phones)` function - API simple

Orquesta todo. Carga lookup una sola vez. Maneja scoring individual o en lotes.

## Troubleshooting

**"Error: S3 bucket no encontrado"**
- Verificar region: `aws s3api get-bucket-location --bucket inalambria-db-sms`
- Verificar IAM permisos: `aws s3 ls s3://inalambria-db-sms/imp3/`

**"Error: DuckDB httpfs cannot load"**
- Instalar DuckDB: `pip install "duckdb>=0.10.0"`

**"CSV no encontrado"**
- Asegurar que `config/all_rule_classifications.csv` existe
- Usar `--csv` flag en CLI si está en otro path

**Memory errors ("Killed" signal)**
- Reducir `batch_size` en `score_phones_batch()`
- Aumentar memoria disponible en instancia
- Verificar que DuckDB limit es `3GB` (no más)

## Testing local (sin S3)

Para testear el parsing/agregación SIN necesidad de AWS:

```python
import pandas as pd
from datetime import datetime
from s3_query.TEMP_aggregator import PhoneScoreAggregator
from s3_query.TEMP_template_lookup import load_classifications

# DataFrame ficticio
df = pd.DataFrame({
    "PhoneNumber": ["573001234567"] * 10,
    "Message": ["tu código otp es 1234"] * 10,
    "ArrivalDate": [datetime.now()] * 10
})

# Cargar lookup
lookup = load_classifications("config/all_rule_classifications.csv")

# Agregar
agg = PhoneScoreAggregator()
result = agg.aggregate("573001234567", df, lookup)

print(result)
```

## Próximos pasos

- [ ] Agregar logging detallado (cuántas particiones se prunean, tiempo de query)
- [ ] Soportar queries por rango de fecha (no solo últimos N días)
- [ ] Caché de resultados (Redis) para teléfonos consultados recientemente
- [ ] Integración con FastAPI para exponer como API REST
