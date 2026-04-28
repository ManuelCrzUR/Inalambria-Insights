# Reporte Ejecutivo: Problema de Solapamiento en Taxonomía del Clasificador

**Para:** Jefe de Proyecto  
**De:** Equipo de Pipeline  
**Fecha:** 28 de Abril de 2026  
**Asunto:** Identificación de solapamientos en taxonomía que afectan clasificación automática

---

## 🚨 Problema en Una Línea

**La taxonomía de 39 categorías tiene solapamientos que causan que 38% de mensajes no puedan ser clasificados automáticamente y requieran revisión humana.**

---

## 📊 Impacto

Con 6.7M mensajes diarios:
- **38% requiere revisión humana** = **2.5M mensajes/día** que no se pueden procesar automáticamente
- **Esto es inmanejable sin manual labeling a escala**

---

## 🔴 Solapamientos Detectados (Críticos)

### 1. **Alertas de Seguridad Bancaria** (2+ ocurrencias observadas)
```
Categoría A: banking::otp_2fa
  Descripción: "Contraseñas de un solo uso para autorización"
  Ejemplo: "Tu código 847291"

Categoría B: banking::fraud_alerts
  Descripción: "Notificaciones de actividad sospechosa"
  Ejemplo: "Si no eres tú, reporta de inmediato"

CONFLICTO: Un OTP podría considerarse "actividad sospechosa"
OBSERVADO: Itaú login (68k mensajes) - confunde ambas categorías
```

### 2. **Servicios Públicos - Factura vs Pago** (2+ ocurrencias observadas)
```
Categoría A: utilities::water
  Descripción: "Notificaciones de facturación y consumo"
  Ejemplo: "Tu factura de agua está disponible"

Categoría B: utilities::payment_due
  Descripción: "Recordatorios de pago vencido o próximo"
  Ejemplo: "Pago vencido - EAAB"

CONFLICTO: Mismo mensaje = ambas categorías
OBSERVADO: EAAB (153k mensajes) - 2 instancias de confusión
```

### 3. **Cobranza - Niveles de Escalamiento** (2+ ocurrencias observadas)
```
Categoría A: lending_and_credit::collection_notice
  Descripción: "Cobranza del prestamista original"
  Ejemplo: "Pago pendiente de cuota"

Categoría B: collections::extrajudicial_notice
  Descripción: "Cobro pre-legal de firma de recuperación"
  Ejemplo: "Notificación de cobro de deuda"

CONFLICTO: Ambas son notificaciones de cobranza, solo difieren en escalamiento
OBSERVADO: 2 instancias en test de 100 plantillas
IMPACTO: Crítico para credit scoring (diferencia entre mora temprana vs grave)
```

### 4. **Pensión vs Transacción Bancaria** (2+ ocurrencias observadas)
```
Categoría A: pension_and_employment::afp_contribution
  Descripción: "Notificación de aporte a fondo de pensión"
  Ejemplo: "Tu AFP recibió $123,456"

Categoría B: banking::transaction_alerts
  Descripción: "Confirmación de débito/crédito"
  Ejemplo: "Se debitó $123,456 de tu cuenta"

CONFLICTO: AFP es movimiento de dinero que se ve como "transacción bancaria"
OBSERVADO: 2 instancias en test de 100
IMPACTO: Confunde señales de empleo formal (AFP) con movimiento general
```

### 5. **Confirmación vs Recordatorio de Pago**
```
Categoría A: lending_and_credit::payment_confirmation
  Descripción: "Confirmación de que se RECIBIÓ el pago"
  Ejemplo: "Pago confirmado - cuota recibida"

Categoría B: banking::payment_due
  Descripción: "Recordatorio de que FALTA pagar"
  Ejemplo: "Tu pago vence el 30 de abril"

CONFLICTO: Uno es "ya pagué", otro es "debo pagar" - opuestos
IMPACTO: Crítico para credit scoring (puntual vs moroso)
```

### 6. **Gobierno vs Comercio** (Contexto faltante)
```
Categoría A: government::other_public
  Descripción: "Notificaciones SENA, Supersalud, etc"

Categoría B: commerce_retail::ecommerce
  Descripción: "Confirmaciones de pedido/entrega"

CONFLICTO: Avemaria (empresa privada) se confunde como gobierno
CAUSA: Falta de contexto en el texto ("promo especial")
IMPACTO: Menor, pero indica necesidad de mejor información del sender
```

