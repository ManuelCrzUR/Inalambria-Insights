"""
test_data_reader.py - Ejemplos y tests básicos del data_reader

Estos tests muestran:
1. Cómo crear datos de prueba
2. Cómo usar el reader
3. Cómo verificar que funciona correctamente
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

from pipeline.core.data_reader import (
    read_messages,
    filter_delivered_only,
    dataframe_to_sms_messages,
)
from pipeline.core.models import SMSMessage


# ============================================================================
# FIXTURES - Datos de prueba
# ============================================================================

def create_sample_parquet(path: str = "tests/sample_sms.parquet"):
    """
    Crea un parquet de muestra para testing.

    Incluye:
    - 3 mensajes entregados (StatusId=3)
    - 2 mensajes fallidos (StatusId=1)
    """
    data = {
        "Message": [
            "Tu saldo es $100.000 USD",
            "Tu código es 123456",
            "Compra confirmada: $50.000 COP",
            "Tu código expiró",  # fallido
            "Reintentar envío",  # fallido
        ],
        "PhoneNumber": [
            "+573001234567",
            "+573001234567",
            "+573009876543",
            "+573005555555",
            "+573005555555",
        ],
        "StatusId": [3, 3, 3, 1, 1],  # Solo los primeros 3 son entregados
        "ClientId": [1, 1, 2, 3, 3],
        "ClientName": ["BBVA", "BBVA", "Amazon", "TEST", "TEST"],
        "PriorityId": [1, 2, 1, 1, 1],
        "PriorityDescription": ["High", "Normal", "High", "Normal", "Normal"],
        "OperatorName": ["Movistar", "Claro", "Vodafone", "Claro", "Movistar"],
        "ArrivalDate": [
            datetime(2026, 4, 19, 10, 0, 0),
            datetime(2026, 4, 19, 10, 5, 0),
            datetime(2026, 4, 19, 10, 10, 0),
            datetime(2026, 4, 19, 10, 15, 0),
            datetime(2026, 4, 19, 10, 20, 0),
        ],
        "AccountName": ["Account1", "Account1", "Account2", "Account3", "Account3"],
        "SenderId": ["BBVA_SMS", "BBVA_SMS", "AMZN", "TEST", "TEST"],
        "OperatorId": [1, 2, 3, 2, 1],
        "AccountId": [100, 100, 200, 300, 300],
        "MTMessageId": [1001, 1002, 1003, 1004, 1005],
        "TransactionNumber": ["TXN001", "TXN002", "TXN003", "TXN004", "TXN005"],
        "CampaignName": ["Campaign_A", "Campaign_A", "Campaign_B", "Campaign_C", "Campaign_C"],
        "Segments": [1, 1, 2, 1, 1],
        "Part": [1, 1, 1, 1, 1],
        "Attempt": [1, 1, 1, 2, 3],
        "Tool": [1, 1, 2, 1, 1],
        "RequestIp": ["192.168.1.1", "192.168.1.2", "10.0.0.1", "192.168.2.1", "192.168.2.2"],
        "Variables": [None, None, None, None, None],
    }

    df = pd.DataFrame(data)

    # Crear directorio si no existe
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(path)
    print(f"✅ Parquet de muestra creado: {path}")
    return path


# ============================================================================
# TESTS UNITARIOS
# ============================================================================

def test_filter_delivered_only():
    """Test: filtrado de mensajes entregados"""
    print("\n🧪 Test: filter_delivered_only")

    data = {
        "StatusId": [3, 3, 1, 1, 3],
        "Message": ["msg1", "msg2", "msg3", "msg4", "msg5"],
        "PhoneNumber": ["111", "222", "333", "444", "555"],
        "ClientId": [1, 1, 2, 2, 1],
        "ClientName": ["A", "A", "B", "B", "A"],
        "PriorityId": [1, 1, 1, 1, 1],
        "PriorityDescription": ["H", "H", "H", "H", "H"],
        "OperatorName": ["Op1", "Op1", "Op2", "Op2", "Op1"],
        "ArrivalDate": [None] * 5,
        "AccountName": ["Acc1"] * 5,
    }
    df = pd.DataFrame(data)

    filtered = filter_delivered_only(df)

    assert len(filtered) == 3, f"Esperaba 3, obtuve {len(filtered)}"
    assert all(filtered["StatusId"] == 3), "Todos deben tener StatusId=3"
    print("   ✅ Paso")


def test_dataframe_to_sms_messages():
    """Test: conversión de DataFrame a SMSMessage"""
    print("🧪 Test: dataframe_to_sms_messages")

    data = {
        "Message": ["Hola $100"],
        "PhoneNumber": ["+573001234567"],
        "StatusId": [3],
        "ClientId": [1],
        "ClientName": ["BBVA"],
        "PriorityId": [1],
        "PriorityDescription": ["High"],
        "OperatorName": ["Movistar"],
        "ArrivalDate": [datetime(2026, 4, 19)],
        "AccountName": ["Account1"],
    }
    df = pd.DataFrame(data)

    messages = dataframe_to_sms_messages(df)

    assert len(messages) == 1, f"Esperaba 1 mensaje, obtuve {len(messages)}"
    assert isinstance(messages[0], SMSMessage), "Debe ser SMSMessage"
    assert messages[0].message == "Hola $100"
    assert messages[0].phone_number == "+573001234567"
    assert messages[0].client_name == "BBVA"
    print("   ✅ Paso")


def test_read_messages_end_to_end():
    """Test: flujo completo (leer, filtrar, convertir)"""
    print("🧪 Test: read_messages (E2E)")

    # Crear datos de muestra
    parquet_path = create_sample_parquet()

    # Leer
    messages = read_messages(parquet_path, verbose=False)

    # Verificaciones
    assert len(messages) == 3, f"Esperaba 3 mensajes entregados, obtuve {len(messages)}"
    assert all(isinstance(m, SMSMessage) for m in messages), "Todos deben ser SMSMessage"
    assert all(m.status_id == 3 for m in messages), "Todos deben tener status_id=3"

    # Verificar contenido específico
    assert any(m.client_name == "BBVA" for m in messages), "Debe haber un BBVA"
    assert any(m.phone_number == "+573009876543" for m in messages), "Debe haber ese teléfono"

    print("   ✅ Paso")


# ============================================================================
# DEMO - Uso básico
# ============================================================================

def demo_usage():
    """Demo: cómo usar el reader en tu pipeline"""
    print("\n📚 DEMO - Uso básico del data_reader\n")

    # 1. Crear datos de muestra
    parquet_path = create_sample_parquet()

    # 2. Leer mensajes
    print("\n1️⃣  Lectura básica:")
    messages = read_messages(parquet_path)

    # 3. Acceder a los datos
    print("\n2️⃣  Primeros 2 mensajes:")
    for i, msg in enumerate(messages[:2]):
        print(f"\n   Mensaje {i+1}:")
        print(f"      Texto: {msg.message}")
        print(f"      Teléfono: {msg.phone_number}")
        print(f"      Cliente: {msg.client_name}")
        print(f"      Prioridad: {msg.priority_description}")
        print(f"      Status: {msg.status_id} (3=entregado)")

    # 4. Procesar en batch
    print(f"\n3️⃣  Procesamiento en batch:")
    print(f"   Total de mensajes: {len(messages)}")

    unique_clients = set(m.client_name for m in messages if m.client_name)
    print(f"   Clientes únicos: {len(unique_clients)} → {unique_clients}")

    unique_operators = set(m.operator_name for m in messages if m.operator_name)
    print(f"   Operadores: {len(unique_operators)} → {unique_operators}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TESTS - Data Reader")
    print("=" * 70)

    # Ejecutar tests unitarios
    test_filter_delivered_only()
    test_dataframe_to_sms_messages()
    test_read_messages_end_to_end()

    print("\n✅ Todos los tests pasaron\n")

    # Ejecutar demo
    demo_usage()

    print("\n" + "=" * 70)
    print("🎉 Data Reader está listo para usar")
    print("=" * 70)
