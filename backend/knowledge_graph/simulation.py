"""
Physarum Knowledge Graph Simulation — 60 Synthetic Patient Cases.

Builds the full medical knowledge graph, runs 60 realistic cases through the
navigator → backpropagator pipeline, and generates publication-quality
visualizations showing how the graph evolves through Physarum reinforcement.

Usage:
    python -m knowledge_graph.simulation          # from backend/
    python knowledge_graph/simulation.py          # from backend/
"""

import json
import logging
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    from .builder import build_medical_knowledge_graph
    from .navigator import ConversationNavigator
    from .backpropagator import GraphBackpropagator
    from .graph_engine import MedicalKnowledgeGraph, NodeType, EdgeType
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from knowledge_graph.builder import build_medical_knowledge_graph
    from knowledge_graph.navigator import ConversationNavigator
    from knowledge_graph.backpropagator import GraphBackpropagator
    from knowledge_graph.graph_engine import MedicalKnowledgeGraph, NodeType, EdgeType

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)

RANDOM_SEED = 42
VIZ_DIR = Path(__file__).resolve().parent.parent / "data" / "viz"

# ── 60 Synthetic Patient Cases ────────────────────────────────────────────────
# Categories: 15 tropical, 10 cardiovascular, 8 respiratory, 7 GI,
#             5 maternal, 5 mental health, 5 renal, 5 other

