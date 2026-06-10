from dataclasses import dataclass
from typing import Optional

from triage_core.task_packet import TaskPacket
from triage_core.privacy_scanner import scan_task_packet, PrivacyReport, PrivacyViolationError

class UnsafePacketError(Exception):
    pass

class LocalRouteUnavailableError(Exception):
    pass

@dataclass
class VerifiedTaskPacket(TaskPacket):
    scan_report: Optional[PrivacyReport] = None

    def __post_init__(self):
        if self.scan_report is None:
            raise ValueError("scan_report must be provided for a VerifiedTaskPacket.")

@dataclass
class ExternalSafeTaskPacket(VerifiedTaskPacket):
    pass

def verify_packet(packet: TaskPacket) -> VerifiedTaskPacket:
    report = scan_task_packet(packet)
    if not report.passed:
        raise PrivacyViolationError(f"Privacy scan failed: {', '.join(report.violations)}")
    
    return VerifiedTaskPacket(
        prompt=packet.prompt,
        data=packet.data,
        task_id=packet.task_id,
        validator=packet.validator,
        privacy_metadata=packet.privacy_metadata,
        scan_report=report
    )

def make_external_safe_packet(packet: VerifiedTaskPacket) -> ExternalSafeTaskPacket:
    if not packet.scan_report.passed:
        raise UnsafePacketError("Cannot make external safe packet: scan report did not pass.")
        
    meta = packet.privacy_metadata
    
    if meta.contains_pii:
        raise UnsafePacketError("Cannot make external safe packet: contains PII.")
    if meta.contains_sensitive_content:
        raise UnsafePacketError("Cannot make external safe packet: contains sensitive content.")
    if meta.contains_precise_location:
        raise UnsafePacketError("Cannot make external safe packet: contains precise location.")
    if meta.redaction_required:
        raise UnsafePacketError("Cannot make external safe packet: redaction required.")
    if not meta.external_model_allowed:
        raise UnsafePacketError("Cannot make external safe packet: external models not allowed.")
    if meta.data_class != "public":
        raise UnsafePacketError(f"Cannot make external safe packet: data_class is '{meta.data_class}', not 'public'.")
        
    return ExternalSafeTaskPacket(
        prompt=packet.prompt,
        data=packet.data,
        task_id=packet.task_id,
        validator=packet.validator,
        privacy_metadata=packet.privacy_metadata,
        scan_report=packet.scan_report
    )
