# Guía: Ejecutar con `uv` (en lugar de pip)

`uv` es una herramienta moderna, rápida y confiable para manejar proyectos Python. Es 10-100x más rápida que pip.

## Instalación de `uv`

### Opción 1: En tu máquina local

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

O con `pip`:
```bash
pip install uv
```

**Verificar instalación:**
```bash
uv --version
# uv 0.1.x
```

### Opción 2: En AWS instance

```bash
# Opción A: Installer script (recomendado)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Opción B: Con pip
pip install uv

# Verificar
uv --version
```

---

## Flujo básico con `uv`

### 1️⃣ Clonar/descargar el repo

```bash
cd /path/to/prod_pipeline
```

### 2️⃣ Crear virtual environment con `uv`

```bash
uv venv
# O explícitamente:
uv venv .venv

# Activar venv (igual que con venv estándar)
source .venv/bin/activate          # Linux/macOS
# o
.\.venv\Scripts\activate            # Windows
```

### 3️⃣ Instalar dependencias

```bash
# Instalar todo (core + duckdb)
uv sync

# O instalar solo core (sin dev)
uv sync --no-dev

# O instalar con extras (dev, prod)
uv sync --extra dev
```

### 4️⃣ Ejecutar scripts

```bash
# Con venv activado
python scripts/TEMP_score_phones.py 573001234567

# O directamente (sin activar venv)
uv run python scripts/TEMP_score_phones.py 573001234567

# Ejecutar CLI con argumentos
uv run python scripts/TEMP_score_phones.py \
    573001234567 573009876543 \
    --lookback-days 180 \
    --output resultado.json
```

---

## Comandos `uv` principales

### Crear y activar venv

```bash
# Crear venv en .venv/
uv venv

# Crear con Python específico
uv venv --python 3.11

# Activar (igual que venv estándar)
source .venv/bin/activate
```

### Instalar dependencias

```bash
# Instalar del pyproject.toml (crear uv.lock)
uv sync

# Solo dependencias core (sin dev/prod)
uv sync --no-dev

# Con extras específicos
uv sync --extra dev
uv sync --extra prod
uv sync --extra dev --extra prod

# Instalar un paquete nuevo
uv pip install numpy>=2.0.0
```

### Ejecutar sin activar venv

```bash
# Ejecutar un script
uv run python scripts/TEMP_score_phones.py 573001234567

# Ejecutar pytest
uv run pytest tests/

# Ejecutar con argumentos
uv run python -m s3_query.TEMP_phone_scorer
```

### Actualizar dependencias

```bash
# Regenerar uv.lock si cambió pyproject.toml
uv sync

# Actualizar a versiones más nuevas
uv pip install --upgrade duckdb
```

### Limpiar

```bash
# Eliminar venv
rm -rf .venv

# Limpiar cache
uv cache clean
```

---

## Ejemplo completo: Setup local

```bash
# 1. Clonar repo
git clone <repo> prod_pipeline
cd prod_pipeline

# 2. Crear venv
uv venv

# 3. Activar
source .venv/bin/activate

# 4. Instalar dependencias (incluyendo duckdb)
uv sync --extra dev

# 5. Verificar instalación
python -c "import duckdb; print(duckdb.__version__)"
# 0.10.x

# 6. Ejecutar tests
uv run pytest tests/

# 7. Ejecutar scoring (con datos locales mock)
uv run python scripts/TEMP_score_phones.py --help
```

---

## Ejemplo completo: AWS instance

