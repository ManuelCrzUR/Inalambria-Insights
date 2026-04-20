# 📖 Ejemplos de Uso - data_reader.py

## Uso Básico

### 1. Leer todos los mensajes entregados
```python
from pipeline.core.data_reader import read_messages

# Leer parquet + filtrar StatusId=3 + convertir a objetos
messages = read_messages("data/sms_december_2025.parquet")

print(f"Mensajes leídos: {len(messages)}")
# Output: Mensajes leídos: 487532
```

### 2. Acceder a un mensaje
```python
msg = messages[0]

print(msg.message)              # "Tu saldo es $100.000 USD"
print(msg.phone_number)         # "+573001234567"
print(msg.client_name)          # "BBVA"
print(msg.priority_description) # "High"
print(msg.status_id)            # 3 (entregado)
print(msg.timestamp)            # datetime(2025, 12, 15, 10:30:00)
```

### 3. Procesar en batch
```python
# Agrupar por cliente
from collections import defaultdict

by_client = defaultdict(list)
for msg in messages:
    by_client[msg.client_name].append(msg)

for client, msgs in by_client.items():
    print(f"{client}: {len(msgs)} mensajes")
    
# Output:
# BBVA: 125432 mensajes
# Claro: 98765 mensajes
# Amazon: 87654 mensajes
# ...
```

---

## Casos de Uso Avanzados

### 4. Filtrar por cliente específico
```python
# Todos los mensajes de BBVA
bbva_messages = [m for m in messages if m.client_name == "BBVA"]

print(f"Mensajes BBVA: {len(bbva_messages)}")
```

### 5. Estadísticas por operador
```python
from collections import Counter

operators = Counter(m.operator_name for m in messages if m.operator_name)

for operator, count in operators.most_common(3):
    print(f"{operator}: {count} mensajes")

# Output:
# Movistar: 215432 mensajes
# Claro: 187654 mensajes
# Vodafone: 84446 mensajes
```

### 6. Encontrar mensajes con características específicas
```python
# Mensajes de alta prioridad
high_priority = [
    m for m in messages 
    if m.priority_id == 1 or m.priority_description == "High"
]

print(f"Mensajes de alta prioridad: {len(high_priority)}")

# Mensajes de un operador específico
movistar_msgs = [m for m in messages if m.operator_name == "Movistar"]

print(f"Mensajes Movistar: {len(movistar_msgs)}")
```

### 7. Acceder a los datos crudos (DataFrame)
```python
from pipeline.core.data_reader import read_messages_raw

# Obtener DataFrame filtrado
df = read_messages_raw("data/sms_december_2025.parquet")

# Hacer análisis exploratorio
print(df.info())
print(df.describe())
print(df.groupby("ClientName").size())
```

---

## Integración con el Pipeline

### 8. Pipeline completo (futura arquitectura)
```python
from pipeline.core.data_reader import read_messages
from pipeline.core.text_normalizer import normalize_messages  # (próximo)
from pipeline.core.template_extractor import extract_templates  # (próximo)

# 1. Leer
messages = read_messages("data/sms.parquet")

# 2. Normalizar (próximo modulo)
normalized = normalize_messages(messages)

# 3. Extraer plantillas (próximo modulo)
templates = extract_templates(normalized)

# 4. Guardar
templates.to_parquet("output/templates_clean.parquet")
```

### 9. Con Pandas (si necesitas)
```python
from pipeline.core.data_reader import dataframe_to_sms_messages, filter_delivered_only
import pandas as pd

# Leer crudo
df = pd.read_parquet("data/sms.parquet")

# Filtrar directamente en Pandas si lo necesitas
df_cleaned = df[df["StatusId"] == 3]
df_specific_client = df_cleaned[df_cleaned["ClientName"] == "BBVA"]

# Convertir a objetos
messages = dataframe_to_sms_messages(df_specific_client)
```

### 10. Para Testing
```python
from tests.test_data_reader import create_sample_parquet
from pipeline.core.data_reader import read_messages

# Crear datos de prueba
parquet_path = create_sample_parquet("tests/sample_sms.parquet")

# Usar en tus propios tests
messages = read_messages(parquet_path, verbose=False)

assert len(messages) == 3
assert messages[0].client_name == "BBVA"
```

---

## Manejo de Errores

### ¿Qué pasa si falta un parquet?
```python
from pipeline.core.data_reader import read_messages

try:
    messages = read_messages("data/no_existe.parquet")
except FileNotFoundError as e:
    print(f"Error: {e}")
    # Output: Error: Parquet no existe: data/no_existe.parquet
```

### ¿Qué pasa si faltan columnas?
```python
try:
    messages = read_messages("data/malformed.parquet")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Faltan columnas requeridas: {'Message', 'PhoneNumber'}
```

---

## Performance

### 11. Procesar 500k mensajes
```python
import time

start = time.time()
messages = read_messages("data/sms_500k.parquet")
elapsed = time.time() - start

print(f"Procesados {len(messages)} mensajes en {elapsed:.2f}s")
# Output: Procesados 487532 mensajes en 2.34s
```

---

## Checklist de Uso

- ✅ Instalar dependencias: `pip install -r requirements.txt`
- ✅ Tener un parquet con las columnas requeridas
- ✅ Importar: `from pipeline.core.data_reader import read_messages`
- ✅ Llamar: `messages = read_messages("path/to/data.parquet")`
- ✅ Procesar: `for msg in messages: ...`

---

**Próximos módulos:** `text_normalizer.py` → `template_extractor.py` → `deduplicator.py`
