# Pipeline Inalambria — Procesamiento diario de SMS (v2)

> Documento actualizado que integra el pipeline original con la arquitectura de clasificación en cascada (L1–L4) definida en sesión de diseño.

---

## 1. Descripción general

Pipeline completo de procesamiento diario desde el parquet de S3 hasta la construcción del perfil por número. Opera sobre **plantillas deduplicadas**, no sobre mensajes crudos. Incluye:

- Normalización y generación de ID único por plantilla.
- Bifurcación paralela: registro de todos los mensajes + clasificación solo de plantillas únicas.
- 3 niveles de similitud para evitar llamadas innecesarias al modelo.
- Cascada de clasificación L1–L4 para plantillas genuinamente nuevas.
- Lógica de umbral Redis para servir el 87% del tráfico desde caché.

---

## 2. Flujo principal

```
Parquet S3 (~500k mensajes diarios)
        ↓
   Normalización
   (números, fechas, montos → tokens)
        ↓
   sha256(plantilla)[:16]  →  ID único
        ↓
   ┌─────────────────────────────────────┐
   │        DOS ACCIONES EN PARALELO     │
   └─────────────────────────────────────┘
         ↙                          ↘
  REGISTRAR                     CLASIFICAR
  (todos los mensajes)          (solo plantillas únicas)
         ↓                          ↓
  numero_perfiles              Deduplicar
  (numero, id, sender) +1      500k → ~2k únicas
         ↓                          ↓
  Fin del registro          3 niveles de similitud
                                     ↓
                           ¿Ya conocemos este ID?
                           Redis 87% · SQL 13%
                            ↙              ↘
                          SÍ               NO
                           ↓                ↓
                     Categoría         Cascada L1–L4
                     conocida          (ver sección 4)
                           ↓                ↓
                     Actualizar       Guardar en SQL
                     ultima_vez       (siempre)
                     apariciones           ↓
                                    ¿Supera umbral?
                                    >= 50 · 90 días
                                     ↙          ↘
                                 Subir a      Solo SQL
                                 Redis        (13% poco
                                 (300k)        frecuente)
```

---

## 3. Regla de oro

> El registro de `numero_perfiles` ocurre **antes** de deduplicar.
> La deduplicación es solo para el proceso de clasificación, nunca para el registro.
> Sin esto se pierde el valor principal de la API.

---

## 4. Cascada de clasificación L1–L4

La cascada opera exclusivamente sobre **plantillas genuinamente nuevas** — aquellas que los 3 niveles de similitud no pudieron resolver. El cuerpo del mensaje es la señal primaria; el sender es señal secundaria de desempate.

La taxonomía tiene **10 categorías y 38 subcategorías**, estructurada en JSON.

### L1 — Motor de reglas

Sin ML. Dos pasos en secuencia:

1. **Match exacto:** busca el hash de la plantilla en Redis (87% del tráfico) y en SQL (13%).
2. **Regex + sender:** reglas manuales sobre patrones conocidos, con el sender como tiebreaker.

Si ninguno resuelve → pasa a L2.

### L2 — FastText plano

- Modelo FastText entrenado sobre las 38 subcategorías como labels directos (clasificador plano, no jerárquico).
- Opera sobre plantillas deduplicadas.
- **Condición de activación:** requiere ~500 ejemplos etiquetados por subcategoría para las categorías dominantes antes de entrar a producción.
- Si la confianza del resultado supera el umbral → fin. Si hay alta confusión intra-categoría → pasa a L3.

### L3 — Submodelos especializados (condicional)

Solo se activa para las categorías donde la matriz de confusión de L2 muestra errores intra-categoría altos. No se activa para todas las categorías.

Estructura:

- **Orquestador ligero** (regresión logística sobre embeddings, no otro FastText): detecta la categoría con ambigüedad alta y enruta al submodelo correspondiente.
- **Submodelos por categoría:** uno por cada categoría que justifique especialización (ej: Financiero, Retail). Cada submodelo se puede re-entrenar de forma independiente.
- Si la confianza sigue siendo baja → pasa a L4.

> **Criterio para activar un submodelo:** la matriz de confusión de L2 muestra que las confusiones dentro de esa categoría son sistemáticamente altas. No se crean submodelos preventivamente.

### L4 — Fallback LLM escalonado