```bash
# 1. SSH a instancia
ssh -i <key.pem> ec2-user@<ip>

# 2. Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Agregar uv a PATH (si es necesario)
export PATH="$HOME/.cargo/bin:$PATH"

# 4. Clonar repo
git clone <repo> prod_pipeline
cd prod_pipeline

# 5. Crear venv
uv venv

# 6. Activar
source .venv/bin/activate

# 7. Instalar todo (incluyendo duckdb)
uv sync

# 8. Verificar acceso S3
aws s3 ls s3://inalambria-db-sms/imp3/year=2026/month=05/ --human-readable | head

# 9. Copiar CSV (vía SCP desde máquina local)
# En tu máquina local:
scp -i <key.pem> ~/Downloads/all_rule_classifications.csv \
    ec2-user@<ip>:/home/ec2-user/prod_pipeline/config/

# 10. Ejecutar scoring
uv run python scripts/TEMP_score_phones.py 573001234567 --lookback-days 30

# 11. Ejecutar con archivo de entrada
echo "573001234567" > phones.txt
echo "573009876543" >> phones.txt

uv run python scripts/TEMP_score_phones.py \
    --file phones.txt \
    --output resultado.json \
    --ref batch_test_001

# 12. Ver resultado
cat resultado.json | jq '.'
```

---

## uv.lock - Reproducibilidad exacta

Cuando corres `uv sync`, se crea un archivo `uv.lock` que congela TODAS las versiones exactas:

```bash
# Después de uv sync
ls -la uv.lock

# Este archivo debe commitearse a git
git add uv.lock
git commit -m "chore: lock dependencies with uv"
```

Así, cualquiera que clone el repo y corra `uv sync` obtiene EXACTAMENTE las mismas versiones.

```bash
# Para todos es igual
uv sync
# Instala las EXACTAS versiones del uv.lock
```

---

## Troubleshooting con `uv`

### "`uv: command not found`"

```bash
# Agregar a PATH
export PATH="$HOME/.cargo/bin:$PATH"

# O instalar con pip
pip install uv
```

### "`error: no Python interpreter found`"

```bash
# uv necesita al menos un Python 3.8 instalado
python3 --version

# Si no tienes Python, instálalo primero
# Luego: uv venv
```

### "`DuckDB httpfs not available`"

```bash
# Reinstalar con uv
uv pip install --force-reinstall "duckdb>=0.10.0"

# O regenerar venv
rm -rf .venv
uv venv
uv sync
```

### Caché corrupta

```bash
# Limpiar caché
uv cache clean

# Regenerar lock
uv sync --refresh
```

---

## Comparación: pip vs uv

| Tarea | pip | uv |
|-------|-----|-----|
| Instalar | `pip install -r requirements.txt` | `uv sync` |
| Crear venv | `python -m venv .venv` | `uv venv` |
| Ejecutar script | `python script.py` (requiere venv activado) | `uv run python script.py` |
| Agregar paquete | `pip install pkg` | `uv pip install pkg` |
| Velocidad | Lento (~10-30s) | Muy rápido (~1-2s) |
| Reproducibilidad | `requirements.txt` puede variar | `uv.lock` garantiza exactitud |

---

## Arquivos necesarios

✅ `pyproject.toml` — Configuración principal (creado)

✅ `requirements.txt` — Para compatibilidad (existente, se mantendrá)

✅ `uv.lock` — Se crea automáticamente con `uv sync`

✅ `.venv/` — Se crea con `uv venv` (no commitar a git)

---

## Flujo recomendado para AWS

```bash
# 1. Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Instalar dependencias
cd /home/ec2-user/prod_pipeline
uv sync

# 3. Ejecutar scoring
uv run python scripts/TEMP_score_phones.py 573001234567

# 4. Ejecutar con lotes
uv run python scripts/TEMP_score_phones.py --file phones.txt --output resultado.json

# 5. Monitorear RAM (en otra terminal)
watch -n 1 "free -h"
```

---

## Recursos

- [uv Documentation](https://docs.astral.sh/uv/)
- [uv GitHub](https://github.com/astral-sh/uv)
- [pyproject.toml Spec](https://packaging.python.org/specifications/pyproject-toml/)

---

**¿Preguntas?**

Si algo no funciona:
1. `uv --version` (verificar que está instalado)
2. `uv cache clean` (limpiar caché)
3. `rm -rf .venv && uv venv && uv sync` (reiniciar desde cero)
