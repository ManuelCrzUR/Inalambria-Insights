"""
test_text_normalizer.py - Tests para TextNormalizer

Prueba:
1. Normalización de mensajes individuales
2. Normalización de DataFrames
3. Normalización de múltiples chunks con progreso
"""

import sys
import pandas as pd
import pytest

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.text_normalizer import TextNormalizer
from pipeline.monitor.progress_ui_live import PipelineLiveUI


class TestTextNormalizer:
    """Tests para la clase TextNormalizer."""

    def setup_method(self):
        """Setup antes de cada test."""
        self.normalizer = TextNormalizer()

    # ========================================================================
    # Tests de normalize_message (mensaje individual)
    # ========================================================================

    def test_normalize_message_lowercase(self):
        """Convierte a minúsculas."""
        text = "HOLA MUNDO"
        result = self.normalizer.normalize_message(text)
        assert result == "hola mundo"

    def test_normalize_message_strip(self):
        """Elimina espacios al inicio y final."""
        text = "  hola mundo  "
        result = self.normalizer.normalize_message(text)
        assert result == "hola mundo"

    def test_normalize_message_multiple_spaces(self):
        """Normaliza espacios múltiples a uno solo."""
        text = "hola    mundo   de   sms"
        result = self.normalizer.normalize_message(text)
        assert result == "hola mundo de sms"

    def test_normalize_message_combined(self):
        """Aplica todas las normalizaciones juntas."""
        text = "  HOLA   MUNDO   SMS  "
        result = self.normalizer.normalize_message(text)
        assert result == "hola mundo sms"

    def test_normalize_message_none(self):
        """Maneja None convirtiendo a string vacío."""
        result = self.normalizer.normalize_message(None)
        assert result == ""

    def test_normalize_message_number(self):
        """Maneja números convirtiendo a string."""
        result = self.normalizer.normalize_message(12345)
        assert result == "12345"

    def test_normalize_message_empty_string(self):
        """Maneja string vacío."""
        result = self.normalizer.normalize_message("")
        assert result == ""

    def test_normalize_message_tabs_newlines(self):
        """Normaliza tabs y newlines a espacios."""
        text = "hola\t\tmundo\nnueva\nlínea"
        result = self.normalizer.normalize_message(text)
        assert result == "hola mundo nueva línea"

    # ========================================================================
    # Tests de normalize_chunk (DataFrame)
    # ========================================================================

    def test_normalize_chunk_adds_column(self):
        """Agrega columna NormalizedMessage al DataFrame."""
        df = pd.DataFrame({
            "Message": ["HOLA", "MUNDO"],
            "PhoneNumber": ["1234", "5678"]
        })
        result = self.normalizer.normalize_chunk(df)

        assert "NormalizedMessage" in result.columns
        assert len(result) == 2

    def test_normalize_chunk_preserves_original(self):
        """No modifica el DataFrame original."""
        df = pd.DataFrame({
            "Message": ["HOLA", "MUNDO"],
        })
        original_message = df["Message"].iloc[0]

        self.normalizer.normalize_chunk(df)

        assert df["Message"].iloc[0] == original_message

    def test_normalize_chunk_correct_values(self):
        """Normaliza correctamente los valores."""
        df = pd.DataFrame({
            "Message": ["  HOLA  ", "  MUNDO  "],
        })
        result = self.normalizer.normalize_chunk(df)

        assert result["NormalizedMessage"].iloc[0] == "hola"
        assert result["NormalizedMessage"].iloc[1] == "mundo"

    def test_normalize_chunk_missing_message_column(self):
        """Maneja DataFrames sin columna Message."""
        df = pd.DataFrame({
            "PhoneNumber": ["1234", "5678"]
        })
        result = self.normalizer.normalize_chunk(df)

        # No debe fallar, solo retorna el DF sin NormalizedMessage
        assert "NormalizedMessage" not in result.columns

    def test_normalize_chunk_empty_dataframe(self):
        """Maneja DataFrames vacíos."""
        df = pd.DataFrame({"Message": []})
        result = self.normalizer.normalize_chunk(df)

        assert "NormalizedMessage" in result.columns
        assert len(result) == 0

    # ========================================================================
    # Tests de normalize_all_with_updates (múltiples chunks)
    # ========================================================================

    def test_normalize_all_with_updates(self):
        """Normaliza múltiples chunks correctamente."""
        chunks = [
            pd.DataFrame({"Message": ["  HOLA  ", "  MUNDO  "]}),
            pd.DataFrame({"Message": ["  SMS  "]}),
        ]

        ui = PipelineLiveUI()
        result = self.normalizer.normalize_all_with_updates(chunks, ui, 3)

        assert len(result) == 2
        assert result[0]["NormalizedMessage"].iloc[0] == "hola"
        assert result[1]["NormalizedMessage"].iloc[0] == "sms"

    def test_normalize_all_with_updates_preserves_chunks(self):
        """Preserva la estructura de chunks."""
        chunks = [
            pd.DataFrame({"Message": ["A", "B"]}),
            pd.DataFrame({"Message": ["C", "D", "E"]}),
        ]

        ui = PipelineLiveUI()
        result = self.normalizer.normalize_all_with_updates(chunks, ui, 5)

        assert len(result[0]) == 2
        assert len(result[1]) == 3

    def test_normalize_all_with_updates_custom_frequency(self):
        """Acepta frecuencia de actualización personalizada."""
        chunks = [pd.DataFrame({"Message": ["TEST"] * 1000})]

        ui = PipelineLiveUI()
        # No debe fallar con frecuencia diferente
        result = self.normalizer.normalize_all_with_updates(
            chunks, ui, 1000, update_frequency=200
        )

        assert len(result[0]) == 1000

    # ========================================================================
    # Tests de normalize_all (versión rápida)
    # ========================================================================

    def test_normalize_all(self):
        """Normaliza múltiples chunks en versión rápida."""
        chunks = [
            pd.DataFrame({"Message": ["  HOLA  ", "  MUNDO  "]}),
            pd.DataFrame({"Message": ["  SMS  "]}),
        ]

        ui = PipelineLiveUI()
        result = self.normalizer.normalize_all(chunks, ui, 3)

        assert len(result) == 2
        assert result[0]["NormalizedMessage"].iloc[0] == "hola"


class TestNormalizationIntegration:
    """Tests de integración con datos reales."""

    def test_real_sms_messages(self):
        """Normaliza mensajes SMS reales."""
        messages = [
            "Hola! Este es un mensaje de prueba.",
            "  OTRO MENSAJE   CON   ESPACIOS  ",
            "MensajeEnMayúsculas",
            "\t\nMensaje\ncon\tquebrados\n",
        ]

        normalizer = TextNormalizer()
        df = pd.DataFrame({"Message": messages})
        result = normalizer.normalize_chunk(df)

        assert result["NormalizedMessage"].iloc[0] == "hola! este es un mensaje de prueba."
        assert result["NormalizedMessage"].iloc[1] == "otro mensaje con espacios"
        assert result["NormalizedMessage"].iloc[2] == "mensajeenmayúsculas"
        assert result["NormalizedMessage"].iloc[3] == "mensaje con quebrados"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
