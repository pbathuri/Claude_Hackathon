"""
Bio-Inspired Self-Evolving Medical Knowledge Graph

Inspired by:
- Physarum polycephalum (slime mold): Edge conductivity strengthens with flow,
  decays without use — the graph learns optimal symptom→condition→specialty paths
- E. coli chemotaxis: Biased random exploration toward high-confidence regions
- Branching leaf syndrome: New connections emerge from correlation discovery,
  creating dendritic expansion of medical knowledge

The graph serves three roles:
1. NAVIGATION: Guides the chatbot to ask the most relevant follow-up questions
2. BACKPROPAGATION: After conversation + doctor resolution, reinforces/weakens paths
3. DOCTOR MATCHING: Most-traversed paths reveal which specialties are needed
"""

from .graph_engine import MedicalKnowledgeGraph
from .navigator import ConversationNavigator
from .backpropagator import GraphBackpropagator
from .doctor_matcher import GraphDoctorMatcher

__all__ = [
    "MedicalKnowledgeGraph",
    "ConversationNavigator",
    "GraphBackpropagator",
    "GraphDoctorMatcher",
]
