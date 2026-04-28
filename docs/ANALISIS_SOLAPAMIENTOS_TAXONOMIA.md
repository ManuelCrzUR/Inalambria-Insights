# Análisis Detallado: Solapamientos en Taxonomía

**Fecha:** 28 de Abril de 2026  
**Datos:** Test de 100 plantillas frecuentes  
**Método:** Análisis de patrones de desacuerdo entre Panel 1 (gpt-4o-mini) y Panel 2 (gpt-5-nano)

---

## 📊 Matriz de Solapamientos Detectados

### NIVEL 1: Solapamientos Críticos (Obstaculizan Automatización)

#### 1️⃣ **Banking - Alertas de Seguridad**

| Aspecto | otp_2fa | fraud_alerts | Conflicto |
|---------|---------|--------------|-----------|
| **Definición** | "Contraseñas de un solo uso para autorización" | "Notificaciones de actividad sospechosa" | Ambas = seguridad |
| **Propósito** | Verificar identidad del usuario | Alertar de acceso no autorizado | ¿OTP = acceso sospechoso? |
| **Señal Credit** | Actitud prudente del usuario | Control activo del banco | Ambas positivas |
| **Ejemplo Real** | "Tu código Itaú: 847291" | "Acceso desde Colombia a las 23:30" | ¿Es lo mismo? |
| **Confusión Observada** | ❌ Mini: otp_2fa, Nano: fraud_alerts | Itaú app login (68,521 mensajes) | |

**Raíz del problema:**
- OTP es "código temporal" (tipo de mensaje)
- fraud_alert es "tipo de situación" (contexto)
- El mismo mensaje puede ser ambos

**Propuesta de fusión:**
```json
{
  "label": "banking::security_alerts",
  "description": "Cualquier notificación de seguridad bancaria: códigos OTP, 
  detección de fraude, bloqueos, accesos. Todas son señales de monitoreo activo."
}
```

---

#### 2️⃣ **Utilities - Factura vs Recordatorio de Pago**

| Aspecto | water | payment_due | Conflicto |
|---------|-------|-------------|-----------|
| **Definición** | "Facturación y consumo de acueducto" | "Recordatorio de pago vencido/próximo" | ¿Cuál es el enfoque? |
| **Enfoque** | QUÉ SERVICIO (agua) | ACCIÓN REQUERIDA (pagar) | Ortogonal |
| **Ejemplo** | "Tu factura de agua por $45,890" | "Pago vencido - EAAB" | ¿Mismo mensaje? |
| **Confusión Observada** | ❌ Mini: payment_due, Nano: water | EAAB (153,471 mensajes) | 2 instancias |

**Análisis del problema:**
```
EAAB factura = "La eaab informa que su factura ya está disponible para pago"

Interpretación A (Mini):
  → Es un recordatorio de PAGO VENCIDO → utilities::payment_due

Interpretación B (Nano):
  → Es una notificación del servicio de AGUA → utilities::water
```

**Por qué sucede:**
- Ambas categorías son válidas para el mismo mensaje
- No hay jerarquía clara (¿servicio es más importante que acción?)

**Propuesta:** Consolidar bajo enfoque de ACCIÓN
```json
{
  "label": "utilities::service_notifications",
  "description": "Cualquier notificación de servicios públicos 
  (agua, luz, gas, internet): facturas, pagos, consumo. Señal de vivienda estable."
}
```

---

#### 3️⃣ **Cobranza - Escalamiento de Severidad**

| Aspecto | collection_notice | extrajudicial_notice | legal_notice | Conflicto |
|---------|---|---|---|---|
| **Definición** | "Del prestamista original" | "Firma de recuperación pre-legal" | "Proceso judicial formal" | Niveles |
| **Severidad** | Mora temprana | Mora media | Mora grave | ¿Cuál es cuál? |
| **Señal Credit** | Estrés financiero | Riesgo elevado | Default probable | Crítica diferencia |
| **Confusión** | ❌ Mini vs Nano confunden las dos primeras | Lending vs Collections | |

