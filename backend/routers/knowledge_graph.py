"""
Knowledge Graph API Router.

Exposes the bio-inspired medical knowledge graph for:
1. Conversation navigation (chatbot uses this to decide what to ask next)
2. Post-case learning (doctor feedback strengthens/weakens graph paths)
3. Doctor matching (graph-powered specialty scoring)
4. Graph introspection (visualize hottest paths, stats, evolution)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from auth.middleware import get_current_actor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])

# ── Singleton graph instance (initialized in main.py lifespan) ───────────────
_graph = None
_backpropagator = None
_doctor_matcher = None


def init_knowledge_graph(persist_path: str = "./data/knowledge_graph.json"):
    """Initialize the knowledge graph. Called from main.py lifespan."""
    global _graph, _backpropagator, _doctor_matcher

    from knowledge_graph.builder import build_medical_knowledge_graph
    from knowledge_graph.backpropagator import GraphBackpropagator
    from knowledge_graph.doctor_matcher import GraphDoctorMatcher

    _graph = build_medical_knowledge_graph(persist_path=persist_path)
    _backpropagator = GraphBackpropagator(_graph)
    _doctor_matcher = GraphDoctorMatcher(_graph)

    logger.info("[KG Router] Knowledge graph initialized: %s", _graph.stats())
    return _graph


def get_graph():
    if _graph is None:
        raise HTTPException(status_code=503, detail="Knowledge graph not initialized")
    return _graph


# ── Request/Response Models ──────────────────────────────────────────────────

class NavigateRequest(BaseModel):
    case_id: str
    symptoms: list[str]
    transcript: Optional[str] = None

class QuickQueryRequest(BaseModel):
    symptoms: list[str]

class NavigateResponse(BaseModel):
    reported_symptoms: list[str]
    suggested_questions: list[dict]
    activated_conditions: list[dict]
    activated_body_systems: list[dict]
    suggested_specialties: list[dict]
    risk_factors_to_check: list[dict]
    conversation_depth: int
    graph_confidence: float
    emergency: Optional[dict] = None

class BackpropRequest(BaseModel):
    case_id: str
    doctor_diagnosis: Optional[str] = None
    doctor_specialty: Optional[str] = None
    outcome: str = "resolved"

class DoctorMatchRequest(BaseModel):
    symptoms: list[str]
    conditions: list[str] = []
    body_area: Optional[str] = None
    country_code: Optional[str] = None
    available_doctors: list[dict] = []


# ── Navigation Endpoints ─────────────────────────────────────────────────────

@router.post("/navigate", response_model=NavigateResponse)
async def navigate(request: NavigateRequest):
    """
    Navigate the knowledge graph for a conversation.
    Call this after each patient turn to get suggested follow-up questions
    and understand what conditions are being activated.
    """
    graph = get_graph()

    from services.navigator_store import get_navigator, persist_navigator

    nav = get_navigator(request.case_id, graph)

    # Process transcript if provided (extract symptoms from voice)
    if request.transcript:
        nav.process_transcript(request.transcript)

    # Process explicit symptoms
    if request.symptoms:
        context = nav.process_symptoms(request.symptoms)
    else:
        context = nav.process_symptoms([])

    persist_navigator(request.case_id, nav)

    # Check for emergencies
    emergency = nav.check_emergency()

    return NavigateResponse(
        reported_symptoms=context["reported_symptoms"],
        suggested_questions=context["suggested_questions"],
        activated_conditions=context["activated_conditions"],
        activated_body_systems=context["activated_body_systems"],
        suggested_specialties=context["suggested_specialties"],
        risk_factors_to_check=context["risk_factors_to_check"],
        conversation_depth=context["conversation_depth"],
        graph_confidence=context["graph_confidence"],
        emergency=emergency,
    )


@router.post("/query")
async def quick_query(request: QuickQueryRequest):
    """
    Quick symptom query for the doctor portal — no case_id needed.
    Returns conditions, specialties, body systems for a set of symptoms.
    """
    import uuid
    graph = get_graph()
    from knowledge_graph.navigator import ConversationNavigator

    temp_id = f"query-{uuid.uuid4().hex[:8]}"
    nav = ConversationNavigator(graph, case_id=temp_id)
    context = nav.process_symptoms(request.symptoms)

    return {
        "reported_symptoms": context["reported_symptoms"],
        "suggested_questions": context["suggested_questions"],
        "activated_conditions": context["activated_conditions"],
        "activated_body_systems": context["activated_body_systems"],
        "suggested_specialties": context["suggested_specialties"],
        "graph_confidence": context["graph_confidence"],
    }


@router.post("/navigate/question-asked")
async def mark_question_asked(case_id: str, question_id: str):
    """Mark a suggested question as asked, so it won't be suggested again."""
    from services.navigator_store import get_navigator, persist_navigator
    from services import session_store

    graph = get_graph()
    if not session_store.case_nav_get(case_id):
        raise HTTPException(status_code=404, detail="No active navigation session for this case")

    nav = get_navigator(case_id, graph)
    nav.mark_question_asked(question_id)
    persist_navigator(case_id, nav)
    return {"status": "ok"}