SYNTHETIC_CASES = [
    # ── Tropical Infectious (15) ──────────────────────────────────────────
    {"symptoms": ["fever", "chills", "headache", "body aches", "excessive sweating"],
     "country": "Nigeria", "true_diagnosis": "Malaria", "doctor_specialty": "Infectious Disease", "severity": 7},
    {"symptoms": ["fever", "chills", "fatigue", "nausea", "body aches"],
     "country": "Kenya", "true_diagnosis": "Malaria", "doctor_specialty": "Infectious Disease", "severity": 6},
    {"symptoms": ["fever", "headache", "chills", "vomiting"],
     "country": "India", "true_diagnosis": "Malaria", "doctor_specialty": "Infectious Disease", "severity": 7},
    {"symptoms": ["fever", "joint pain", "rash", "headache", "muscle pain"],
     "country": "Philippines", "true_diagnosis": "Dengue Fever", "doctor_specialty": "Infectious Disease", "severity": 8},
    {"symptoms": ["fever", "body aches", "rash", "headache", "fatigue"],
     "country": "India", "true_diagnosis": "Dengue Fever", "doctor_specialty": "Infectious Disease", "severity": 7},
    {"symptoms": ["fever", "headache", "abdominal pain", "loss of appetite", "diarrhea"],
     "country": "Nigeria", "true_diagnosis": "Typhoid Fever", "doctor_specialty": "Infectious Disease", "severity": 7},
    {"symptoms": ["fever", "constipation", "headache", "abdominal pain", "fatigue"],
     "country": "India", "true_diagnosis": "Typhoid Fever", "doctor_specialty": "Infectious Disease", "severity": 6},
    {"symptoms": ["diarrhea", "vomiting", "dehydration"],
     "country": "Kenya", "true_diagnosis": "Cholera", "doctor_specialty": "Emergency Medicine", "severity": 9},
    {"symptoms": ["diarrhea", "dehydration", "vomiting", "nausea"],
     "country": "Nigeria", "true_diagnosis": "Cholera", "doctor_specialty": "Emergency Medicine", "severity": 9},
    {"symptoms": ["cough", "night sweats", "weight loss", "fatigue", "fever"],
     "country": "India", "true_diagnosis": "Tuberculosis", "doctor_specialty": "Infectious Disease", "severity": 7},
    {"symptoms": ["cough", "coughing blood", "fever", "weight loss", "fatigue"],
     "country": "Philippines", "true_diagnosis": "Tuberculosis", "doctor_specialty": "Infectious Disease", "severity": 8},
    {"symptoms": ["cough", "night sweats", "fever", "weight loss"],
     "country": "Kenya", "true_diagnosis": "Tuberculosis", "doctor_specialty": "Infectious Disease", "severity": 7},
    {"symptoms": ["headache", "fever", "neck pain", "confusion", "light sensitivity"],
     "country": "Nigeria", "true_diagnosis": "Meningitis", "doctor_specialty": "Infectious Disease", "severity": 9},
    {"symptoms": ["fever", "confusion", "shortness of breath", "low blood pressure", "palpitations"],
     "country": "India", "true_diagnosis": "Sepsis", "doctor_specialty": "Emergency Medicine", "severity": 10},
    {"symptoms": ["fever", "chills", "headache", "nausea", "vomiting"],
     "country": "Philippines", "true_diagnosis": "Malaria", "doctor_specialty": "Infectious Disease", "severity": 7},

    # ── Cardiovascular (10) ───────────────────────────────────────────────
    {"symptoms": ["headache", "dizziness", "vision changes", "chest pain"],
     "country": "Nigeria", "true_diagnosis": "Hypertension", "doctor_specialty": "Cardiology", "severity": 6},
    {"symptoms": ["headache", "dizziness", "shortness of breath"],
     "country": "India", "true_diagnosis": "Hypertension", "doctor_specialty": "Cardiology", "severity": 5},
    {"symptoms": ["shortness of breath", "swollen legs", "fatigue", "palpitations", "cough"],
     "country": "Nigeria", "true_diagnosis": "Heart Failure", "doctor_specialty": "Cardiology", "severity": 8},
    {"symptoms": ["shortness of breath", "swollen legs", "fatigue"],
     "country": "India", "true_diagnosis": "Heart Failure", "doctor_specialty": "Cardiology", "severity": 7},
    {"symptoms": ["slurred speech", "weakness", "numbness", "confusion", "headache"],
     "country": "India", "true_diagnosis": "Stroke", "doctor_specialty": "Neurology", "severity": 10},
    {"symptoms": ["slurred speech", "weakness", "vision changes", "confusion"],
     "country": "Nigeria", "true_diagnosis": "Stroke", "doctor_specialty": "Neurology", "severity": 10},
    {"symptoms": ["headache", "dizziness", "chest pain"],
     "country": "Kenya", "true_diagnosis": "Hypertension", "doctor_specialty": "Cardiology", "severity": 6},
    {"symptoms": ["shortness of breath", "swollen legs", "palpitations", "fatigue"],
     "country": "Philippines", "true_diagnosis": "Heart Failure", "doctor_specialty": "Cardiology", "severity": 8},
    {"symptoms": ["chest pain", "shortness of breath", "fatigue", "palpitations"],
     "country": "India", "true_diagnosis": "Coronary Artery Disease", "doctor_specialty": "Cardiology", "severity": 8},
    {"symptoms": ["palpitations", "shortness of breath", "dizziness", "fatigue"],
     "country": "Kenya", "true_diagnosis": "Atrial Fibrillation", "doctor_specialty": "Cardiology", "severity": 6},

    # ── Respiratory (8) ───────────────────────────────────────────────────
    {"symptoms": ["cough", "fever", "shortness of breath", "chest pain", "chills"],
     "country": "Kenya", "true_diagnosis": "Pneumonia", "doctor_specialty": "Pulmonology", "severity": 7},
    {"symptoms": ["cough", "fever", "shortness of breath", "fatigue"],
     "country": "India", "true_diagnosis": "Pneumonia", "doctor_specialty": "Pulmonology", "severity": 7},
    {"symptoms": ["wheezing", "shortness of breath", "chest tightness", "cough"],
     "country": "Philippines", "true_diagnosis": "Asthma", "doctor_specialty": "Pulmonology", "severity": 6},
    {"symptoms": ["wheezing", "cough", "shortness of breath"],
     "country": "India", "true_diagnosis": "Asthma", "doctor_specialty": "Pulmonology", "severity": 5},
    {"symptoms": ["cough", "shortness of breath", "wheezing", "fatigue"],
     "country": "India", "true_diagnosis": "COPD", "doctor_specialty": "Pulmonology", "severity": 7},
    {"symptoms": ["cough", "fever", "shortness of breath", "chills", "fatigue"],
     "country": "Nigeria", "true_diagnosis": "Pneumonia", "doctor_specialty": "Pulmonology", "severity": 8},
    {"symptoms": ["wheezing", "chest tightness", "cough", "shortness of breath"],
     "country": "Kenya", "true_diagnosis": "Asthma", "doctor_specialty": "Pulmonology", "severity": 5},
    {"symptoms": ["cough", "fever", "sore throat", "fatigue"],
     "country": "Philippines", "true_diagnosis": "Bronchitis", "doctor_specialty": "Pulmonology", "severity": 4},

    # ── Gastrointestinal (7) ──────────────────────────────────────────────
    {"symptoms": ["diarrhea", "vomiting", "nausea", "abdominal pain", "fever"],
     "country": "Nigeria", "true_diagnosis": "Gastroenteritis", "doctor_specialty": "General Practice", "severity": 5},
    {"symptoms": ["diarrhea", "vomiting", "dehydration", "nausea"],
     "country": "India", "true_diagnosis": "Gastroenteritis", "doctor_specialty": "General Practice", "severity": 6},
    {"symptoms": ["abdominal pain", "nausea", "vomiting", "fever", "loss of appetite"],
     "country": "Philippines", "true_diagnosis": "Appendicitis", "doctor_specialty": "Surgery", "severity": 8},
    {"symptoms": ["abdominal pain", "heartburn", "nausea", "blood in stool"],
     "country": "India", "true_diagnosis": "Peptic Ulcer Disease", "doctor_specialty": "Gastroenterology", "severity": 6},
    {"symptoms": ["diarrhea", "vomiting", "abdominal pain", "dehydration"],
     "country": "Kenya", "true_diagnosis": "Gastroenteritis", "doctor_specialty": "General Practice", "severity": 5},
    {"symptoms": ["abdominal pain", "nausea", "fever", "vomiting"],
     "country": "Nigeria", "true_diagnosis": "Appendicitis", "doctor_specialty": "Surgery", "severity": 8},
    {"symptoms": ["abdominal pain", "heartburn", "nausea"],
     "country": "Philippines", "true_diagnosis": "Peptic Ulcer Disease", "doctor_specialty": "Gastroenterology", "severity": 5},

    # ── Maternal / Reproductive (5) ───────────────────────────────────────
    {"symptoms": ["high blood pressure", "headache", "vision changes", "swelling"],
     "country": "Nigeria", "true_diagnosis": "Pre-eclampsia", "doctor_specialty": "Obstetrics and Gynecology", "severity": 8},
    {"symptoms": ["high blood pressure", "swelling", "abdominal pain", "headache"],
     "country": "Kenya", "true_diagnosis": "Pre-eclampsia", "doctor_specialty": "Obstetrics and Gynecology", "severity": 8},
    {"symptoms": ["pelvic pain", "vaginal bleeding", "abdominal pain", "dizziness"],
     "country": "Philippines", "true_diagnosis": "Ectopic Pregnancy", "doctor_specialty": "Obstetrics and Gynecology", "severity": 9},
    {"symptoms": ["excessive thirst", "frequent urination", "fatigue", "blurred vision"],
     "country": "India", "true_diagnosis": "Gestational Diabetes", "doctor_specialty": "Obstetrics and Gynecology", "severity": 5},
    {"symptoms": ["high blood pressure", "headache", "swelling", "vision changes"],
     "country": "India", "true_diagnosis": "Pre-eclampsia", "doctor_specialty": "Obstetrics and Gynecology", "severity": 8},

    # ── Mental Health (5) ─────────────────────────────────────────────────
    {"symptoms": ["depression", "insomnia", "fatigue", "loss of appetite", "difficulty concentrating"],
     "country": "India", "true_diagnosis": "Major Depressive Disorder", "doctor_specialty": "Psychiatry", "severity": 7},
    {"symptoms": ["depression", "fatigue", "insomnia", "weight loss"],
     "country": "Philippines", "true_diagnosis": "Major Depressive Disorder", "doctor_specialty": "Psychiatry", "severity": 6},
    {"symptoms": ["anxiety", "palpitations", "insomnia", "panic attacks"],
     "country": "Kenya", "true_diagnosis": "Generalized Anxiety Disorder", "doctor_specialty": "Psychiatry", "severity": 6},
    {"symptoms": ["anxiety", "insomnia", "depression", "difficulty concentrating"],
     "country": "Nigeria", "true_diagnosis": "Post-Traumatic Stress Disorder", "doctor_specialty": "Psychiatry", "severity": 7},
    {"symptoms": ["anxiety", "insomnia", "tremor", "palpitations", "panic attacks"],
     "country": "India", "true_diagnosis": "Generalized Anxiety Disorder", "doctor_specialty": "Psychiatry", "severity": 5},

    # ── Renal / Urological (5) ────────────────────────────────────────────
    {"symptoms": ["flank pain", "blood in urine", "nausea", "vomiting", "painful urination"],
     "country": "India", "true_diagnosis": "Kidney Stones", "doctor_specialty": "Urology", "severity": 8},
    {"symptoms": ["painful urination", "frequent urination", "fever", "abdominal pain"],
     "country": "Nigeria", "true_diagnosis": "Urinary Tract Infection", "doctor_specialty": "General Practice", "severity": 4},
    {"symptoms": ["painful urination", "frequent urination", "blood in urine"],
     "country": "Philippines", "true_diagnosis": "Urinary Tract Infection", "doctor_specialty": "General Practice", "severity": 4},
    {"symptoms": ["fatigue", "swelling", "nausea", "frequent urination"],
     "country": "Kenya", "true_diagnosis": "Chronic Kidney Disease", "doctor_specialty": "Nephrology", "severity": 7},
    {"symptoms": ["flank pain", "blood in urine", "nausea", "painful urination"],
     "country": "Nigeria", "true_diagnosis": "Kidney Stones", "doctor_specialty": "Urology", "severity": 7},

    # ── Other: Dermatological, Hematological, Neurological (5) ────────────
    {"symptoms": ["itching", "rash", "dry skin"],
     "country": "Philippines", "true_diagnosis": "Eczema", "doctor_specialty": "Dermatology", "severity": 3},
    {"symptoms": ["bone pain", "joint pain", "fatigue"],
     "country": "Nigeria", "true_diagnosis": "Sickle Cell Disease", "doctor_specialty": "Hematology", "severity": 8},
    {"symptoms": ["seizure", "confusion", "loss of consciousness"],
     "country": "Kenya", "true_diagnosis": "Epilepsy", "doctor_specialty": "Neurology", "severity": 8},
    {"symptoms": ["fatigue", "dizziness", "weakness", "shortness of breath"],
     "country": "India", "true_diagnosis": "Anemia", "doctor_specialty": "Hematology", "severity": 5},
    {"symptoms": ["rash", "itching", "skin lesion"],
     "country": "Nigeria", "true_diagnosis": "Fungal Skin Infection", "doctor_specialty": "Dermatology", "severity": 3},
]

