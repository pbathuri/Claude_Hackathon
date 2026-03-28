"""
Graph-Based Doctor Matcher.

Uses the knowledge graph's most-traversed paths to match cases with
the most relevant doctors. Goes beyond simple specialty matching:

1. SPECIALTY MATCH: condition → specialty edges (strongest signal)
2. EXPERIENCE MATCH: doctors who resolved similar cases before
3. REGIONAL MATCH: doctors familiar with tropical/regional conditions
4. CONDUCTIVITY MATCH: high-conductivity specialty edges = proven expertise paths

The Physarum metaphor: doctors are like "sinks" in the slime mold network.
Cases flow toward the doctors whose specialty paths have the highest conductivity.
Over time, the graph learns which doctor profiles match which symptom patterns best.
"""

import logging
from typing import Optional
from collections import defaultdict

from .graph_engine import (
    MedicalKnowledgeGraph, NodeType, EdgeType,
)

logger = logging.getLogger(__name__)


class GraphDoctorMatcher:
    """
    Matches cases to doctors using knowledge graph paths.
    """

    def __init__(self, graph: MedicalKnowledgeGraph):
        self.graph = graph
        # Track which doctors handled which conditions (for experience matching)
        self._doctor_experience: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # doctor_id → {condition_name: times_handled}

    def record_doctor_resolution(self, doctor_id: str, specialization: str,
                                  condition: str, outcome: str = "resolved") -> None:
        """
        Record that a doctor resolved a case for a specific condition.
        Builds up the experience profile for better future matching.
        """
        self._doctor_experience[doctor_id][condition.lower()] += 1

        # Also reinforce the condition → specialty edge if applicable
        spec_node = self.graph.find_node(specialization, NodeType.SPECIALTY)
        cond_node = self.graph.find_node(condition, NodeType.CONDITION)
        if spec_node and cond_node:
            edge = self.graph.get_edge(cond_node.id, spec_node.id)
            if edge and outcome == "resolved":
                self.graph.reinforce_edge(cond_node.id, spec_node.id, amount=0.5)
                logger.debug("[DoctorMatcher] Reinforced %s→%s after resolution",
                           condition, specialization)

    def match_doctors(
        self,
        symptoms: list[str],
        conditions: list[str],
        body_area: Optional[str] = None,
        country_code: Optional[str] = None,
        available_doctors: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Score and rank doctors for a case based on knowledge graph analysis.

        Args:
            symptoms: Patient's reported symptoms
            conditions: Predicted or diagnosed conditions
            body_area: Affected body area
            country_code: Patient's country code
            available_doctors: List of doctor dicts with at minimum:
                {id, specialization, country_code, languages}

        Returns:
            Scored doctor list, highest match first
        """
        if not available_doctors:
            return []

        # ── Step 1: Determine ideal specialties from the graph ───────────
        ideal_specialties = self._get_ideal_specialties(symptoms, conditions)

        # ── Step 2: Score each doctor ────────────────────────────────────
        scored_doctors = []
        for doc in available_doctors:
            score = self._score_doctor(
                doctor=doc,
                ideal_specialties=ideal_specialties,
                conditions=conditions,
                country_code=country_code,
            )
            scored_doctors.append({
                **doc,
                "kg_match_score": round(score, 3),
                "match_details": self._explain_match(doc, ideal_specialties, conditions),
            })

        scored_doctors.sort(key=lambda d: d["kg_match_score"], reverse=True)
        return scored_doctors

    def _get_ideal_specialties(self, symptoms: list[str], conditions: list[str]) -> dict[str, float]:
        """
        Determine ideal specialties from the graph based on symptoms and conditions.
        Returns: {specialty_name: relevance_score}
        """
        specialty_scores: dict[str, float] = {}

        # From conditions → specialties (primary signal)
        for cond_name in conditions:
            cond_node = self.graph.find_node(cond_name, NodeType.CONDITION)
            if not cond_node:
                matches = self.graph.find_nodes_fuzzy(cond_name, NodeType.CONDITION, limit=1)
                cond_node = matches[0] if matches else None

            if cond_node:
                for spec_node, edge in self.graph.get_neighbors(
                    cond_node.id, edge_type=EdgeType.TREATED_BY, target_type=NodeType.SPECIALTY
                ):
                    # Use conductivity — well-reinforced paths carry more weight
                    score = edge.effective_weight * edge.confidence
                    specialty_scores[spec_node.name] = (
                        specialty_scores.get(spec_node.name, 0) + score
                    )

        # From symptoms → conditions → specialties (secondary signal)
        for sym_name in symptoms:
            sym_node = self.graph.find_node(sym_name, NodeType.SYMPTOM)
            if not sym_node:
                continue
            for cond_node, sym_edge in self.graph.get_neighbors(
                sym_node.id, edge_type=EdgeType.INDICATES, target_type=NodeType.CONDITION
            ):
                for spec_node, cond_edge in self.graph.get_neighbors(
                    cond_node.id, edge_type=EdgeType.TREATED_BY, target_type=NodeType.SPECIALTY
                ):
                    score = sym_edge.effective_weight * cond_edge.effective_weight * 0.5
                    specialty_scores[spec_node.name] = (
                        specialty_scores.get(spec_node.name, 0) + score
                    )

        # Always include General Practice as fallback
        if "General Practice" not in specialty_scores:
            specialty_scores["General Practice"] = 0.3

        return specialty_scores

    def _score_doctor(
        self,
        doctor: dict,
        ideal_specialties: dict[str, float],
        conditions: list[str],
        country_code: Optional[str],
    ) -> float:
        """Score a single doctor against the case requirements."""
        score = 0.0

        # ── Specialty match (40% weight) ─────────────────────────────────
        doc_spec = doctor.get("specialization", "").strip()
        if doc_spec in ideal_specialties:
            score += ideal_specialties[doc_spec] * 40
        else:
            # Partial credit for related specialties
            for ideal_spec, relevance in ideal_specialties.items():
                if self._specialties_related(doc_spec, ideal_spec):
                    score += relevance * 20
                    break

        # ── Experience match (30% weight) ─────────────────────────────────
        doc_id = doctor.get("id", "")
        if doc_id in self._doctor_experience:
            exp = self._doctor_experience[doc_id]
            for cond in conditions:
                times = exp.get(cond.lower(), 0)
                if times > 0:
                    # Diminishing returns: first few cases matter most
                    score += min(30, times * 10)

        # ── Country/regional match (20% weight) ──────────────────────────
        doc_country = doctor.get("country_code", "")
        if country_code and doc_country == country_code:
            score += 20

        # ── Availability bonus (10% weight) ──────────────────────────────
        if doctor.get("availability") == "online":
            score += 10

        return score

    def _explain_match(self, doctor: dict, ideal_specialties: dict[str, float],
                       conditions: list[str]) -> dict:
        """Explain why this doctor was matched."""
        doc_spec = doctor.get("specialization", "")
        reasons = []

        if doc_spec in ideal_specialties:
            reasons.append(f"Specialty '{doc_spec}' is ideal (score: {ideal_specialties[doc_spec]:.2f})")

        doc_id = doctor.get("id", "")
        if doc_id in self._doctor_experience:
            for cond in conditions:
                times = self._doctor_experience[doc_id].get(cond.lower(), 0)
                if times > 0:
                    reasons.append(f"Handled '{cond}' {times} time(s) before")

        if not reasons:
            reasons.append("General availability match")

        return {"reasons": reasons, "ideal_specialties": ideal_specialties}

    def _specialties_related(self, spec_a: str, spec_b: str) -> bool:
        """Check if two specialties are related using the knowledge graph."""
        node_a = self.graph.find_node(spec_a, NodeType.SPECIALTY)
        node_b = self.graph.find_node(spec_b, NodeType.SPECIALTY)
        if not node_a or not node_b:
            return False

        # Check if they share conditions (overlap in what they treat)
        conditions_a = set()
        for edge in self.graph.get_incoming_edges(node_a.id):
            if edge.edge_type == EdgeType.TREATED_BY:
                conditions_a.add(edge.source_id)

        for edge in self.graph.get_incoming_edges(node_b.id):
            if edge.edge_type == EdgeType.TREATED_BY:
                if edge.source_id in conditions_a:
                    return True

        return False

    def get_specialty_heatmap(self) -> dict:
        """
        Return a heatmap of specialty demand based on graph conductivity.
        Shows which specialty paths are "hottest" (most reinforced).
        """
        heatmap = {}
        for spec_node in self.graph.get_nodes_by_type(NodeType.SPECIALTY):
            total_conductivity = 0
            incoming = self.graph.get_incoming_edges(spec_node.id)
            for edge in incoming:
                if edge.edge_type == EdgeType.TREATED_BY:
                    total_conductivity += edge.conductivity

            heatmap[spec_node.name] = {
                "total_conductivity": round(total_conductivity, 3),
                "incoming_edges": len(incoming),
                "avg_conductivity": round(
                    total_conductivity / len(incoming) if incoming else 0, 3
                ),
                "visit_count": spec_node.visit_count,
            }

        return dict(sorted(heatmap.items(), key=lambda x: x[1]["total_conductivity"], reverse=True))
