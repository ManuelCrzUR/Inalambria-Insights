# AWS Setup & Verificación

Pasos para setear el módulo en AWS instance y verificar que funciona.

## Pre-requisitos

- Instancia EC2 con Python 3.8+
- IAM Role con permisos:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        "Resource": [
          "arn:aws:s3:::inalambria-db-sms",
          "arn:aws:s3:::inalambria-db-sms/*"
        ]
      }
    ]
  }
  ```

## 1. Verificar acceso S3 base (sin DuckDB)

```bash
# SSH a la instancia
ssh -i <key.pem> ec2-user@<ip>

# Verificar región
aws s3api get-bucket-location --bucket inalambria-db-sms
# Salida esperada: {"LocationConstraint": "us-east-2"}

# Listar particiones disponibles
aws s3 ls s3://inalambria-db-sms/imp3/ --human-readable

# Ver un mes específico
aws s3 ls s3://inalambria-db-sms/imp3/year=2026/month=05/ --human-readable | head -10
```

## 2. Instalar dependencias

### Opción A: Con `uv` (recomendado)

```bash
# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Instalar todo (core + duckdb + dev)
cd /home/ec2-user/prod_pipeline
uv sync

# Activar venv
source .venv/bin/activate

# Verificar que DuckDB se instaló
python -c "import duckdb; print(duckdb.__version__)"
```

### Opción B: Con pip

```bash
# Actualizar pip
pip install --upgrade pip

# Instalar DuckDB
pip install "duckdb>=0.10.0"

# Verificar que DuckDB se instaló
python -c "import duckdb; print(duckdb.__version__)"
```

## 3. Descargar CSV de clasificaciones

Desde máquina local:

```bash
scp -i <key.pem> ~/Downloads/all_rule_classifications.csv \
    ec2-user@<ip>:/home/ec2-user/pipeline/config/all_rule_classifications.csv
```

O si está en Google Drive:

```bash
# En la instancia:
cd /home/ec2-user/pipeline/config/
# Descargar manualmente desde Google Drive y subirlo vía SCP
```

Verificar que existe:

```bash
ls -lh /home/ec2-user/pipeline/config/all_rule_classifications.csv
# ~150-200 MB esperado
```

## 4. Test 1: DuckDB + S3 básico

```python
# test_duckdb_s3.py
import duckdb
from datetime import date, timedelta

conn = duckdb.connect()
conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute("SET s3_region='us-east-2';")
conn.execute("SET s3_use_credential_chain=true;")

# Query simple
df = conn.execute("""
    SELECT COUNT(*) as cnt
    FROM read_parquet(
        's3://inalambria-db-sms/imp3/year=2026/month=05/day=01/*.parquet'
    )
""").df()

print(f"✓ DuckDB + S3 funciona. {df['cnt'].sum()} registros")
conn.close()
```

Correr:

```bash
python test_duckdb_s3.py
# Esperado: ✓ DuckDB + S3 funciona. XXXXXX registros
```

## 5. Test 2: s3_query módulo - Scan simple

```python
# test_s3_query.py
import sys
sys.path.insert(0, '/home/ec2-user/pipeline')

from s3_query.TEMP_s3_scanner import scan_messages

# Buscar UN teléfono (ajustar número real si existe)
df = scan_messages(["573001234567"], lookback_days=30)

print(f"✓ Found {len(df)} messages for 573001234567")
print(df.head())
```

Correr:

```bash
cd /home/ec2-user/pipeline
python test_s3_query.py

# Esperado:
# ✓ Found XXX messages for 573001234567
# PhoneNumber             Message  ArrivalDate
# 0   573001234567  tu código otp es 1234  2026-05-01 10:30:00
# ...
```

Si retorna 0 registros: el teléfono no existe en S3. Es normal. Continúa.

## 6. Test 3: Score phones - JSON output

```python
# test_score_phones.py
import sys
import json
sys.path.insert(0, '/home/ec2-user/pipeline')

