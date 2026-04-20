#!/usr/bin/env python3
"""
test_real_data_limited.py - Prueba con LÍMITE de registros

Para parquets muy grandes (6.7M filas), lee solo los primeros
N registros para evitar saturar memoria.

Uso:
    python3 test_real_data_limited.py
"""

import sys
import time
from collections import Counter

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.data_reader import read_messages_limited


def print_sep(title=""):
    if title:
        print(f"\n{'='*70}\n  {title}\n{'='*70}\n")
    else:
        print(f"{'='*70}\n")


def main():
    parquet_path = "/home/manuel-cruz/Desktop/Twnel/Diciembre2025-20260330T205027Z-1-003/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    print_sep("🚀 PRUEBA CON LÍMITE DE REGISTROS")
    print("Nota: Parquet tiene 6.7M filas, leeremos solo 50k para testing.\n")

    # Leer limitado
    start = time.time()
    messages = read_messages_limited(parquet_path, limit=50000, verbose=True)
    elapsed = time.time() - start

    print(f"\n⏱️  Tiempo total: {elapsed:.2f}s")
    print(f"📈 Velocidad: {len(messages)/elapsed:,.0f} msg/seg\n")

    # ESTADÍSTICAS
    print_sep("📊 ESTADÍSTICAS DE LA MUESTRA (50k mensajes)")

    unique_clients = len(set(m.client_name for m in messages if m.client_name))
    unique_operators = len(set(m.operator_name for m in messages if m.operator_name))
    unique_phones = len(set(m.phone_number for m in messages))
    unique_priorities = len(set((m.priority_id, m.priority_description) for m in messages))

    print(f"Clientes únicos: {unique_clients}")
    print(f"Operadores únicos: {unique_operators}")
    print(f"Números de teléfono únicos: {unique_phones:,}")
    print(f"Prioridades distintas: {unique_priorities}")

    # TOP CLIENTES
    print_sep("🏆 TOP 5 CLIENTES")

    client_counts = Counter(m.client_name for m in messages if m.client_name)
    for i, (client, count) in enumerate(client_counts.most_common(5), 1):
        pct = (count / len(messages)) * 100
        bar = "█" * int(pct / 2)
        print(f"{i}. {client:40} | {count:6,} ({pct:5.1f}%) {bar}")

    # OPERADORES
    print_sep("📱 DISTRIBUCIÓN POR OPERADOR")

    operator_counts = Counter(m.operator_name for m in messages if m.operator_name)
    for operator, count in operator_counts.most_common():
        pct = (count / len(messages)) * 100
        bar = "█" * int(pct / 3)
        print(f"{operator:20} | {count:6,} ({pct:5.1f}%) {bar}")

    # PRIORIDADES
    print_sep("⚡ DISTRIBUCIÓN DE PRIORIDADES")

    priority_counts = Counter(
        (m.priority_id, m.priority_description)
        for m in messages
        if m.priority_id and m.priority_description
    )

    for (pid, pdesc), count in sorted(priority_counts.items()):
        pct = (count / len(messages)) * 100
        bar = "█" * int(pct / 2)
        print(f"ID={pid} | {pdesc:25} | {count:6,} ({pct:5.1f}%) {bar}")

    # MUESTRAS
    print_sep("📄 MUESTRA DE 3 MENSAJES REALES")

    for i, msg in enumerate(messages[:3], 1):
        print(f"Mensaje {i}:")
        print(f"  📞 Teléfono: {msg.phone_number}")
        print(f"  🏢 Cliente: {msg.client_name}")
        print(f"  📱 Operador: {msg.operator_name}")
        print(f"  ⚡ Prioridad: {msg.priority_description}")
        print(f"  📅 Timestamp: {msg.timestamp}")
        print(f"  📝 Texto: {msg.message[:100]}...\n")

    # RESUMEN
    print_sep("✅ PRUEBA COMPLETADA")

    print(f"""
┌─────────────────────────────────────────┐
│ DATOS EXITOSAMENTE PROCESADOS          │
├─────────────────────────────────────────┤
│ Mensajes: {len(messages):,}
│ Clientes: {unique_clients}
│ Operadores: {unique_operators}
│ Teléfonos: {unique_phones:,}
│ Tiempo: {elapsed:.2f}s
│ Velocidad: {len(messages)/elapsed:,.0f} msg/seg
└─────────────────────────────────────────┘

✨ El data_reader funciona correctamente con datos reales.

🎯 Próximas opciones:
  1. Cambiar limit=50000 a otro número para más datos
  2. Usar read_messages_streaming() para procesar TODO en chunks
  3. Pasar al siguiente módulo (text_normalizer.py)
""")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
