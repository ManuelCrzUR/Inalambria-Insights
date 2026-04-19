# 🏗️ Arquitectura del Core - data_reader.py

## Principios de Diseño

### 1. **Funciones Simples y Composables**
Cada función hace **UNA COSA**:
- `read_raw_parquet()` → Lee y retorna
- `filter_delivered_only()` → Filtra StatusId=3
- `dataframe_to_sms_messages()` → Convierte a objetos

Puedes combinarlas de diferentes formas sin cambiar el código.

### 2. **Sin Dependencias de Negocio**
El reader solo conoce:
- Pandas (para datos)
- Datetime (para timestamps)
- SMSMessage (modelo del proyecto)

No depende de: Redis, API, clasificadores, etc.

### 3. **Fácil de Testear**
```python
# Test unitario (sin necesidad de parquets reales)
def test_dataframe_to_sms_messages():
    df = pd.DataFrame({"Message": ["hola"], ...})
    messages = dataframe_to_sms_messages(df)
    assert len(messages) == 1
```

### 4. **Errores Explícitos**
```python
# ❌ Malo - falla silenciosamente
def read_file(path):
    return pd.read_parquet(path)

# ✅ Bueno - claro qué puede fallar
def read_raw_parquet(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(f"Parquet no existe: {path}")
    try:
        return pd.read_parquet(path)
    except Exception as e:
        raise Exception(f"Error leyendo parquet {path}: {e}")
```

---

## Estructura del Código

### Sección 1: Configuración (REQUIRED_COLUMNS, OPTIONAL_COLUMNS)
```python
REQUIRED_COLUMNS = {
    "Message": "message",
    "PhoneNumber": "phone_number",
    ...
}
```
✅ **Ventaja:** Cambias nombres de columnas en un lugar.

### Sección 2: Validación
```python
def validate_required_columns(df: pd.DataFrame) -> None:
```
✅ **Ventaja:** Faltas en columnas se detectan ANTES de procesar.

### Sección 3: Lectura
```python
def read_raw_parquet(path: str) -> pd.DataFrame:
```
✅ **Ventaja:** Separado de filtrado. Útil para debugging.

### Sección 4: Filtrado
```python
def filter_delivered_only(df: pd.DataFrame) -> pd.DataFrame:
```
✅ **Ventaja:** Lógica de negocio clara (StatusId=3).

### Sección 5: Conversión
```python
def _extract_sms_message(row: pd.Series) -> SMSMessage:
def _safe_int(value) -> Optional[int]:
def _safe_str(value) -> Optional[str]:
```
✅ **Ventaja:** Conversiones atómicas, reutilizables.

### Sección 6: API Principal
```python
def read_messages(path: str, verbose: bool = True) -> List[SMSMessage]:
```
✅ **Ventaja:** Una línea para "leer parquet completamente".

---

## Flujo de Datos

```
Parquet en Disk
    ↓ read_raw_parquet()
DataFrame (todos los mensajes)
    ↓ filter_delivered_only()
DataFrame (solo StatusId=3)
    ↓ dataframe_to_sms_messages()
List[SMSMessage] (objetos tipados)
```

Cada paso es independiente:
- ¿Necesitas ver el DataFrame crudo? Usa `read_raw_parquet()`
- ¿Solo los entregados? Usa `filter_delivered_only()`
- ¿Objetos listos para el pipeline? Usa `read_messages()`

---

## Seguridad de Tipos

El código usa **type hints** en todas las funciones:

```python
# ✅ Claro qué entra y qué sale
def read_messages(path: str, verbose: bool = True) -> List[SMSMessage]:
    ...

# ❌ Ambiguo
def read_messages(path, verbose):
    ...
```

**Beneficio:** 
- IDE autocomplete funciona
- `mypy` detecta errores antes de runtime
- Documentación clara en el código

---

## Cómo Extender

### Caso 1: Agregar filtros adicionales
```python
# Crear una nueva función de filtro
def filter_by_client(df: pd.DataFrame, client_name: str) -> pd.DataFrame:
    return df[df["ClientName"] == client_name].copy()

# Usar en el pipeline
df = read_raw_parquet(path)
df = filter_delivered_only(df)
df = filter_by_client(df, "BBVA")
messages = dataframe_to_sms_messages(df)
```

### Caso 2: Soportar S3
```python
# Crear nueva función (sin tocar las existentes)
def read_s3_parquet(bucket: str, key: str) -> pd.DataFrame:
    import boto3
    s3 = boto3.client('s3')
    # ... lógica de S3
    return df

# Usar igual que el local
df = read_s3_parquet("my-bucket", "data/sms.parquet")
df_delivered = filter_delivered_only(df)
messages = dataframe_to_sms_messages(df_delivered)
```

### Caso 3: Agregar campos al SMSMessage
Si el parquet tiene una nueva columna:
1. Agrega a `REQUIRED_COLUMNS` o `OPTIONAL_COLUMNS`
2. Agrega el campo a `SMSMessage` en `models.py`
3. Actualiza `_extract_sms_message()` para asignarlo

---

## Testing

### Unitarios (sin datos reales)
```python
def test_dataframe_to_sms_messages():
    df = pd.DataFrame({...})  # Datos mínimos
    messages = dataframe_to_sms_messages(df)
    assert len(messages) == 1
```

### Integración (con datos reales)
```python
def test_read_messages_e2e():
    messages = read_messages("tests/sample_sms.parquet")
    assert len(messages) > 0
    assert all(m.status_id == 3 for m in messages)
```

### Cómo ejecutar
```bash
pip install -r requirements.txt
python -m pytest tests/test_data_reader.py -v
```

---

## Ventajas de Esta Arquitectura

| Aspecto | Ventaja |
|--------|---------|
| **Composición** | Funciones pequeñas que se combinan |
| **Testabilidad** | Cada función es independiente |
| **Mantenibilidad** | Cambios localizados |
| **Reutilización** | Mismo código en API, batch, tests |
| **Escalabilidad** | Fácil agregar formatos (CSV, SQL, S3) |
| **Claridad** | Tipos claros, errores explícitos |

---

## Próximos Pasos

1. **Instalar dependencias:**
   ```bash
   pip install pandas pyarrow numpy
   ```

2. **Probar con un parquet real:**
   ```python
   from pipeline.core.data_reader import read_messages
   
   messages = read_messages("path/to/your/data.parquet")
   print(f"✅ Leídos {len(messages)} mensajes")
   ```

3. **Crear el siguiente módulo:**
   - `text_normalizer.py` — Limpiar texto
   - `template_extractor.py` — Aplicar regex

---

**Versión:** 0.1.0 | **Estado:** ✅ Completado | **Siguiente:** `text_normalizer.py`
