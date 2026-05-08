"""
orchestrator.py - Orquestador del Clasificador (Panel + Árbitro)

Coordina la clasificación de plantillas a través del panel heterogéneo
(gpt-4o-mini + gpt-5-nano) y, si es necesario, invoca al árbitro (gpt-5.4)
para resolver desacuerdos.

Arquitectura:
    template → L0: RuleClassifier.classify() → match?
                                              ├─ YES → final label (rule, confidence=1.0)
                                              └─ NO  → L1: panel.classify_parallel()
                                                        → agreement?
                                                          ├─ YES → final label
                                                          └─ NO  → L2: arbiter → final label

Emite ClassificationResult con trazabilidad completa (votos del panel, árbitro, level_used).
"""

import asyncio
from typing import AsyncIterator, Optional, List
from pipeline.core.models import ClassificationResult
from pipeline.stages.classifier.base import PanelVote
from pipeline.stages.classifier.panel import HeterogeneousPanel
from pipeline.stages.classifier.arbiter import Arbiter
from pipeline.stages.classifier.storage import ClassificationStore
from pipeline.stages.rule_classifier import RuleClassifier


class ClassifierStage:
    """
    Orquestador de clasificación LLM.
    Consume un async iterator de templates y emite ClassificationResult.
    """

    def __init__(
        self,
        panel: HeterogeneousPanel,
        arbiter: Arbiter,
        store: ClassificationStore,
        rule_classifier: Optional[RuleClassifier] = None,
        agreement_threshold: float = 0.5,
        concurrency: int = 10,
    ):
        """
        Inicializa el orquestador.

        Args:
            panel: HeterogeneousPanel (mini + nano en paralelo)
            arbiter: Arbiter (gpt-5.4)
            store: ClassificationStore (persistencia)
            rule_classifier: RuleClassifier L0 (opcional, si None omite L0)
            agreement_threshold: confianza mínima para considerar acuerdo (0.0-1.0)
            concurrency: llamadas LLM paralelas máximas
        """
        self.panel = panel
        self.arbiter = arbiter
        self.store = store
        self.rule_classifier = rule_classifier
        self.agreement_threshold = agreement_threshold
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

    async def classify_template(
        self,
        template_id: str,
        template_text: str,
        applied_rules: List[str],
        client_name: Optional[str] = None,
        frequency: int = 1,
    ) -> ClassificationResult:
        """
        Clasifica una plantilla individual.

        Flujo:
        1. L0 RuleClassifier: intenta clasificar por reglas determinísticas.
        2. Si match → retorna resultado (confidence=1.0, level_used="rule").
        3. Si miss → escala a L1: Panel vota en paralelo (mini + nano).
        4. Si acuerdo → final label = panel vote (level_used="panel_agreement").
        5. Si NO acuerdo → L2: árbitro arbitra.
        6. Si árbitro dice ABSTAIN → marca para revisión humana.

        Args:
            template_id: hash único de la plantilla
            template_text: texto con placeholders
            applied_rules: reglas regex aplicadas
            client_name: nombre del cliente (opcional)
            frequency: cuántas veces aparece (para contexto)

        Returns:
            ClassificationResult con trazabilidad completa
        """
        try:
            async with self.semaphore:
                # ── L0: RuleClassifier (nuevo) ──────────────────────────────
                if self.rule_classifier:
                    rule_match = self.rule_classifier.classify(template_text, client_name)
                    if rule_match:
                        return ClassificationResult(
                            template_id=template_id,
                            template_text=template_text,
                            applied_rules=applied_rules,
                            frequency=frequency,
                            label=rule_match.label,
                            category=rule_match.label.split("::")[0] if "::" in rule_match.label else rule_match.label,
                            subcategory=rule_match.label.split("::")[1] if "::" in rule_match.label else "",
                            confidence=rule_match.confidence,
                            level_used="rule",
                            agreement=True,
                            metadata={"rule_name": rule_match.rule_name},
                        )

                # ── L1: Panel vota en paralelo ──────────────────────────────
                vote1, vote2 = await self.panel.classify_parallel(
                    template_text, applied_rules, client_name
                )

                # Paso 2: Evalúa acuerdo
                labels_agree = vote1.label == vote2.label
                min_conf = min(vote1.confidence, vote2.confidence)
                agreement = labels_agree and min_conf >= self.agreement_threshold  # threshold reducido a 0.5

                if agreement:
                    # Panel de acuerdo → etiqueta final = voto del panel
                    result = ClassificationResult(
                        template_id=template_id,
                        template_text=template_text,
                        applied_rules=applied_rules,
                        frequency=frequency,
                        label=vote1.label,
                        category=vote1.label.split("::")[0] if "::" in vote1.label else vote1.label,
                        subcategory=vote1.label.split("::")[1] if "::" in vote1.label else "",
                        confidence=min_conf,
                        level_used="panel_agreement",
                        agreement=True,
                        panel_judge_1=vote1.label,
                        panel_judge_1_conf=vote1.confidence,
                        panel_judge_2=vote2.label,
                        panel_judge_2_conf=vote2.confidence,
                    )
                else:
                    # Panel en desacuerdo → árbitro arbitra
                    arbiter_response = await self.arbiter.arbitrate(
                        template_text,
                        applied_rules,
                        vote1,
                        vote2,
                        client_name=client_name,
                        frequency=frequency,
                    )

                    is_abstain = arbiter_response.label == "ABSTAIN"
                    level = "human_review" if is_abstain else "arbiter"

                    result = ClassificationResult(
                        template_id=template_id,
                        template_text=template_text,
                        applied_rules=applied_rules,
                        frequency=frequency,
                        label=arbiter_response.label,
                        category=(
                            arbiter_response.label.split("::")[0]
                            if "::" in arbiter_response.label
                            else arbiter_response.label
                        ),
                        subcategory=(
                            arbiter_response.label.split("::")[1]
                            if "::" in arbiter_response.label
                            else ""
                        ),
                        confidence=arbiter_response.confidence,
                        level_used=level,
                        agreement=False,
                        panel_judge_1=vote1.label,
                        panel_judge_1_conf=vote1.confidence,
                        panel_judge_2=vote2.label,
                        panel_judge_2_conf=vote2.confidence,
                        arbiter_label=arbiter_response.label,
                        arbiter_abstained=is_abstain,
                        arbiter_reasoning=arbiter_response.reasoning,
                        needs_human_review=is_abstain,
                    )

                return result

        except Exception as e:
            # Fallback: error en el proceso → resultado con metadata de error
            return ClassificationResult(
                template_id=template_id,
                template_text=template_text,
                applied_rules=applied_rules,
                frequency=frequency,
                label="ERROR",
                category="ERROR",
                subcategory="",
                confidence=0.0,
                level_used="error",
                agreement=False,
                needs_human_review=True,
                metadata={"error": str(e), "error_type": type(e).__name__},
            )

    async def classify_stream(
        self, templates: AsyncIterator[dict]
    ) -> AsyncIterator[ClassificationResult]:
        """
        Clasifica un stream de plantillas.

        Cada resultado se persiste vía store.append() antes de ser emitido.
        Usa asyncio.as_completed para emitir conforme terminen (no espera orden).

        Args:
            templates: async iterator de dicts con keys:
                       {template_id, template_text, applied_rules, client_name?, frequency?}

        Yields:
            ClassificationResult (ya persistido)
        """
        pending_tasks = set()

        async def classify_and_store(template: dict) -> ClassificationResult:
            result = await self.classify_template(
                template_id=template.get("template_id"),
                template_text=template.get("template_text"),
                applied_rules=template.get("applied_rules", []),
                client_name=template.get("client_name"),
                frequency=template.get("frequency", 1),
            )
            await self.store.append(result)
            return result

        # Produce tareas de clasificación conforme vienen templates
        async for template in templates:
            task = asyncio.create_task(classify_and_store(template))
            pending_tasks.add(task)

            # Si alcanzamos el límite de concurrencia, espera a que terminen algunas
            if len(pending_tasks) >= self.concurrency:
                done, pending_tasks = await asyncio.wait(
                    pending_tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    yield await task

        # Procesa las tareas restantes
        while pending_tasks:
            done, pending_tasks = await asyncio.wait(
                pending_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                yield await task
