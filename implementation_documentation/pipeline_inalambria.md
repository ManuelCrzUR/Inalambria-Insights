# Pipeline Inalambria — Procesamiento diario de SMS

## Descripción general

Pipeline completo de procesamiento diario desde el parquet de S3 hasta la construcción del perfil por número. Incluye los 3 niveles de similitud para reducir el uso del modelo, la lógica de umbral para Redis, y el registro separado por número.

---

## Flujo principal

```
Parquet S3 (500k mensajes)
        ↓
   Normalizar
   (números, fechas, montos → tokens)
        ↓
   sha256(plantilla)[:16]  →  ID único
        ↓
   ┌────────────────────────────────────┐
   │         DOS ACCIONES EN PARALELO   │
   └────────────────────────────────────┘
         ↙                        ↘
  REGISTRAR                   CLASIFICAR
  (todos los mensajes)        (solo plantillas únicas)
         ↓                        ↓
  numero_perfiles            Deduplicar
  (numero, id,               500k → ~2k únicas
   sender) +1                     ↓
         ↓               3 niveles de similitud
  Fin del registro               ↓
  cada número guardado    ¿Ya conocemos este ID?
                          Redis 87% · SQL 13%
                           ↙           ↘
                         SÍ             NO
                          ↓              ↓
                    Categoría          Modelo
                    conocida        (una sola vez)
                          ↓              ↓
                    Actualizar      Guardar en SQL
                    ultima_vez      (siempre)
                    apariciones          ↓
                                  ¿Supera umbral?
                                  >= 50 · 90 días
                                   ↙         ↘
                               Subir a     Solo SQL
                               Redis       (13% poco
                               (300k)       frecuente)
```

---

## Resultado final: perfil por número

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

## Los 3 niveles de similitud

| Nivel | Método | Cuándo corre | Detecta |
|---|---|---|---|
| N1 | Levenshtein | Tiempo real | 1-2 palabras cambiadas · mismo sender |
| N2 | MinHash | Nocturno | Variantes estructurales · n-gramas compartidos |
| N3 | Embeddings | Periódico | Mismo significado · texto diferente |

**Objetivo:** el modelo LLM solo se usa para plantillas genuinamente nuevas que los 3 niveles no pudieron resolver.

---

## Lógica del umbral Redis

- **SQL siempre:** toda plantilla nueva queda persistida sin excepción.
- **Redis si:** `apariciones >= 50` AND `ultima_vez` dentro de los últimos 90 días.
- **Job nocturno:** revisa qué templates nuevos del día superaron el umbral y los promueve a Redis.
- **Capacidad:** 300k templates en Redis ≈ 150MB RAM → cubre ~87% del tráfico.

---

## Regla de oro

> El registro de `numero_perfiles` ocurre **antes** de deduplicar.  
> La deduplicación es solo para el proceso de clasificación, nunca para el registro.  
> Sin esto se pierde el valor principal de la API.
