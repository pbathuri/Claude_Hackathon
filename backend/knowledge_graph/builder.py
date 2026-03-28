"""
Knowledge Graph Builder — Seeds and enriches the graph.

Combines curated seed data + scraped data into a complete medical knowledge graph.
Run once at startup, then periodically to incorporate new scraped data.
"""

import logging
import time

from .graph_engine import MedicalKnowledgeGraph, NodeType, EdgeType, PhysarumConfig
from .seed_data import (
    BODY_SYSTEMS, SYMPTOMS, CONDITIONS, SPECIALTIES, RISK_FACTORS,
    MEDICATIONS, QUESTIONS,
    SYMPTOM_CONDITION_EDGES, CONDITION_SPECIALTY_EDGES,
    CONDITION_BODY_SYSTEM_EDGES, SYMPTOM_BODY_SYSTEM_EDGES,
    RISK_CONDITION_EDGES, CONDITION_MEDICATION_EDGES,
    SYMPTOM_COOCCURRENCE_EDGES, QUESTION_SYMPTOM_EDGES,
)

logger = logging.getLogger(__name__)


def build_medical_knowledge_graph(persist_path: str = None) -> MedicalKnowledgeGraph:
    """
    Build the complete medical knowledge graph from seed data.
    Returns a fully populated, ready-to-navigate graph.
    """
    config = PhysarumConfig(
        decay_rate=0.02,
        reinforcement_rate=0.15,
        exploration_rate=0.15,
        co_occurrence_threshold=3,
        sprout_confidence=0.3,
        decay_interval_hours=24.0,
    )

    graph = MedicalKnowledgeGraph(config=config, persist_path=persist_path)

    # If graph was loaded from persistence, check if it already has data
    if len(graph.nodes) > 50:
        logger.info("[Builder] Graph loaded from persistence: %d nodes, %d edges",
                     len(graph.nodes), len(graph.edges))
        return graph

    start = time.time()
    logger.info("[Builder] Seeding medical knowledge graph...")

    # ── Step 1: Add all nodes ────────────────────────────────────────────

    # Body Systems
    for bs in BODY_SYSTEMS:
        graph.add_node(bs["name"], NodeType.BODY_SYSTEM, metadata=bs.get("metadata", {}))
    logger.info("[Builder] Added %d body systems", len(BODY_SYSTEMS))

    # Symptoms
    for sym in SYMPTOMS:
        graph.add_node(sym["name"], NodeType.SYMPTOM, metadata=sym.get("metadata", {}))
    logger.info("[Builder] Added %d symptoms", len(SYMPTOMS))

    # Conditions
    for cond in CONDITIONS:
        graph.add_node(
            cond["name"], NodeType.CONDITION,
            metadata=cond.get("metadata", {}),
            icd11_code=cond.get("icd11_code"),
        )
    logger.info("[Builder] Added %d conditions", len(CONDITIONS))

    # Specialties
    for spec in SPECIALTIES:
        graph.add_node(spec["name"], NodeType.SPECIALTY, metadata=spec.get("metadata", {}))
    logger.info("[Builder] Added %d specialties", len(SPECIALTIES))

    # Risk Factors
    for rf in RISK_FACTORS:
        graph.add_node(rf["name"], NodeType.RISK_FACTOR, metadata=rf.get("metadata", {}))
    logger.info("[Builder] Added %d risk factors", len(RISK_FACTORS))

    # Medications
    for med in MEDICATIONS:
        graph.add_node(med["name"], NodeType.MEDICATION, metadata=med.get("metadata", {}))
    logger.info("[Builder] Added %d medications", len(MEDICATIONS))

    # Questions
    for q in QUESTIONS:
        graph.add_node(q["name"], NodeType.QUESTION, metadata=q.get("metadata", {}))
    logger.info("[Builder] Added %d questions", len(QUESTIONS))

    # ── Step 2: Add all edges ────────────────────────────────────────────

    edge_count = 0

    # Symptom → Condition (INDICATES)
    for sym_name, cond_name, weight, confidence in SYMPTOM_CONDITION_EDGES:
        sym = graph.find_node(sym_name, NodeType.SYMPTOM)
        cond = graph.find_node(cond_name, NodeType.CONDITION)
        if sym and cond:
            graph.add_edge(sym.id, cond.id, EdgeType.INDICATES,
                          base_weight=weight, confidence=confidence, source="medical_textbook")
            edge_count += 1
    logger.info("[Builder] Added %d symptom→condition edges", edge_count)

    # Condition → Specialty (TREATED_BY)
    spec_edges = 0
    for cond_name, spec_name, weight, confidence in CONDITION_SPECIALTY_EDGES:
        cond = graph.find_node(cond_name, NodeType.CONDITION)
        spec = graph.find_node(spec_name, NodeType.SPECIALTY)
        if cond and spec:
            graph.add_edge(cond.id, spec.id, EdgeType.TREATED_BY,
                          base_weight=weight, confidence=confidence, source="medical_textbook")
            spec_edges += 1
    logger.info("[Builder] Added %d condition→specialty edges", spec_edges)

    # Condition → Body System (LOCATED_IN)
    bs_edges = 0
    for cond_name, bs_name in CONDITION_BODY_SYSTEM_EDGES:
        cond = graph.find_node(cond_name, NodeType.CONDITION)
        bs = graph.find_node(bs_name, NodeType.BODY_SYSTEM)
        if cond and bs:
            graph.add_edge(cond.id, bs.id, EdgeType.LOCATED_IN,
                          base_weight=0.7, confidence=0.95, source="medical_textbook")
            bs_edges += 1
    logger.info("[Builder] Added %d condition→body_system edges", bs_edges)

    # Symptom → Body System (LOCATED_IN)
    sym_bs_edges = 0
    for sym_name, bs_name in SYMPTOM_BODY_SYSTEM_EDGES:
        sym = graph.find_node(sym_name, NodeType.SYMPTOM)
        bs = graph.find_node(bs_name, NodeType.BODY_SYSTEM)
        if sym and bs:
            graph.add_edge(sym.id, bs.id, EdgeType.LOCATED_IN,
                          base_weight=0.6, confidence=0.90, source="medical_textbook")
            sym_bs_edges += 1
    logger.info("[Builder] Added %d symptom→body_system edges", sym_bs_edges)

    # Risk Factor → Condition (RISK_FOR)
    risk_edges = 0
    for rf_name, cond_name, weight, confidence in RISK_CONDITION_EDGES:
        rf = graph.find_node(rf_name, NodeType.RISK_FACTOR)
        cond = graph.find_node(cond_name, NodeType.CONDITION)
        if rf and cond:
            graph.add_edge(rf.id, cond.id, EdgeType.RISK_FOR,
                          base_weight=weight, confidence=confidence, source="medical_textbook")
            risk_edges += 1
    logger.info("[Builder] Added %d risk_factor→condition edges", risk_edges)

    # Condition → Medication (MANAGED_WITH)
    med_edges = 0
    for cond_name, med_name, weight, confidence in CONDITION_MEDICATION_EDGES:
        cond = graph.find_node(cond_name, NodeType.CONDITION)
        med = graph.find_node(med_name, NodeType.MEDICATION)
        if cond and med:
            graph.add_edge(cond.id, med.id, EdgeType.MANAGED_WITH,
                          base_weight=weight, confidence=confidence, source="medical_textbook")
            med_edges += 1
    logger.info("[Builder] Added %d condition→medication edges", med_edges)

    # Symptom ↔ Symptom (PRESENTS_WITH — bidirectional)
    cooccur_edges = 0
    for sym_a, sym_b, weight, confidence in SYMPTOM_COOCCURRENCE_EDGES:
        node_a = graph.find_node(sym_a, NodeType.SYMPTOM)
        node_b = graph.find_node(sym_b, NodeType.SYMPTOM)
        if node_a and node_b:
            graph.add_edge(node_a.id, node_b.id, EdgeType.PRESENTS_WITH,
                          base_weight=weight, confidence=confidence, source="medical_textbook",
                          bidirectional=True)
            cooccur_edges += 1
    logger.info("[Builder] Added %d symptom co-occurrence edges", cooccur_edges)

    # Question → Symptom (FOLLOW_UP)
    q_edges = 0
    for q_name, sym_name, weight, confidence in QUESTION_SYMPTOM_EDGES:
        q = graph.find_node(q_name, NodeType.QUESTION)
        sym = graph.find_node(sym_name, NodeType.SYMPTOM)
        if q and sym:
            graph.add_edge(q.id, sym.id, EdgeType.FOLLOW_UP,
                          base_weight=weight, confidence=confidence, source="medical_textbook")
            q_edges += 1
    logger.info("[Builder] Added %d question→symptom edges", q_edges)

    elapsed = time.time() - start
    stats = graph.stats()
    logger.info(
        "[Builder] Knowledge graph built in %.2fs | "
        "nodes=%d | edges=%d | node_types=%s",
        elapsed, stats["total_nodes"], stats["total_edges"],
        stats["nodes_by_type"],
    )

    # ── Step 3: Run data pipeline enrichment (optional, cache-backed) ────
    import os
    if os.environ.get("SKIP_PIPELINE_ENRICHMENT", "").lower() in ("1", "true", "yes"):
        logger.info("[Builder] Skipping pipeline enrichment (SKIP_PIPELINE_ENRICHMENT=1)")
    else:
        try:
            from .data_pipeline import enrich_graph_from_pipeline

            logger.info("[Builder] Running data pipeline enrichment...")
            enrichment_report = enrich_graph_from_pipeline(graph, use_cache=True)
            logger.info("[Builder] Pipeline enrichment: +%d nodes, +%d edges",
                         enrichment_report.get("nodes_added", 0),
                         enrichment_report.get("edges_added", 0))
        except Exception as exc:
            logger.warning("[Builder] Pipeline enrichment skipped: %s", exc)

    elapsed = time.time() - start
    stats = graph.stats()
    logger.info(
        "[Builder] Final graph after enrichment in %.2fs | "
        "nodes=%d | edges=%d | node_types=%s",
        elapsed, stats["total_nodes"], stats["total_edges"],
        stats["nodes_by_type"],
    )

    # Persist
    if persist_path:
        graph.save()

    return graph


async def enrich_from_scraper(graph: MedicalKnowledgeGraph, cache_dir: str = "./data/scraper_cache") -> dict:
    """
    Enrich the graph with scraped data from APIs.
    Should be run after initial build, on a periodic schedule.

    DEPRECATED: Use data_pipeline.enrich_graph_from_pipeline() instead.
    Kept for backward compatibility.
    """
    from .data_pipeline import enrich_graph_from_pipeline

    return enrich_graph_from_pipeline(graph, use_cache=True)
