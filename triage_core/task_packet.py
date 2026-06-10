from dataclasses import dataclass, field
from typing import Optional, Callable

@dataclass
class PrivacyMetadata:
    data_class: str = "public"
    contains_pii: bool = False
    contains_sensitive_content: bool = False
    contains_precise_location: bool = False
    external_model_allowed: bool = True
    retention_policy: str = "default"
    redaction_required: bool = False

@dataclass
class TaskPacket:
    prompt: str
    data: str
    task_id: Optional[str] = None
    validator: Optional[Callable[[str], bool]] = None
    privacy_metadata: PrivacyMetadata = field(default_factory=PrivacyMetadata)
