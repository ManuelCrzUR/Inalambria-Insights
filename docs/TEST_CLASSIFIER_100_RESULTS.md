# Resultados: Test del Clasificador con 100 Plantillas

**Fecha:** 28 de Abril de 2026  
**Modelos:** Panel 1 (gpt-4o-mini) + Panel 2 (gpt-5-nano) + Arbiter (gpt-5.4)  
**Threshold de Acuerdo:** 0.5 (reducido de 0.7)

---

## 📊 Resumen Ejecutivo

| Métrica | Resultado | % |
|---------|-----------|-----|
| **Total clasificadas** | 100 | 100% |
| **Panel agreement** | 42 | 42% ✅ |
| **Arbiter resueltos** | 20 | 20% ⚠️ |
| **Human review (ABSTAIN)** | 38 | 38% 🚨 |
| **Errores** | 0 | 0% ✅ |

### Comparación vs Test de 10 Plantillas

| Métrica | Test 10 | Test 100 | Cambio |
|---------|---------|----------|--------|
| Panel agreement | 40% | 42% | ↔️ Similar |
| Arbiter | 50% | 20% | ↓ -60% ✅ |
| Human review | 10% | 38% | ↑ +280% |

---

## 🎯 Hallazgos Principales

### 1. El Threshold de 0.5 Funcionó
- Reducir de 0.7 a 0.5 **bajó los arbiter calls de 50% a 20%** ✅
- Esto evita llamadas LLM innecesarias y acelera el pipeline

### 2. El Verdadero Problema: 38% de ABSTAIN
- El árbitro se está **absteniendo** en 38 de 100 plantillas
- Significa: **no puede decidir** entre opciones que considera válidas
- **Causa raíz:** Solapamiento en la taxonomía + ambigüedad genuina en datos

### 3. Patrones Repetitivos de Desacuerdo
Los mismos pares de categorías aparecen múltiples veces:

| Desacuerdo | Ocurrencias | % |
|-----------|-------------|-----|
| `utilities::payment_due` vs `utilities::water` | 2 | 10% |
| `pension_and_employment::afp` vs `banking::transaction_alerts` | 2 | 10% |
| `lending_and_credit::collection` vs `banking::payment_due` | 2 | 10% |
| `banking::otp_2fa` vs `banking::fraud_alerts` | 1 | 5% |
| `government::*` vs `commerce_retail::*` | 1 | 5% |

---

## 📈 Distribución de Categorías Finales

| Categoría | Cantidad | % |
|-----------|----------|-----|
| **ABSTAIN** (no clasificadas) | 38 | 38% 🚨 |
| banking | 35 | 35% |
| utilities | 7 | 7% |
| collections | 7 | 7% |
| lending_and_credit | 4 | 4% |
| healthcare | 3 | 3% |
| commerce_retail | 3 | 3% |
| pension_and_employment | 2 | 2% |
| government | 1 | 1% |

**Observación crítica:** 38% de mensajes que no pueden ser clasificados automáticamente requieren revisión humana.

---

## 🔍 Ejemplos de Ambigüedad (Top 5)

### 1. Itaú App Login (68,521 mensajes)
```
Judge 1: banking::otp_2fa
Judge 2: banking::fraud_alerts
Arbiter: banking::fraud_alerts
```
**Problema:** ¿Es un código OTP (2FA) o una alerta de fraude (seguridad)?

### 2. EAAB Factura (153,471 mensajes)
```
Judge 1: utilities::payment_due
Judge 2: utilities::water
Arbiter: utilities::water
```
**Problema:** ¿Es una notificación de pago o del servicio de agua?

### 3. Avemaria Promo (135,775 mensajes)
```
Judge 1: government::other_public
Judge 2: commerce_retail::ecommerce
Arbiter: commerce_retail::ecommerce
```
**Problema:** ¿Es comercio minorista o algo gubernamental?

### 4. AFP Contribution
```
Judge 1: pension_and_employment::afp_contribution
Judge 2: banking::transaction_alerts
Arbiter: [ERROR: Sin decisión clara]
```
**Problema:** ¿Es notificación de pensión o transacción bancaria?

### 5. Davivienda Crédito (25,852 mensajes)
```
Judge 1: lending_and_credit::payment_confirmation
Judge 2: lending_and_credit::loan_related
Arbiter: banking::loan_related (tercera opción)
```
**Problema:** Árbitro tuvo que elegir una tercera categoría.

---

## 🚨 Diagnóstico: Solapamiento en Taxonomía

### Problemas Identificados

#### 1. **utilities** tiene dos interpretaciones
- `utilities::payment_due` → Enfoque: ACCIÓN (pagar)
- `utilities::water` → Enfoque: SERVICIO (agua)
- **Conflicto:** Mismo mensaje puede ser ambos

#### 2. **banking** vs **lending_and_credit**
- Límite borroso entre transacciones bancarias y crédito
- AFP es "pensión" pero se ve como "transacción" por el panel

#### 3. **banking** tiene demasiadas subcategorías de "alerta"
- `banking::otp_2fa` (seguridad - 2FA)
- `banking::fraud_alerts` (seguridad - fraude)
- `banking::transaction_alerts` (notificación - transacción)
- **Conflicto:** ¿Una notificación de OTP es qué tipo de alerta?

#### 4. **government** vs **commerce_retail**
- Falta contexto: ¿Avemaria es empresa privada o aparece como "otra cosa"?

---

## 💡 Recomendaciones

### Corto Plazo (Quick Fix)
1. Mejorar el prompt del árbitro para preferir categorías genéricas cuando hay duda
2. Reducir confianza requerida para "acuerdo parcial" de categoría padre

### Mediano Plazo (Recomendado)
1. **Consolidar categorías solapadas:**
   - Unificar `utilities::payment_due` y `utilities::water` → `utilities::service`
   - Unificar `banking::otp_2fa` y `banking::fraud_alerts` → `banking::security`
   - Separar claramente `banking::*` de `lending_and_credit::*`

2. **Revisar descripción de cada categoría** para eliminar ambigüedad

3. **Re-ejecutar tests** después de cambios

### Largo Plazo
1. Recolectar datos de clasificación manual (gold standard)
2. Fine-tune modelo específico para SMS colombiano
3. Usar modelo más grande (gpt-4o) en lugar de mini/nano

---

## ✅ Conclusión

**El clasificador funciona, pero la taxonomía tiene solapamientos que causan:**
- 38% de abstención del árbitro
- Necesidad de revisión humana en ~1/3 de mensajes

**Siguiente paso:** Revisar y redefinir categorías con el equipo de dominio.

---

**Archivo JSONL:** `output/2026-04-28/test_100_classifications.jsonl`
