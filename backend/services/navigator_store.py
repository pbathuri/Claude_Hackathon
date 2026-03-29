"""Process-local cache + Redis persistence for ConversationNavigator instances."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from knowledge_graph.navigator import ConversationNavigator
from services import session_store

if TYPE_CHECKING:
    from knowledge_graph.graph_engine import MedicalKnowledgeGraph

_lock = threading.RLock()
_local: dict[str, ConversationNavigator] = {}


def get_navigator(case_id: str, graph: MedicalKnowledgeGraph) -> ConversationNavigator:
    with _lock:
        if case_id in _local:
            return _local[case_id]
        snap = session_store.case_nav_get(case_id)
        if snap:
            nav = ConversationNavigator.from_snapshot(graph, snap)
            _local[case_id] = nav
            return nav
        nav = ConversationNavigator(graph, case_id=case_id)
        _local[case_id] = nav
        return nav


def persist_navigator(case_id: str, nav: ConversationNavigator) -> None:
    with _lock:
        _local[case_id] = nav
        session_store.case_nav_set(case_id, nav.to_snapshot())


def clear_navigator(case_id: str) -> None:
    with _lock:
        _local.pop(case_id, None)
        session_store.case_nav_delete(case_id)
