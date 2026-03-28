"""
Core Knowledge Graph Engine — Physarum polycephalum inspired.

The slime mold Physarum polycephalum creates optimal transport networks by:
1. Sending flow through all possible paths simultaneously
2. Strengthening tubes (edges) that carry more flow
3. Letting unused tubes decay and eventually disappear
4. Discovering new paths when existing ones become congested

We adapt this for medical knowledge:
- NODES: symptoms, conditions, body_systems, specialties, risk_factors, medications
- EDGES: weighted connections with conductivity (σ) that evolves:
    σ(t+1) = (1 - decay) * σ(t) + reinforcement * flow
- FLOW: each patient conversation is a "flow" through the graph
- CONDUCTIVITY: high σ = well-established medical relationship
- DECAY: unused paths weaken over time (prevents stale knowledge)
- BRANCHING: new edges sprout when co-occurrence exceeds threshold

The E. coli chemotaxis layer adds biased random exploration:
- High-conductivity edges are preferred (chemotactic gradient)
- But low-probability paths are still explored (tumble behavior)
- This prevents the graph from collapsing to a single pathway
"""

import json
import math
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Node Types ───────────────────────────────────────────────────────────────
class NodeType(str, Enum):
    SYMPTOM = "symptom"
    CONDITION = "condition"
    BODY_SYSTEM = "body_system"
    SPECIALTY = "specialty"
    RISK_FACTOR = "risk_factor"
    MEDICATION = "medication"
    QUESTION = "question"           # follow-up questions the bot can ask
    DEMOGRAPHIC = "demographic"     # age group, sex, region


# ── Edge Types ───────────────────────────────────────────────────────────────
class EdgeType(str, Enum):
    PRESENTS_WITH = "presents_with"         # symptom → symptom co-occurrence
    INDICATES = "indicates"                 # symptom → condition
    LOCATED_IN = "located_in"              # symptom/condition → body_system
    TREATED_BY = "treated_by"              # condition → specialty
    RISK_FOR = "risk_for"                  # risk_factor → condition
    MANAGED_WITH = "managed_with"          # condition → medication
    FOLLOW_UP = "follow_up"               # question → symptom (what question reveals)
    CONTRAINDICATES = "contraindicates"    # medication → condition
    DEMOGRAPHIC_RISK = "demographic_risk"  # demographic → condition


# ── Data Classes ─────────────────────────────────────────────────────────────
@dataclass
class GraphNode:
    id: str
    name: str
    node_type: NodeType
    metadata: dict = field(default_factory=dict)
    # ICD-11 code, SNOMED code, severity range, etc.
    icd11_code: Optional[str] = None
    activation: float = 0.0         # current activation level (for navigation)
    visit_count: int = 0            # total times visited across all conversations
    created_at: float = field(default_factory=time.time)
    last_visited: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "metadata": self.metadata,
            "icd11_code": self.icd11_code,
            "activation": self.activation,
            "visit_count": self.visit_count,
            "created_at": self.created_at,
            "last_visited": self.last_visited,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GraphNode":
        d = dict(d)
        d["node_type"] = NodeType(d["node_type"])
        return cls(**d)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    # ── Physarum parameters ──
    conductivity: float = 0.1       # σ: strength of connection (0→1+)
    base_weight: float = 0.1        # initial medical knowledge weight
    flow: float = 0.0               # current flow through this edge
    # ── Evolution tracking ──
    reinforcement_count: int = 0    # times this edge was reinforced
    decay_count: int = 0            # times decay was applied
    created_at: float = field(default_factory=time.time)
    last_reinforced: float = 0.0
    # ── Metadata ──
    confidence: float = 0.5         # medical confidence (0=speculative, 1=textbook)
    source: str = "seed"            # where this edge came from (seed/scraped/learned)
    metadata: dict = field(default_factory=dict)

    @property
    def effective_weight(self) -> float:
        """Combined weight: base medical knowledge + learned conductivity."""
        return self.base_weight + self.conductivity

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "conductivity": self.conductivity,
            "base_weight": self.base_weight,
            "flow": self.flow,
            "reinforcement_count": self.reinforcement_count,
            "decay_count": self.decay_count,
            "created_at": self.created_at,
            "last_reinforced": self.last_reinforced,
            "confidence": self.confidence,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GraphEdge":
        d = dict(d)
        d["edge_type"] = EdgeType(d["edge_type"])
        return cls(**d)


