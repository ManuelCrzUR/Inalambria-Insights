# 📋 Schema de Metadata - SMS Data

**Fuente:** Tabla `sms_data` en `sms_diciembre2025.duckdb`  
**Total de columnas:** 47  
**Última actualización:** Abril 19, 2026

---

## 🎯 Campos Principales (Implementados en models.py)

### 1. Contenido y Destinatario
| Campo | Tipo | Descripción | Uso en Pipeline |
|-------|------|-------------|-----------------|
| `Message` | VARCHAR | Texto del mensaje SMS | **Cada mensaje** |
| `PhoneNumber` | VARCHAR | Número que recibe (destinatario) | **Cada mensaje** |
| `Phone` | VARCHAR | Alias de PhoneNumber | - |

### 2. Cliente / Emisor ✅ (Cambio: sender_id → client_id + client_name)
| Campo | Tipo | Descripción | Uso en Pipeline |
|-------|------|-------------|-----------------|
| `ClientId` | BIGINT | ID único del cliente/empresa que envía | **Profile builder** |
| `ClientName` | VARCHAR | Nombre del cliente (ej: "BBVA", "CLARO") | **Cada estadística** |
| `SenderId` | VARCHAR | Identificador del remitente/shortcode | Metadata |
| `ResponsibleId` | BIGINT | ID del responsable de la cuenta | - |
| `ResponsibleName` | VARCHAR | Nombre del responsable | - |

### 3. Prioridad ✅ (Nueva en metadata)
| Campo | Tipo | Descripción | Uso en Pipeline |
|-------|------|-------------|-----------------|
| `PriorityId` | BIGINT | ID de prioridad del mensaje | **Cada plantilla** |
| `PriorityDescription` | VARCHAR | Descripción: "Alto", "Normal", "Bajo" | **Cada plantilla** |

### 4. Estado del Mensaje
| Campo | Tipo | Descripción | Uso en Pipeline |
|-------|------|-------------|-----------------|
| `StatusId` | INTEGER | Estado: 3=entregado, 1=fallido, etc | **Filtrado** |
| `StatusDescription` | VARCHAR | Texto del estado | - |

### 5. Operador / Proveedor ✅ (Nueva en metadata)
| Campo | Tipo | Descripción | Uso en Pipeline |
|-------|------|-------------|-----------------|
| `OperatorId` | BIGINT | ID del operador móvil | - |
| `OperatorName` | VARCHAR | Nombre: "Movistar", "Claro", "Vodafone" | **En TemplateStats** |

### 6. Cuenta / Facturación
| Campo | Tipo | Descripción | Uso en Pipeline |
|-------|------|-------------|-----------------|
| `AccountId` | BIGINT | ID de cuenta de facturación | - |
| `AccountName` | VARCHAR | Nombre de la cuenta | **En Template/Stats** |

### 7. Timestamps ✅ (Multiple opciones)
| Campo | Tipo | Descripción | Recomendado |
|-------|------|-------------|------------|
| `ArrivalDate` | TIMESTAMP | Cuándo llegó el mensaje al sistema | ✅ Principal |
| `InputSystemDate` | TIMESTAMP | Cuándo entró al sistema | - |
| `SendGatewayDate` | TIMESTAMP | Cuándo se envió al gateway | - |
| `ResponseGatewayDate` | TIMESTAMP | Cuándo respondió el gateway | - |
| `DequeueDate` | TIMESTAMP | Cuándo se eliminó de cola | - |
| `ValidationDate` | TIMESTAMP | Cuándo se validó | - |
| `SendGatewayDate2` | TIMESTAMP | Segundo envío al gateway | - |

### 8. SMS Multipart
| Campo | Tipo | Descripción | Uso |
|-------|------|-------------|-----|
| `Segments` | INTEGER | Número total de segmentos | **En SMSMessage** |
| `Part` | INTEGER | Número de parte actual | **En SMSMessage** |

### 9. Reintentos y Técnico
| Campo | Tipo | Descripción | Uso |
|-------|------|-------------|-----|
| `Attempt` | BIGINT | Número de reintento | **En metadata** |
| `Tool` | INTEGER | Herramienta/API de envío | **En metadata** |
| `RequestIp` | VARCHAR | IP origen de la solicitud | **En metadata** |

### 10. Campaña y Variables
| Campo | Tipo | Descripción | Uso |
|-------|------|-------------|-----|
| `CampaignName` | VARCHAR | Nombre de la campaña | **En TemplateStats** |
| `Variables` | VARCHAR | Variables de plantilla (JSON) | **En metadata** |

### 11. Identificadores Internos
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `MTMessageId` | BIGINT | ID único del mensaje |
| `TransactionNumber` | VARCHAR | Número de transacción |
| `SMPPConnectionId` | BIGINT | ID de conexión SMPP |
| `SMPPConnectionName` | VARCHAR | Nombre de conexión SMPP |
| `WSConnectionId` | BIGINT | ID de conexión Web Service |
| `WSConnectionName` | VARCHAR | Nombre conexión Web Service |
| `SendMethodId` | BIGINT | ID del método de envío |
| `MTMessageTypeId` | BIGINT | ID del tipo de mensaje |