CASE_CATEGORIES = {
    "Tropical Infectious": range(0, 15),
    "Cardiovascular": range(15, 25),
    "Respiratory": range(25, 33),
    "Gastrointestinal": range(33, 40),
    "Maternal": range(40, 45),
    "Mental Health": range(45, 50),
    "Renal / Urological": range(50, 55),
    "Other": range(55, 60),
}


# ── Snapshot Helpers ──────────────────────────────────────────────────────────

def _snapshot_indicates_edges(graph: MedicalKnowledgeGraph) -> dict[str, float]:
    """Snapshot conductivity of all INDICATES (symptom→condition) edges."""
    snap = {}
    for (src_id, tgt_id), edge in graph.edges.items():
        if edge.edge_type == EdgeType.INDICATES:
            src = graph.get_node(src_id)
            tgt = graph.get_node(tgt_id)
            if src and tgt:
                snap[f"{src.name}\u2192{tgt.name}"] = edge.conductivity
    return snap


def _snapshot_all_edges(graph: MedicalKnowledgeGraph) -> dict[tuple[str, str], float]:
    """Snapshot conductivity of every edge, keyed by (source_id, target_id)."""
    return {key: edge.conductivity for key, edge in graph.edges.items()}


# ── Main Simulation ──────────────────────────────────────────────────────────

