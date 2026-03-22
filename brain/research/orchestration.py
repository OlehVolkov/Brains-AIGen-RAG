from __future__ import annotations

import re
from datetime import UTC, datetime

from brain.shared import logger, snippet
from brain.sources.pdf.search import search_pdf_corpus
from brain.research.memory import MemoryStore
from brain.research.models import ResearchRunConfig
from brain.sources.vault.search import search_vault_knowledge


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
    pdf_results: list[dict],
    memory_results: list[dict],
) -> str:
    lines = [f"Query: {query}", ""]
    for label, rows in (
        ("Vault context", vault_results),
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
    return "\n".join(lines).strip()


def _heuristic_role_output(role: str, query: str, context_text: str) -> str:
    preview = snippet(context_text, 700)
    if role == "researcher":
        return (
            f"Research focus for '{query}':\n"
            "- summarize the strongest retrieved evidence\n"
            "- identify gaps, assumptions, and adjacent concepts\n"
            "- keep attention on repository-grounded facts\n\n"
            f"Context preview:\n{preview}"
        )
    if role == "coder":
        return (
            f"Implementation view for '{query}':\n"
            "- translate findings into concrete scripts, note updates, or indexing steps\n"
            "- prefer small modular changes in `/.brain`\n"
            "- keep outputs reproducible and index-safe\n\n"
            f"Context preview:\n{preview}"
        )
    return (
        f"Review view for '{query}':\n"
        "- challenge weak assumptions and unsupported jumps\n"
        "- flag missing sources, missing mirrors, or indexing gaps\n"
        "- suggest the next verification step\n\n"
        f"Context preview:\n{preview}"
    )


def _call_ollama(prompt: str, *, model: str, base_url: str) -> str:
    from langchain_ollama import ChatOllama

    llm = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
        validate_model_on_init=False,
    )
    response = llm.invoke(prompt)
    return response.content if isinstance(response.content, str) else str(response.content)


def _run_role(
    role: str,
    query: str,
    context_text: str,
    *,
    model: str,
    base_url: str,
) -> tuple[str, str | None]:
    prompt = (
        f"You are the {role} agent in a local research loop.\n"
        "Work only with the provided repository-grounded context.\n"
        "Be concise, structured, and avoid invented facts.\n\n"
        f"{context_text}\n\n"
        f"Task: produce the {role} contribution for the query '{query}'."
    )
    try:
        return _call_ollama(prompt, model=model, base_url=base_url), None
    except Exception as exc:
        return _heuristic_role_output(role, query, context_text), (
            f"{role} agent fell back to heuristic mode ({type(exc).__name__}: {exc})."
        )


def _run_reflection(
    query: str,
    context_text: str,
    reviewer_output: str,
    *,
    model: str,
    base_url: str,
) -> tuple[str, str | None]:
    prompt = (
        "You are the self-reflection step in a local research loop.\n"
        "Read the context and the reviewer critique.\n"
        "Return a short revision note with missing checks, sharper framing, and the next best step.\n\n"
        f"{context_text}\n\n"
        f"Reviewer critique:\n{reviewer_output}"
    )
    try:
        return _call_ollama(prompt, model=model, base_url=base_url), None
    except Exception as exc:
        return (
            "Reflection note:\n"
            "- tighten conclusions to repository-backed claims\n"
            "- verify the strongest missing source or mirror note\n"
            "- prefer one next action over a wide todo list",
            f"reflection loop fell back to heuristic mode ({type(exc).__name__}: {exc}).",
        )


