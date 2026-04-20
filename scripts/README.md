# Scripts de ejecución

Scripts para correr etapas individuales o el pipeline completo desde la raíz del proyecto.

> **Importante:** Ejecutar siempre desde la **raíz del repositorio**, no desde dentro de `/scripts`.

```bash
# Correcto ✅
python scripts/run_pipeline_live.py

# Incorrecto ❌
cd scripts && python run_pipeline_live.py
```

---

## Configuración previa

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con la ruta real al archivo .parquet
```

---

## Scripts disponibles

### `run_pipeline_live.py` — Pipeline completo con UI en vivo

Ejecuta las 3 fases del pipeline (lectura → normalización → extracción de plantillas) con una interfaz visual que se actualiza en tiempo real.

```bash
python scripts/run_pipeline_live.py
```

**Fases:**
1. Lectura del parquet en chunks
2. Normalización de texto (lowercase, espacios, caracteres raros)
3. Extracción de plantillas

---

### `run_stage_data_reader.py` — Solo etapa de lectura

Lee el parquet sin procesarlo y muestra estadísticas: total de mensajes, clientes, operadores, rango de fechas.

```bash
python scripts/run_stage_data_reader.py
```

**Útil para:** verificar que el archivo parquet es legible y tiene el formato esperado.

---

### `run_stage_text_normalizer.py` — Solo etapa de normalización

Lee el parquet y aplica normalización de texto, mostrando estadísticas de cuántos mensajes fueron modificados.

```bash
python scripts/run_stage_text_normalizer.py
```

**Útil para:** validar el comportamiento del normalizador sobre datos reales.