**Problema crítico para Credit Scoring:**
- Estas NO son "lo mismo", son ESCALAS de severidad
- El modelo debe distinguir CLARA Y CONSISTENTEMENTE
- Si confunde, la puntuación de crédito es inútil

**Ejemplo observado:**
```
Davivienda crédito:
  Mini: lending_and_credit::payment_confirmation
  Nano: lending_and_credit::loan_related
  Arbiter: collections::extrajudicial_notice (¿TERCERA opción?)
```

**Propuesta:** Mantener jerarquía clara, mejorar descripciones
```json
{
  "label": "lending_and_credit::collection_notice",
  "description": "Notificación de atraso en pago de cuota. Del prestamista original, 
  antes de escalar a firma de cobranza. SEÑAL: Mora temprana (<30 días)."
},
{
  "label": "collections::extrajudicial_notice",
  "description": "Notificación de cobro por firma externa. Ya escaló de prestamista. 
  SEÑAL: Mora media (30-90 días)."
},
{
  "label": "collections::legal_notice",
  "description": "Proceso judicial formal. SEÑAL: Mora grave (>90 días), default próximo."
}
```

---

#### 4️⃣ **Pensión vs Transacción Bancaria**

| Aspecto | afp_contribution | banking::transaction_alerts | Conflicto |
|---------|---|---|---|
| **Definición** | "Notificación de aporte a fondo pensión" | "Confirmación de débito/crédito" | AFP es un tipo de transacción |
| **Significado** | Empleo formal registrado | Movimiento de dinero genérico | ¿Es AFP "transacción"? |
| **Señal Credit** | MUY POSITIVA (empleo formal) | Neutral (solo movimiento) | ¡OPUESTAS! |
| **Confusión Observada** | ❌ Nano ve AFP como banking::transaction | 2 instancias | |

**Por qué es grave:**
- AFP es señal de empleo formal → POSITIVO para scoring
- Si se clasifica como "transacción" pierde el contexto
- El modelo está confundiendo el SIGNIFICADO

**Propuesta:** Clarificar que no es solo transacción
```json
{
  "label": "pension_and_employment::afp_contribution",
  "description": "Notificación específica de aporte a fondo de pensión privada. 
  NO es transacción genérica. SEÑAL: Empleo formal en nómina."
}
```

Y mejorar banking::transaction_alerts:
```json
{
  "label": "banking::transaction_alerts",
  "description": "Confirmación de débito/crédito genérico. EXCLUYE: 
  pensiones (ver pension_and_employment), servicios públicos (ver utilities)."
}
```

---

### NIVEL 2: Solapamientos Menores (Documentados pero No Críticos)

#### 5️⃣ **Pago Confirmado vs Pago Recordatorio**
```
Conflicto: payment_confirmation (recibido) vs banking::payment_due (pendiente)
Tipo: OPUESTOS (confundirlos = scoring erróneo)
Observado: 1 instancia en test
Solución: Descripciones más claras en prompt
```

#### 6️⃣ **Gobierno vs Comercio (Contexto Faltante)**
```
Conflicto: government::other_public vs commerce_retail::ecommerce
Tipo: Contexto insuficiente en el texto
Ejemplo: "Avemaria: envío gratis" → ¿Por qué se parece gobierno?
Solución: Incluir información del remitente (sender_name, sender_type)
```

---

## 🔍 Análisis de Causas Raíz

### Problema 1: Taxonomía Mixta en Dimensión