# ── Backpropagation Endpoints ────────────────────────────────────────────────

@router.post("/backpropagate")
async def backpropagate(
    request: BackpropRequest,
    _actor: dict = Depends(get_current_actor),
):
    """
    Backpropagate learning from a completed case.
    Call this after the doctor provides their diagnosis and the case is resolved.
    The graph learns from the outcome — correct paths strengthen, wrong ones weaken.
    """
    global _backpropagator
    graph = get_graph()

    if _backpropagator is None:
        from knowledge_graph.backpropagator import GraphBackpropagator
        _backpropagator = GraphBackpropagator(graph)

    from services import session_store
    from services.navigator_store import get_navigator, clear_navigator

    if not session_store.case_nav_get(request.case_id):
        raise HTTPException(status_code=404, detail="No navigation trace for this case")

    nav = get_navigator(request.case_id, graph)
    trace = nav.get_trace()

    result = _backpropagator.backpropagate(
        trace=trace,
        doctor_diagnosis=request.doctor_diagnosis,
        doctor_specialty=request.doctor_specialty,
        outcome=request.outcome,
    )

    # Record doctor experience for future matching
    if _doctor_matcher and request.doctor_diagnosis and request.doctor_specialty:
        _doctor_matcher.record_doctor_resolution(
            doctor_id="",  # would come from case
            specialization=request.doctor_specialty,
            condition=request.doctor_diagnosis,
            outcome=request.outcome,
        )

    # Persist updated graph
    if graph.persist_path:
        graph.save()

    clear_navigator(request.case_id)

    return result


# ── Doctor Matching Endpoints ────────────────────────────────────────────────

@router.post("/match-doctors")
async def match_doctors(request: DoctorMatchRequest):
    """
    Score and rank available doctors for a case using knowledge graph analysis.
    Goes beyond simple specialty matching — uses graph conductivity (Physarum paths)
    to find doctors whose expertise best matches the symptom pattern.
    """
    global _doctor_matcher
    graph = get_graph()

    if _doctor_matcher is None:
        from knowledge_graph.doctor_matcher import GraphDoctorMatcher
        _doctor_matcher = GraphDoctorMatcher(graph)

    scored = _doctor_matcher.match_doctors(
        symptoms=request.symptoms,
        conditions=request.conditions,
        body_area=request.body_area,
        country_code=request.country_code,
        available_doctors=request.available_doctors,
    )

    return {"doctors": scored, "total": len(scored)}


# ── Graph Introspection Endpoints ────────────────────────────────────────────

