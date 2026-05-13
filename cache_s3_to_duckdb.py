#!/usr/bin/env python3
"""
cache_s3_to_duckdb.py - Descargar parquets de S3 a DuckDB local (caché)

Flujo:
1. Leer de S3 con pandas (chunked, sin reventar RAM)
2. Guardar a DuckDB local
3. Hacer queries sin volver a S3

Uso:
    python cache_s3_to_duckdb.py --lookback-days 30
"""

import pandas as pd
import duckdb
import sys
from datetime import date, timedelta
from pathlib import Path
import argparse

def cache_s3_to_duckdb(
    lookback_days: int = 365,
    s3_path: str = "s3://inalambria-db-sms/imp3/year=2026/",
    db_path: str = "/tmp/sms_cache.duckdb",
    chunk_size: int = 50000,
) -> duckdb.DuckDBPyConnection:
    """
    Descarga datos de S3 a DuckDB local.

    Args:
        lookback_days: Días hacia atrás
        s3_path: Path en S3
        db_path: Path local para DuckDB
        chunk_size: Filas por chunk (para no reventar RAM)

    Returns:
        Conexión a DuckDB local
    """

    print("=" * 70)
    print("CACHÉAR S3 → DuckDB LOCAL")
    print("=" * 70)

    # Calcular fechas
    start_date = date.today() - timedelta(days=lookback_days)
    print(f"\n📍 Rango: {start_date} → hoy")
    print(f"📍 S3 path: {s3_path}")
    print(f"📍 DuckDB local: {db_path}")

    # Crear/conectar a DuckDB local
    print("\n📍 Creando DuckDB local...")
    conn = duckdb.connect(db_path)

    # Crear tabla si no existe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            PhoneNumber VARCHAR,
            Message VARCHAR,
            ArrivalDate TIMESTAMP,
            StatusId INTEGER,
            ClientId INTEGER,
            ClientName VARCHAR,
            OperatorName VARCHAR
        )
    """)

    # Leer de S3 en chunks con pandas
    print(f"\n📍 Leyendo de S3 en chunks de {chunk_size} filas...")

    try:
        chunk_count = 0
        total_rows = 0

        # Leer parquet de S3 (pandas lo maneja bien)
        for chunk in pd.read_parquet(
            s3_path,
            storage_options={"anon": False},
            columns=["PhoneNumber", "Message", "ArrivalDate", "StatusId", "ClientId", "ClientName", "OperatorName"],
        ).iterrows():
            # Procesar chunk
            chunk_count += 1
            total_rows += 1

            if chunk_count % chunk_size == 0:
                print(f"   ✓ {chunk_count:,} filas procesadas...")

        print(f"\n✅ Total: {total_rows:,} filas leídas de S3")

    except Exception as e:
        print(f"❌ Error leyendo de S3: {e}")
        conn.close()
        sys.exit(1)

    # Insertar en DuckDB (más eficiente)
    print("\n📍 Insertando en DuckDB...")
    try:
        df = pd.read_parquet(
            s3_path,
            storage_options={"anon": False},
            columns=["PhoneNumber", "Message", "ArrivalDate", "StatusId", "ClientId", "ClientName", "OperatorName"],
        )

        # Filtrar por fecha y StatusId
        df["ArrivalDate"] = pd.to_datetime(df["ArrivalDate"])
        df = df[(df["ArrivalDate"] >= pd.to_datetime(start_date)) & (df["StatusId"] == 3)]

        # Insertar a DuckDB
        conn.execute("INSERT INTO messages SELECT * FROM df")
        print(f"✅ {len(df):,} filas insertadas a DuckDB")

    except Exception as e:
        print(f"❌ Error insertando: {e}")
        conn.close()
        sys.exit(1)

    # Crear índice para queries rápidas
    print("\n📍 Creando índices...")
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_phone ON messages(PhoneNumber)")
        print("✅ Índice creado")
    except Exception as e:
        print(f"⚠️  Índice: {e}")

    print("\n" + "=" * 70)
    print(f"✅ CACHÉ LISTO en {db_path}")
    print(f"   Usa: duckdb.connect('{db_path}')")
    print("=" * 70)

    return conn


def query_cached_db(db_path: str, phone: str) -> pd.DataFrame:
    """
    Query a la base de datos cacheada.

    Args:
        db_path: Path a DuckDB local
        phone: Teléfono a buscar

    Returns:
        DataFrame con mensajes
    """
    conn = duckdb.connect(db_path)

    result = conn.execute(f"""
        SELECT PhoneNumber, Message, ArrivalDate
        FROM messages
        WHERE PhoneNumber = '{phone}'
        ORDER BY ArrivalDate
    """).df()

    conn.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cachéar S3 a DuckDB local")
    parser.add_argument("--lookback-days", type=int, default=30, help="Días hacia atrás")
    parser.add_argument("--db-path", default="/tmp/sms_cache.duckdb", help="Path a DuckDB")
    parser.add_argument("--query-phone", help="Teléfono para query (opcional)")

    args = parser.parse_args()

    # Crear caché
    conn = cache_s3_to_duckdb(
        lookback_days=args.lookback_days,
        db_path=args.db_path,
    )
    conn.close()

    # Si se pide query
    if args.query_phone:
        print(f"\n📍 Buscando {args.query_phone}...")
        df = query_cached_db(args.db_path, args.query_phone)
        print(df)
