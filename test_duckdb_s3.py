#!/usr/bin/env python3
"""
test_duckdb_s3.py - Test de conexión DuckDB a S3

Verifica que DuckDB puede conectarse a S3 usando credenciales del IAM role.
Útil para debuggear problemas de autenticación.
"""

import duckdb
import sys

print("=" * 70)
print("TEST: DuckDB + S3 (inalambria-db-sms)")
print("=" * 70)

try:
    conn = duckdb.connect()
    print("✅ DuckDB conectado")
except Exception as e:
    print(f"❌ Error al conectar DuckDB: {e}")
    sys.exit(1)

# Instalar httpfs
try:
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    print("✅ httpfs instalado y cargado")
except Exception as e:
    print(f"❌ Error al instalar httpfs: {e}")
    sys.exit(1)

# Configurar región
try:
    conn.execute("SET s3_region='us-east-2';")
    print("✅ Región S3 configurada (us-east-2)")
except Exception as e:
    print(f"❌ Error al configurar región: {e}")
    sys.exit(1)

# Intentar auto_credentials (DuckDB 1.4+)
print("\n📍 Intentando auto_credentials...")
try:
    conn.execute("SET auto_credentials=true;")
    print("✅ auto_credentials=true configurado")
except Exception as e:
    print(f"⚠️  auto_credentials no disponible: {e}")

# Test de query simple a S3
print("\n📍 Testeando query a S3...")
try:
    result = conn.execute("""
        SELECT COUNT(*) as cnt
        FROM read_parquet('s3://inalambria-db-sms/imp3/year=2026/month=05/day=01/*.parquet')
        LIMIT 1
    """).fetchall()
    print(f"✅ Query funcionó!")
    print(f"   Resultado: {result}")
except Exception as e:
    print(f"❌ Query falló: {e}")
    print("\n📋 Soluciones:")
    print("  1. Verificar IAM role: aws sts get-caller-identity")
    print("  2. Verificar S3 access: aws s3 ls s3://inalambria-db-sms/imp3/")
    print("  3. Actualizar DuckDB: pip install --upgrade duckdb")
    sys.exit(1)

conn.close()

print("\n" + "=" * 70)
print("✅ TEST EXITOSO - DuckDB puede acceder a S3")
print("=" * 70)
