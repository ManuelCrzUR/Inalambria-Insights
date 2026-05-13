"""
TEMP_aggregator.py - Agrega mensajes → estructura JSON de scoring

Toma los mensajes de S3 para un teléfono, normaliza, extrae templates,
y construye patrones temporales, conteos por categoría, y tipos de mensaje.
"""

import pandas as pd
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, Optional

from pipeline.core.text_normalizer import TextNormalizer
from pipeline.stages.template_extractor import TemplateExtractor


# Mapeo de subcategorías → tipos de mensaje de alto nivel
MESSAGE_TYPE_MAP = {
    "otp_2fa": ["otp_2fa", "otp_alerts", "2fa"],
    "transactional": [
        "transaction_alerts",
        "balance_alerts",
        "payment_confirmation",
        "disbursement",
    ],
    "billing": [
        "payment_due",
        "invoice",
        "water",
        "electricity",
        "gas",
        "internet",
    ],
    "marketing_promotional": [
        "commerce",
        "retail",
        "gambling",
        "loan_offer_response",
    ],
    "service_notifications": [],  # Catch-all para lo que no encaja
}


class PhoneScoreAggregator:
    """Agrega datos de SMS → scoring JSON."""

    def __init__(self):
        self.normalizer = TextNormalizer()
        self.extractor = TemplateExtractor()

    def aggregate(
        self,
        phone: str,
        df: pd.DataFrame,
        lookup: Dict[str, Dict],
        request_reference: Optional[str] = None,
        lookback_days: int = 365,
    ) -> Dict[str, Any]:
        """
        Agrega mensajes para UN teléfono → JSON de scoring.

        Args:
            phone: Número de teléfono
            df: DataFrame con columnas [PhoneNumber, Message, ArrivalDate]
            lookup: Dict {template_id: {categoria, subcategoria, ...}}
            request_reference: ID de referencia (loan_app_123, etc.)
            lookback_days: Días de lookback usado en query

        Returns:
            Dict con estructura JSON completa
        """
        if df.empty:
            return self._empty_score(phone, request_reference, lookback_days)

        # Procesar cada mensaje
        records = []
        for _, row in df.iterrows():
            msg = row["Message"]
            arrival = pd.to_datetime(row["ArrivalDate"])

            # Normalizar + extraer template
            normalized = self.normalizer.normalize_message(msg)
            template = self.extractor.extract_text(normalized)

            # Lookup categoría
            cat_info = lookup.get(template.template_id, {})
            categoria = cat_info.get("categoria", "unknown")
            subcategoria = cat_info.get("subcategoria", "unknown")

            records.append(
                {
                    "template_id": template.template_id,
                    "arrival_date": arrival,
                    "hour": arrival.hour,
                    "weekday": arrival.day_name().upper()[:3],  # MON, TUE, etc.
                    "categoria": categoria,
                    "subcategoria": subcategoria,
                }
            )

        df_records = pd.DataFrame(records)

        # Construir componentes del JSON
        temporal = self._build_temporal_patterns(df_records)
        categories = self._build_categories(df_records)
        message_types = self._build_message_types(df_records, lookback_days)
        metadata = self._build_metadata(phone, request_reference, lookback_days)

        return {
            "phone_number": phone,
            "temporal_patterns": temporal,
            "categories": categories,
            "message_types": message_types,
            "metadata": metadata,
        }

    def _build_temporal_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Construye hourly_distribution, daypart_distribution, weekday_distribution."""
        total_msgs = len(df)

        # Hourly: 24 buckets [0-23]
        hourly = df.groupby("hour").size().reset_index(name="messages_last_365d")
        # Asegurar todos los 24 buckets
        all_hours = pd.DataFrame({"hour": range(24)})
        hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)
        hourly["messages_last_365d"] = hourly["messages_last_365d"].astype(int)
        hourly_list = hourly.to_dict("records")

        # Dayparts
        def get_daypart(hour):
            if 0 <= hour < 6:
                return "night_00_06"
            elif 6 <= hour < 12:
                return "morning_06_12"
            elif 12 <= hour < 18:
                return "afternoon_12_18"
            else:
                return "evening_18_24"

        df["daypart"] = df["hour"].apply(get_daypart)
        daypart_counts = df.groupby("daypart").size()

        daypart_dist = {
            "night_00_06_share_last_365d": daypart_counts.get("night_00_06", 0) / total_msgs,
            "morning_06_12_share_last_365d": daypart_counts.get("morning_06_12", 0) / total_msgs,
            "afternoon_12_18_share_last_365d": daypart_counts.get("afternoon_12_18", 0)
            / total_msgs,
            "evening_18_24_share_last_365d": daypart_counts.get("evening_18_24", 0) / total_msgs,
        }

        # Weekdays (MON, TUE, WED, etc.)
        weekday_order = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        weekday = df.groupby("weekday").size().reset_index(name="messages_last_365d")
        weekday = weekday[weekday["weekday"].isin(weekday_order)].sort_values(
            "weekday", key=lambda x: x.map({d: i for i, d in enumerate(weekday_order)})
        )
        weekday["messages_last_365d"] = weekday["messages_last_365d"].astype(int)
        weekday_list = weekday.to_dict("records")

        return {
            "hourly_distribution": hourly_list,
            "daypart_distribution": daypart_dist,
            "weekday_distribution": weekday_list,
        }

    def _build_categories(self, df: pd.DataFrame) -> list[Dict[str, Any]]:
        """Construye array de categorías con subcategorías."""
        categories = []

        for categoria in df["categoria"].unique():
            if categoria == "unknown":
                continue

            df_cat = df[df["categoria"] == categoria]
            total_cat = len(df_cat)
            total_all = len(df)

            # first_seen, last_seen
            first_seen = df_cat["arrival_date"].min()
            last_seen = df_cat["arrival_date"].max()

            # Subcategorías dentro de esta categoría
            subcats = []
            for subcat in df_cat["subcategoria"].unique():
                if subcat == "unknown":
                    continue
                df_subcat = df_cat[df_cat["subcategoria"] == subcat]
                count_subcat = len(df_subcat)
                subcats.append(
                    {
                        "subcategory": subcat,
                        "messages_last_365d": count_subcat,
                        "share_within_category": count_subcat / total_cat if total_cat > 0 else 0,
                    }
                )

            categories.append(
                {
                    "category": categoria,
                    "messages_last_365d": total_cat,
                    "share_last_365d": total_cat / total_all if total_all > 0 else 0,
                    "first_seen_at": first_seen.isoformat() + "Z",
                    "last_seen_at": last_seen.isoformat() + "Z",
                    "subcategories": sorted(
                        subcats, key=lambda x: x["messages_last_365d"], reverse=True
                    ),
                }
            )

        return sorted(categories, key=lambda x: x["messages_last_365d"], reverse=True)

    def _build_message_types(self, df: pd.DataFrame, lookback_days: int) -> Dict[str, Any]:
        """Mapea subcategorías → 5 tipos de mensaje de alto nivel."""
        counts = {
            "otp_2fa": 0,
            "transactional": 0,
            "billing": 0,
            "marketing_promotional": 0,
            "service_notifications": 0,
        }

        for _, row in df.iterrows():
            subcat = row["subcategoria"]
            mapped = False

            for msg_type, subcats_list in MESSAGE_TYPE_MAP.items():
                if subcat in subcats_list:
                    counts[msg_type] += 1
                    mapped = True
                    break

            if not mapped:
                counts["service_notifications"] += 1

        return {
            "lookback_days": lookback_days,
            "counts_last_365d": counts,
        }

    def _build_metadata(
        self, phone: str, request_reference: Optional[str], lookback_days: int
    ) -> Dict[str, Any]:
        """Metadata del scoring."""
        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "request_reference": request_reference,
            "granularity": "standard",
            "data_lookback_days": lookback_days,
            "version": "1.0.0",
        }

    def _empty_score(
        self, phone: str, request_reference: Optional[str], lookback_days: int
    ) -> Dict[str, Any]:
        """Retorna estructura JSON vacía cuando no hay mensajes."""
        return {
            "phone_number": phone,
            "temporal_patterns": {
                "hourly_distribution": [
                    {"hour": h, "messages_last_365d": 0} for h in range(24)
                ],
                "daypart_distribution": {
                    "night_00_06_share_last_365d": 0.0,
                    "morning_06_12_share_last_365d": 0.0,
                    "afternoon_12_18_share_last_365d": 0.0,
                    "evening_18_24_share_last_365d": 0.0,
                },
                "weekday_distribution": [],
            },
            "categories": [],
            "message_types": {
                "lookback_days": lookback_days,
                "counts_last_365d": {
                    "otp_2fa": 0,
                    "transactional": 0,
                    "billing": 0,
                    "marketing_promotional": 0,
                    "service_notifications": 0,
                },
            },
            "metadata": self._build_metadata(phone, request_reference, lookback_days),
        }