def run_simulation():
    """Run the full 60-case simulation and return all collected metrics."""
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    print("=" * 72)
    print("  PHYSARUM KNOWLEDGE GRAPH SIMULATION")
    print("  60 synthetic patient cases across 4 countries")
    print("=" * 72)

    # ── Build graph ──────────────────────────────────────────────────────
    print("\n[1/4] Building knowledge graph from seed data...")
    graph = build_medical_knowledge_graph()
    stats_before = graph.stats()
    before_conductivities = _snapshot_all_edges(graph)
    initial_edge_count = len(graph.edges)
    print(f"       Nodes: {stats_before['total_nodes']}  |  Edges: {stats_before['total_edges']}")

    # ── Prepare tracking structures ──────────────────────────────────────
    backprop = GraphBackpropagator(graph)
    conductivity_snapshots: list[dict[str, float]] = []
    case_results: list[dict] = []
    cumulative_sprouted: list[int] = []
    total_sprouted = 0

    print(f"\n[2/4] Running {len(SYNTHETIC_CASES)} cases through navigator \u2192 backpropagator...\n")
    t0 = time.time()

    for idx, case in enumerate(SYNTHETIC_CASES):
        case_id = f"SIM-{idx + 1:03d}"

        # Navigate
        nav = ConversationNavigator(graph, case_id=case_id)
        context = nav.process_symptoms(case["symptoms"])
        activated = context["activated_conditions"]

        # Evaluate prediction accuracy
        pred_names = [c["condition"].lower() for c in activated]
        true_lower = case["true_diagnosis"].lower()
        top1_correct = len(pred_names) > 0 and pred_names[0] == true_lower
        top3_correct = true_lower in pred_names[:3]

        # Backpropagate
        trace = nav.get_trace()
        bp_result = backprop.backpropagate(
            trace=trace,
            doctor_diagnosis=case["true_diagnosis"],
            doctor_specialty=case["doctor_specialty"],
            outcome="resolved",
        )

        total_sprouted += bp_result["new_edges_sprouted"]
        learned_now = sum(1 for e in graph.edges.values() if e.source == "learned")
        cumulative_sprouted.append(learned_now)

        # Snapshot INDICATES edges
        conductivity_snapshots.append(_snapshot_indicates_edges(graph))

        # Record result
        result = {
            "case_id": case_id,
            "case_idx": idx,
            "country": case["country"],
            "true_diagnosis": case["true_diagnosis"],
            "severity": case["severity"],
            "doctor_specialty": case["doctor_specialty"],
            "symptoms": case["symptoms"],
            "predicted_top1": activated[0]["condition"] if activated else None,
            "predicted_top3": [c["condition"] for c in activated[:3]],
            "top1_correct": top1_correct,
            "top3_correct": top3_correct,
            "outcome_score": bp_result["outcome_score"],
            "reinforced_edges": bp_result["reinforced_edges"],
            "weakened_edges": bp_result["weakened_edges"],
            "new_edges_sprouted": bp_result["new_edges_sprouted"],
            "total_learned_edges": sum(1 for e in graph.edges.values() if e.source == "learned"),
        }
        case_results.append(result)

        status = "\u2713" if top1_correct else ("\u2248" if top3_correct else "\u2717")
        print(
            f"  [{idx + 1:2d}/60] {status}  {case_id}  "
            f"{case['country']:<12s}  {case['true_diagnosis']:<30s}  "
            f"pred={result['predicted_top1'] or 'N/A':<30s}  "
            f"score={bp_result['outcome_score']:.2f}  "
            f"+{bp_result['reinforced_edges']}/-{bp_result['weakened_edges']}/"
            f"*{bp_result['new_edges_sprouted']}"
        )

    elapsed = time.time() - t0
    stats_after = graph.stats()
    after_conductivities = _snapshot_all_edges(graph)

    # ── Summary ──────────────────────────────────────────────────────────
    top1_acc = sum(r["top1_correct"] for r in case_results) / len(case_results)
    top3_acc = sum(r["top3_correct"] for r in case_results) / len(case_results)
    learning_stats = backprop.get_learning_stats()

    print(f"\n{'=' * 72}")
    print(f"  SIMULATION COMPLETE  ({elapsed:.1f}s)")
    print(f"{'=' * 72}")
    print(f"  Top-1 Accuracy: {top1_acc:.1%}  |  Top-3 Accuracy: {top3_acc:.1%}")
    print(f"  Edges before: {stats_before['total_edges']}  |  after: {stats_after['total_edges']}  "
          f"(+{stats_after['total_edges'] - stats_before['total_edges']} learned)")
    print(f"  Avg conductivity: {stats_before['avg_conductivity']:.4f} \u2192 {stats_after['avg_conductivity']:.4f}")
    print(f"  Total reinforced: {sum(r['reinforced_edges'] for r in case_results)}")
    print(f"  Total weakened:   {sum(r['weakened_edges'] for r in case_results)}")
    print(f"  Total sprouted:   {total_sprouted}")

    return {
        "graph": graph,
        "case_results": case_results,
        "conductivity_snapshots": conductivity_snapshots,
        "cumulative_sprouted": cumulative_sprouted,
        "before_conductivities": before_conductivities,
        "after_conductivities": after_conductivities,
        "stats_before": stats_before,
        "stats_after": stats_after,
        "learning_stats": learning_stats,
        "initial_edge_count": initial_edge_count,
        "elapsed": elapsed,
    }


