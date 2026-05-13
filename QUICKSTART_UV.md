# ⚡ Quick Start con `uv`

## En tu máquina local

```bash
# 1. Instalar uv (una sola vez)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Entrar al proyecto
cd /path/to/prod_pipeline

# 3. Crear venv e instalar dependencias (todo junto)
uv sync

# 4. Activar venv
source .venv/bin/activate

# 5. Listo! Ahora puedes correr
python scripts/TEMP_score_phones.py 573001234567
```

## En AWS instance

```bash
# 1. SSH
ssh -i <key.pem> ec2-user@<ip>

# 2. Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# 3. Clonar proyecto
git clone <repo-url> prod_pipeline
cd prod_pipeline

# 4. Instalar todo (core + duckdb)
uv sync

# 5. Copiar CSV (desde tu máquina local, otra terminal)
scp -i <key.pem> ~/Downloads/all_rule_classifications.csv \
    ec2-user@<ip>:/home/ec2-user/prod_pipeline/config/

# 6. En AWS, activar venv y correr
source .venv/bin/activate

# Test rápido
python scripts/TEMP_score_phones.py 573001234567

# O con archivo
python scripts/TEMP_score_phones.py --file phones.txt --output resultado.json
```

## Comandos frecuentes

```bash
# Ejecutar sin activar venv (útil en scripts)
uv run python scripts/TEMP_score_phones.py 573001234567

# Ejecutar tests
uv run pytest tests/

# Ejecutar Python interactivo
uv run python

# Instalar nueva dependencia
uv pip install newpkg

# Limpiar todo y reiniciar
rm -rf .venv uv.lock
uv sync
```

## Archivo de configuración

✅ **pyproject.toml** — Crea este archivo (ya incluido)

Define:
- Dependencias core: `pandas`, `pyarrow`, `numpy`, `rich`, `openai`, `python-dotenv`, `duckdb`
- Dependencias dev: `pytest`, `black`, `flake8`, `mypy`
- Python version: 3.9+

`uv sync` lee este archivo y instala TODO automáticamente.

---

**Ver detalles completos en `UV_GUIDE.md`**
