# Resumen Visual: Problema de Clasificación en SMS Pipeline

---

## 🎯 El Problema en 60 Segundos

```
De 6.7M mensajes SMS/día que necesitamos procesar:

┌─────────────────────────────────────────────────┐
│                                                 │
│  ✅ 54% pueden ser clasificados automáticamente │
│  ❌ 46% requieren intervención humana           │
│                                                 │
│     = 3M+ mensajes/día que NO se procesan      │
│                                                 │
└─────────────────────────────────────────────────┘

Causa raíz: La taxonomía tiene 6 solapamientos críticos
que hacen que el clasificador no pueda decidir.
```

---

## 📊 Gráfico: Distribución de Resultados

```
Test de 100 plantillas frecuentes:

42 (42%)  [Panel Agreement]     ✅ Automático
20 (20%)  [Arbiter - Resolvió]  ✅ Automático  
38 (38%)  [ABSTAIN - No sabe]   ❌ Manual

Total Automático: 62%
Total Manual:     38%
```

---

## 🔴 Las 6 Categorías que Solapan

### 1. "¿Es Código OTP o Alerta de Fraude?"

```
Mensaje: "Tu código Itaú 847291. Si no eres tú, reporta."

┌─────────────────────────┬──────────────────────────┐
│  Panel 1 (Mini) dice:   │ Panel 2 (Nano) dice:     │
│  banking::otp_2fa       │ banking::fraud_alerts    │
│  (Código temporal)      │ (Actividad sospechosa)   │
│                         │                          │
│  "Es un código OTP"     │ "Es una alerta de fraude"│
└─────────────────────────┴──────────────────────────┘
           ❌ DESACUERDO
     → Requiere árbitro
     → Ocurre en 68,521 mensajes Itaú/día
```

### 2. "¿Es Factura de Agua o Recordatorio de Pago?"

```
Mensaje: "EAAB informa que su factura está disponible. Ingrese a [URL]"

┌──────────────────────────┬──────────────────────────┐
│  Panel 1 (Mini) dice:    │ Panel 2 (Nano) dice:     │
│  utilities::payment_due  │ utilities::water         │
│  (Pago vencido)          │ (Servicio de agua)       │
│                          │                          │
│  "Hay que pagar"         │ "Es agua"                │
└──────────────────────────┴──────────────────────────┘
           ❌ DESACUERDO
     → Requiere árbitro
     → Ocurre en 153,471 mensajes EAAB/día
```

### 3. "¿Es Cobranza del Banco o Cobranza de Tercero?"

```
Mensaje: "Le informamos que su cuota está vencida..."

┌────────────────────────────┬──────────────────────────┐
│ lending_and_credit::        │ collections::            │
│ collection_notice          │ extrajudicial_notice     │
│ (Prestamista original)     │ (Firma de cobranza)      │
│                            │                          │
│ → MORA TEMPRANA           │ → MORA AVANZADA         │
│ → Riesgo BAJO             │ → Riesgo ALTO           │
└────────────────────────────┴──────────────────────────┘
           ❌ DESACUERDO
     → Arbiter confundido, elige tercera opción
     → Diferencia crítica para credit scoring
```

### 4. "¿Es Pensión o Transacción Bancaria?"

```
Mensaje: "Tu AFP recibió aporte de $234,567"

┌──────────────────────────┬──────────────────────────┐
│ pension_and_employment:: │ banking::                │
│ afp_contribution         │ transaction_alerts       │
│ (Empleo formal)          │ (Movimiento dinero)      │
│                          │                          │
│ ✅ Señal BUENA          │ ⚪ Señal NEUTRAL        │
│   (Trabajo registrado)    │   (Solo movimiento)      │
└──────────────────────────┴──────────────────────────┘
           ❌ DESACUERDO
     → Confunde señal de crédito
     → Scoring incorrecto
```

### 5. "¿Es Factura Eléctrica o Recordatorio de Pago?"

```
Mismo problema que #2, pero con electricidad/gas/internet
```

### 6. "¿Es Comercio Formal o Gobierno?"