---

## 📈 Análisis Estadístico

### Ocurrencias de Desacuerdos en Test de 100 Plantillas

| Solapamiento | Veces | Mensajes Afectados | Severidad |
|---|---|---|---|
| banking::otp_2fa vs banking::fraud_alerts | 1 | 68,521 | 🔴 ALTA |
| utilities::water vs utilities::payment_due | 2 | 153,471 | 🔴 ALTA |
| lending_and_credit::* vs collections::* | 2 | 50,000+ | 🔴 CRÍTICA |
| pension vs banking::transaction_alerts | 2 | N/A | 🟡 MEDIA |
| government vs commerce_retail | 1 | 135,775 | 🟡 MEDIA |

**Extrapolación a 6.7M mensajes:**
- Mínimo: **400k mensajes/día** con solapamientos detectados
- Máximo: **2.5M mensajes/día** con ambigüedad genuina

---

## 🛠️ Causa Raíz

### ¿Por qué sucede esto?

1. **Taxonomía diseñada por atributos diferentes:**
   - Algunos por TIPO DE SERVICIO (water, electricity, internet)
   - Otros por ACCIÓN (payment_due, payment_confirmation)
   - Otros por ENTIDAD (banking, utilities, government)
   - Resultado: No hay estructura jerárquica clara

2. **Falta de claridad en límites:**
   - ¿Una factura de servicios es "utilities::water" o "utilities::payment_due"?
   - ¿Una notificación de cobranza es "lending" o "collections"?
   - ¿Un OTP es "seguridad" (fraud_alerts) u "autorización" (otp_2fa)?

3. **Dos paneles (mini + nano) tienen sesgos diferentes:**
   - Mini interpreta una categoría de forma, Nano de otra
   - Sin consenso explícito, no hay acuerdo

---

## 💡 Opciones de Solución

### Opción 1: Redefinir Taxonomía (RECOMENDADO) ⭐
**Consolidar categorías solapadas:**

| De Ahora | A Propuesto | Ganancia |
|----------|-------------|----------|
| banking::otp_2fa + banking::fraud_alerts | banking::security_alerts | Elimina confusión |
| utilities::water + utilities::payment_due | utilities::service_notifications | Enfoque único |
| lending::collection + collections::* | collections::* (unificado) | Claridad en escalamiento |
| pension::afp vs banking::transaction | banking::formal_employment_signals | Contexto correcto |

**Esfuerzo:** 1-2 semanas de revisión de taxonomía + re-etiquetado de datos de entrenamiento  
**Ganancia esperada:** Reducir ABSTAIN de 38% a ~5-10%  
**ROI:** Evitar 2.5M mensajes/día de revisión manual

### Opción 2: Mejorar Clasificador (Mitigation)
- Usar modelos más grandes (gpt-4o en lugar de mini/nano)
- Añadir contexto adicional del remitente (sender_name, sender_category)
- Fine-tune con datos de SMS colombianos reales

**Esfuerzo:** 2-3 semanas  
**Ganancia esperada:** Reducir ABSTAIN de 38% a ~20-25%  
**Costo:** 3x más API calls de OpenAI

### Opción 3: Aceptar Manual Review (NO RECOMENDADO)
- Mantener 38% de ABSTAIN
- Procesar manualmente 2.5M mensajes/día
- Costo: Equipo de 50+ personas

---

## 📋 Recomendación

### Corto Plazo (Semana 1-2)
**Hacer Opción 1: Redefinir taxonomía**
- Consolidar las 8 categorías solapadas en 5 categorías más claras
- Documentar límites explícitos para cada una
- Actualizar descripciones

### Mediano Plazo (Semana 3-4)
**Implementar Opción 2: Mejorar clasificador**
- Usar modelos más fuertes en el panel
- Incluir información del remitente

### Resultado Esperado
- Panel agreement: 42% → 70%+ ✅
- Arbiter: 20% → 10%
- Human review: 38% → <5%
- **Automatización total: ~95%**

---

## 🎯 Siguiente Paso

**¿Aprobamos redefinir la taxonomía?** 

Si es sí, necesitamos 2 horas con el equipo de dominio (Credit Scoring + SMS especialistas) para:
1. Identificar los 5 conceptos core que queremos capturar
2. Redefinir límites explícitos
3. Re-etiquetar datos de entrenamiento si es necesario

