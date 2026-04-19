"""
data_reader.py - Lectura de datos desde parquet

Responsabilidades:
- Leer archivos parquet (local)
- Filtrar mensajes entregados (StatusId=3)
- Convertir a objetos SMSMessage tipados
- Streaming por row_groups (para archivos grandes)

Patrón: Funciones simples y composables.
Cada función hace UNA cosa. Fácil de testear y entender.
"""

from typing import List, Optional, Generator
from pathlib import Path
import pandas as pd
from datetime import datetime

from .models import SMSMessage

try:
    import pyarrow.parquet as pq
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False


# ============================================================================
# CAMPOS REQUERIDOS Y MAPEOS
# ============================================================================

REQUIRED_COLUMNS = {
    "Message": "message",
    "PhoneNumber": "phone_number",
    "StatusId": "status_id",
    "ClientId": "client_id",
    "ClientName": "client_name",
    "PriorityId": "priority_id",
    "PriorityDescription": "priority_description",
    "OperatorName": "operator_name",
    "ArrivalDate": "timestamp",
    "AccountName": "account_name",
}

OPTIONAL_COLUMNS = {
    "SenderId": "sender_id",
    "OperatorId": "operator_id",
    "AccountId": "account_id",
    "MTMessageId": "mt_message_id",
    "TransactionNumber": "transaction_number",
    "CampaignName": "campaign_name",
    "Segments": "segments",
    "Part": "part",
    "Attempt": "attempt",
    "Tool": "tool",
    "RequestIp": "request_ip",
    "Variables": "variables",
}


# ============================================================================
# VALIDACIÓN
# ============================================================================

def validate_required_columns(df: pd.DataFrame) -> None:
    """
    Valida que el DataFrame tenga todas las columnas requeridas.

    Args:
        df: DataFrame a validar

    Raises:
        ValueError: Si faltan columnas requeridas
    """
    missing = set(REQUIRED_COLUMNS.keys()) - set(df.columns)

    if missing:
        available = ", ".join(sorted(df.columns))
        raise ValueError(
            f"Faltan columnas requeridas: {missing}\n"
            f"Disponibles: {available}"
        )


# ============================================================================
# LECTURA CRUDA
# ============================================================================

def read_raw_parquet(path: str) -> pd.DataFrame:
    """
    Lee un archivo parquet sin procesamiento.

    Args:
        path: Ruta al archivo .parquet

    Returns:
        DataFrame con todos los mensajes

    Raises:
        FileNotFoundError: Si el archivo no existe
        Exception: Si hay error al leer parquet
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Parquet no existe: {path}")

    try:
        df = pd.read_parquet(path)
        return df
    except Exception as e:
        raise Exception(f"Error leyendo parquet {path}: {e}")


# ============================================================================
# FILTRADO
# ============================================================================

def filter_delivered_only(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra solo mensajes con StatusId=3 (entregados correctamente).

    StatusId=3 → Mensaje entregado sin problemas
    Otros StatusId → Fallido, retransmitido, pendiente, etc.

    Args:
        df: DataFrame crudo

    Returns:
        DataFrame con solo mensajes entregados
    """
    before_count = len(df)
    df_filtered = df[df["StatusId"] == 3].copy()
    after_count = len(df_filtered)

    filtered_out = before_count - after_count
    if filtered_out > 0:
        print(f"ℹ️  Filtrados {filtered_out} mensajes no entregados "
              f"({after_count} / {before_count} mantenidos)")

    return df_filtered


# ============================================================================
# CONVERSIÓN A OBJETOS
# ============================================================================

