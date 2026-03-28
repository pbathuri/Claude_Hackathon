"""
Conversation Navigator — Graph-guided follow-up question selection.

During a patient conversation, the navigator:
1. Activates symptom nodes based on what the patient reports
2. Spreads activation through the graph (activation spreading)
3. Uses E. coli chemotaxis to select the best follow-up question
4. Tracks the conversation path for later backpropagation
5. Predicts likely conditions based on activation patterns

The navigator does NOT diagnose — it guides the chatbot to ask
the most information-rich questions based on the current symptom pattern.
"""

import logging
import random
from typing import Optional

from .graph_engine import (
    MedicalKnowledgeGraph, GraphNode, GraphEdge, ConversationTrace,
    NodeType, EdgeType,
)

logger = logging.getLogger(__name__)


class ConversationNavigator:
    """
    Navigates the knowledge graph during a patient conversation.
    One instance per active conversation.
    """

    def __init__(self, graph: MedicalKnowledgeGraph, case_id: Optional[str] = None):
        self.graph = graph
        self.trace = ConversationTrace(case_id=case_id)
        self.activated_nodes: dict[str, float] = {}  # node_id → activation level
        self.asked_questions: set[str] = set()       # question node IDs already asked
        self.reported_symptoms: list[str] = []       # symptom names reported by patient
        self._symptom_node_ids: list[str] = []       # corresponding node IDs

    # ── Process Patient Input ────────────────────────────────────────────

    def process_symptoms(self, symptom_names: list[str]) -> dict:
        """
        Process new symptoms reported by the patient.
        Returns navigation context for the LLM: suggested questions,
        activated conditions, relevant body systems.

        Handles: duplicates, unknown symptoms, empty input.
        """
        new_symptom_ids = []
        # Track unknown symptoms for fallback question generation
        self._unknown_symptoms: list[str] = getattr(self, "_unknown_symptoms", [])

        for name in symptom_names:
            name_lower = name.lower().strip()
            if not name_lower:
                continue

            # Deduplicate: skip if already reported (by name)
            if name_lower in [s.lower() for s in self.reported_symptoms]:
                continue

            # Try exact match first, then fuzzy
            node = self.graph.find_node(name_lower, NodeType.SYMPTOM)
            if not node:
                matches = self.graph.find_nodes_fuzzy(name_lower, NodeType.SYMPTOM, limit=1)
                node = matches[0] if matches else None

            if node:
                # Avoid duplicate node IDs
                if node.id not in self._symptom_node_ids:
                    new_symptom_ids.append(node.id)
                    self._symptom_node_ids.append(node.id)
                    self.trace.visited_nodes.append(node.id)
                if node.name not in self.reported_symptoms:
                    self.reported_symptoms.append(node.name)
                    self.trace.activated_symptoms.append(node.name)
                logger.info("[Navigator] Activated symptom: %s (%s)", node.name, node.id)
            else:
                # Track unknown symptoms for context — graph learns later
                if name_lower not in self._unknown_symptoms:
                    self._unknown_symptoms.append(name_lower)
                logger.info("[Navigator] Unknown symptom: '%s' — not in graph", name_lower)

        # Record co-occurrences for branching leaf syndrome (only new pairs)
        if new_symptom_ids:
            for i, sid_a in enumerate(self._symptom_node_ids):
                for sid_b in self._symptom_node_ids[i + 1:]:
                    self.graph.record_co_occurrence(sid_a, sid_b)

        # Spread activation from all symptom nodes
        if self._symptom_node_ids:
            self.activated_nodes = self.graph.spread_activation(
                self._symptom_node_ids, depth=3, decay_factor=0.6
            )

        return self._build_navigation_context()

    def process_transcript(self, transcript: str) -> dict:
        """
        Extract symptoms from a voice transcript and process them.
        Uses keyword matching against known symptom names.
        """
        transcript_lower = transcript.lower()
        found_symptoms = []

        for node in self.graph.get_nodes_by_type(NodeType.SYMPTOM):
            if node.name.lower() in transcript_lower and node.name not in self.reported_symptoms:
                found_symptoms.append(node.name)

        if found_symptoms:
            logger.info("[Navigator] Extracted from transcript: %s", found_symptoms)
            return self.process_symptoms(found_symptoms)

        return self._build_navigation_context()

    # ── Navigation Context ───────────────────────────────────────────────

    def _build_navigation_context(self) -> dict:
        """Build the full navigation context for the LLM."""
        unknown = getattr(self, "_unknown_symptoms", [])
        return {
            "reported_symptoms": self.reported_symptoms,
            "unknown_symptoms": unknown,
            "suggested_questions": self.get_suggested_questions(top_n=5),
            "activated_conditions": self.get_activated_conditions(top_n=8),
            "activated_body_systems": self.get_activated_body_systems(),
            "suggested_specialties": self.get_suggested_specialties(top_n=3),
            "risk_factors_to_check": self.get_relevant_risk_factors(top_n=3),
            "conversation_depth": len(self.reported_symptoms) + len(unknown),
            "graph_confidence": self._compute_confidence(),
        }

    # ── Question Selection (Chemotaxis) ──────────────────────────────────

    def get_suggested_questions(self, top_n: int = 5) -> list[dict]:
        """
        Select the best follow-up questions using E. coli chemotaxis.

        Strategy: Questions are scored by how much NEW information they could reveal.
        Questions that probe high-activation but unconfirmed conditions score highest.
        """
        question_scores: list[tuple[GraphNode, float]] = []

        for q_node in self.graph.get_nodes_by_type(NodeType.QUESTION):
            if q_node.id in self.asked_questions:
                continue

            score = 0.0

            # Score based on what symptoms this question reveals
            neighbors = self.graph.get_neighbors(
                q_node.id, edge_type=EdgeType.FOLLOW_UP, target_type=NodeType.SYMPTOM
            )
            for symptom_node, edge in neighbors:
                if symptom_node.name not in self.reported_symptoms:
                    # Unreported symptom — check if it would help differentiate
                    sym_activation = self.activated_nodes.get(symptom_node.id, 0)
                    score += edge.effective_weight * (1 + sym_activation)

            # Boost questions relevant to activated conditions
            for cond_id, activation in sorted(
                self.activated_nodes.items(), key=lambda x: x[1], reverse=True
            )[:5]:
                cond_node = self.graph.get_node(cond_id)
                if cond_node and cond_node.node_type == NodeType.CONDITION:
                    # Check if this question's symptoms connect to this condition
                    for symptom_node, edge in neighbors:
                        cond_edges = self.graph.get_neighbors(
                            symptom_node.id, edge_type=EdgeType.INDICATES
                        )
                        for ce_node, ce_edge in cond_edges:
                            if ce_node.id == cond_id:
                                score += activation * ce_edge.effective_weight * 0.5

            # Priority boost from question metadata
            priority = q_node.metadata.get("priority", 3)
            score *= (4 - priority) / 3  # priority 1 gets 1.0x, priority 3 gets 0.33x

            # Tropical relevance boost if patient has tropical indicators
            if q_node.metadata.get("tropical_relevant"):
                tropical_symptoms = {"fever", "chills", "body aches", "diarrhea", "rash"}
                if tropical_symptoms.intersection(set(self.reported_symptoms)):
                    score *= 1.5

            if score > 0:
                question_scores.append((q_node, score))

        # E. coli tumble: occasionally boost a random low-scoring question
        if len(question_scores) > 1 and random.random() < self.graph.config.exploration_rate:
            idx = random.randint(0, len(question_scores) - 1)
            node, old_score = question_scores[idx]
            max_score = max(s for _, s in question_scores)
            if max_score > 0:
                question_scores[idx] = (node, old_score + max_score * 0.3)

        question_scores.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                "question": q.name,
                "question_id": q.id,
                "relevance_score": round(score, 3),
                "reveals": q.metadata.get("reveals", "unknown"),
            }
            for q, score in question_scores[:top_n]
        ]

    # ── Condition Activation ─────────────────────────────────────────────

    def get_activated_conditions(self, top_n: int = 8) -> list[dict]:
        """
        Get conditions most strongly activated by current symptoms.
        This is NOT a diagnosis — it's a probabilistic ranking for navigation.
        """
        condition_scores: dict[str, float] = {}

        for node_id, activation in self.activated_nodes.items():
            node = self.graph.get_node(node_id)
            if node and node.node_type == NodeType.CONDITION:
                condition_scores[node_id] = activation

        # Also check direct symptom→condition edges
        for sym_id in self._symptom_node_ids:
            for cond_node, edge in self.graph.get_neighbors(
                sym_id, edge_type=EdgeType.INDICATES, target_type=NodeType.CONDITION
            ):
                bonus = edge.effective_weight * edge.confidence
                condition_scores[cond_node.id] = (
                    condition_scores.get(cond_node.id, 0) + bonus
                )

        sorted_conditions = sorted(condition_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for cond_id, score in sorted_conditions[:top_n]:
            node = self.graph.get_node(cond_id)
            if node:
                # Count how many of the patient's symptoms map to this condition
                matching = 0
                for sym_id in self._symptom_node_ids:
                    if self.graph.get_edge(sym_id, cond_id):
                        matching += 1

                results.append({
                    "condition": node.name,
                    "condition_id": node.id,
                    "activation_score": round(score, 3),
                    "matching_symptoms": matching,
                    "total_reported": len(self._symptom_node_ids),
                    "icd11_code": node.icd11_code,
                    "is_emergency": node.metadata.get("emergency", False),
                })

        self.trace.predicted_conditions = [r["condition"] for r in results[:3]]
        return results

    # ── Body System Activation ───────────────────────────────────────────

    def get_activated_body_systems(self) -> list[dict]:
        """Which body systems are most involved?"""
        system_scores: dict[str, float] = {}

        for node_id, activation in self.activated_nodes.items():
            node = self.graph.get_node(node_id)
            if node and node.node_type == NodeType.BODY_SYSTEM:
                system_scores[node_id] = activation

        # Direct symptom → body_system edges
        for sym_id in self._symptom_node_ids:
            for sys_node, edge in self.graph.get_neighbors(
                sym_id, edge_type=EdgeType.LOCATED_IN, target_type=NodeType.BODY_SYSTEM
            ):
                system_scores[sys_node.id] = system_scores.get(sys_node.id, 0) + edge.effective_weight

        sorted_systems = sorted(system_scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {
                "system": self.graph.get_node(sid).name,
                "activation": round(score, 3),
            }
            for sid, score in sorted_systems if self.graph.get_node(sid)
        ]

    # ── Specialty Suggestion ─────────────────────────────────────────────

    def get_suggested_specialties(self, top_n: int = 3) -> list[dict]:
        """
        Suggest medical specialties based on activated conditions.
        Follows condition → specialty edges with conductivity weighting.
        """
        specialty_scores: dict[str, float] = {}

        # For each activated condition, follow TREATED_BY edges
        conditions = self.get_activated_conditions(top_n=5)
        for cond in conditions:
            cond_id = cond["condition_id"]
            for spec_node, edge in self.graph.get_neighbors(
                cond_id, edge_type=EdgeType.TREATED_BY, target_type=NodeType.SPECIALTY
            ):
                score = cond["activation_score"] * edge.effective_weight
                specialty_scores[spec_node.id] = (
                    specialty_scores.get(spec_node.id, 0) + score
                )

        sorted_specialties = sorted(specialty_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for spec_id, score in sorted_specialties[:top_n]:
            node = self.graph.get_node(spec_id)
            if node:
                results.append({
                    "specialty": node.name,
                    "specialty_id": node.id,
                    "match_score": round(score, 3),
                })

        if results:
            self.trace.final_specialty = results[0]["specialty"]

        return results

    # ── Risk Factor Relevance ────────────────────────────────────────────

    def get_relevant_risk_factors(self, top_n: int = 3) -> list[dict]:
        """Find risk factors connected to activated conditions that the chatbot should ask about."""
        risk_scores: dict[str, float] = {}

        for cond_id, activation in self.activated_nodes.items():
            cond_node = self.graph.get_node(cond_id)
            if not cond_node or cond_node.node_type != NodeType.CONDITION:
                continue

            # Check incoming RISK_FOR edges
            for edge in self.graph.get_incoming_edges(cond_id):
                source = self.graph.get_node(edge.source_id)
                if source and source.node_type == NodeType.RISK_FACTOR:
                    if edge.edge_type == EdgeType.RISK_FOR:
                        score = activation * edge.effective_weight
                        risk_scores[source.id] = risk_scores.get(source.id, 0) + score

        sorted_risks = sorted(risk_scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"risk_factor": self.graph.get_node(rid).name, "relevance": round(score, 3)}
            for rid, score in sorted_risks[:top_n]
            if self.graph.get_node(rid)
        ]

    # ── Confidence ───────────────────────────────────────────────────────

    def _compute_confidence(self) -> float:
        """
        How confident are we in the current navigation?
        Based on: number of symptoms, edge confidences, activation spread.
        """
        if not self._symptom_node_ids:
            return 0.0

        # Factor 1: Number of symptoms (more = more confident)
        symptom_factor = min(1.0, len(self._symptom_node_ids) / 5)

        # Factor 2: Average edge confidence on activated paths
        edge_confidences = []
        for sym_id in self._symptom_node_ids:
            for edge in self.graph.get_outgoing_edges(sym_id):
                if edge.target_id in self.activated_nodes:
                    edge_confidences.append(edge.confidence)
        conf_factor = sum(edge_confidences) / len(edge_confidences) if edge_confidences else 0.3

        # Factor 3: Activation concentration (peaked = more certain)
        if self.activated_nodes:
            activations = list(self.activated_nodes.values())
            max_act = max(activations)
            avg_act = sum(activations) / len(activations)
            concentration = max_act / avg_act if avg_act > 0 else 1.0
            conc_factor = min(1.0, concentration / 5)
        else:
            conc_factor = 0.0

        return round(symptom_factor * 0.3 + conf_factor * 0.4 + conc_factor * 0.3, 3)

    # ── Mark Question Asked ──────────────────────────────────────────────

    def mark_question_asked(self, question_id: str) -> None:
        """Mark a question as asked so it won't be suggested again."""
        self.asked_questions.add(question_id)
        self.trace.visited_nodes.append(question_id)

    # ── Get Trace ────────────────────────────────────────────────────────

    def get_trace(self) -> ConversationTrace:
        """Get the conversation trace for backpropagation."""
        return self.trace

    # ── Emergency Detection (graph-based) ────────────────────────────────

    def check_emergency(self) -> Optional[dict]:
        """
        Check if activated conditions include emergencies.
        Returns emergency info if detected, None otherwise.
        """
        for cond in self.get_activated_conditions(top_n=5):
            if cond.get("is_emergency") and cond["activation_score"] > 0.3:
                return {
                    "is_emergency": True,
                    "condition": cond["condition"],
                    "activation_score": cond["activation_score"],
                    "matching_symptoms": cond["matching_symptoms"],
                }
        return None