def _run_final(
    query: str,
    context_text: str,
    roles: dict[str, dict[str, str]],
    reflections: list[str],
    *,
    model: str,
    base_url: str,
) -> tuple[str, str | None]:
    prompt = (
        "You are the synthesis stage of a local research agent.\n"
        "Combine researcher, coder, reviewer, and reflection outputs into one final answer.\n"
        "Keep it repository-grounded and action-oriented.\n\n"
        f"{context_text}\n\n"
        f"Researcher:\n{roles['researcher']['content']}\n\n"
        f"Coder:\n{roles['coder']['content']}\n\n"
        f"Reviewer:\n{roles['reviewer']['content']}\n\n"
        "Reflections:\n"
        + "\n\n".join(reflections)
    )
    try:
        return _call_ollama(prompt, model=model, base_url=base_url), None
    except Exception as exc:
        return (
            "Final synthesis:\n"
            f"- query: {query}\n"
            "- use the researcher output as the working summary\n"
            "- use the coder output as the implementation plan\n"
            "- use the reviewer and reflection outputs as the verification checklist",
            f"final synthesis fell back to heuristic mode ({type(exc).__name__}: {exc}).",
        )


def run_think_loop(config: ResearchRunConfig) -> dict:
    logger.info("Starting research loop for query: {}", config.query)
    warnings: list[str] = []
    session_id = config.session_id or _default_session_id(config.query)
    store = MemoryStore(config.paths)
    memory_results = store.recall(config.query, limit=config.memory_k)

    vault_results: list[dict] = []
    try:
        vault_payload = search_vault_knowledge(
            query=config.query,
            mode="hybrid",
            reranker="none",
            k=config.vault_k,
            fetch_k=max(config.vault_k, 10),
            snippet_chars=240,
        )
        vault_results = vault_payload.get("results", [])
        warnings.extend(vault_payload.get("warnings", []))
    except Exception as exc:
        logger.warning("Vault retrieval unavailable inside research loop.")
        warnings.append(f"vault retrieval unavailable ({type(exc).__name__}: {exc}).")

    pdf_results: list[dict] = []
    try:
        pdf_payload = search_pdf_corpus(
            query=config.query,
            mode="hybrid",
            reranker="none",
            k=config.pdf_k,
            fetch_k=max(config.pdf_k, 10),
            snippet_chars=240,
        )
        pdf_results = pdf_payload.get("results", [])
        warnings.extend(pdf_payload.get("warnings", []))
    except Exception as exc:
        logger.warning("PDF retrieval unavailable inside research loop.")
        warnings.append(f"pdf retrieval unavailable ({type(exc).__name__}: {exc}).")

    context_text = _context_to_text(
        config.query,
        vault_results=vault_results,
        pdf_results=pdf_results,
        memory_results=memory_results,
    )

    roles: dict[str, dict[str, str]] = {}
    for role in ("researcher", "coder", "reviewer"):
        logger.debug("Running role step: {}", role)
        content, warning = _run_role(
            role,
            config.query,
            context_text,
            model=config.model,
            base_url=config.ollama_base_url,
        )
        roles[role] = {"content": content}
        if warning:
            warnings.append(warning)

    reflections: list[str] = []
    for _ in range(config.reflection_rounds):
        logger.debug("Running reflection step.")
        reflection, warning = _run_reflection(
            config.query,
            context_text,
            roles["reviewer"]["content"],
            model=config.model,
            base_url=config.ollama_base_url,
        )
        reflections.append(reflection)
        if warning:
            warnings.append(warning)

    final_answer, warning = _run_final(
        config.query,
        context_text,
        roles,
        reflections,
        model=config.model,
        base_url=config.ollama_base_url,
    )
    if warning:
        warnings.append(warning)

    payload = {
        "session_id": session_id,
        "created_at": datetime.now(UTC).isoformat(),
        "query": config.query,
        "model": config.model,
        "warnings": warnings,
        "vault_results": vault_results,
        "pdf_results": pdf_results,
        "memory_results": memory_results,
        "roles": roles,
        "reflections": reflections,
        "final_answer": final_answer,
    }

    if config.save_memory:
        summary = roles["researcher"]["content"]
        store.append(
            {
                "session_id": session_id,
                "created_at": payload["created_at"],
                "query": config.query,
                "summary": summary,
                "final_answer": final_answer,
            }
        )
        store.save_session(session_id, payload)
        logger.info("Saved research session artifacts for session {}", session_id)

    logger.info("Finished research loop for query: {}", config.query)
    return payload
