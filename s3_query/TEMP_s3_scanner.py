"""
TEMP_s3_scanner.py - Consulta S3 via DuckDB + httpfs

DuckDB con httpfs hace pushdown de filtros de partición hive (year/month)
y solo descarga row groups que coinciden con los teléfonos consultados.
Memoria: ~3GB techo duro. Sin archivos en disco.
"""

import duckdb
import pandas as pd
from datetime import date, timedelta
import os
from pathlib import Path


def _get_duckdb_conn(memory_limit: str = "3GB", region: str = "us-east-2") -> duckdb.DuckDBPyConnection:
    """
    Crea conexión DuckDB in-memory con httpfs para acceso a S3.

    En EC2 con IAM role: credenciales se resuelven automáticamente vía IMDS.
    Fallback: lee AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY de env vars.
    """
    conn = duckdb.connect()  # in-memory connection

    # Instalar y cargar extensión httpfs
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")

    # Limitar RAM
    conn.execute(f"SET memory_limit='{memory_limit}';")

    # Región S3
    conn.execute(f"SET s3_region='{region}';")

    # Usar IAM role en EC2 (credential_chain = IMDS)
    conn.execute("SET s3_use_credential_chain=true;")

    return conn


def _build_partition_filter(lookback_days: int) -> tuple[str, date]:
    """
    Calcula filtro de partición hive para pushdown.

    Para lookback_days=365 desde hoy (2026-05-13):
    start_date = 2025-05-13 → año 2025

    Retorna: (filtro_año, fecha_inicio)
    El filtro año poda particiones antes del año requerido.
    La fecha se usa luego para filtro exacto de ArrivalDate.
    """
    start_date = date.today() - timedelta(days=lookback_days)
    year_filter = f"year >= {start_date.year}"
    return year_filter, start_date


def scan_messages(
    phones: list[str],
    lookback_days: int = 365,
    bucket: str = "s3://inalambria-db-sms/imp3",
    region: str = "us-east-2",
) -> pd.DataFrame:
    """
    Consulta S3 parquets via DuckDB, retorna DataFrame filtrado.

    Solo descarga row groups de particiones que coinciden con:
    - StatusId = 3 (mensajes entregados)
    - year >= start_year (pushdown de partición hive)
    - ArrivalDate >= start_date (row group filtering)
    - PhoneNumber IN (phones) (filtrando en memoria)

    Args:
        phones: Lista de números de teléfono (ej: ["573001234567", "573009876543"])
        lookback_days: Días hacia atrás (default 365)
        bucket: S3 bucket path con hive partitioning
        region: AWS region (default us-east-2)

    Returns:
        DataFrame con columnas: PhoneNumber, Message, ArrivalDate

    Raises:
        duckdb.CatalogException: Si el bucket/path no existe o no hay permisos
        ValueError: Si la lista de teléfonos está vacía
    """
    if not phones:
        raise ValueError("phones list cannot be empty")

    conn = _get_duckdb_conn(region=region)

    try:
        partition_filter, start_date = _build_partition_filter(lookback_days)

        # Escapar teléfonos para SQL (aunque DuckDB parametriza, ser explícito)
        phone_list = ", ".join(f"'{p}'" for p in phones)

        query = f"""
            SELECT PhoneNumber, Message, ArrivalDate
            FROM read_parquet(
                '{bucket}/**/*.parquet',
                hive_partitioning = true,
                union_by_name = true
            )
            WHERE StatusId = 3
              AND {partition_filter}
              AND ArrivalDate >= CAST('{start_date}' AS DATE)
              AND PhoneNumber IN ({phone_list})
            ORDER BY PhoneNumber, ArrivalDate
        """

        df = conn.execute(query).df()

        return df

    finally:
        conn.close()


def scan_messages_batch(
    phones: list[str],
    batch_size: int = 100,
    lookback_days: int = 365,
    bucket: str = "s3://inalambria-db-sms/imp3",
    region: str = "us-east-2",
) -> dict[str, pd.DataFrame]:
    """
    Consulta múltiples teléfonos en lotes, retorna dict {phone: DataFrame}.

    Útil para no sobrecargar memoria con muchos teléfonos a la vez.
    Cada lote se consulta por separado.

    Args:
        phones: Lista de teléfonos
        batch_size: Teléfonos por consulta
        lookback_days: Días hacia atrás
        bucket: S3 bucket path
        region: AWS region

    Returns:
        Dict {phone_number: DataFrame}
    """
    results = {}

    for i in range(0, len(phones), batch_size):
        batch = phones[i : i + batch_size]
        df_batch = scan_messages(batch, lookback_days, bucket, region)

        for phone in batch:
            results[phone] = df_batch[df_batch["PhoneNumber"] == phone].copy()

    return results