@dataclass
class ConversationTrace:
    """Records a single conversation's path through the graph."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id: Optional[str] = None
    visited_nodes: list[str] = field(default_factory=list)
    traversed_edges: list[tuple[str, str]] = field(default_factory=list)
    activated_symptoms: list[str] = field(default_factory=list)
    predicted_conditions: list[str] = field(default_factory=list)
    final_specialty: Optional[str] = None
    doctor_validated: bool = False
    doctor_diagnosis: Optional[str] = None
    outcome_score: float = 0.0     # 1=correct prediction, 0=wrong
    timestamp: float = field(default_factory=time.time)


# ── Physarum Parameters ──────────────────────────────────────────────────────
@dataclass
class PhysarumConfig:
    decay_rate: float = 0.02            # σ decay per cycle (unused edges weaken)
    reinforcement_rate: float = 0.15    # σ boost per flow unit
    min_conductivity: float = 0.01      # floor — edges never fully die
    max_conductivity: float = 5.0       # ceiling — prevents runaway
    flow_normalization: float = 1.0     # scale factor for flow computation
    # E. coli chemotaxis parameters
    exploration_rate: float = 0.15      # probability of "tumble" (random exploration)
    gradient_sensitivity: float = 2.0   # how strongly conductivity biases direction
    # Branching leaf parameters
    co_occurrence_threshold: int = 3    # min co-occurrences before new edge sprouts
    sprout_confidence: float = 0.3      # initial confidence of sprouted edges
    # Decay cycle
    decay_interval_hours: float = 24.0  # how often to run global decay


# ── Core Graph Engine ────────────────────────────────────────────────────────
class MedicalKnowledgeGraph:
    """
    The living knowledge graph. Nodes are medical concepts, edges are
    relationships whose strength evolves through the Physarum algorithm.
    """

    def __init__(self, config: Optional[PhysarumConfig] = None, persist_path: Optional[str] = None):
        self.config = config or PhysarumConfig()
        self.persist_path = persist_path

        # Core storage
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[tuple[str, str], GraphEdge] = {}  # (source, target) → edge
        self.adjacency: dict[str, set[str]] = defaultdict(set)  # node → neighbors
        self.reverse_adjacency: dict[str, set[str]] = defaultdict(set)

        # Index by type for fast lookup
        self._type_index: dict[NodeType, set[str]] = defaultdict(set)
        self._name_index: dict[str, str] = {}  # lowercase name → node_id

        # Co-occurrence tracking for branching leaf syndrome
        self._co_occurrence: dict[tuple[str, str], int] = defaultdict(int)

        # Conversation traces for learning
        self.traces: list[ConversationTrace] = []
        self._last_decay: float = time.time()

        # Load persisted state if available
        if persist_path:
            self._load(persist_path)

    # ── Node Operations ──────────────────────────────────────────────────

    def add_node(self, name: str, node_type: NodeType, **kwargs) -> GraphNode:
        """Add a node. Returns existing node if name+type already exists."""
        lookup_key = f"{node_type.value}:{name.lower()}"
        if lookup_key in self._name_index:
            return self.nodes[self._name_index[lookup_key]]

        node_id = kwargs.pop("id", None) or f"{node_type.value}_{uuid.uuid4().hex[:8]}"
        node = GraphNode(id=node_id, name=name, node_type=node_type, **kwargs)
        self.nodes[node_id] = node
        self._type_index[node_type].add(node_id)
        self._name_index[lookup_key] = node_id
        return node

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def find_node(self, name: str, node_type: Optional[NodeType] = None) -> Optional[GraphNode]:
        """Find node by name, optionally filtered by type."""
        if node_type:
            lookup_key = f"{node_type.value}:{name.lower()}"
            nid = self._name_index.get(lookup_key)
            return self.nodes.get(nid) if nid else None
        # Search across all types
        for nt in NodeType:
            lookup_key = f"{nt.value}:{name.lower()}"
            nid = self._name_index.get(lookup_key)
            if nid:
                return self.nodes[nid]
        return None

    def find_nodes_fuzzy(self, query: str, node_type: Optional[NodeType] = None, limit: int = 10) -> list[GraphNode]:
        """Fuzzy search nodes by name substring."""
        query_lower = query.lower()
        results = []
        search_set = self._type_index.get(node_type, set()) if node_type else set(self.nodes.keys())
        for nid in search_set:
            node = self.nodes[nid]
            if query_lower in node.name.lower():
                results.append(node)
        results.sort(key=lambda n: n.visit_count, reverse=True)
        return results[:limit]

    def get_nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        return [self.nodes[nid] for nid in self._type_index.get(node_type, set())]

    # ── Edge Operations ──────────────────────────────────────────────────

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        base_weight: float = 0.1,
        confidence: float = 0.5,
        source: str = "seed",
        bidirectional: bool = False,
        **kwargs,
    ) -> GraphEdge:
        """Add a directed edge. Set bidirectional=True for symmetric relationships."""
        if source_id not in self.nodes or target_id not in self.nodes:
            raise ValueError(f"Both nodes must exist: {source_id}, {target_id}")

        key = (source_id, target_id)
        if key in self.edges:
            return self.edges[key]

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            base_weight=base_weight,
            conductivity=base_weight,  # start conductivity = base
            confidence=confidence,
            source=source,
            **kwargs,
        )
        self.edges[key] = edge
        self.adjacency[source_id].add(target_id)
        self.reverse_adjacency[target_id].add(source_id)

        if bidirectional:
            rev_key = (target_id, source_id)
            if rev_key not in self.edges:
                rev_edge = GraphEdge(
                    source_id=target_id,
                    target_id=source_id,
                    edge_type=edge_type,
                    base_weight=base_weight,
                    conductivity=base_weight,
                    confidence=confidence,
                    source=source,
                    **kwargs,
                )
                self.edges[rev_key] = rev_edge
                self.adjacency[target_id].add(source_id)
                self.reverse_adjacency[source_id].add(target_id)

        return edge

    def get_edge(self, source_id: str, target_id: str) -> Optional[GraphEdge]:
        return self.edges.get((source_id, target_id))

    def get_outgoing_edges(self, node_id: str) -> list[GraphEdge]:
        """All edges from this node, sorted by effective weight descending."""
        neighbors = self.adjacency.get(node_id, set())
        edges = [self.edges[(node_id, n)] for n in neighbors if (node_id, n) in self.edges]
        edges.sort(key=lambda e: e.effective_weight, reverse=True)
        return edges

    def get_incoming_edges(self, node_id: str) -> list[GraphEdge]:
        """All edges pointing to this node."""
        sources = self.reverse_adjacency.get(node_id, set())
        edges = [self.edges[(s, node_id)] for s in sources if (s, node_id) in self.edges]
        edges.sort(key=lambda e: e.effective_weight, reverse=True)
        return edges

    def get_neighbors(self, node_id: str, edge_type: Optional[EdgeType] = None,
                      target_type: Optional[NodeType] = None) -> list[tuple[GraphNode, GraphEdge]]:
        """Get neighbors with optional filtering by edge type and target node type."""
        results = []
        for edge in self.get_outgoing_edges(node_id):
            target = self.nodes.get(edge.target_id)
            if not target:
                continue
            if edge_type and edge.edge_type != edge_type:
                continue
            if target_type and target.node_type != target_type:
                continue
            results.append((target, edge))
        return results

    # ── Physarum: Flow & Reinforcement ───────────────────────────────────

    def send_flow(self, path: list[str], flow_amount: float = 1.0) -> None:
        """
        Send flow along a path through the graph (Physarum tube reinforcement).
        Each edge in the path gets its conductivity increased proportional to flow.
        """
        for i in range(len(path) - 1):
            key = (path[i], path[i + 1])
            edge = self.edges.get(key)
            if edge:
                edge.flow += flow_amount
                old_σ = edge.conductivity
                # Physarum update: σ += reinforcement * flow
                edge.conductivity = min(
                    self.config.max_conductivity,
                    edge.conductivity + self.config.reinforcement_rate * flow_amount,
                )
                edge.reinforcement_count += 1
                edge.last_reinforced = time.time()
                logger.debug(
                    "[Physarum] Reinforced %s→%s: σ %.3f→%.3f (flow=%.2f)",
                    path[i][:12], path[i + 1][:12], old_σ, edge.conductivity, flow_amount,
                )

            # Update node visit counts
            node = self.nodes.get(path[i])
            if node:
                node.visit_count += 1
                node.last_visited = time.time()

        # Last node in path
        if path:
            node = self.nodes.get(path[-1])
            if node:
                node.visit_count += 1
                node.last_visited = time.time()

    def reinforce_edge(self, source_id: str, target_id: str, amount: float = 1.0) -> None:
        """Directly reinforce a single edge."""
        edge = self.edges.get((source_id, target_id))
        if edge:
            edge.conductivity = min(
                self.config.max_conductivity,
                edge.conductivity + self.config.reinforcement_rate * amount,
            )
            edge.reinforcement_count += 1
            edge.last_reinforced = time.time()

    def apply_global_decay(self) -> int:
        """
        Physarum decay: all edges lose conductivity over time.
        Unused edges weaken, well-used edges barely notice.
        Returns number of edges that hit minimum conductivity.
        """
        decayed_to_min = 0
        now = time.time()

        for edge in self.edges.values():
            old_σ = edge.conductivity
            # Decay proportional to time since last reinforcement
            edge.conductivity = max(
                self.config.min_conductivity,
                edge.conductivity * (1 - self.config.decay_rate),
            )
            edge.flow *= 0.5  # flow also decays
            edge.decay_count += 1

            if edge.conductivity <= self.config.min_conductivity:
                decayed_to_min += 1

        self._last_decay = now
        logger.info("[Physarum] Global decay applied | edges=%d | at_minimum=%d",
                     len(self.edges), decayed_to_min)
        return decayed_to_min

    def maybe_decay(self) -> bool:
        """Run decay if enough time has passed since last decay cycle."""
        hours_since = (time.time() - self._last_decay) / 3600
        if hours_since >= self.config.decay_interval_hours:
            self.apply_global_decay()
            return True
        return False

    # ── Branching Leaf Syndrome: New Edge Discovery ──────────────────────

    def record_co_occurrence(self, node_id_a: str, node_id_b: str) -> Optional[GraphEdge]:
        """
        Track that two nodes appeared together in a conversation.
        If co-occurrence exceeds threshold AND no edge exists, sprout a new edge.
        This is the branching leaf / Physarum network expansion mechanism.
        """
        if node_id_a == node_id_b:
            return None
        key = tuple(sorted([node_id_a, node_id_b]))
        self._co_occurrence[key] += 1

        if self._co_occurrence[key] >= self.config.co_occurrence_threshold:
            # Check if edge already exists in either direction
            if (node_id_a, node_id_b) not in self.edges and (node_id_b, node_id_a) not in self.edges:
                node_a = self.nodes.get(node_id_a)
                node_b = self.nodes.get(node_id_b)
                if not node_a or not node_b:
                    return None

                # Determine edge type from node types
                edge_type = self._infer_edge_type(node_a, node_b)
                if edge_type:
                    edge = self.add_edge(
                        node_id_a, node_id_b, edge_type,
                        base_weight=0.05,
                        confidence=self.config.sprout_confidence,
                        source="learned",
                        bidirectional=(node_a.node_type == node_b.node_type),
                    )
                    logger.info(
                        "[BranchLeaf] New edge sprouted: %s (%s) → %s (%s) | co_occur=%d",
                        node_a.name, node_a.node_type.value,
                        node_b.name, node_b.node_type.value,
                        self._co_occurrence[key],
                    )
                    return edge
        return None

    def _infer_edge_type(self, node_a: GraphNode, node_b: GraphNode) -> Optional[EdgeType]:
        """Infer edge type from the types of two co-occurring nodes."""
        type_pair = (node_a.node_type, node_b.node_type)
        mapping = {
            (NodeType.SYMPTOM, NodeType.SYMPTOM): EdgeType.PRESENTS_WITH,
            (NodeType.SYMPTOM, NodeType.CONDITION): EdgeType.INDICATES,
            (NodeType.CONDITION, NodeType.SYMPTOM): EdgeType.INDICATES,
            (NodeType.SYMPTOM, NodeType.BODY_SYSTEM): EdgeType.LOCATED_IN,
            (NodeType.CONDITION, NodeType.BODY_SYSTEM): EdgeType.LOCATED_IN,
            (NodeType.CONDITION, NodeType.SPECIALTY): EdgeType.TREATED_BY,
            (NodeType.RISK_FACTOR, NodeType.CONDITION): EdgeType.RISK_FOR,
            (NodeType.CONDITION, NodeType.MEDICATION): EdgeType.MANAGED_WITH,
            (NodeType.QUESTION, NodeType.SYMPTOM): EdgeType.FOLLOW_UP,
            (NodeType.DEMOGRAPHIC, NodeType.CONDITION): EdgeType.DEMOGRAPHIC_RISK,
        }
        return mapping.get(type_pair)

    # ── E. coli Chemotaxis: Navigation ───────────────────────────────────

    def get_navigation_scores(self, current_nodes: list[str],
                               target_type: Optional[NodeType] = None) -> list[tuple[GraphNode, float]]:
        """
        Compute chemotaxis-like navigation scores from current position.
        High-conductivity neighbors get high scores (gradient following),
        but exploration_rate chance of boosting low-score neighbors (tumble).

        Returns: [(node, score), ...] sorted by score descending.
        """
        import random
        scores: dict[str, float] = defaultdict(float)

        for current_id in current_nodes:
            for edge in self.get_outgoing_edges(current_id):
                target = self.nodes.get(edge.target_id)
                if not target:
                    continue
                if target_type and target.node_type != target_type:
                    continue
                if target.id in current_nodes:
                    continue  # don't revisit

                # Chemotactic gradient: score based on conductivity
                gradient = edge.effective_weight ** self.config.gradient_sensitivity
                scores[target.id] += gradient

        # E. coli tumble: random boost for exploration
        all_candidates = list(scores.keys())
        if all_candidates and random.random() < self.config.exploration_rate:
            tumble_target = random.choice(all_candidates)
            max_score = max(scores.values()) if scores else 1.0
            scores[tumble_target] += max_score * 0.5
            logger.debug("[Chemotaxis] Tumble boost for %s", tumble_target[:12])

        result = [(self.nodes[nid], score) for nid, score in scores.items()]
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    # ── Activation Spreading ─────────────────────────────────────────────

    def spread_activation(self, seed_nodes: list[str], depth: int = 3,
                          decay_factor: float = 0.5) -> dict[str, float]:
        """
        Spread activation from seed nodes through the graph.
        Each hop reduces activation by decay_factor.
        Returns: {node_id: activation_level}
        """
        activation: dict[str, float] = {}
        frontier = [(nid, 1.0) for nid in seed_nodes]

        for _ in range(depth):
            next_frontier = []
            for node_id, current_activation in frontier:
                if node_id in activation and activation[node_id] >= current_activation:
                    continue
                activation[node_id] = max(activation.get(node_id, 0), current_activation)

                for edge in self.get_outgoing_edges(node_id):
                    propagated = current_activation * decay_factor * edge.effective_weight
                    if propagated > 0.01:  # threshold to prevent infinite spreading
                        next_frontier.append((edge.target_id, propagated))

            frontier = next_frontier

        return activation

    # ── Graph Statistics ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """Summary statistics of the graph."""
        edge_conductivities = [e.conductivity for e in self.edges.values()]
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": {
                nt.value: len(ids) for nt, ids in self._type_index.items()
            },
            "edges_by_type": self._count_edges_by_type(),
            "avg_conductivity": sum(edge_conductivities) / len(edge_conductivities) if edge_conductivities else 0,
            "max_conductivity": max(edge_conductivities) if edge_conductivities else 0,
            "min_conductivity": min(edge_conductivities) if edge_conductivities else 0,
            "learned_edges": sum(1 for e in self.edges.values() if e.source == "learned"),
            "total_traces": len(self.traces),
            "co_occurrences_tracked": len(self._co_occurrence),
        }

    def _count_edges_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for e in self.edges.values():
            counts[e.edge_type.value] += 1
        return dict(counts)

    def get_hottest_paths(self, top_n: int = 10) -> list[dict]:
        """Return the highest-conductivity edges (most validated medical paths)."""
        sorted_edges = sorted(self.edges.values(), key=lambda e: e.conductivity, reverse=True)
        results = []
        for edge in sorted_edges[:top_n]:
            src = self.nodes.get(edge.source_id)
            tgt = self.nodes.get(edge.target_id)
            if src and tgt:
                results.append({
                    "source": src.name,
                    "source_type": src.node_type.value,
                    "target": tgt.name,
                    "target_type": tgt.node_type.value,
                    "edge_type": edge.edge_type.value,
                    "conductivity": round(edge.conductivity, 4),
                    "confidence": round(edge.confidence, 2),
                    "reinforcements": edge.reinforcement_count,
                    "source_info": edge.source,
                })
        return results

    # ── Persistence ──────────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> None:
        """Serialize graph to JSON."""
        save_path = Path(path or self.persist_path or "knowledge_graph.json")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "config": {
                "decay_rate": self.config.decay_rate,
                "reinforcement_rate": self.config.reinforcement_rate,
                "exploration_rate": self.config.exploration_rate,
                "co_occurrence_threshold": self.config.co_occurrence_threshold,
            },
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "co_occurrences": {
                f"{k[0]}|{k[1]}": v for k, v in self._co_occurrence.items()
            },
            "last_decay": self._last_decay,
        }

        save_path.write_text(json.dumps(data, indent=2))
        logger.info("[KG] Saved graph: %d nodes, %d edges → %s",
                     len(self.nodes), len(self.edges), save_path)

    def _load(self, path: str) -> None:
        """Load graph from JSON."""
        load_path = Path(path)
        if not load_path.exists():
            logger.info("[KG] No persisted graph at %s — starting fresh", path)
            return

        data = json.loads(load_path.read_text())

        for nd in data.get("nodes", []):
            node = GraphNode.from_dict(nd)
            self.nodes[node.id] = node
            self._type_index[node.node_type].add(node.id)
            lookup_key = f"{node.node_type.value}:{node.name.lower()}"
            self._name_index[lookup_key] = node.id

        for ed in data.get("edges", []):
            edge = GraphEdge.from_dict(ed)
            key = (edge.source_id, edge.target_id)
            self.edges[key] = edge
            self.adjacency[edge.source_id].add(edge.target_id)
            self.reverse_adjacency[edge.target_id].add(edge.source_id)

        for k, v in data.get("co_occurrences", {}).items():
            parts = k.split("|")
            if len(parts) == 2:
                self._co_occurrence[tuple(parts)] = v

        self._last_decay = data.get("last_decay", time.time())

        logger.info("[KG] Loaded graph: %d nodes, %d edges from %s",
                     len(self.nodes), len(self.edges), path)

    # ── Subgraph Extraction ──────────────────────────────────────────────

    def extract_subgraph(self, center_node_id: str, depth: int = 2) -> dict:
        """Extract a subgraph centered on a node for visualization/API response."""
        visited = set()
        frontier = {center_node_id}
        nodes_out = []
        edges_out = []

        for _ in range(depth):
            next_frontier = set()
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                node = self.nodes.get(nid)
                if node:
                    nodes_out.append(node.to_dict())
                for edge in self.get_outgoing_edges(nid):
                    edges_out.append(edge.to_dict())
                    if edge.target_id not in visited:
                        next_frontier.add(edge.target_id)
                for edge in self.get_incoming_edges(nid):
                    edges_out.append(edge.to_dict())
                    if edge.source_id not in visited:
                        next_frontier.add(edge.source_id)
            frontier = next_frontier

        return {
            "center": center_node_id,
            "depth": depth,
            "nodes": nodes_out,
            "edges": edges_out,
        }
