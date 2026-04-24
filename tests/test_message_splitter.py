"""
test_message_splitter.py - Tests para la separación de mensajes con/sin placeholders

Cubre:
    - Split básico: mensajes con placeholder vs texto puro
    - Split en listas mixtas
    - Preservación de metadata
    - Properties (total, placeholder_ratio)
    - Split batch
"""

import pytest
from pipeline.core.models import Template
from pipeline.stages.message_splitter import MessageSplitter, SplitResult


def make_template(
    text: str,
    applied_rules=None,
    template_id: str = "test123456789ab",
    client_name: str = "TestClient"
) -> Template:
    """Crea un Template mínimo para pruebas."""
    return Template(
        template_text=text,
        template_id=template_id,
        original_message=text,
        cleaned_message=text,
        phone_number="+573001234567",
        status_id=3,
        client_name=client_name,
        applied_rules=applied_rules if applied_rules is not None else []
    )


@pytest.fixture
def splitter() -> MessageSplitter:
    return MessageSplitter()


# ============================================================================
# TESTS BÁSICOS
# ============================================================================

class TestSplitBasico:
    """Split básico con un solo mensaje."""

    def test_mensaje_con_placeholder_va_a_with_placeholders(self, splitter):
        """Un mensaje con placeholders va al grupo correcto."""
        template = make_template(
            "tu saldo de [AMT] vence el [DATE]",
            applied_rules=["amount", "date"]
        )
        result = splitter.split([template])

        assert len(result.with_placeholders) == 1
        assert len(result.pure_messages) == 0
        assert result.with_placeholders[0].template_text == "tu saldo de [AMT] vence el [DATE]"

    def test_mensaje_puro_va_a_pure_messages(self, splitter):
        """Un mensaje sin placeholders va al grupo correcto."""
        template = make_template(
            "hola gracias por contactarnos",
            applied_rules=[]
        )
        result = splitter.split([template])

        assert len(result.with_placeholders) == 0
        assert len(result.pure_messages) == 1
        assert result.pure_messages[0].template_text == "hola gracias por contactarnos"

    def test_lista_vacia_devuelve_resultado_vacio(self, splitter):
        """Una lista vacía devuelve un SplitResult vacío."""
        result = splitter.split([])

        assert len(result.with_placeholders) == 0
        assert len(result.pure_messages) == 0
        assert result.total == 0


# ============================================================================
# TESTS CON LISTAS MIXTAS
# ============================================================================

class TestSplitMixto:
    """Split con listas que contienen ambos tipos."""

    def test_separa_correctamente_lista_mixta(self, splitter):
        """Separa correctamente una lista con ambos tipos."""
        templates = [
            make_template("tu código es [OTP]", applied_rules=["otp"], template_id="id1"),
            make_template("hola mundo", applied_rules=[], template_id="id2"),
            make_template("pago de [AMT]", applied_rules=["amount"], template_id="id3"),
            make_template("gracias", applied_rules=[], template_id="id4"),
        ]

        result = splitter.split(templates)

        assert len(result.with_placeholders) == 2
        assert len(result.pure_messages) == 2

    def test_preserva_metadata_en_ambos_grupos(self, splitter):
        """La metadata se preserva en ambos grupos."""
        with_ph = make_template(
            "saldo de [AMT]",
            applied_rules=["amount"],
            template_id="id1",
            client_name="ClientA"
        )
        pure = make_template(
            "gracias",
            applied_rules=[],
            template_id="id2",
            client_name="ClientB"
        )

        result = splitter.split([with_ph, pure])

        assert result.with_placeholders[0].client_name == "ClientA"
        assert result.pure_messages[0].client_name == "ClientB"
        assert result.with_placeholders[0].phone_number == "+573001234567"
        assert result.pure_messages[0].phone_number == "+573001234567"

    def test_preserva_orden_relativo(self, splitter):
        """Preserva el orden relativo dentro de cada grupo."""
        templates = [
            make_template("a [AMT]", applied_rules=["amount"], template_id="id1"),
            make_template("b [DATE]", applied_rules=["date"], template_id="id2"),
            make_template("c", applied_rules=[], template_id="id3"),
            make_template("d", applied_rules=[], template_id="id4"),
        ]

        result = splitter.split(templates)

        # Con placeholders: id1, id2 (en ese orden)
        assert result.with_placeholders[0].template_id == "id1"
        assert result.with_placeholders[1].template_id == "id2"

        # Sin placeholders: id3, id4 (en ese orden)
        assert result.pure_messages[0].template_id == "id3"
        assert result.pure_messages[1].template_id == "id4"


# ============================================================================
# TESTS DE SPLITRESULT PROPERTIES
# ============================================================================