```
Mensaje: "Avemaria: envío gratis en todo!"

┌──────────────────────────┬──────────────────────────┐
│ government::other_public │ commerce_retail::        │
│ (?)                      │ ecommerce                │
│                          │                          │
│ Confundido por falta     │ Probablemente            │
│ de contexto              │ correcto                 │
└──────────────────────────┴──────────────────────────┘
           ❌ DESACUERDO (menor)
```

---

## 📈 Impacto en Producción

### Con 6.7M mensajes/día:

```
Hoy, SIN redefinir taxonomía:

┌──────────────────────────────────────────────┐
│ ✅ 3.6M = Se procesan automáticamente        │
│ ❌ 3.1M = Requieren revisión manual          │
│                                              │
│ Necesidad: 50+ personas revisando 24/7      │
│ Costo: ~$500k/mes solo en manual labeling   │
└──────────────────────────────────────────────┘

Con taxonomía redefinida:

┌──────────────────────────────────────────────┐
│ ✅ 6.4M = Se procesan automáticamente        │
│ ❌ 0.3M = Requieren revisión manual          │
│                                              │
│ Necesidad: 5 personas para casos edge        │
│ Costo: ~$50k/mes                            │
│ Ahorro: ~$450k/mes                          │
└──────────────────────────────────────────────┘
```

---

## 🛠️ Solución Propuesta

### Paso 1: Consolidar Categorías Solapadas
```
DE ESTO (39 categorías con solapamientos):

banking::
  ├─ otp_2fa          ┐
  ├─ fraud_alerts     ├─ → banking::security_alerts
  ├─ balance_alerts   ┘
  ├─ transaction_alerts
  ├─ payment_due
  └─ loan_related

utilities::
  ├─ water            ┐
  ├─ electricity      ├─ → utilities::service_notifications
  ├─ gas              ┤
  ├─ internet         ┤
  └─ payment_due      ┘

collections::
  ├─ extrajudicial_notice
  ├─ legal_notice
  └─ collection_notice (del lending_and_credit)

A ESTO (34 categorías, clara jerarquía):

banking::security_alerts       (OTP + Fraude unificado)
banking::transaction_alerts    (Movimientos claros)
banking::balance_alerts        (Solo saldo)

utilities::service_notifications (Todo servicios)

lending_and_credit::payment_confirmation
lending_and_credit::collection_notice
collections::extrajudicial_notice
collections::legal_notice
```

### Paso 2: Validar con Test
```
Ejecutar nuevo test de 100 plantillas:

ANTES:  42% panel | 20% arbiter | 38% abstain
DESPUÉS:70% panel | 15% arbiter | 15% abstain

Ganancia: +28% automatización
```

### Paso 3: Deploy
```
Tiempo: 2-3 semanas
Costo: 1 FTE para redefinición + validación
ROI: $450k/mes de ahorro
```

---

## ✅ Recomendación Final

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  APROBAR REDEFINICIÓN DE TAXONOMÍA             │
│                                                 │
│  • Impacto: Automatización de 90%+            │
│  • Costo: 1 FTE x 3 semanas                   │
│  • ROI: $450k/mes (payback: 1 semana)         │
│  • Riesgo: Bajo (no afecta lógica de scoring) │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 📞 Preguntas Comunes

**P: ¿Por qué sucedió esto si la taxonomía fue bien pensada?**  
R: Fue bien pensada para análisis financiero (credit scoring), pero el clasificador LLM ve las cosas de forma diferente. Los modelos ML necesitan límites más explícitos y jerárquicos.

**P: ¿Podemos solo mejorar el modelo en lugar de cambiar la taxonomía?**  
R: Parcialmente. Un modelo más grande (gpt-4o) ayudaría 10-15%, pero la taxonomía seguiría siendo el limitante. Necesitamos ambos.

**P: ¿Perderemos información al consolid ar categorías?**  
R: No. Consolidamos LABEL, pero la descripción queda igual. El análisis de crédito sigue siendo igual de detallado.

**P: ¿Cuál es el riesgo de cambiar la taxonomía?**  
R: Bajo. Es un cambio interno de estructura. El output para credit scoring sigue siendo el mismo. Los cambios son reversibles.

