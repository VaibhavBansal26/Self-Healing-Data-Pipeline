from __future__ import annotations

import json
from typing import Dict, Any, List
from uuid import uuid4
from src.config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION


def _vector_store():
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return Chroma(collection_name=CHROMA_COLLECTION, embedding_function=embeddings, persist_directory=CHROMA_PERSIST_DIR)


def incident_to_text(payload: Dict[str, Any], error_message: str) -> str:
    return json.dumps({"payload": payload, "error_message": error_message}, sort_keys=True)


def search_similar_incidents(payload: Dict[str, Any], error_message: str, k: int = 3) -> List[Dict[str, Any]]:
    try:
        store = _vector_store()
        query = incident_to_text(payload, error_message)
        docs = store.similarity_search_with_score(query, k=k)
        results = []
        for doc, score in docs:
            metadata = dict(doc.metadata)
            metadata["score"] = float(score)
            try:
                metadata["original_payload"] = json.loads(metadata.get("original_payload", "{}"))
                healed = metadata.get("healed_payload")
                metadata["healed_payload"] = json.loads(healed) if healed else None
            except Exception:
                pass
            results.append(metadata)
        return results
    except Exception as exc:
        print(f"Vector memory search skipped: {exc}")
        return []


def store_incident_memory(
    incident_id: int,
    original_payload: Dict[str, Any],
    error_message: str,
    action: str,
    status: str,
    healed_payload: Dict[str, Any] | None = None,
):
    try:
        from langchain_core.documents import Document

        store = _vector_store()
        text = incident_to_text(original_payload, error_message)
        metadata = {
            "incident_id": str(incident_id),
            "action": action,
            "status": status,
            "original_payload": json.dumps(original_payload, sort_keys=True),
            "healed_payload": json.dumps(healed_payload, sort_keys=True) if healed_payload else "",
        }
        store.add_documents([Document(page_content=text, metadata=metadata)], ids=[str(uuid4())])
    except Exception as exc:
        print(f"Vector memory write skipped: {exc}")