Solo se activa cuando ningún nivel anterior supera el umbral de confianza. Flujo escalonado para minimizar costo:

```
Plantilla de baja confianza
        ↓
GPT-4o-mini
(sender + plantillas similares conocidas como contexto)
        ↓
 ¿Confianza alta?
   ↙         ↘
 SÍ           NO
  ↓            ↓
Acepta      GPT-5 nano (low reasoning)
            segunda opinión
                ↓
         ¿Coinciden?
          ↙       ↘
        SÍ         NO
         ↓          ↓
       Acepta    Decisor de alta capacidad
                 (modelo de razonamiento completo)
                     ↓
                  Acepta
```

**Notas de diseño:**
- El caso más caro (llegar al decisor) debe ser raro con un umbral bien calibrado.
- El contexto que recibe GPT-4o-mini incluye: sender, plantillas similares ya clasificadas, y top-k candidatos de L2/L3 con sus scores.
- El umbral de confianza que activa L4 debe calibrarse midiendo la curva precision/recall de L2 por subcategoría.

---

## 5. Datos de entrenamiento — rol del LLM

El LLM **no es parte del pipeline de producción**. Es la fábrica de datos que permite entrenar L2 y L3.

Durante la fase de acumulación (antes de que L2 entre a producción), GPT-4o-mini clasifica todas las plantillas nuevas. Cada clasificación se persiste en SQL con su label y score de confianza. Este corpus acumulado es el dataset de entrenamiento de FastText.

El paso de fase 0 (solo LLM) a fase 1 (L2 activo) ocurre cuando SQL tiene cobertura suficiente de ejemplos etiquetados. No requiere intervención manual — se acumula con el volumen diario del pipeline.

> **Criterio de calidad:** antes de usar los labels del LLM como training data, filtrar por score de confianza mínimo para evitar ruido en el dataset de FastText.

---

## 6. Los 3 niveles de similitud

Corren antes de la cascada de clasificación para evitar llamadas innecesarias al modelo.

| Nivel | Método | Cuándo corre | Detecta |
|---|---|---|---|
| N1 | Levenshtein | Tiempo real | 1-2 palabras cambiadas · mismo sender |
| N2 | MinHash | Nocturno | Variantes estructurales · n-gramas compartidos |
| N3 | Embeddings | Periódico | Mismo significado · texto diferente |

**Objetivo:** la cascada L1–L4 solo corre para plantillas genuinamente nuevas que los 3 niveles no pudieron resolver.

---

## 7. Lógica del umbral Redis

- **SQL siempre:** toda plantilla clasificada queda persistida sin excepción.
- **Redis si:** `apariciones >= 50` AND `ultima_vez` dentro de los últimos 90 días.
- **Job nocturno:** revisa qué plantillas nuevas del día superaron el umbral y las promueve a Redis.
- **Capacidad:** 300k plantillas en Redis ≈ 150MB RAM → cubre ~87% del tráfico.

---

## 8. Perfil por número — resultado final

Al final del proceso diario, cada número tiene un perfil acumulado en `numero_perfiles`:

| Campo | Descripción |
|---|---|
| `numero` | Número de teléfono — llave de consulta |
| `template_id` | Hash de la plantilla recibida |
| `sender` | Quién envió el mensaje |
| `apariciones` | Cuántas veces recibió esa plantilla |
| `primera_vez` | Fecha del primer registro |
| `ultima_vez` | Fecha del último registro |

---

## 9. Decisiones de arquitectura clave

| Decisión | Razonamiento |
|---|---|
| Operar sobre plantillas, no mensajes crudos | Reduce el volumen de 500k a ~2k unidades de clasificación |
| Cuerpo del mensaje como señal primaria | El sender solo actúa como tiebreaker |
| FastText plano (38 clases) antes que jerárquico | Más simple, más fácil de evaluar; submodelos solo donde la matriz de confusión lo justifica |
| L3 condicional por categoría | Evita entrenar submodelos sin evidencia de que mejoran |
| L4 escalonado (mini → nano → decisor) | Minimiza costo: el caso común lo resuelve el modelo más barato |
| LLM fuera del pipeline de producción | El LLM es fábrica de datos, no componente de serving |
| Registro antes de deduplicar | Preserva el valor de la API: cada número tiene su historial completo |