### 12. Tickets y Respuestas
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `BindAnswer` | VARCHAR | Respuesta del bind SMPP |
| `DeliverAnswer` | VARCHAR | Respuesta de entrega |
| `TicketKDC` | VARCHAR | Ticket del sistema |

### 13. Temporales
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `Year` | INTEGER | Año (2025) |
| `Month` | INTEGER | Mes (12) |
| `Day` | VARCHAR | Día (1-31) |
| `SimpleDate` | VARCHAR | Fecha formateada |

### 14. Extras
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ShortCode` | BIGINT | Short code del emisor |
| `PackageId` | VARCHAR | ID del package |

---

## 📊 Cambios en models.py

### ✅ SMSMessage
**Antes:** `sender_id`, `metadata` genérico  
**Ahora:**
```python
# Identificadores del cliente
client_id: Optional[int] = None
client_name: Optional[str] = None

# Prioridad (NUEVA)
priority_id: Optional[int] = None
priority_description: Optional[str] = None

# Operador (NUEVA)
operator_id: Optional[int] = None
operator_name: Optional[str] = None

# Cuenta (NUEVA)
account_id: Optional[int] = None
account_name: Optional[str] = None

# Segmentación SMS (NUEVA)
segments: int = 1
part: int = 1
attempt: int = 1

# Técnico (NUEVA)
tool: Optional[int] = None
request_ip: Optional[str] = None
variables: Optional[str] = None
```

### ✅ NormalizedMessage
**Antes:** `sender_id`, campos mínimos  
**Ahora:**
```python
client_id: Optional[int] = None
client_name: Optional[str] = None
priority_id: Optional[int] = None
priority_description: Optional[str] = None
operator_name: Optional[str] = None
account_name: Optional[str] = None
```

### ✅ Template
**Antes:** `sender_id`, reducido  
**Ahora:**
```python
client_id: Optional[int] = None
client_name: Optional[str] = None
priority_id: Optional[int] = None
priority_description: Optional[str] = None
operator_name: Optional[str] = None
account_name: Optional[str] = None
```

### ✅ TemplateStats
**Antes:** `senders` (List[str])  
**Ahora:**
```python
client_names: List[str]  # En lugar de senders
priority_ids: List[int]  # Prioridades distintas
operator_names: List[str]  # Operadores distintos
phone_numbers_count: int  # En lugar de phone_numbers
```

### ✅ PipelineStats
**Ahora agrega:**
```python
unique_clients: int
unique_operators: int
unique_priorities: int
unique_phone_numbers: int
```

---

## 🎯 Recomendaciones de Uso

### Para lectura del parquet/DB
```python
# Campos obligatorios para cada mensaje
required_fields = [
    "Message",
    "PhoneNumber",
    "ClientId",
    "ClientName",
    "StatusId",
    "PriorityId",
    "PriorityDescription",
    "OperatorName",
    "ArrivalDate"  # Para timestamp
]
```

### Para normalización
- **Usar:** `PhoneNumber` como destinatario principal
- **Usar:** `ClientName` + `ClientId` para identificar emisor
- **Usar:** `PriorityDescription` (+ `PriorityId` como fallback)

### Para templates
- **Guardar:** `ClientName`, `PriorityId`, `OperatorName` en metadata
- **Indexar:** `template_id` + `client_id` para búsquedas rápidas

### Para estadísticas finales
- **Agregar por:** `client_name`, `priority_id`, `operator_name`
- **Contar:** Usuarios únicos, operadores, prioridades

---

## 📈 Query Base para Lectura

```sql
SELECT
    Message,
    PhoneNumber,
    ClientId,
    ClientName,
    PriorityId,
    PriorityDescription,
    StatusId,
    OperatorName,
    AccountName,
    Segments,
    Part,
    Attempt,
    ArrivalDate,
    CampaignName,
    MTMessageId
FROM sms_data
WHERE StatusId = 3  -- Solo entregados
LIMIT 1000
```

---

## 🔗 Relación entre tablas conceptuales

```
SMSMessage (crudo) ──MAIN KEY──> (Message, PhoneNumber)
    ├─ ClientId/ClientName (quién envía)
    ├─ PriorityId/Description (prioridad)
    ├─ OperatorName (operador móvil)
    └─ ArrivalDate (cuándo)
        ↓
   NormalizedMessage (limpio)
        ↓
   Template (con placeholders)
        ├─ template_id = hash(template_text)
        └─ Preserva: client_name, priority_id, operator_name
        ↓
   TemplateStats (agregadas)
        └─ Group By: template_id
        ├─ Agg: COUNT(*) → frequency
        ├─ Agg: DISTINCT ClientName → client_names
        ├─ Agg: DISTINCT PriorityId → priority_ids
        └─ Agg: DISTINCT OperatorName → operator_names
```

---

**Versión:** 0.1.0 | **Estado:** ✅ Finalizado | **Próximo:** Implementar `data_reader.py`
