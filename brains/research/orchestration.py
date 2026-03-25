from __future__ import annotations

import re
from datetime import UTC, datetime

from brains.research.memory import MemoryStore
from brains.research.models import ResearchRunConfig
from brains.shared import logger, snippet
from brains.sources.graph.search import explain_graph_path_knowledge, search_graph_knowledge
from brains.sources.pdf.search import search_pdf_corpus
from brains.sources.vault.search import search_vault_knowledge


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "session"


def _default_session_id(query: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{_slugify(query)}"


def _context_to_text(
    query: str,
    *,
    vault_results: list[dict],
    graph_results: list[dict],
    graph_paths: list[dict],
    pdf_results: list[dict],
    memory_results: list[dict],
) -> str:
    lines = [f"Query: {query}", ""]
    for label, rows in (
        ("Vault context", vault_results),
        ("Graph context", graph_results),
        ("PDF context", pdf_results),
        ("Memory context", memory_results),
    ):
        lines.append(f"{label}:")
        if not rows:
            lines.append("- none")
            lines.append("")
            continue
        for row in rows:
            source_path = row.get("source_path", row.get("session_id", "memory"))
            rendered = row.get("snippet") or row.get("summary") or ""
            lines.append(f"- {source_path}: {rendered}")
        lines.append("")
    lines.append("Graph paths:")
    if not graph_paths:
        lines.append("- none")
    else:
        for payload in graph_paths:
            lines.append(
                "- "
                f"{payload.get('resolved_source_path')} -> {payload.get('resolved_target_path')} "
                f"(hops={payload.get('hops')})"
            )
            for step in payload.get("summary", [])[:3]:
                lines.append(f"  {step}")
    lines.append("")
    return "\n".join(lines).strip()


def _distinct_source_paths(rows: list[dict], *, limit: int) -> list[str]:
    paths: list[str] = []
    for row in rows:
        source_path = str(row.get("source_path", ""))
        if not source_path or source_path in paths:
            continue
        paths.append(source_path)
        if len(paths) >= limit:
            break
    return paths


def _collect_graph_paths(vault_results: list[dict], *, limit: int = 2) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    seed_paths = _distinct_source_paths(vault_results, limit=4)
    if len(seed_paths) < 2:
        return [], warnings

    explanations: list[dict] = []
    for index, left in enumerate(seed_paths):
        for right in seed_paths[index + 1 :]:
            try:
                payload = explain_graph_path_knowledge(
                    source=left,
                    target=right,
                    max_hops=2,
                )
            except FileNotFoundError:
                warnings.append("Graph artifacts not found; skipping graph path context.")
                return explanations, warnings
            except Exception as exc:
                warnings.append(f"graph path context unavailable ({type(exc).__name__}: {exc}).")
                return explanations, warnings

            if payload.get("path_found"):
                explanations.append(payload)
            if len(explanations) >= limit:
                return explanations, warnings
    return explanations, warnings


def _make_bundle_summary(
    query: str,
    *,
    vault_results: list[dict],
    graph_results: list[dict],
    graph_paths: list[dict],
    pdf_results: list[dict],
    memory_results: list[dict],
) -> str:
    return (
        f"Prepared external-agent retrieval bundle for '{query}' "
        f"(vault={len(vault_results)}, graph={len(graph_results)}, "
        f"graph_paths={len(graph_paths)}, pdf={len(pdf_results)}, memory={len(memory_results)})."
    )


def _make_agent_handoff(query: str, context_text: str) -> str:
    preview = snippet(context_text, 2400)
    return (
        "External agent handoff:\n"
        f"- query: {query}\n"
        "- use the retrieved vault, graph, PDF, and memory context below\n"
        "- perform the final synthesis outside `/.brains`\n"
        "- keep conclusions grounded in the retrieved repository evidence\n\n"
        f"{preview}"
    )


def run_think_loop(config: ResearchRunConfig) -> dict:
    logger.info("Starting research bundle preparation for query: {}", config.query)
    warnings: list[str] = []
    session_id = config.session_id or _default_session_id(config.query)
    store = MemoryStore(config.paths)
    memory_results = store.recall(config.query, limit=config.memory_k)

    vault_results: list[dict] = []
    try:
        vault_payload = search_vault_knowledge(
            query=config.query,
            mode="auto",
            reranker="none",
            k=config.vault_k,
            fetch_k=max(config.vault_k, 10),
            snippet_chars=240,
        )
        vault_results = vault_payload.get("results", [])
        warnings.extend(vault_payload.get("warnings", []))
    except Exception as exc:
        logger.warning("Vault retrieval unavailable inside research bundle builder.")
        warnings.append(f"vault retrieval unavailable ({type(exc).__name__}: {exc}).")

    graph_results: list[dict] = []
    try:
        graph_payload = search_graph_knowledge(
            query=config.query,
            k=max(1, min(config.vault_k, 4)),
            max_hops=1,
        )
        graph_results = graph_payload.get("results", [])
        warnings.extend(graph_payload.get("warnings", []))
    except Exception as exc:
        logger.warning("Graph retrieval unavailable inside research bundle builder.")
        warnings.append(f"graph retrieval unavailable ({type(exc).__name__}: {exc}).")

    pdf_results: list[dict] = []
    try:
        pdf_payload = search_pdf_corpus(
            query=config.query,
            mode="auto",
            reranker="none",
            k=config.pdf_k,
            fetch_k=max(config.pdf_k, 10),
            snippet_chars=240,
        )
        pdf_results = pdf_payload.get("results", [])
        warnings.extend(pdf_payload.get("warnings", []))
    except Exception as exc:
        logger.warning("PDF retrieval unavailable inside research bundle builder.")
        warnings.append(f"pdf retrieval unavailable ({type(exc).__name__}: {exc}).")

    graph_paths, graph_path_warnings = _collect_graph_paths(vault_results)
    warnings.extend(graph_path_warnings)

    context_text = _context_to_text(
        config.query,
        vault_results=vault_results,
        graph_results=graph_results,
        graph_paths=graph_paths,
        pdf_results=pdf_results,
        memory_results=memory_results,
    )
    summary = _make_bundle_summary(
        config.query,
        vault_results=vault_results,
        graph_results=graph_results,
        graph_paths=graph_paths,
        pdf_results=pdf_results,
        memory_results=memory_results,
    )
    agent_handoff = _make_agent_handoff(config.query, context_text)

    payload = {
        "session_id": session_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": config.query,
        "mode": "retrieval_bundle",
        "warnings": warnings,
        "summary": summary,
        "agent_handoff": agent_handoff,
        "vault_results": vault_results,
        "graph_results": graph_results,
        "graph_paths": graph_paths,
        "pdf_results": pdf_results,
        "memory_results": memory_results,
        "final_answer": summary,
    }

    if config.save_memory:
        store.append(
            {
                "session_id": session_id,
                "created_at": payload["created_at"],
                "query": config.query,
                "summary": summary,
                "final_answer": summary,
            }
        )
        store.save_session(session_id, payload)
        logger.info("Saved research bundle artifacts for session {}", session_id)

    logger.info("Finished research bundle preparation for query: {}", config.query)
    return payload
