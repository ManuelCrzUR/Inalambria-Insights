"""
progress_monitor.py - Monitor de progreso del pipeline

Trackea el progreso de cada stage del pipeline:
- Data Reader: % de parquets leídos
- Text Normalizer: % de mensajes normalizados
- Template Extractor: % de plantillas extraídas
- etc.

Cada stage emite eventos que el monitor captura y renderiza.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import time


class StageStatus(Enum):
    """Estados posibles de un stage"""
    PENDING = "⏳ Pendiente"
    RUNNING = "⏳ Ejecutándose"
    COMPLETED = "✅ Completado"
    ERROR = "❌ Error"
    PAUSED = "⏸️  Pausado"


@dataclass
class StageProgress:
    """Progreso de un stage individual"""
    name: str                          # "Data Reader"
    status: StageStatus = StageStatus.PENDING
    total_items: int = 0               # Total a procesar
    processed_items: int = 0           # Procesados hasta ahora

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    error_message: Optional[str] = None
    additional_info: Dict = field(default_factory=dict)  # {clave: valor}

    def __post_init__(self):
        """Inicializa timestamp si estamos corriendo"""
        if self.status == StageStatus.RUNNING and not self.start_time:
            self.start_time = datetime.now()

    @property
    def percentage(self) -> float:
        """Porcentaje completado (0-100)"""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Segundos transcurridos"""
        if not self.start_time:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def items_per_second(self) -> float:
        """Velocidad de procesamiento"""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.processed_items / elapsed

    @property
    def eta_seconds(self) -> float:
        """Segundos estimados hasta completar"""
        if self.items_per_second == 0:
            return 0.0
        remaining = self.total_items - self.processed_items
        return remaining / self.items_per_second

    @property
    def eta_timedelta(self) -> timedelta:
        """ETA como timedelta"""
        return timedelta(seconds=int(self.eta_seconds))

    def start(self, total_items: int) -> None:
        """Inicia el procesamiento"""
        self.status = StageStatus.RUNNING
        self.total_items = total_items
        self.processed_items = 0
        self.start_time = datetime.now()
        self.end_time = None

    def update(self, processed: int, **kwargs) -> None:
        """Actualiza progreso"""
        self.processed_items = processed
        for key, value in kwargs.items():
            self.additional_info[key] = value

    def increment(self, amount: int = 1, **kwargs) -> None:
        """Incrementa el contador"""
        self.processed_items += amount
        for key, value in kwargs.items():
            self.additional_info[key] = value

    def complete(self) -> None:
        """Marca como completado"""
        self.status = StageStatus.COMPLETED
        self.end_time = datetime.now()
        self.processed_items = self.total_items

    def error(self, message: str) -> None:
        """Marca como error"""
        self.status = StageStatus.ERROR
        self.error_message = message
        self.end_time = datetime.now()


class PipelineMonitor:
    """
    Monitor central del pipeline.

    Trackea múltiples stages en paralelo.
    Cada stage emite eventos que el monitor captura.

    Uso:
        monitor = PipelineMonitor()

        # Agregar stages
        monitor.add_stage("Data Reader")
        monitor.add_stage("Text Normalizer")

        # Procesar
        reader_stage = monitor.get_stage("Data Reader")
        reader_stage.start(total_items=1394)  # 1394 row_groups

        for i in range(1394):
            reader_stage.increment(1, speed_msg_per_sec=250000)

        reader_stage.complete()
    """

    def __init__(self):
        self.stages: Dict[str, StageProgress] = {}
        self.start_time = datetime.now()
        self.global_errors: List[str] = []

    def add_stage(self, stage_name: str) -> StageProgress:
        """Agrega un nuevo stage al pipeline"""
        stage = StageProgress(name=stage_name)
        self.stages[stage_name] = stage
        return stage

    def get_stage(self, stage_name: str) -> Optional[StageProgress]:
        """Obtiene un stage por nombre"""
        return self.stages.get(stage_name)

    def get_all_stages(self) -> List[StageProgress]:
        """Retorna todos los stages en orden de inserción"""
        return list(self.stages.values())

    @property
    def elapsed_seconds(self) -> float:
        """Segundos desde que comenzó el pipeline"""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def overall_percentage(self) -> float:
        """Porcentaje general del pipeline"""
        if not self.stages:
            return 0.0

        running_stages = [s for s in self.stages.values()
                         if s.status == StageStatus.RUNNING]

        if not running_stages:
            return 0.0

        # Promedio de los stages en ejecución
        avg = sum(s.percentage for s in running_stages) / len(running_stages)
        return avg

    def add_error(self, error_message: str) -> None:
        """Agrega error global"""
        self.global_errors.append(error_message)

    def get_summary(self) -> Dict:
        """Retorna resumen del estado actual"""
        return {
            "elapsed_seconds": self.elapsed_seconds,
            "overall_percentage": self.overall_percentage,
            "stages": {
                name: {
                    "status": stage.status.value,
                    "percentage": stage.percentage,
                    "processed": stage.processed_items,
                    "total": stage.total_items,
                    "speed": f"{stage.items_per_second:,.0f} items/sec",
                    "eta": str(stage.eta_timedelta),
                }
                for name, stage in self.stages.items()
            },
            "errors": self.global_errors
        }