def _parse_timestamp(value) -> Optional[datetime]:
    """
    Convierte un valor a datetime, retorna None si es inválido.

    Args:
        value: Valor a convertir (puede ser None, str, datetime, etc)

    Returns:
        datetime object o None
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, datetime):
        return value

    try:
        return pd.to_datetime(value)
    except Exception:
        return None


def _extract_sms_message(row: pd.Series) -> SMSMessage:
    """
    Convierte una fila de DataFrame a un objeto SMSMessage.

    Esta función es el "contrato" entre los datos crudos
    y la estructura tipada del pipeline.

    Args:
        row: Fila de un DataFrame

    Returns:
        SMSMessage completamente inicializado
    """
    # Campos requeridos (obligatorios)
    msg = SMSMessage(
        message=str(row.get("Message", "")),
        status_id=int(row.get("StatusId", 0)),
        phone_number=str(row.get("PhoneNumber", "")),
        client_id=_safe_int(row.get("ClientId")),
        client_name=_safe_str(row.get("ClientName")),
        priority_id=_safe_int(row.get("PriorityId")),
        priority_description=_safe_str(row.get("PriorityDescription")),
        timestamp=_parse_timestamp(row.get("ArrivalDate")),
        operator_id=_safe_int(row.get("OperatorId")),
        operator_name=_safe_str(row.get("OperatorName")),
        account_id=_safe_int(row.get("AccountId")),
        account_name=_safe_str(row.get("AccountName")),
        sender_id=_safe_str(row.get("SenderId")),
        mt_message_id=_safe_int(row.get("MTMessageId")),
        transaction_number=_safe_str(row.get("TransactionNumber")),
        campaign_name=_safe_str(row.get("CampaignName")),
        segments=_safe_int(row.get("Segments", 1)) or 1,
        part=_safe_int(row.get("Part", 1)) or 1,
        attempt=_safe_int(row.get("Attempt", 1)) or 1,
        tool=_safe_int(row.get("Tool")),
        request_ip=_safe_str(row.get("RequestIp")),
        variables=_safe_str(row.get("Variables")),
    )

    return msg


def _safe_int(value) -> Optional[int]:
    """Convierte valor a int, retorna None si falla."""
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_str(value) -> Optional[str]:
    """Convierte valor a str, retorna None si está vacío."""
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    return s if s else None


def dataframe_to_sms_messages(df: pd.DataFrame) -> List[SMSMessage]:
    """
    Convierte un DataFrame a lista de SMSMessage.

    Valida que todas las columnas requeridas existan,
    luego itera fila por fila.

    Args:
        df: DataFrame con datos SMS

    Returns:
        List[SMSMessage] — uno por fila del DataFrame

    Raises:
        ValueError: Si faltan columnas requeridas
    """
    validate_required_columns(df)

    messages = []
    for idx, row in df.iterrows():
        try:
            msg = _extract_sms_message(row)
            messages.append(msg)
        except Exception as e:
            print(f"⚠️  Error en fila {idx}: {e}")
            continue

    return messages


# ============================================================================
# API PRINCIPAL
# ============================================================================

def read_messages(path: str, verbose: bool = True) -> List[SMSMessage]:
    """
    Endpoint principal: lee parquet y retorna mensajes entregados.

    Flujo:
    1. Lee parquet crudo
    2. Filtra StatusId=3 (entregados)
    3. Convierte a objetos SMSMessage

    Args:
        path: Ruta al archivo .parquet
        verbose: Si True, imprime información de progreso

    Returns:
        List[SMSMessage] — solo mensajes entregados correctamente

    Raises:
        FileNotFoundError: Si el parquet no existe
        ValueError: Si el parquet no tiene las columnas necesarias
    """
    if verbose:
        print(f"📖 Leyendo parquet: {path}")

    # 1. Leer crudo
    df = read_raw_parquet(path)
    if verbose:
        print(f"   → {len(df)} mensajes totales")

    # 2. Filtrar entregados
    df_delivered = filter_delivered_only(df)
    if verbose:
        print(f"   → {len(df_delivered)} mensajes entregados")

    # 3. Convertir a objetos
    messages = dataframe_to_sms_messages(df_delivered)
    if verbose:
        print(f"   → ✅ {len(messages)} SMSMessage creados")

    return messages


def read_messages_raw(path: str) -> pd.DataFrame:
    """
    Retorna el DataFrame filtrado y listo para inspección.
    Útil para debugging y análisis exploratorio.

    Args:
        path: Ruta al archivo .parquet

    Returns:
        DataFrame con solo mensajes entregados
    """
    df = read_raw_parquet(path)
    df_delivered = filter_delivered_only(df)
    return df_delivered


# ============================================================================
# STREAMING (Para archivos grandes - procesa en chunks)
# ============================================================================

def read_messages_streaming(
    path: str,
    chunk_size: int = 50000,
    verbose: bool = True
):
    """
    Lee parquet en chunks para no saturar memoria.

    Ideal para archivos de millones de registros.
    Usa un generator que yield chunks de mensajes.

    Args:
        path: Ruta al archivo .parquet
        chunk_size: Cuántos mensajes por chunk (default: 50k)
        verbose: Mostrar progreso

    Yields:
        List[SMSMessage] — chunks de mensajes

    Ejemplo:
        for chunk in read_messages_streaming("data.parquet", chunk_size=50000):
            # Procesar chunk sin saturar memoria
            for msg in chunk:
                print(msg.phone_number)
    """
    if verbose:
        print(f"📖 Streaming parquet: {path} (chunk_size={chunk_size:,})")

    # Leer parquet en chunks directamente
    parquet_file = Path(path)
    if not parquet_file.exists():
        raise FileNotFoundError(f"Parquet no existe: {path}")

    try:
        # Leer en chunks automáticos
        chunk_num = 0
        for df_chunk in pd.read_parquet(path):
            chunk_num += 1

            # Filtrar
            df_filtered = df_chunk[df_chunk["StatusId"] == 3].copy()

            if len(df_filtered) == 0:
                continue

            # Convertir
            messages = dataframe_to_sms_messages(df_filtered)

            if verbose:
                print(f"   → Chunk {chunk_num}: {len(messages):,} mensajes")

            yield messages

    except Exception as e:
        raise Exception(f"Error leyendo parquet en streaming {path}: {e}")


def read_messages_limited(
    path: str,
    limit: int = 100000,
    verbose: bool = True
) -> List[SMSMessage]:
    """
    Lee un máximo de N mensajes (útil para testing).

    Alternativa a read_messages() cuando el archivo es muy grande
    y solo quieres una muestra.

    Args:
        path: Ruta al archivo .parquet
        limit: Máximo de mensajes a leer (default: 100k)
        verbose: Mostrar progreso

    Returns:
        List[SMSMessage] — hasta 'limit' mensajes

    Ejemplo:
        # Lee solo 100k mensajes en vez de 6.7M
        messages = read_messages_limited("data.parquet", limit=100000)
    """
    if verbose:
        print(f"📖 Leyendo parquet (limitado a {limit:,}): {path}")

    # Leer crudo
    df = read_raw_parquet(path)
    if verbose:
        print(f"   → {len(df):,} mensajes totales")

    # Filtrar
    df_delivered = filter_delivered_only(df)

    # Limitar
    df_limited = df_delivered.iloc[:limit]
    if verbose:
        print(f"   → {len(df_limited):,} mensajes después de límite")

    # Convertir
    messages = dataframe_to_sms_messages(df_limited)
    if verbose:
        print(f"   → ✅ {len(messages)} SMSMessage creados")

    return messages


# ============================================================================
# STREAMING POR ROW_GROUPS (Para archivos enormes - DIVIDE Y VENCERÁS)
# ============================================================================

def iter_parquet_chunks(
    path: str,
    delivered_only: bool = True,
    verbose: bool = True
) -> Generator[pd.DataFrame, None, None]:
    """
    Lee parquet por row_groups nativos (divide y vencerás).

    Cada row_group (~50k-200k filas) se carga en memoria,
    se procesa, y se libera. Nunca hay más de un chunk en RAM.

    Ideal para archivos de millones de registros (6.7M+).

    Args:
        path: Ruta al archivo .parquet
        delivered_only: Filtrar StatusId=3
        verbose: Mostrar progreso

    Yields:
        pd.DataFrame — un row_group a la vez

    Ejemplo:
        for chunk in iter_parquet_chunks("data.parquet"):
            # Procesar chunk (memory footprint mínimo)
            stats.update(chunk)
            # chunk se libera automáticamente
    """
    if not PYARROW_AVAILABLE:
        raise ImportError(
            "pyarrow es requerido para streaming. "
            "pip install pyarrow"
        )

    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Parquet no existe: {path}")

    try:
        # Abrir con pyarrow para acceso a row_groups
        pf = pq.ParquetFile(str(path_obj))
        num_groups = pf.metadata.num_row_groups

        if verbose:
            print(f"📖 Leyendo parquet por row_groups: {path}")
            print(f"   Row groups total: {num_groups}")

        # Leer row_group por row_group
        for i in range(num_groups):
            # Leer solo este row_group
            table = pf.read_row_group(i)
            df = table.to_pandas()

            # Filtrar si es necesario
            if delivered_only:
                df = df[df["StatusId"] == 3].copy()

            # Saltar chunks vacíos
            if len(df) == 0:
                continue

            if verbose and i % max(1, num_groups // 10) == 0:
                print(f"   → Row group {i+1}/{num_groups} ({len(df):,} rows)")

            yield df

            # Liberar explícitamente
            del df
            del table

        if verbose:
            print(f"   ✅ Streaming completado")

    except Exception as e:
        raise Exception(f"Error leyendo parquet por chunks {path}: {e}")
