"""
Graph Backpropagator — Post-conversation learning.

After a conversation completes AND a doctor provides their diagnosis/response,
the backpropagator reinforces or weakens the paths that were traversed.

This is the core learning mechanism inspired by Physarum polycephalum:
- Paths that led to correct predictions get REINFORCED (tube gets wider)
- Paths that led to wrong predictions get WEAKENED (tube narrows)
- New co-occurrence patterns may SPROUT new edges (branching leaf)

The feedback loop:
1. Patient conversation → ConversationTrace (navigator)
2. Doctor reviews case → provides diagnosis + specialty
3. Backpropagator compares trace predictions vs doctor reality
4. Reinforces correct paths, weakens incorrect ones
5. Updates global graph statistics
"""

import logging
import time
from typing import Optional

from .graph_engine import (
    MedicalKnowledgeGraph, ConversationTrace, GraphEdge,
    NodeType, EdgeType,
)

logger = logging.getLogger(__name__)


class GraphBackpropagator:
    """
    Learns from completed cases to evolve the knowledge graph.
    """

    def __init__(self, graph: MedicalKnowledgeGraph):
        self.graph = graph
        self.total_backpropagations = 0
        self.correct_predictions = 0
        self.incorrect_predictions = 0

    def backpropagate(
        self,
        trace: ConversationTrace,
        doctor_diagnosis: Optional[str] = None,
        doctor_specialty: Optional[str] = None,
        outcome: str = "resolved",  # resolved, escalated, emergency
        severity_accurate: bool = True,
    ) -> dict:
        """
        Backpropagate learning from a completed case.

        Args:
            trace: The conversation trace from the navigator
            doctor_diagnosis: What the doctor actually diagnosed
            doctor_specialty: The specialty that handled it
            outcome: How the case resolved
            severity_accurate: Whether triage severity was correct

        Returns:
            Summary of what was reinforced/weakened
        """
        self.total_backpropagations += 1
        trace.doctor_validated = True
        trace.doctor_diagnosis = doctor_diagnosis

        summary = {
            "trace_id": trace.trace_id,
            "case_id": trace.case_id,
            "reinforced_edges": 0,
            "weakened_edges": 0,
            "new_edges_sprouted": 0,
            "outcome_score": 0.0,
        }

        # ── Step 1: Score the prediction accuracy ────────────────────────
        outcome_score = self._score_prediction(trace, doctor_diagnosis, doctor_specialty)
        trace.outcome_score = outcome_score
        summary["outcome_score"] = outcome_score

        # ── Step 2: Reinforce symptom → condition paths ──────────────────
        if doctor_diagnosis:
            diag_node = self.graph.find_node(doctor_diagnosis, NodeType.CONDITION)
            if not diag_node:
                # Try fuzzy match
                matches = self.graph.find_nodes_fuzzy(doctor_diagnosis, NodeType.CONDITION, limit=1)
                diag_node = matches[0] if matches else None

            if diag_node:
                # Reinforce all symptom → diagnosis edges
                for sym_name in trace.activated_symptoms:
                    sym_node = self.graph.find_node(sym_name, NodeType.SYMPTOM)
                    if sym_node:
                        edge = self.graph.get_edge(sym_node.id, diag_node.id)
                        if edge:
                            # Existing edge: reinforce based on outcome
                            amount = outcome_score * 1.5 if outcome == "resolved" else outcome_score * 0.5
                            self.graph.reinforce_edge(sym_node.id, diag_node.id, amount)
                            summary["reinforced_edges"] += 1
                            logger.debug("[Backprop] Reinforced %s→%s by %.2f",
                                        sym_node.name, diag_node.name, amount)
                        else:
                            # No edge exists: record co-occurrence for potential sprouting
                            sprouted = self.graph.record_co_occurrence(sym_node.id, diag_node.id)
                            if sprouted:
                                summary["new_edges_sprouted"] += 1

                # Record traversed edges in trace
                for sym_name in trace.activated_symptoms:
                    sym_node = self.graph.find_node(sym_name, NodeType.SYMPTOM)
                    if sym_node:
                        trace.traversed_edges.append((sym_node.id, diag_node.id))

        # ── Step 3: Reinforce condition → specialty paths ────────────────
        if doctor_specialty and doctor_diagnosis:
            spec_node = self.graph.find_node(doctor_specialty, NodeType.SPECIALTY)
            diag_node = self.graph.find_node(doctor_diagnosis, NodeType.CONDITION)

            if spec_node and diag_node:
                edge = self.graph.get_edge(diag_node.id, spec_node.id)
                if edge:
                    self.graph.reinforce_edge(diag_node.id, spec_node.id, outcome_score)
                    summary["reinforced_edges"] += 1
                else:
                    sprouted = self.graph.record_co_occurrence(diag_node.id, spec_node.id)
                    if sprouted:
                        summary["new_edges_sprouted"] += 1

        # ── Step 4: Weaken incorrect prediction paths ────────────────────
        if doctor_diagnosis and trace.predicted_conditions:
            predicted_set = set(c.lower() for c in trace.predicted_conditions)
            actual = doctor_diagnosis.lower()

            if actual not in predicted_set:
                self.incorrect_predictions += 1
                # Weaken edges to incorrectly predicted conditions
                for wrong_pred in trace.predicted_conditions:
                    wrong_node = self.graph.find_node(wrong_pred, NodeType.CONDITION)
                    if wrong_node:
                        for sym_name in trace.activated_symptoms:
                            sym_node = self.graph.find_node(sym_name, NodeType.SYMPTOM)
                            if sym_node:
                                edge = self.graph.get_edge(sym_node.id, wrong_node.id)
                                if edge:
                                    # Weaken: reduce conductivity slightly
                                    old_σ = edge.conductivity
                                    edge.conductivity = max(
                                        self.graph.config.min_conductivity,
                                        edge.conductivity * 0.9,  # 10% reduction
                                    )
                                    summary["weakened_edges"] += 1
                                    logger.debug("[Backprop] Weakened %s→%s: %.3f→%.3f",
                                                sym_node.name, wrong_node.name,
                                                old_σ, edge.conductivity)
            else:
                self.correct_predictions += 1

        # ── Step 5: Send flow along the full conversation path ───────────
        if trace.visited_nodes:
            self.graph.send_flow(trace.visited_nodes, flow_amount=outcome_score)

        # ── Step 6: Record symptom co-occurrences ────────────────────────
        sym_ids = []
        for sym_name in trace.activated_symptoms:
            node = self.graph.find_node(sym_name, NodeType.SYMPTOM)
            if node:
                sym_ids.append(node.id)

        for i, sid_a in enumerate(sym_ids):
            for sid_b in sym_ids[i + 1:]:
                sprouted = self.graph.record_co_occurrence(sid_a, sid_b)
                if sprouted:
                    summary["new_edges_sprouted"] += 1

        # ── Step 7: Maybe run global decay ───────────────────────────────
        self.graph.maybe_decay()

        # ── Store trace ──────────────────────────────────────────────────
        self.graph.traces.append(trace)

        logger.info(
            "[Backprop] case=%s | score=%.2f | reinforced=%d | weakened=%d | sprouted=%d",
            trace.case_id, outcome_score,
            summary["reinforced_edges"], summary["weakened_edges"],
            summary["new_edges_sprouted"],
        )

        return summary

    def _score_prediction(
        self,
        trace: ConversationTrace,
        doctor_diagnosis: Optional[str],
        doctor_specialty: Optional[str],
    ) -> float:
        """
        Score how well the graph's predictions matched the doctor's assessment.
        0.0 = completely wrong, 1.0 = perfectly matched
        """
        score = 0.0
        factors = 0

        if doctor_diagnosis and trace.predicted_conditions:
            actual_lower = doctor_diagnosis.lower()
            # Check if actual diagnosis was in top predictions
            for rank, pred in enumerate(trace.predicted_conditions):
                if pred.lower() == actual_lower:
                    # Higher score for higher rank
                    score += 1.0 - (rank * 0.15)
                    factors += 1
                    break
            else:
                # Partial credit for related conditions (same body system)
                actual_node = self.graph.find_node(doctor_diagnosis, NodeType.CONDITION)
                if actual_node:
                    actual_systems = set()
                    for sys_node, _ in self.graph.get_neighbors(
                        actual_node.id, target_type=NodeType.BODY_SYSTEM
                    ):
                        actual_systems.add(sys_node.id)

                    for pred in trace.predicted_conditions:
                        pred_node = self.graph.find_node(pred, NodeType.CONDITION)
                        if pred_node:
                            for sys_node, _ in self.graph.get_neighbors(
                                pred_node.id, target_type=NodeType.BODY_SYSTEM
                            ):
                                if sys_node.id in actual_systems:
                                    score += 0.3  # same body system = partial credit
                                    factors += 1
                                    break
                if factors == 0:
                    score = 0.1  # minimum score for attempt
                    factors = 1

        if doctor_specialty and trace.final_specialty:
            if doctor_specialty.lower() == trace.final_specialty.lower():
                score += 1.0
            else:
                score += 0.2
            factors += 1

        return round(score / max(factors, 1), 3)

    def get_learning_stats(self) -> dict:
        """Return statistics about the backpropagation learning."""
        total = self.correct_predictions + self.incorrect_predictions
        accuracy = self.correct_predictions / total if total > 0 else 0

        return {
            "total_backpropagations": self.total_backpropagations,
            "correct_predictions": self.correct_predictions,
            "incorrect_predictions": self.incorrect_predictions,
            "prediction_accuracy": round(accuracy, 3),
            "total_traces": len(self.graph.traces),
            "graph_stats": self.graph.stats(),
        }

    def batch_backpropagate(self, cases: list[dict]) -> dict:
        """
        Process multiple completed cases at once.
        Each case dict should have: trace, doctor_diagnosis, doctor_specialty, outcome
        """
        total_summary = {
            "cases_processed": 0,
            "total_reinforced": 0,
            "total_weakened": 0,
            "total_sprouted": 0,
            "avg_outcome_score": 0,
        }

        scores = []
        for case in cases:
            trace = case.get("trace")
            if not trace:
                continue

            result = self.backpropagate(
                trace=trace,
                doctor_diagnosis=case.get("doctor_diagnosis"),
                doctor_specialty=case.get("doctor_specialty"),
                outcome=case.get("outcome", "resolved"),
            )

            total_summary["cases_processed"] += 1
            total_summary["total_reinforced"] += result["reinforced_edges"]
            total_summary["total_weakened"] += result["weakened_edges"]
            total_summary["total_sprouted"] += result["new_edges_sprouted"]
            scores.append(result["outcome_score"])

        if scores:
            total_summary["avg_outcome_score"] = round(sum(scores) / len(scores), 3)

        return total_summary