```
Estructura actual INCONSISTENTE:

utilities::
  ├─ BY SERVICE (water, electricity, gas, internet)
  └─ BY ACTION (payment_due)  ❌ Inconsistencia

banking::
  ├─ BY ACTION (transaction_alerts, payment_due)
  ├─ BY FEATURE (balance_alerts)
  └─ BY PURPOSE (fraud_alerts, otp_2fa)  ❌ Inconsistencia

collections::
  └─ BY ESCALATION (extrajudicial, legal)  ✅ Consistente

commerce_retail::
  ├─ BY SEGMENT (high_end, mid_market, popular)
  └─ BY CHANNEL (ecommerce)  ❌ Inconsistencia
```

**Impacto:** Un mensaje válido puede caber en 2+ categorías sin estar "equivocado".

### Problema 2: Falta de Límites Explícitos

```
Pregunta: "Una factura de agua es ¿water o payment_due?"

Respuesta esperada: "Depende del contenido"
- Si dice "Tu consumo fue X m³" → water
- Si dice "Pago vencido desde hace 30 días" → payment_due
- Si dice "Se disponibilizó tu factura, paga ahora" → AMBOS APLICAN 😱
```

### Problema 3: Ambigüedad en el Lenguaje Natural

```
Texto: "Tu código de seguridad Bancolombia es 847291"

Interpretación A: "Código de SEGURIDAD" → banking::fraud_alerts
Interpretación B: "Código de un solo USO" → banking::otp_2fa

Ambas son técnicamente correctas.
Necesitamos regla explícita: ¿Cuál es prioridad?
```

---

## 📈 Impacto en Producción

### Extrapolación a 6.7M Mensajes/Día

Basado en test de 100:

| Solapamiento | % en Test | Mensajes/Día | Acción Requerida |
|---|---|---|---|
| banking::security_alerts | 1% | 67,000 | Manual |
| utilities::services | 2% | 134,000 | Manual |
| collections::escalation | 2% | 134,000 | Manual |
| pension vs banking | 2% | 134,000 | Manual |
| Otros solapamientos | 1% | 67,000 | Manual |
| **TOTAL SOLAPAMIENTOS** | **8%** | **536,000/día** | **Manual** |
| ABSTAIN (genuino) | 38% | 2,546,000/día | Manual |
| **TOTAL MANUAL** | **46%** | **3,082,000/día** | **⚠️ CRÍTICO** |

---

## ✅ Matriz de Decisiones

```
Para cada solapamiento:

┌─────────────────────────┬──────────────┬──────────────┬─────────────┐
│ Solapamiento            │ Fusionar?    │ Clarificar?  │ Prioridad   │
├─────────────────────────┼──────────────┼──────────────┼─────────────┤
│ otp_2fa vs fraud_alerts │ SÍ → security│ —            │ 🔴 CRÍTICA  │
│ water vs payment_due    │ SÍ → service │ —            │ 🔴 CRÍTICA  │
│ collection escalation   │ NO           │ SÍ (claro)   │ 🔴 CRÍTICA  │
│ pension vs transaction  │ SÍ (aislada) │ SÍ (prompt)  │ 🟡 MEDIA    │
│ govt vs commerce        │ NO           │ SÍ (context) │ 🟡 MEDIA    │
└─────────────────────────┴──────────────┴──────────────┴─────────────┘
```

---

## 🎯 Plan de Acción Recomendado

**Fase 1: Redefinir (1 semana)**
- Consolidar otp_2fa + fraud_alerts → banking::security_alerts
- Consolidar utilities services → utilities::service_notifications
- Clarificar collection notices → mantener estructura pero mejorar descripciones

**Fase 2: Validar (1 semana)**
- Re-correr test de 100 con nueva taxonomía
- Medir reducción de ABSTAIN
- Validar que credit scoring logic sigue siendo válida

**Fase 3: Implementar (2 semanas)**
- Actualizar datos de entrenamiento
- Re-entrenar modelo si es necesario
- Deploy a producción

**Resultado esperado:**
- Solapamientos explícitos: 8% → <2%
- ABSTAIN: 38% → ~10%
- Automatización: 54% → ~88%