from s3_query.TEMP_phone_scorer import score_phones

# Score UN teléfono
result = score_phones(
    "573001234567",
    lookback_days=30,
    request_reference="test_123"
)

print(json.dumps(result, indent=2, default=str))
```

Correr:

```bash
python test_score_phones.py | head -50

# Esperado: JSON completo con estructura
# {
#   "phone_number": "573001234567",
#   "temporal_patterns": {...},
#   "categories": [...],
#   "message_types": {...},
#   "metadata": {...}
# }
```

## 7. Test 4: Monitorear memoria durante scoring

En una terminal, correr `htop`:

```bash
htop
# Buscar proceso python, columna RES (memoria residente)
# Verificar que no supere ~4GB (instancia tiene 8GB)
```

En otra terminal, scoring de múltiples teléfonos:

```bash
python scripts/TEMP_score_phones.py 573001234567 573009876543 573005551234 \
    --lookback-days 180 \
    --output resultado.json

# Monitorear en htop mientras corre
# RES debe estar siempre < 4GB
```

## 8. Test 5: CLI con archivo de teléfonos

```bash
# Crear archivo test
cat > phones_test.txt << EOF
573001234567
573009876543
573005551234
EOF

# Score desde archivo
python scripts/TEMP_score_phones.py \
    --file phones_test.txt \
    --output resultado.json \
    --ref batch_test_001

# Verificar resultado
cat resultado.json | jq '.[0] | keys'
# [
#   "phone_number",
#   "temporal_patterns",
#   "categories",
#   "message_types",
#   "metadata"
# ]
```

## 9. Environment variables (opcional)

Si necesitas cambiar region/bucket:

```bash
export S3_REGION=us-east-2
export S3_BUCKET=s3://inalambria-db-sms/imp3

# O pasar por CLI
python scripts/TEMP_score_phones.py --s3-region us-east-2 --s3-bucket s3://inalambria-db-sms/imp3
```

## Checklist de verificación

- [ ] AWS S3 accessible: `aws s3 ls s3://inalambria-db-sms/imp3/`
- [ ] DuckDB installed: `python -c "import duckdb"`
- [ ] CSV exists: `ls config/all_rule_classifications.csv`
- [ ] Test 1 passed: DuckDB + S3 query
- [ ] Test 2 passed: s3_query scan
- [ ] Test 3 passed: JSON scoring output
- [ ] Test 4 passed: Memory < 4GB during scoring
- [ ] Test 5 passed: CLI with file input
- [ ] Tamaño CSV verificado: `ls -lh config/all_rule_classifications.csv`

## Common Issues

### "s3:NoSuchBucket"
- Verificar que la region es correcta: `aws s3api get-bucket-location --bucket inalambria-db-sms`
- Bucket name exacto: `inalambria-db-sms` (no typos)

### "Access Denied (403)"
- Verificar IAM role: `aws sts get-caller-identity`
- Role debe tener permisos `s3:GetObject` y `s3:ListBucket` en ese bucket

### "duckdb: httpfs not available"
- Reinstalar DuckDB: `pip install --force-reinstall "duckdb>=0.10.0"`
- Verificar Python version: `python --version` (debe ser 3.8+)

### "CSV file not found"
- Verificar path exacto: `ls /home/ec2-user/pipeline/config/all_rule_classifications.csv`
- Si está en otro lugar, pasar `--csv /path/to/csv` en CLI

### "Memory: Killed"
- Reducir `batch_size`: `score_phones_batch(phones, batch_size=50)`
- O consultar teléfonos de uno en uno

## Próximos pasos

Una vez verificado:

1. Integrar scoring en aplicación principal (FastAPI, Lambda, etc.)
2. Agregar caching de resultados (Redis)
3. Agregar logging detallado
4. Configurar alertas si consultas tardan > X segundos
