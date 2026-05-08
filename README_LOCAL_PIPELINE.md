# 🚀 Ejecutar Pipeline Localmente con Datos de Google Drive

Script para procesar todo el pipeline en tu máquina local, descargando parquets de Google Drive.

## ✨ Ventajas vs Colab

| Aspecto | Colab | Local |
|--------|-------|-------|
| **Velocidad** | Media (GPU variable) | ⚡ Rápido (sin límites) |
| **Datos** | Limita a 500k templates | Ilimitado |
| **Ejecución** | Max 12h (timeout) | Ilimitada |
| **Almacenamiento SQL** | Pierde cada ejecución | Persistente local |
| **Control** | Menos | ✅ Total |
| **Offline** | No | Sí (después de descargar) |

## 📋 Requisitos

```bash
# Instalar dependencias
pip install pydrive2 google-auth-oauthlib

# El pipeline ya debe estar instalado
pip install -e .
```

## 🔑 Paso 1: Obtener el Folder ID de Google Drive

1. Abre tu carpeta de parquets en [Google Drive](https://drive.google.com)
2. La URL se ve así: `https://drive.google.com/drive/folders/ESTO_ES_TU_FOLDER_ID`
3. Copia `ESTO_ES_TU_FOLDER_ID`

## 🎯 Paso 2: Ejecutar el Pipeline

### Opción A: Línea de comandos (rápido)

```bash
cd C:\Users\manue\Desktop\Twnel\pipeline

python run_pipeline_locally.py --folder-id "TU_FOLDER_ID"
```

**Primera ejecución:** Abrirá navegador para autenticar con Google. Aprueba y cierra.

### Opción B: Con archivo de configuración

1. Edita `config_pipeline_local.json`:
   ```json
   {
     "drive_folder_id": "TU_FOLDER_ID_AQUI",
     "output_dir": "C:\\Users\\manue\\.cache\\twnel_pipeline\\reports",
     "db_path": "C:\\Users\\manue\\.cache\\twnel_pipeline\\pipeline.db",
     "sample_size": null
   }
   ```

2. Ejecuta:
   ```bash
   python run_pipeline_locally.py --config config_pipeline_local.json
   ```

### Opción C: Testing con sample pequeño

```bash
python run_pipeline_locally.py --folder-id "TU_FOLDER_ID" --sample-size 100
```

Procesa solo 100 templates (para testing rápido).

## 📊 Salida Esperada

Mientras se ejecuta:
```
2026-05-08 14:32:00 - __main__ - INFO - 🚀 Iniciando pipeline local...
2026-05-08 14:32:00 - __main__ - INFO - ✅ Autenticado con Google Drive
2026-05-08 14:32:01 - __main__ - INFO - Buscando parquets en carpeta...
2026-05-08 14:32:05 - __main__ - INFO -   Descargando datos_20260508.parquet...
2026-05-08 14:32:10 - __main__ - INFO - ✅ Datos_20260508.parquet cargado (50000 filas)
2026-05-08 14:32:10 - __main__ - INFO - Total: 50000 mensajes a procesar
2026-05-08 14:32:10 - __main__ - INFO - Templates únicos extraídos: 2050
...
```

Al terminar:
```
╔════════════════════════════════════════════════════════════════╗
║           📊 RULE CLASSIFIER - REPORTE LOCAL                   ║
╚════════════════════════════════════════════════════════════════╝

🎯 COBERTURA POR TEMPLATES:
   Clasificados:     1,230 / 2,050 (60.0%)
   Sin clasificar:     820 / 2,050 (40.0%)

📱 COBERTURA POR MENSAJES:
   Clasificados:     45,000 (90.0%)
   Sin clasificar:     5,000 (10.0%)
   Total:             50,000

💰 AHORRO ESTIMADO (vs LLM):
   Sin L0: $0.205 (LLM x todos)
   Con L0: $0.082 (LLM x sin clasificar)
   Ahorro: $0.123 (60.0%) 🎉

📂 DISTRIBUCIÓN POR CATEGORÍA
────────────────────────────────────────────────────────────────
  banking::otp_2fa                400 templates | 15,000 msgs (33.3%)
  healthcare::eps                 250 templates | 10,000 msgs (22.2%)
  commerce_retail::ecommerce      300 templates |  8,000 msgs (17.8%)
  digital_services::otp_2fa       150 templates |  6,000 msgs (13.3%)
  ...
```

## 📁 Archivos Generados

En `C:\Users\manue\.cache\twnel_pipeline\reports\`:

| Archivo | Contenido | Uso |
|---------|-----------|-----|
| `reporte_YYYYMMDD_HHMMSS.txt` | Resumen con métricas | Lectura rápida |
| `classified_templates_*.csv` | Templates clasificados | ✅ Validación |
| `unclassified_templates_*.csv` | Top 100 sin clasificar | 🔄 Crear nuevas reglas |

Base de datos SQL (persistente):
```
C:\Users\manue\.cache\twnel_pipeline\pipeline.db
```

## 🔍 Consultar Base de Datos Después

```python
import asyncio
from pipeline.storage import SQLTemplateStore, DatabaseConfig

async def check_results():
    config = DatabaseConfig()  # Lee pipeline.db automáticamente
    store = SQLTemplateStore(config=config)
    await store.initialize()
    
    # Métricas por nivel
    stats = await store.stats_by_level()
    for stat in stats:
        print(f"{stat['level_used']}: {stat['count']} templates, "
              f"avg confidence: {stat['avg_confidence']:.2%}")
    
    # Top 10 sin clasificar (para agregar nuevas reglas)
    unclassified = await store.query_by_confidence(min_conf=0.0, max_conf=0.99)
    for t in unclassified[:10]:
        print(f"- {t['template_id']}: {t['template_text']}")

asyncio.run(check_results())
```

## 🎯 Workflow Recomendado

### 1️⃣ Ejecutar pipeline (primera vez)
```bash
python run_pipeline_locally.py --folder-id "TU_FOLDER_ID"
```

### 2️⃣ Revisar top 100 sin clasificar
Abrir `unclassified_templates_*.csv` en Excel/Sheets
- Agrupar por `client_name`
- Ordenar por `frequency` descendente
- Identificar patrones

### 3️⃣ Crear nuevas reglas
Editar `pipeline/stages/rule_classifier.py`:
```python
CLASSIFICATION_RULES.extend([
    ClassificationRule(
        name="mi_nueva_regla",
        label="categoria::subcategoria",
        priority=25,
        required_all=frozenset({"TOKEN1", "TOKEN2"}),
    ),
])
```

### 4️⃣ Re-ejecutar y medir
```bash
python run_pipeline_locally.py --folder-id "TU_FOLDER_ID"
```
Comparar cobertura antes/después

## 💡 Tips

### Speed: Procesar sin descargar de Drive
```bash
# Descarga una sola vez
python run_pipeline_locally.py --folder-id "ID" --output-dir "./data"

# Luego procesa offline (copia parquets a carpeta local)
# Edita config para apuntar a carpeta local
python run_pipeline_locally.py --no-drive-auth
```

### Debug: Sample pequeño
```bash
# Prueba con 50 templates
python run_pipeline_locally.py --folder-id "ID" --sample-size 50
```

### Custom output
```bash
python run_pipeline_locally.py --folder-id "ID" --output-dir "./mi_folder"
```

## ⚠️ Troubleshooting

### "No se puede importar pipeline"
```bash
# Reinstalar en modo desarrollo
pip install -e .
```

### "ModuleNotFoundError: google_auth_oauthlib"
```bash
pip install google-auth-oauthlib pydrive2
```

### "Folder ID no encontrado"
- Verifica el folder ID es correcto
- El folder debe estar en la raíz de tu Drive personal
- Comparte carpeta conmigo si no es accesible

### "Timeout en Drive"
- Intenta con `--sample-size 100` primero
- Divide archivos grandes en múltiples carpetas

---

**¡Listo! Tu pipeline local está corriendo. 🚀**
