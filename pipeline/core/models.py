"""
models.py - Definición de tipos de datos para el pipeline

Este módulo define las dataclasses que representan el flujo de datos
a través del pipeline. Cada clase es un "contenedor de datos" con
tipos bien definidos.

Flujo de transformaciones:
    SMSMessage (crudo) 
    → NormalizedMessage (limpio)
    → Template (con placeholders)
    → TemplateStats (agregado)

Principio: Los tipos definen el contrato entre módulos.
Sin tipos, es fácil pasar datos incorrectos entre funciones.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime


# ============================================================================
# NIVEL 1: DATOS CRUDOS (entrada del pipeline)
# ============================================================================

@dataclass
class SMSMessage:
    """
    Representa un mensaje SMS crudo tal como viene del parquet/database.
    
    Estos son los datos de ENTRADA al pipeline, sin procesar.
    Pueden tener espacios raros, caracteres especiales, etc.
    
    Fuente: Tabla sms_data (47 columnas disponibles)
    """
    
    # Campos principales
    message: str
    """El texto del mensaje. Puede estar sin normalizar."""
    
    status_id: int
    """ID de estado: 3=entregado, 1=fallido, etc."""
    
    phone_number: str
    """Número de teléfono que recibe el mensaje (destinatario)."""
    
    # Identificadores del cliente/emisor
    client_id: Optional[int] = None
    """ID de la empresa/cliente que envía (de tabla: ClientId)."""
    
    client_name: Optional[str] = None
    """Nombre de la empresa/cliente que envía (de tabla: ClientName)."""
    
    # Prioridad y timestamps
    priority_id: Optional[int] = None
    """ID de prioridad del mensaje (de tabla: PriorityId)."""
    
    priority_description: Optional[str] = None
    """Descripción texto: 'Alto', 'Normal', 'Bajo', etc."""
    
    timestamp: Optional[datetime] = None
    """Timestamp principal (ArrivalDate o SendGatewayDate)."""
    
    # Información del operador/proveedor
    operator_id: Optional[int] = None
    """ID del operador móvil (de tabla: OperatorId)."""
    
    operator_name: Optional[str] = None
    """Nombre del operador: 'Movistar', 'Claro', 'Vodafone', etc."""
    
    # Identificadores internos
    sender_id: Optional[str] = None
    """Identificador del remitente/shortcode (de tabla: SenderId)."""
    
    mt_message_id: Optional[int] = None
    """ID único del mensaje en el sistema (de tabla: MTMessageId)."""
    
    transaction_number: Optional[str] = None
    """Número de transacción (de tabla: TransactionNumber)."""
    
    # Información de envío
    account_id: Optional[int] = None
    """ID de cuenta/facturación (de tabla: AccountId)."""
    
    account_name: Optional[str] = None
    """Nombre de la cuenta (de tabla: AccountName)."""
    
    campaign_name: Optional[str] = None
    """Nombre de la campaña SMS (de tabla: CampaignName)."""
    
    # Detalles técnicos
    segments: int = 1
    """Número de segmentos de SMS (multipart)."""
    
    part: int = 1
    """Número de parte (para SMS multipart)."""
    
    attempt: int = 1
    """Número de reintento de envío."""
    
    tool: Optional[int] = None
    """Herramienta/API usada para enviar."""
    
    request_ip: Optional[str] = None
    """IP de origen de la solicitud."""
    
    # Metadata adicional
    variables: Optional[str] = None
    """Variables de plantilla (JSON o serializado)."""
    
    metadata: Dict = field(default_factory=dict)
    """Campos adicionales dinámicos."""
    
    def __repr__(self) -> str:
        return f"SMSMessage(status={self.status_id}, client={self.client_name}, phone={self.phone_number[-4:]}, priority={self.priority_description})"


# ============================================================================
# NIVEL 2: DATOS NORMALIZADOS (tras limpieza)
# ============================================================================

@dataclass
class NormalizedMessage:
    """
    Representa un mensaje SMS normalizado.
    
    Tras pasar por TextCleaner: espacios limpios, caracteres normales,
    sin saltos de línea raros, etc.
    
    El texto está limpio pero SIN placeholders aún.
    """
    
    original_message: str
    """El mensaje tal como vino del parquet."""
    
    cleaned_message: str
    """El mensaje tras limpieza: espacios OK, caracteres normales."""
    
    status_id: int
    phone_number: str
    
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    priority_id: Optional[int] = None
    priority_description: Optional[str] = None
    
    timestamp: Optional[datetime] = None
    operator_name: Optional[str] = None
    account_name: Optional[str] = None
    
    metadata: Dict = field(default_factory=dict)
    
    def __repr__(self) -> str:
        before_len = len(self.original_message)
        after_len = len(self.cleaned_message)
        return f"NormalizedMessage(len: {before_len}→{after_len}, client={self.client_name})"


# ============================================================================
# NIVEL 3: TEMPLATES CON PLACEHOLDERS (tras extracción)
# ============================================================================

@dataclass
class Template:
    """
    Representa un mensaje con placeholders reemplazados.
    
    Tras pasar por RegexProcessor: los valores específicos se reemplazan
    con placeholders genéricos.
    
    Ej: "Tu saldo de $100.000 vence el 14/12/2025"
        → "Tu saldo de [AMOUNT] vence el [DATE]"
    """
    
    template_text: str
    """El texto con placeholders: 'Tu saldo de [AMOUNT] vence el [DATE]'."""
    
    template_id: str
    """Hash MD5 (primeros 16 chars) del template_text. ID único."""
    
    original_message: str
    """El mensaje original sin placeholders (para referencia)."""
    
    cleaned_message: str
    """El mensaje normalizado antes de placeholders."""
    
    phone_number: str
    status_id: int = 3
    """Status del mensaje original (default: 3 = entregado)."""
    
    # Información del cliente/emisor
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    
    # Prioridad
    priority_id: Optional[int] = None
    priority_description: Optional[str] = None
    
    # Timestamps y contexto
    timestamp: Optional[datetime] = None
    operator_name: Optional[str] = None
    account_name: Optional[str] = None
    
    # Tracking de transformaciones (para debugging)
    applied_rules: List[str] = field(default_factory=list)
    """Qué reglas regex se aplicaron (ej: ['url', 'amount', 'date'])."""
    
    metadata: Dict = field(default_factory=dict)
    
    def __repr__(self) -> str:
        rules_str = ",".join(self.applied_rules) if self.applied_rules else "none"
        return f"Template({self.template_id}, rules=[{rules_str}], client={self.client_name})"


# ============================================================================
# NIVEL 4: PLANTILLAS AGREGADAS (estadísticas)
# ============================================================================

@dataclass
class TemplateStats:
    """
    Representa una plantilla única CON sus estadísticas de frecuencia.
    
    Este es el "producto final" del pipeline. Es el resultado de
    GROUP BY + COUNT sobre todos los Templates.
    """
    
    template_id: str
    """Hash único de la plantilla (MD5[:16])."""
    
    template_text: str
    """El texto con placeholders."""
    
    frequency: int
    """Cuántas veces aparece esta plantilla en los datos."""
    
    client_names: List[str] = field(default_factory=list)
    """Clientes únicos que han enviado esta plantilla."""
    
    priority_ids: List[int] = field(default_factory=list)
    """Prioridades distintas registradas para esta plantilla."""
    
    first_seen: Optional[datetime] = None
    """Cuándo apareció por primera vez."""
    
    last_seen: Optional[datetime] = None
    """Cuándo fue la última vez que apareció."""
    
    phone_numbers_count: int = 0
    """Cuántos números distintos recibieron esta plantilla."""
    
    operator_names: List[str] = field(default_factory=list)
    """Operadores distintos que la procesaron."""
    
    metadata: Dict = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"TemplateStats({self.template_id}, freq={self.frequency}, clients={len(self.client_names)})"


# ============================================================================
# CONTENEDOR DE BATCH (para procesar lotes)
# ============================================================================

@dataclass
class MessageBatch:
    """
    Contenedor para procesar un lote de mensajes juntos.
    
    Permite pasar múltiples mensajes a través de un stage sin
    un DataFrame (útil para streaming o testing).
    """
    
    messages: List[SMSMessage] = field(default_factory=list)
    """Lista de mensajes SMSMessage crudos."""
    
    batch_id: str = ""
    """Identificador único del lote (ej: timestamp, número secuencial)."""
    
    timestamp: datetime = field(default_factory=datetime.now)
    """Cuándo se creó este batch."""
    
    source: str = ""
    """De dónde vino el lote (ej: 'parquet_file_001', 's3_stream')."""
    
    metadata: Dict = field(default_factory=dict)
    
    def __len__(self) -> int:
        return len(self.messages)
    
    def __repr__(self) -> str:
        return f"MessageBatch(id={self.batch_id}, size={len(self.messages)})"


# ============================================================================
# ESTADÍSTICAS GLOBALES DEL PIPELINE
# ============================================================================

@dataclass
class PipelineStats:
    """
    Resumen de estadísticas al terminar una corrida del pipeline.
    """
    
    total_messages_processed: int = 0
    """Cuántos mensajes entraron al pipeline."""
    
    messages_after_filter: int = 0
    """Cuántos pasaron el filtro de status."""
    
    unique_templates: int = 0
    """Cuántas plantillas únicas se encontraron."""
    
    total_rules_applied: int = 0
    """Cuántas veces se aplicaron reglas regex."""
    
    processing_time_seconds: float = 0.0
    """Tiempo total de procesamiento."""
    
    unique_clients: int = 0
    """Cuántos clientes/emisores distintos."""
    
    unique_operators: int = 0
    """Cuántos operadores distintos."""
    
    unique_priorities: int = 0
    """Cuántas prioridades distintas."""
    
    unique_phone_numbers: int = 0
    """Cuántos números de teléfono distintos."""
    
    errors: List[str] = field(default_factory=list)
    """Errores encontrados durante el procesamiento."""
    
    def __repr__(self) -> str:
        return (f"PipelineStats(messages={self.total_messages_processed}, "
                f"templates={self.unique_templates}, "
                f"clients={self.unique_clients}, "
                f"time={self.processing_time_seconds:.2f}s)")


# ============================================================================
# CONFIGURACIÓN DE REGEX RULES
# ============================================================================

@dataclass
class RegexRuleConfig:
    """
    Define una regla de reemplazo con regex.
    
    Se compila una sola vez al iniciar el pipeline
    y se reutiliza en todo el batch.
    """
    
    name: str
    """Nombre identificador: 'url', 'amount', 'date', etc."""
    
    pattern: str
    """Patrón regex (ej: r'\\$[\\d\\.,]+')."""
    
    placeholder: str
    """Qué poner en lugar del patrón (ej: '[AMOUNT]')."""
    
    priority: int = 0
    """Orden de aplicación (menor primero). Específico antes que general."""
    
    enabled: bool = True
    """Permite desactivar reglas sin borrarlas."""
    
    def __repr__(self) -> str:
        status = "✓" if self.enabled else "✗"
        return f"Rule({status} {self.name}, priority={self.priority})"