# ── Visualization ─────────────────────────────────────────────────────────────

def _setup_plot_style():
    plt.style.use("dark_background")
    sns.set_theme(style="darkgrid", rc={
        "axes.facecolor": "#1a1a2e",
        "figure.facecolor": "#0f0f1a",
        "grid.color": "#2a2a4a",
        "text.color": "#e0e0e0",
        "axes.labelcolor": "#e0e0e0",
        "xtick.color": "#c0c0c0",
        "ytick.color": "#c0c0c0",
    })


def plot_evolution_heatmap(results: dict, output_dir: Path):
    """Heatmap: top-20 edge conductivities across all 60 cases."""
    _setup_plot_style()
    snapshots = results["conductivity_snapshots"]

    all_labels = set()
    for snap in snapshots:
        all_labels.update(snap.keys())

    final = snapshots[-1]
    top_20 = sorted(final.items(), key=lambda x: x[1], reverse=True)[:20]
    labels = [label for label, _ in top_20]

    matrix = np.zeros((len(labels), len(snapshots)))
    for col, snap in enumerate(snapshots):
        for row, label in enumerate(labels):
            matrix[row, col] = snap.get(label, 0.0)

    fig, ax = plt.subplots(figsize=(18, 10))
    cmap = sns.color_palette("coolwarm", as_cmap=True)
    sns.heatmap(
        matrix, ax=ax, cmap=cmap, linewidths=0.3, linecolor="#2a2a4a",
        xticklabels=[str(i + 1) if (i + 1) % 5 == 0 or i == 0 else "" for i in range(len(snapshots))],
        yticklabels=labels,
        cbar_kws={"label": "Edge Conductivity (\u03c3)", "shrink": 0.8},
    )
    ax.set_xlabel("Case Number", fontsize=13, fontweight="bold")
    ax.set_ylabel("Edge (symptom \u2192 condition)", fontsize=13, fontweight="bold")
    ax.set_title("Physarum Conductivity Evolution \u2014 Top 20 Symptom\u2192Condition Edges",
                 fontsize=16, fontweight="bold", pad=15)
    ax.tick_params(axis="y", labelsize=9)
    ax.tick_params(axis="x", labelsize=9)

    fig.tight_layout()
    fig.savefig(output_dir / "evolution_heatmap.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  \u2713 evolution_heatmap.png")


