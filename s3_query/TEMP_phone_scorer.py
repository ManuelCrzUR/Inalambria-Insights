"""
TEMP_phone_scorer.py - API principal: Scoring de teléfonos

Orquesta scan_messages + template_lookup + aggregator
para retornar JSON de scoring financiero.
"""

from typing import Dict, Any, Optional
import os
from pathlib import Path

# Imports condicionales (duckdb puede no estar disponible)
try:
    from .TEMP_s3_scanner import scan_messages, scan_messages_batch
except ImportError:
    scan_messages = None
    scan_messages_batch = None

from .TEMP_template_lookup import load_classifications
from .TEMP_aggregator import PhoneScoreAggregator


class PhoneScorer:
    """Scoring de teléfonos: orquesta todos los componentes."""

    def __init__(
        self,
        classifications_csv: str | Path,
        s3_bucket: str = "s3://inalambria-db-sms/imp3",
        s3_region: str = "us-east-2",
    ):
        """
        Inicializa scorer con CSV de clasificaciones.

        Args:
            classifications_csv: Ruta a all_rule_classifications.csv
            s3_bucket: S3 bucket path (default inalambria-db-sms/imp3)
            s3_region: AWS region (default us-east-2)
        """
        self.classifications_csv = Path(classifications_csv)
        self.s3_bucket = s3_bucket
        self.s3_region = s3_region

        # Cargar clasificaciones una sola vez
        self.lookup = load_classifications(self.classifications_csv)
        self.aggregator = PhoneScoreAggregator()

    def score_phones(
        self,
        phones: str | list[str],
        lookback_days: int = 365,
        request_reference: Optional[str] = None,
    ) -> Dict[str, Any] | list[Dict[str, Any]]:
        """
        Scoring para uno o múltiples teléfonos.

        Args:
            phones: Número de teléfono (str) o lista de números
            lookback_days: Días hacia atrás (default 365)
            request_reference: ID de referencia (loan_app_123, etc.)

        Returns:
            Si phones es str: Dict con scoring de ese teléfono
            Si phones es list: List[Dict] con scoring de cada teléfono

        Raises:
            ValueError: Si los teléfonos están vacíos
            FileNotFoundError: Si no encuentra el CSV de clasificaciones
        """
        if isinstance(phones, str):
            return self._score_single(phones, lookback_days, request_reference)

        if isinstance(phones, list):
            return [self._score_single(p, lookback_days, request_reference) for p in phones]

        raise TypeError(f"phones debe ser str o list, no {type(phones)}")

    def _score_single(
        self, phone: str, lookback_days: int, request_reference: Optional[str]
    ) -> Dict[str, Any]:
        """Scoring para UN teléfono."""
        # Consultar S3
        df = scan_messages(
            [phone],
            lookback_days=lookback_days,
            bucket=self.s3_bucket,
            region=self.s3_region,
        )

        # Agregar → JSON
        score = self.aggregator.aggregate(
            phone=phone,
            df=df,
            lookup=self.lookup,
            request_reference=request_reference,
            lookback_days=lookback_days,
        )

        return score

    def score_phones_batch(
        self,
        phones: list[str],
        lookback_days: int = 365,
        request_reference: Optional[str] = None,
        batch_size: int = 100,
    ) -> list[Dict[str, Any]]:
        """
        Scoring para múltiples teléfonos en lotes (menos memoria).

        Args:
            phones: Lista de teléfonos
            lookback_days: Días hacia atrás
            request_reference: ID de referencia
            batch_size: Teléfonos por lote (default 100)

        Returns:
            List[Dict] con scoring de cada teléfono
        """
        results = []

        for i in range(0, len(phones), batch_size):
            batch = phones[i : i + batch_size]

            # Consultar todos en el lote de una vez
            df_batch = scan_messages(
                batch,
                lookback_days=lookback_days,
                bucket=self.s3_bucket,
                region=self.s3_region,
            )

            # Procesar cada teléfono del lote
            for phone in batch:
                df_phone = df_batch[df_batch["PhoneNumber"] == phone]
                score = self.aggregator.aggregate(
                    phone=phone,
                    df=df_phone,
                    lookup=self.lookup,
                    request_reference=request_reference,
                    lookback_days=lookback_days,
                )
                results.append(score)

        return results


# Función convenience (API simple)
def score_phones(
    phones: str | list[str],
    lookback_days: int = 365,
    classifications_csv: Optional[str | Path] = None,
    s3_bucket: str = "s3://inalambria-db-sms/imp3",
    s3_region: str = "us-east-2",
    request_reference: Optional[str] = None,
) -> Dict[str, Any] | list[Dict[str, Any]]:
    """
    API simplificada: score_phones(phone) → JSON

    Usa path default de CSV si no se especifica.

    Args:
        phones: Teléfono (str) o lista
        lookback_days: Días (default 365)
        classifications_csv: Path a CSV (default: config/all_rule_classifications.csv)
        s3_bucket: S3 bucket
        s3_region: AWS region
        request_reference: ID de referencia

    Returns:
        Dict o List[Dict] con scoring
    """
    if classifications_csv is None:
        # Buscar en config/
        root_dir = Path(__file__).parent.parent
        classifications_csv = root_dir / "config" / "all_rule_classifications.csv"

    scorer = PhoneScorer(
        classifications_csv=classifications_csv,
        s3_bucket=s3_bucket,
        s3_region=s3_region,
    )

    return scorer.score_phones(phones, lookback_days, request_reference)
