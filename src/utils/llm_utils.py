"""
LLM Utilities for Recon Analysis Bot
Centralized helpers for creating and calling LLMs with retries.
Based on poc_risk_agent llm_utils pattern.
"""

from __future__ import annotations

import random
import re
import time
from typing import Any, Iterable, Optional
from time import perf_counter

from src.utils.config_reader import get_config_value
from src.utils.logging import logger

try:
    from openai import APIStatusError, RateLimitError
except Exception:
    APIStatusError = None
    RateLimitError = None


def _str_to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _get_retry_config() -> dict[str, Any]:
    """Load retry configuration with safe defaults."""
    return {
        "max_attempts": _str_to_int(get_config_value("llm.max_attempts", 3), 3),
        "initial_backoff_s": float(get_config_value("llm.initial_backoff_s", 5)),
        "backoff_factor": float(get_config_value("llm.backoff_factor", 2.0)),
        "max_backoff_s": float(get_config_value("llm.max_backoff_s", 60)),
        "jitter_s": float(get_config_value("llm.jitter_s", 1.0)),
        "respect_retry_after": bool(get_config_value("llm.respect_retry_after", True)),
    }


def _extract_retry_after_seconds(error: Exception) -> Optional[int]:
    """Best-effort extraction of retry-after seconds from error objects/messages."""
    if APIStatusError and isinstance(error, APIStatusError):
        try:
            retry_after = error.response.headers.get("retry-after")
            if retry_after:
                return int(retry_after)
        except Exception:
            pass

    if RateLimitError and isinstance(error, RateLimitError):
        pass

    message = str(error)
    match = re.search(r"retry\s+after\s+(\d+)\s*seconds", message, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            return None

    return None


def _is_rate_limit_error(error: Exception) -> bool:
    message = str(error).lower()
    if "429" in message or "rate limit" in message or "quota" in message:
        return True
    if APIStatusError and isinstance(error, APIStatusError):
        try:
            return getattr(error, "status_code", None) == 429
        except Exception:
            return True
    if RateLimitError and isinstance(error, RateLimitError):
        return True
    return False


def _compute_backoff_seconds(
    attempt_index: int,
    initial_backoff_s: float,
    factor: float,
    max_backoff_s: float,
    jitter_s: float,
) -> float:
    base = initial_backoff_s * (factor ** max(0, attempt_index - 1))
    wait = min(base, max_backoff_s)
    if jitter_s:
        wait += random.uniform(0, jitter_s)
    return wait


def _get_encoder_for_model(model_name: str):
    """Return tiktoken encoder for a given model name with sensible fallback."""
    try:
        import tiktoken
        return tiktoken.encoding_for_model(model_name)
    except Exception:
        import tiktoken
        lowered = (model_name or "").lower()
        if lowered.startswith(("gpt-4o", "gpt-4.1", "o4")):
            return tiktoken.get_encoding("o200k_base")
        return tiktoken.get_encoding("cl100k_base")


def estimate_tokens_from_messages(
    messages: Iterable[Any], model_name: str
) -> Optional[int]:
    """Approximate token count for chat messages using tiktoken if available."""
    try:
        enc = _get_encoder_for_model(model_name)
        parts: list[str] = []
        for msg in messages:
            try:
                if hasattr(msg, "content"):
                    content = getattr(msg, "content")
                    if isinstance(content, str):
                        parts.append(content)
                    elif isinstance(content, list):
                        parts.append(" ".join(str(p) for p in content))
                    else:
                        parts.append(str(content))
                elif isinstance(msg, dict):
                    parts.append(str(msg.get("content", "")))
                else:
                    parts.append(str(msg))
            except Exception:
                continue

        text = "\n".join(parts)
        return len(enc.encode(text))
    except Exception:
        return None


def invoke_with_retry_langchain(
    llm: Any,
    messages: Iterable[Any],
    *,
    operation: str = "llm_invoke",
    max_attempts: Optional[int] = None,
) -> Any:
    """
    Invoke a LangChain chat model with retries on 429/rate-limit errors.

    Parameters:
    - llm: LangChain AzureChatOpenAI-compatible object
    - messages: result of ChatPromptTemplate.format_messages(...)
    - operation: label for logs/metrics
    - max_attempts: overrides default attempts if provided
    """
    cfg = _get_retry_config()
    attempts = max_attempts or cfg["max_attempts"]

    provider = "azure_openai"
    model_name = getattr(llm, "azure_deployment", None) or getattr(
        llm, "model", "unknown"
    )

    message_list = messages if isinstance(messages, list) else list(messages)

    # Pre-call token estimate
    try:
        approx_tokens = estimate_tokens_from_messages(message_list, model_name)
        if approx_tokens is not None:
            logger.info(
                "LLM prompt tokens (approx)",
                operation=operation,
                model=model_name,
                tokens=approx_tokens,
                message_count=len(message_list),
            )
    except Exception:
        pass

    for attempt in range(1, attempts + 1):
        start = perf_counter()
        try:
            result = llm.invoke(message_list)
            duration = perf_counter() - start
            logger.info(
                "LLM invoke successful",
                operation=operation,
                model=model_name,
                duration_seconds=duration,
            )
            return result
        except Exception as e:
            duration = perf_counter() - start
            if not _is_rate_limit_error(e) or attempt >= attempts:
                logger.warning(
                    "LLM invoke failed",
                    operation=operation,
                    attempt=attempt,
                    max_attempts=attempts,
                    error=str(e),
                )
                raise

            retry_after = (
                _extract_retry_after_seconds(e) if cfg["respect_retry_after"] else None
            )
            wait_s = (
                float(retry_after)
                if retry_after is not None
                else _compute_backoff_seconds(
                    attempt,
                    cfg["initial_backoff_s"],
                    cfg["backoff_factor"],
                    cfg["max_backoff_s"],
                    cfg["jitter_s"],
                )
            )
            logger.info(
                "LLM rate-limited; retrying",
                operation=operation,
                attempt=attempt,
                wait_seconds=wait_s,
            )
            time.sleep(wait_s)


def create_langchain_azure_chat_openai() -> Any:
    """Create a LangChain AzureChatOpenAI instance from config."""
    try:
        from langchain_openai import AzureChatOpenAI

        endpoint = get_config_value("azure.endpoint")
        api_key = get_config_value("azure.api_key")
        api_version = get_config_value("azure.api_version", "2024-02-15-preview")
        deployment = get_config_value("azure.deployment")
        temperature = float(get_config_value("azure.temperature", 0.2))
        max_tokens = int(get_config_value("azure.max_tokens", 4000))

        if not all([endpoint, api_key, api_version, deployment]):
            raise RuntimeError("Azure OpenAI configuration is incomplete")

        llm = AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            azure_deployment=deployment,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info("Initialized AzureChatOpenAI", deployment=deployment)
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize AzureChatOpenAI: {e}")
        raise


def create_ollama_llm(model_name: str = "llama2", base_url: str = "http://localhost:11434") -> Any:
    """
    Create an Ollama LLM instance for local AI.
    Uses ChatOllama for chat interface compatibility.

    Args:
        model_name: Ollama model name (llama2, llama3, mistral, etc.)
        base_url: Ollama server URL (default: http://localhost:11434)

    Returns:
        Ollama ChatModel instance
    """
    try:
        from langchain_community.chat_models import ChatOllama

        llm = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.2,
        )
        logger.info("Initialized Ollama LLM", model=model_name, base_url=base_url)
        return llm
    except ImportError:
        logger.error("langchain-community not installed. Install with: pip install langchain-community")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize Ollama LLM: {e}")
        raise