def plot_accuracy_curve(results: dict, output_dir: Path):
    """Rolling and cumulative prediction accuracy over 60 cases."""
    _setup_plot_style()
    case_results = results["case_results"]
    n = len(case_results)
    window = 10

    top1 = [r["top1_correct"] for r in case_results]
    top3 = [r["top3_correct"] for r in case_results]

    cum_top1 = np.cumsum(top1) / np.arange(1, n + 1)
    cum_top3 = np.cumsum(top3) / np.arange(1, n + 1)
    roll_top1 = pd.Series(top1).rolling(window, min_periods=1).mean().values
    roll_top3 = pd.Series(top3).rolling(window, min_periods=1).mean().values

    case_nums = np.arange(1, n + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    # Left: cumulative accuracy
    ax1.plot(case_nums, cum_top1, color="#00d4ff", linewidth=2.5, label="Top-1 Cumulative")
    ax1.plot(case_nums, cum_top3, color="#ff6ec7", linewidth=2.5, label="Top-3 Cumulative")
    ax1.fill_between(case_nums, cum_top1, alpha=0.15, color="#00d4ff")
    ax1.fill_between(case_nums, cum_top3, alpha=0.10, color="#ff6ec7")
    ax1.set_xlabel("Case Number", fontsize=13, fontweight="bold")
    ax1.set_ylabel("Cumulative Accuracy", fontsize=13, fontweight="bold")
    ax1.set_title("Cumulative Prediction Accuracy", fontsize=14, fontweight="bold")
    ax1.legend(fontsize=11, loc="lower right")
    ax1.set_ylim(0, 1.05)
    ax1.axhline(y=0.5, color="#555", linestyle="--", alpha=0.5)

    # Category boundaries
    colors_cat = ["#ff9f43", "#1dd1a1", "#54a0ff", "#ff6b6b", "#feca57", "#c8d6e5", "#786fa6", "#f8a5c2"]
    for i, (cat_name, cat_range) in enumerate(CASE_CATEGORIES.items()):
        start, end = cat_range.start + 1, cat_range.stop
        ax1.axvspan(start - 0.5, end + 0.5, alpha=0.06, color=colors_cat[i % len(colors_cat)])

    # Right: rolling accuracy
    ax2.plot(case_nums, roll_top1, color="#00d4ff", linewidth=2.5, label=f"Top-1 Rolling (w={window})")
    ax2.plot(case_nums, roll_top3, color="#ff6ec7", linewidth=2.5, label=f"Top-3 Rolling (w={window})")
    ax2.fill_between(case_nums, roll_top1, alpha=0.15, color="#00d4ff")
    ax2.fill_between(case_nums, roll_top3, alpha=0.10, color="#ff6ec7")
    ax2.set_xlabel("Case Number", fontsize=13, fontweight="bold")
    ax2.set_ylabel("Rolling Accuracy", fontsize=13, fontweight="bold")
    ax2.set_title(f"Rolling Accuracy (window={window})", fontsize=14, fontweight="bold")
    ax2.legend(fontsize=11, loc="lower right")
    ax2.set_ylim(0, 1.05)
    ax2.axhline(y=0.5, color="#555", linestyle="--", alpha=0.5)

    for i, (cat_name, cat_range) in enumerate(CASE_CATEGORIES.items()):
        start, end = cat_range.start + 1, cat_range.stop
        ax2.axvspan(start - 0.5, end + 0.5, alpha=0.06, color=colors_cat[i % len(colors_cat)])

    fig.suptitle("Knowledge Graph Prediction Accuracy Over Time", fontsize=16, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(output_dir / "accuracy_curve.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  \u2713 accuracy_curve.png")


def plot_specialty_heatmap(results: dict, output_dir: Path):
    """Specialty conductivity heatmap by country after simulation."""
    _setup_plot_style()
    graph = results["graph"]
    case_results = results["case_results"]
    countries = ["Nigeria", "India", "Philippines", "Kenya"]

    country_conditions: dict[str, list[str]] = defaultdict(list)
    for r in case_results:
        country_conditions[r["country"]].append(r["true_diagnosis"])

    specialties = [n.name for n in graph.get_nodes_by_type(NodeType.SPECIALTY)]
    specialties.sort()

    matrix = np.zeros((len(specialties), len(countries)))

    for col, country in enumerate(countries):
        for cond_name in set(country_conditions[country]):
            cond_node = graph.find_node(cond_name, NodeType.CONDITION)
            if not cond_node:
                continue
            for spec_node, edge in graph.get_neighbors(
                cond_node.id, edge_type=EdgeType.TREATED_BY, target_type=NodeType.SPECIALTY
            ):
                if spec_node.name in specialties:
                    row = specialties.index(spec_node.name)
                    matrix[row, col] += edge.conductivity

    mask = matrix == 0
    fig, ax = plt.subplots(figsize=(12, 14))
    sns.heatmap(
        matrix, ax=ax, mask=mask, cmap="YlOrRd", linewidths=0.5, linecolor="#2a2a4a",
        xticklabels=countries, yticklabels=specialties, annot=True, fmt=".2f",
        cbar_kws={"label": "Aggregate Conductivity (\u03a3\u03c3)", "shrink": 0.7},
    )
    ax.set_xlabel("Country", fontsize=13, fontweight="bold")
    ax.set_ylabel("Medical Specialty", fontsize=13, fontweight="bold")
    ax.set_title("Specialty Demand Profile by Country\n(Based on Condition\u2192Specialty Edge Conductivity)",
                 fontsize=15, fontweight="bold", pad=15)
    ax.tick_params(axis="y", labelsize=10)
    ax.tick_params(axis="x", labelsize=12)

    fig.tight_layout()
    fig.savefig(output_dir / "specialty_heatmap.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  \u2713 specialty_heatmap.png")


def plot_edge_sprouting(results: dict, output_dir: Path):
    """Cumulative new edges discovered via branching leaf syndrome."""
    _setup_plot_style()
    sprouted = results["cumulative_sprouted"]
    n = len(sprouted)
    case_nums = np.arange(1, n + 1)

    per_case = [sprouted[0]] + [max(0, sprouted[i] - sprouted[i - 1]) for i in range(1, n)]
    peak = max(sprouted) if max(sprouted) > 0 else 1

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={"height_ratios": [2, 1]})

    # Top: cumulative line
    ax1.fill_between(case_nums, sprouted, alpha=0.25, color="#00d4ff")
    ax1.plot(case_nums, sprouted, color="#00d4ff", linewidth=2.5, marker="o", markersize=4)
    ax1.set_ylabel("Cumulative Learned Edges", fontsize=13, fontweight="bold")
    ax1.set_title("Branching Leaf Syndrome \u2014 New Edge Discovery Over Time",
                  fontsize=15, fontweight="bold", pad=10)

    for cat_name, cat_range in CASE_CATEGORIES.items():
        mid = (cat_range.start + cat_range.stop) / 2 + 0.5
        ax1.axvline(x=cat_range.stop + 0.5, color="#444", linestyle=":", alpha=0.5)
        ax1.text(mid, peak * 0.95, cat_name, ha="center", va="top",
                 fontsize=7, color="#aaa", rotation=45)

    # Bottom: per-case bar chart
    colors = ["#ff6b6b" if s > 0 else "#333" for s in per_case]
    ax2.bar(case_nums, per_case, color=colors, width=0.8, alpha=0.85)
    ax2.set_xlabel("Case Number", fontsize=13, fontweight="bold")
    ax2.set_ylabel("Edges Sprouted", fontsize=13, fontweight="bold")
    ax2.set_title("Per-Case Edge Sprouting Events", fontsize=13, fontweight="bold")

    fig.tight_layout()
    fig.savefig(output_dir / "edge_sprouting.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  \u2713 edge_sprouting.png")


def plot_network_snapshot(results: dict, output_dir: Path):
    """Before/after network visualization highlighting edge changes."""
    _setup_plot_style()
    graph = results["graph"]
    before = results["before_conductivities"]
    after = results["after_conductivities"]

    if not HAS_NETWORKX:
        print("  \u26a0 Skipping network_snapshot.png (networkx not installed)")
        return

    symptom_nodes = sorted(
        graph.get_nodes_by_type(NodeType.SYMPTOM),
        key=lambda n: n.visit_count, reverse=True,
    )[:18]
    condition_nodes = sorted(
        graph.get_nodes_by_type(NodeType.CONDITION),
        key=lambda n: n.visit_count, reverse=True,
    )[:14]
    specialty_nodes = sorted(
        graph.get_nodes_by_type(NodeType.SPECIALTY),
        key=lambda n: n.visit_count, reverse=True,
    )[:8]

    selected_ids = {n.id for n in symptom_nodes + condition_nodes + specialty_nodes}

    G_before = nx.DiGraph()
    G_after = nx.DiGraph()
    node_colors_map = {}
    node_labels = {}

    for n in symptom_nodes:
        G_before.add_node(n.id)
        G_after.add_node(n.id)
        node_colors_map[n.id] = "#00d4ff"
        node_labels[n.id] = n.name[:15]
    for n in condition_nodes:
        G_before.add_node(n.id)
        G_after.add_node(n.id)
        node_colors_map[n.id] = "#ff9f43"
        node_labels[n.id] = n.name[:18]
    for n in specialty_nodes:
        G_before.add_node(n.id)
        G_after.add_node(n.id)
        node_colors_map[n.id] = "#feca57"
        node_labels[n.id] = n.name[:15]

    edge_changes = {}
    for key in set(list(before.keys()) + list(after.keys())):
        src_id, tgt_id = key
        if src_id not in selected_ids or tgt_id not in selected_ids:
            continue

        b_val = before.get(key, 0.0)
        a_val = after.get(key, 0.0)

        if b_val > 0:
            G_before.add_edge(src_id, tgt_id, weight=b_val)
        if a_val > 0:
            G_after.add_edge(src_id, tgt_id, weight=a_val)

        if key not in before and key in after:
            edge_changes[key] = "sprouted"
        elif a_val > b_val * 1.1:
            edge_changes[key] = "strengthened"
        elif a_val < b_val * 0.9:
            edge_changes[key] = "weakened"
        else:
            edge_changes[key] = "unchanged"

    pos = nx.spring_layout(G_after, seed=RANDOM_SEED, k=2.5, iterations=80)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 12))

    def _draw_graph(G, ax, title, show_changes=False):
        node_list = list(G.nodes())
        nc = [node_colors_map.get(n, "#888") for n in node_list]
        ns = [120 + graph.get_node(n).visit_count * 8 for n in node_list]

        nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=node_list,
                               node_color=nc, node_size=ns, alpha=0.9, edgecolors="#333")

        if show_changes:
            for edge in G.edges():
                key = (edge[0], edge[1])
                change = edge_changes.get(key, "unchanged")
                color_map = {
                    "strengthened": "#2ecc71", "weakened": "#e74c3c",
                    "sprouted": "#3498db", "unchanged": "#555",
                }
                w = after.get(key, 0.1)
                ax.annotate("", xy=pos[edge[1]], xytext=pos[edge[0]],
                            arrowprops=dict(arrowstyle="-|>", color=color_map[change],
                                          lw=min(3.0, 0.3 + w * 1.5), alpha=0.7))
        else:
            for edge in G.edges():
                key = (edge[0], edge[1])
                w = before.get(key, 0.1)
                ax.annotate("", xy=pos[edge[1]], xytext=pos[edge[0]],
                            arrowprops=dict(arrowstyle="-|>", color="#555",
                                          lw=min(2.5, 0.3 + w * 1.2), alpha=0.5))

        nx.draw_networkx_labels(G, pos, labels={n: node_labels.get(n, "") for n in node_list},
                                ax=ax, font_size=6, font_color="#e0e0e0")
        ax.set_title(title, fontsize=14, fontweight="bold", pad=10)
        ax.set_axis_off()

    _draw_graph(G_before, ax1, "BEFORE Simulation (Seed Graph)")
    _draw_graph(G_after, ax2, "AFTER 60 Cases (Evolved Graph)", show_changes=True)

    legend_elements = [
        mpatches.Patch(color="#00d4ff", label="Symptom"),
        mpatches.Patch(color="#ff9f43", label="Condition"),
        mpatches.Patch(color="#feca57", label="Specialty"),
        plt.Line2D([0], [0], color="#2ecc71", lw=2, label="Strengthened"),
        plt.Line2D([0], [0], color="#e74c3c", lw=2, label="Weakened"),
        plt.Line2D([0], [0], color="#3498db", lw=2, label="Sprouted (new)"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=6,
               fontsize=11, framealpha=0.3, edgecolor="#555")

    fig.suptitle("Knowledge Graph Network \u2014 Before vs After Physarum Evolution",
                 fontsize=17, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(output_dir / "network_snapshot.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  \u2713 network_snapshot.png")


def generate_all_plots(results: dict, output_dir: Path):
    """Generate all 5 visualization PNGs."""
    print(f"\n[3/4] Generating visualizations in {output_dir}/\n")
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_evolution_heatmap(results, output_dir)
    plot_accuracy_curve(results, output_dir)
    plot_specialty_heatmap(results, output_dir)
    plot_edge_sprouting(results, output_dir)
    plot_network_snapshot(results, output_dir)


def save_results_json(results: dict, output_dir: Path):
    """Save comprehensive metrics JSON."""
    print(f"\n[4/4] Saving simulation_results.json...")
    case_results = results["case_results"]
    n = len(case_results)

    by_category = {}
    for cat_name, cat_range in CASE_CATEGORIES.items():
        subset = [case_results[i] for i in cat_range]
        by_category[cat_name] = {
            "cases": len(subset),
            "top1_accuracy": round(sum(r["top1_correct"] for r in subset) / len(subset), 3),
            "top3_accuracy": round(sum(r["top3_correct"] for r in subset) / len(subset), 3),
            "avg_outcome_score": round(sum(r["outcome_score"] for r in subset) / len(subset), 3),
        }

    by_country = {}
    for country in ["Nigeria", "India", "Philippines", "Kenya"]:
        subset = [r for r in case_results if r["country"] == country]
        if subset:
            by_country[country] = {
                "cases": len(subset),
                "top1_accuracy": round(sum(r["top1_correct"] for r in subset) / len(subset), 3),
                "top3_accuracy": round(sum(r["top3_correct"] for r in subset) / len(subset), 3),
                "avg_outcome_score": round(sum(r["outcome_score"] for r in subset) / len(subset), 3),
            }

    hottest = results["graph"].get_hottest_paths(top_n=20)

    output = {
        "simulation_metadata": {
            "total_cases": n,
            "random_seed": RANDOM_SEED,
            "elapsed_seconds": round(results["elapsed"], 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "countries": ["Nigeria", "India", "Philippines", "Kenya"],
        },
        "graph_before": {
            k: v for k, v in results["stats_before"].items()
            if not isinstance(v, float) or not (v != v)
        },
        "graph_after": {
            k: v for k, v in results["stats_after"].items()
            if not isinstance(v, float) or not (v != v)
        },
        "accuracy": {
            "top1_overall": round(sum(r["top1_correct"] for r in case_results) / n, 3),
            "top3_overall": round(sum(r["top3_correct"] for r in case_results) / n, 3),
            "by_category": by_category,
            "by_country": by_country,
        },
        "learning": {
            "total_reinforced": sum(r["reinforced_edges"] for r in case_results),
            "total_weakened": sum(r["weakened_edges"] for r in case_results),
            "total_sprouted": results["cumulative_sprouted"][-1] if results["cumulative_sprouted"] else 0,
            "avg_outcome_score": round(sum(r["outcome_score"] for r in case_results) / n, 3),
            "backpropagator_stats": results["learning_stats"],
        },
        "case_results": [
            {k: v for k, v in r.items() if k != "graph"}
            for r in case_results
        ],
        "top_20_hottest_paths": hottest,
    }

    out_path = output_dir / "simulation_results.json"
    out_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"  \u2713 simulation_results.json ({out_path.stat().st_size / 1024:.1f} KB)")


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    results = run_simulation()
    generate_all_plots(results, VIZ_DIR)
    save_results_json(results, VIZ_DIR)
    print(f"\n{'=' * 72}")
    print(f"  All outputs saved to {VIZ_DIR}/")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
