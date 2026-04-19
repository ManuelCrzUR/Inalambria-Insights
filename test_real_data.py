#!/usr/bin/env python3
"""
test_real_data.py - Prueba del data_reader con datos REALES

Este script muestra cómo usar el reader en producción
y analiza las características de los datos leídos.
"""

import sys
import time
from collections import Counter
from datetime import datetime

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.data_reader import read_messages, read_messages_raw
from pipeline.core.models import SMSMessage


def print_separator(title=""):
    """Imprime un separador bonito"""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    else:
        print(f"{'='*70}\n")


def analyze_real_data(parquet_path: str):
    """
    Analiza un parquet real usando el data_reader.

    Muestra:
    - Estadísticas de lectura (tiempo, volumen)
    - Distribución de datos
    - Calidad de los datos
    """

    print_separator("🚀 PRUEBA REAL DEL DATA READER")

    # 1. LECTURA Y TIMING
    print("\n1️⃣  LECTURA DEL PARQUET")
    print(f"{'-'*70}")
    print(f"Ruta: {parquet_path}")

    start = time.time()
    messages = read_messages(parquet_path, verbose=True)
    elapsed = time.time() - start

    print(f"\n📈 Estadísticas de lectura:")
    print(f"   Tiempo total: {elapsed:.2f}s")
    print(f"   Velocidad: {len(messages)/elapsed:,.0f} mensajes/segundo")
    print(f"   ✅ Leídos {len(messages):,} mensajes")

    if len(messages) == 0:
        print("❌ No hay mensajes para procesar")
        return

    # 2. ESTADÍSTICAS BÁSICAS
    print_separator("📊 ESTADÍSTICAS BÁSICAS")

    unique_clients = len(set(m.client_name for m in messages if m.client_name))
    unique_operators = len(set(m.operator_name for m in messages if m.operator_name))
    unique_phones = len(set(m.phone_number for m in messages if m.phone_number))
    unique_priorities = len(set(m.priority_id for m in messages if m.priority_id))

    print(f"Clientes únicos: {unique_clients}")
    print(f"Operadores únicos: {unique_operators}")
    print(f"Números de teléfono únicos: {unique_phones:,}")
    print(f"Prioridades distintas: {unique_priorities}")

    # 3. TOP CLIENTES
    print_separator("🏆 TOP 10 CLIENTES (por volumen)")

    client_counts = Counter(m.client_name for m in messages if m.client_name)
    for i, (client, count) in enumerate(client_counts.most_common(10), 1):
        pct = (count / len(messages)) * 100
        bar = "█" * int(pct / 2)
        print(f"{i:2}. {client:40} | {count:8,} ({pct:5.1f}%) {bar}")

    # 4. TOP OPERADORES
    print_separator("📱 DISTRIBUCIÓN POR OPERADOR")

    operator_counts = Counter(m.operator_name for m in messages if m.operator_name)
    total_with_operator = sum(1 for m in messages if m.operator_name)

    for operator, count in operator_counts.most_common():
        pct = (count / total_with_operator) * 100 if total_with_operator else 0
        bar = "█" * int(pct / 5)
        print(f"{operator:20} | {count:8,} ({pct:5.1f}%) {bar}")

    # 5. PRIORIDADES
    print_separator("⚡ DISTRIBUCIÓN DE PRIORIDADES")

    priority_counts = Counter(
        (m.priority_id, m.priority_description)
        for m in messages
        if m.priority_id and m.priority_description
    )

    for (pid, pdesc), count in sorted(priority_counts.items()):
        pct = (count / len(messages)) * 100
        bar = "█" * int(pct / 2)
        print(f"ID={pid} | {pdesc:30} | {count:8,} ({pct:5.1f}%) {bar}")

    # 6. MUESTRAS DE DATOS
    print_separator("📄 MUESTRA DE 3 MENSAJES REALES")

    for i, msg in enumerate(messages[:3], 1):
        print(f"\nMensaje {i}:")
        print(f"  Teléfono: {msg.phone_number}")
        print(f"  Cliente: {msg.client_name}")
        print(f"  Operador: {msg.operator_name}")
        print(f"  Prioridad: {msg.priority_description}")
        print(f"  Status: {msg.status_id} ✅")
        print(f"  Timestamp: {msg.timestamp}")
        print(f"  Texto: {msg.message[:80]}{'...' if len(msg.message) > 80 else ''}")

    # 7. CALIDAD DE DATOS
    print_separator("🔍 ANÁLISIS DE CALIDAD")

    with_phone = sum(1 for m in messages if m.phone_number)
    with_client = sum(1 for m in messages if m.client_name)
    with_operator = sum(1 for m in messages if m.operator_name)
    with_timestamp = sum(1 for m in messages if m.timestamp)

    print(f"Con teléfono: {with_phone:,} / {len(messages):,} ({100*with_phone/len(messages):.1f}%)")
    print(f"Con cliente: {with_client:,} / {len(messages):,} ({100*with_client/len(messages):.1f}%)")
    print(f"Con operador: {with_operator:,} / {len(messages):,} ({100*with_operator/len(messages):.1f}%)")
    print(f"Con timestamp: {with_timestamp:,} / {len(messages):,} ({100*with_timestamp/len(messages):.1f}%)")

    # 8. TIEMPO DE MENSAJES
    if with_timestamp > 0:
        timestamps = [m.timestamp for m in messages if m.timestamp]
        min_time = min(timestamps)
        max_time = max(timestamps)
        print(f"\nRango temporal:")
        print(f"  Inicio: {min_time}")
        print(f"  Final: {max_time}")
        print(f"  Duración: {(max_time - min_time).total_seconds() / 3600:.1f} horas")

    # 9. RESUMEN
    print_separator("✅ RESUMEN FINAL")

    print(f"""
┌─────────────────────────────────────────────┐
│ DATOS EXITOSAMENTE PROCESADOS              │
├─────────────────────────────────────────────┤
│ Mensajes: {len(messages):,}
│ Clientes únicos: {unique_clients}
│ Operadores: {unique_operators}
│ Números únicos: {unique_phones:,}
│ Velocidad: {len(messages)/elapsed:,.0f} msg/seg
│ Tiempo: {elapsed:.2f}s
└─────────────────────────────────────────────┘
    """)


if __name__ == "__main__":
    parquet_path = "/home/manuel-cruz/Desktop/Twnel/Diciembre2025-20260330T205027Z-1-003/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    try:
        analyze_real_data(parquet_path)
        print("\n🎉 Prueba completada sin errores\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
