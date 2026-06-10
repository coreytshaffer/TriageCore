import os
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from triage_core.task_packet import TaskPacket
from triage_core.backends import LocalBackend, BackendUnavailableError
import logging

logger = logging.getLogger(__name__)

# Very simple heuristic for token estimation if context_budget isn't fully reliable
def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)

@dataclass
class ContextBundle:
    task_id: str
    summary_text: str
    source_files: List[Dict[str, Any]]
    raw_tokens: int
    compressed_tokens: int
    reduction_ratio: float
    provenance: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)

def _fingerprint_file(filepath: str) -> str:
    try:
        with open(filepath, 'rb') as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)
        return file_hash.hexdigest()
    except Exception:
        return "unreadable"

def compress_context(
    packet: TaskPacket,
    files: List[str],
    backend: Optional[LocalBackend] = None,
) -> ContextBundle:
    # 1. Check sensitivity
    meta = packet.privacy_metadata
    is_sensitive = (
        meta.contains_sensitive_content
        or meta.redaction_required
        or not meta.external_model_allowed
    )

    warnings = []
    source_refs = []
    total_raw_tokens = _estimate_tokens(packet.prompt) + _estimate_tokens(packet.data)
    raw_file_contents = []

    # 2. Process files
    for filepath in files:
        if not os.path.exists(filepath):
            warnings.append(f"File not found: {filepath}")
            continue
        
        fingerprint = _fingerprint_file(filepath)
        size = os.path.getsize(filepath)
        total_raw_tokens += max(1, size // 4)
        
        source_refs.append({
            "path": filepath,
            "fingerprint_sha256": fingerprint,
            "size_bytes": size
        })

        if not is_sensitive:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read(2000)  # read up to 2000 chars as a snippet
                    raw_file_contents.append(f"--- {filepath} ---\n{content}\n")
            except Exception:
                pass

    # 3. Deterministic Extraction vs LLM Summarization
    summary_text = ""
    provenance = None

    if is_sensitive:
        warnings.append("Sensitive metadata detected: bypassing local LLM summarization.")
        summary_text = "[Sensitive content bypassed. Context summarization deferred to CR-002/CR-003.]"
    else:
        # Build raw deterministic bundle first
        context_corpus = f"Task: {packet.prompt}\nData: {packet.data}\n\nFiles:\n" + "\n".join(raw_file_contents)
        
        if backend:
            try:
                # LLM Summarization
                messages = [
                    {"role": "system", "content": "You are a local summarization assistant. Condense the following task context."},
                    {"role": "user", "content": context_corpus}
                ]
                resp = backend.generate(messages, timeout=30)
                summary_text = resp.text
                provenance = {
                    "backend_type": getattr(backend, "name", "unknown"),
                    "backend_uri": backend.get_sanitized_uri() if hasattr(backend, "get_sanitized_uri") else "unknown",
                    "model": getattr(backend, "model", "unknown"),
                    "execution_node": "localhost",
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
            except BackendUnavailableError:
                warnings.append("Backend unavailable. Falling back to deterministic context bundle.")
                summary_text = context_corpus
            except Exception as e:
                warnings.append(f"Backend error ({e}). Falling back to deterministic context bundle.")
                summary_text = context_corpus
        else:
            summary_text = context_corpus

    # 4. Mandatory source verification reminder
    reminder = "\n\n[REMINDER: This is a compressed preflight summary and does not replace source verification. Please verify original files when making critical decisions.]"
    summary_text += reminder

    compressed_tokens = _estimate_tokens(summary_text)
    ratio = 0.0
    if total_raw_tokens > 0:
        ratio = round(1.0 - (compressed_tokens / total_raw_tokens), 2)

    return ContextBundle(
        task_id=packet.task_id or "unknown",
        summary_text=summary_text,
        source_files=source_refs,
        raw_tokens=total_raw_tokens,
        compressed_tokens=compressed_tokens,
        reduction_ratio=ratio,
        provenance=provenance,
        warnings=warnings
    )
