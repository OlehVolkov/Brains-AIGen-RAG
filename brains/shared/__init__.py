from brains.shared.formatting import format_index_summary
from brains.shared.health import check_index_health, resolve_active_index_paths
from brains.shared.langchain import embed_texts, embed_texts_with_model_fallback, split_documents
from brains.shared.ollama import (
    ResolvedOllamaModel,
    iter_pull_ollama_model_statuses,
    list_installed_ollama_models,
    resolve_installed_ollama_model,
)
from brains.shared.preprocessing import clean_markdown_text, clean_pdf_documents
from brains.shared.retrieval import (
    apply_result_thresholds,
    apply_ollama_rerank,
    embed_query_text,
    make_cross_encoder_reranker,
    open_table,
    resolve_fetch_limit,
    resolve_query_mode,
    run_fts_search,
    run_hybrid_search,
    run_vector_search,
    validate_search_config,
)
from brains.shared.runtime import configure_logging, get_console, logger, print_json, print_text
from brains.shared.text import _with_warnings, chunk_id, chunked, normalize_text, snippet

__all__ = [
    "_with_warnings",
    "apply_result_thresholds",
    "apply_ollama_rerank",
    "chunk_id",
    "chunked",
    "check_index_health",
    "clean_markdown_text",
    "clean_pdf_documents",
    "configure_logging",
    "get_console",
    "embed_query_text",
    "embed_texts",
    "embed_texts_with_model_fallback",
    "format_index_summary",
    "logger",
    "iter_pull_ollama_model_statuses",
    "list_installed_ollama_models",
    "make_cross_encoder_reranker",
    "normalize_text",
    "open_table",
    "print_json",
    "print_text",
    "resolve_fetch_limit",
    "resolve_active_index_paths",
    "resolve_query_mode",
    "resolve_installed_ollama_model",
    "ResolvedOllamaModel",
    "run_fts_search",
    "run_hybrid_search",
    "run_vector_search",
    "snippet",
    "split_documents",
    "validate_search_config",
]
