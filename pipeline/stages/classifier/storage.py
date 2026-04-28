"""
storage.py - Persistencia de resultados de clasificación

Gestiona la escritura y lectura de ClassificationResult en JSONL.
Soporta resume: al arrancar, lee los template_ids ya procesados y los salta.

Arquitectura:
    - append-only: nuevos resultados se agregan al final del archivo
    - asyncio.Lock: protege contra escrituras concurrentes
    - load_processed_ids: robusta a líneas corruptas (skip + warning)
"""

import asyncio
import json
import warnings
from pathlib import Path
from typing import Set, Iterator, Optional
from pipeline.core.models import ClassificationResult


class ClassificationStore:
    """
    Store JSONL append-only con soporte para resume.
    """

    def __init__(self, jsonl_path: Path):
        """
        Inicializa el store.

        Args:
            jsonl_path: path al archivo JSONL de salida
        """
        self.jsonl_path = Path(jsonl_path)
        self.lock = asyncio.Lock()
        self._processed_ids: Optional[Set[str]] = None

    async def load_processed_ids(self) -> Set[str]:
        """
        Lee los template_ids ya procesados del JSONL.

        Si el archivo no existe, devuelve set vacío.
        Si una línea es JSON inválido, la skipea con warning y continúa.

        Returns:
            Set de template_ids ya escritos
        """
        if self._processed_ids is not None:
            return self._processed_ids

        self._processed_ids = set()

        if not self.jsonl_path.exists():
            return self._processed_ids

        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        obj = json.loads(line)
                        template_id = obj.get("template_id")
                        if template_id:
                            self._processed_ids.add(template_id)
                    except json.JSONDecodeError as e:
                        warnings.warn(
                            f"Línea {line_num} en {self.jsonl_path} es JSON inválido, "
                            f"la saltamos. Error: {e}"
                        )
        except Exception as e:
            warnings.warn(
                f"Error al leer {self.jsonl_path} para resume: {e}. "
                f"Continuando sin resume."
            )

        return self._processed_ids

    async def append(self, result: ClassificationResult) -> None:
        """
        Appenda un resultado al JSONL.

        Thread-safe vía asyncio.Lock.

        Args:
            result: ClassificationResult a persistir
        """
        async with self.lock:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                line = json.dumps(result.to_dict(), ensure_ascii=False)
                f.write(line + "\n")

    def iter_classifications(self) -> Iterator[dict]:
        """
        Lee todos los resultados del JSONL en orden.

        Yields:
            dict con ClassificationResult deserializado
        """
        if not self.jsonl_path.exists():
            return

        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    warnings.warn(
                        f"Línea inválida en {self.jsonl_path}: {e}, la saltamos."
                    )

    def ensure_parent_exists(self) -> None:
        """Crea el directorio padre si no existe."""
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
