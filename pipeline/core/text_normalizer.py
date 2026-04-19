"""
text_normalizer.py - Normalización de texto para mensajes SMS

Aplica:
- Lowercase
- Strip espacios inicio/final
- Normalizar espacios múltiples a uno solo
"""

import re
import pandas as pd


class TextNormalizer:
    """Normaliza texto de mensajes SMS."""

    def normalize_message(self, text: str) -> str:
        """Normaliza un mensaje individual."""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        text = text.lower()
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def normalize_chunk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega columna NormalizedMessage al DataFrame."""
        df = df.copy()
        if "Message" in df.columns:
            df["NormalizedMessage"] = df["Message"].apply(self.normalize_message)
        return df

    def normalize_all_with_updates(
        self,
        chunks: list,
        ui,
        total_messages: int,
        update_frequency: int = 10_000
    ) -> list:
        """
        Normaliza todos los chunks con progreso en vivo granular.

        Args:
            chunks: Lista de DataFrames
            ui: PipelineLiveUI para reportar progreso
            total_messages: Total de mensajes a procesar
            update_frequency: Cada cuántos mensajes actualizar la UI

        Returns:
            Lista de DataFrames con columna NormalizedMessage
        """
        normalized_chunks = []
        processed = 0

        for chunk_idx, chunk in enumerate(chunks):
            df = chunk.copy()
            if "Message" in df.columns:
                # Procesar mensaje por mensaje para permitir actualizaciones en vivo
                normalized_messages = []
                for msg_idx, msg in enumerate(df["Message"]):
                    normalized = self.normalize_message(msg)
                    normalized_messages.append(normalized)
                    processed += 1

                    # Actualizar UI cada N mensajes
                    if processed % update_frequency == 0 or processed == total_messages:
                        ui.update_phase(
                            "🔧 Normalización de Texto",
                            processed=processed,
                            total=total_messages,
                            **{
                                "Chunk": f"{chunk_idx + 1}/{len(chunks)}",
                                "Progreso chunk": f"{msg_idx + 1}/{len(df)}",
                            }
                        )

                df["NormalizedMessage"] = normalized_messages
            normalized_chunks.append(df)

        return normalized_chunks

    def normalize_all(
        self,
        chunks: list,
        ui,
        total_messages: int
    ) -> list:
        """
        Normaliza todos los chunks con progreso en vivo.

        Args:
            chunks: Lista de DataFrames
            ui: PipelineLiveUI para reportar progreso
            total_messages: Total de mensajes a procesar

        Returns:
            Lista de DataFrames con columna NormalizedMessage
        """
        normalized_chunks = []
        processed = 0

        for chunk in chunks:
            normalized = self.normalize_chunk(chunk)
            normalized_chunks.append(normalized)
            processed += len(chunk)

            if processed % 50_000 == 0 or processed == total_messages:
                ui.update_phase(
                    "🔧 Normalización de Texto",
                    processed=processed,
                    total=total_messages,
                    **{"Chunks procesados": len(normalized_chunks)}
                )

        return normalized_chunks