@router.get("/stats")
async def graph_stats():
    """Full knowledge graph statistics."""
    graph = get_graph()
    stats = graph.stats()
    if _backpropagator:
        stats["learning"] = _backpropagator.get_learning_stats()
    if _doctor_matcher:
        stats["specialty_heatmap"] = _doctor_matcher.get_specialty_heatmap()
    return stats


@router.get("/hottest-paths")
async def hottest_paths(top_n: int = 20):
    """
    The highest-conductivity edges in the graph.
    These are the most validated medical relationships — the paths that
    the Physarum algorithm has reinforced through actual patient conversations.
    """
    graph = get_graph()
    return {"paths": graph.get_hottest_paths(top_n=top_n)}


@router.get("/subgraph/{node_name}")
async def get_subgraph(node_name: str, depth: int = 2):
    """Extract a subgraph centered on a named node (for visualization)."""
    graph = get_graph()
    node = graph.find_node(node_name)
    if not node:
        matches = graph.find_nodes_fuzzy(node_name, limit=1)
        if not matches:
            raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")
        node = matches[0]

    return graph.extract_subgraph(node.id, depth=depth)


@router.get("/conditions/{symptom_name}")
async def conditions_for_symptom(symptom_name: str, top_n: int = 10):
    """
    Get conditions associated with a symptom, ranked by graph conductivity.
    Shows the most likely conditions based on the graph's learned paths.
    """
    graph = get_graph()
    sym_node = graph.find_node(symptom_name.lower())
    if not sym_node:
        matches = graph.find_nodes_fuzzy(symptom_name, limit=1)
        if not matches:
            raise HTTPException(status_code=404, detail=f"Symptom '{symptom_name}' not found")
        sym_node = matches[0]

    from knowledge_graph.graph_engine import EdgeType, NodeType
    conditions = []
    for cond_node, edge in graph.get_neighbors(
        sym_node.id, edge_type=EdgeType.INDICATES, target_type=NodeType.CONDITION
    ):
        conditions.append({
            "condition": cond_node.name,
            "icd11_code": cond_node.icd11_code,
            "conductivity": round(edge.conductivity, 4),
            "confidence": round(edge.confidence, 2),
            "base_weight": round(edge.base_weight, 2),
            "reinforcements": edge.reinforcement_count,
            "is_emergency": cond_node.metadata.get("emergency", False),
        })

    conditions.sort(key=lambda c: c["conductivity"], reverse=True)
    return {"symptom": sym_node.name, "conditions": conditions[:top_n]}


@router.get("/search")
async def search_nodes(q: str, node_type: Optional[str] = None, limit: int = 10):
    """Search the knowledge graph by name."""
    graph = get_graph()
    from knowledge_graph.graph_engine import NodeType as NT

    nt = NT(node_type) if node_type else None
    nodes = graph.find_nodes_fuzzy(q, node_type=nt, limit=limit)
    return {
        "query": q,
        "results": [
            {
                "id": n.id,
                "name": n.name,
                "type": n.node_type.value,
                "visit_count": n.visit_count,
                "icd11_code": n.icd11_code,
            }
            for n in nodes
        ],
    }


@router.post("/enrich")
async def enrich_graph():
    """
    Run the data scraper to enrich the graph with external data.
    Scrapes ICD-11, MedlinePlus, WHO GHO, and OpenFDA.
    """
    graph = get_graph()
    from knowledge_graph.builder import enrich_from_scraper

    try:
        result = await enrich_from_scraper(graph)
        return {"status": "ok", "enrichment": result}
    except Exception as exc:
        logger.error("[KG] Enrichment failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {exc}")


@router.post("/decay")
async def force_decay():
    """Force a global decay cycle on the knowledge graph (Physarum tube shrinkage)."""
    graph = get_graph()
    decayed = graph.apply_global_decay()
    if graph.persist_path:
        graph.save()
    return {"status": "ok", "edges_at_minimum": decayed, "total_edges": len(graph.edges)}