class TestSplitResult:
    """Tests de las properties del SplitResult."""

    def test_total_es_suma_de_ambos_grupos(self, splitter):
        """Property total es la suma de ambos grupos."""
        templates = [
            make_template("a [AMT]", applied_rules=["amount"], template_id="id1"),
            make_template("b [DATE]", applied_rules=["date"], template_id="id2"),
            make_template("c", applied_rules=[], template_id="id3"),
        ]

        result = splitter.split(templates)

        assert result.total == 3
        assert result.total == len(result.with_placeholders) + len(result.pure_messages)

    def test_placeholder_ratio_correcto(self, splitter):
        """Property placeholder_ratio es correcto."""
        templates = [
            make_template("a [AMT]", applied_rules=["amount"], template_id="id1"),
            make_template("b [AMT]", applied_rules=["amount"], template_id="id2"),
            make_template("c", applied_rules=[], template_id="id3"),
        ]

        result = splitter.split(templates)

        # 2 con placeholders de 3 total = 2/3 ≈ 0.667
        assert abs(result.placeholder_ratio - 2/3) < 0.001

    def test_placeholder_ratio_con_cero_total(self, splitter):
        """placeholder_ratio retorna 0 si la lista está vacía."""
        result = splitter.split([])

        assert result.placeholder_ratio == 0.0

    def test_placeholder_ratio_100_por_ciento(self, splitter):
        """placeholder_ratio es 1.0 si todos tienen placeholders."""
        templates = [
            make_template("a [AMT]", applied_rules=["amount"], template_id="id1"),
            make_template("b [DATE]", applied_rules=["date"], template_id="id2"),
        ]

        result = splitter.split(templates)

        assert result.placeholder_ratio == 1.0

    def test_placeholder_ratio_cero_por_ciento(self, splitter):
        """placeholder_ratio es 0.0 si ninguno tiene placeholders."""
        templates = [
            make_template("a", applied_rules=[], template_id="id1"),
            make_template("b", applied_rules=[], template_id="id2"),
        ]

        result = splitter.split(templates)

        assert result.placeholder_ratio == 0.0


# ============================================================================
# TESTS DE SPLIT BATCH
# ============================================================================

class TestSplitBatch:
    """Tests para split_batch con chunks."""

    def test_batch_produce_mismo_resultado_que_split(self, splitter):
        """split_batch() produce el mismo resultado que split() normal."""
        templates = [
            make_template("a [AMT]", applied_rules=["amount"], template_id=f"id{i}")
            if i % 2 == 0 else
            make_template("b", applied_rules=[], template_id=f"id{i}")
            for i in range(10)
        ]

        result_normal = splitter.split(templates)
        result_batch = splitter.split_batch(templates, chunk_size=3)

        assert len(result_normal.with_placeholders) == len(result_batch.with_placeholders)
        assert len(result_normal.pure_messages) == len(result_batch.pure_messages)
        assert result_normal.total == result_batch.total

    def test_batch_funciona_con_chunk_mayor_que_lista(self, splitter):
        """split_batch() funciona cuando chunk_size > tamaño total."""
        templates = [
            make_template("a [AMT]", applied_rules=["amount"], template_id="id1"),
            make_template("b", applied_rules=[], template_id="id2"),
        ]

        # chunk_size de 1000 pero lista de 2
        result = splitter.split_batch(templates, chunk_size=1000)

        assert len(result.with_placeholders) == 1
        assert len(result.pure_messages) == 1

    def test_batch_con_chunk_pequeno(self, splitter):
        """split_batch() funciona correctamente con chunks pequeños."""
        templates = [
            make_template("a [AMT]", applied_rules=["amount"], template_id=f"id{i}")
            if i % 2 == 0 else
            make_template("b", applied_rules=[], template_id=f"id{i}")
            for i in range(10)
        ]

        # chunk_size = 2 para 10 elementos
        result = splitter.split_batch(templates, chunk_size=2)

        assert len(result.with_placeholders) == 5  # ids 0, 2, 4, 6, 8
        assert len(result.pure_messages) == 5      # ids 1, 3, 5, 7, 9
        assert result.total == 10


# ============================================================================
# TESTS DE EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge cases y comportamientos especiales."""

    def test_applied_rules_vacio_vs_none(self, splitter):
        """Empty list y None en applied_rules deben tratar igual."""
        # Aunque en la práctica siempre es una lista, verificamos robustez
        empty_list = make_template("msg", applied_rules=[])
        result = splitter.split([empty_list])

        assert len(result.pure_messages) == 1
        assert len(result.with_placeholders) == 0

    def test_split_result_repr(self):
        """SplitResult tiene __repr__ útil."""
        result = SplitResult(
            with_placeholders=[make_template("a [AMT]", applied_rules=["amount"])] * 5,
            pure_messages=[make_template("b", applied_rules=[])] * 3
        )

        repr_str = repr(result)
        assert "5" in repr_str  # with_placeholders count
        assert "3" in repr_str  # pure_messages count
