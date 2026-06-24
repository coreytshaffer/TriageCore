import re
from dataclasses import dataclass, field
from typing import List, Optional

from triage_core.task_packet import TaskPacket

@dataclass
class PrivacyReport:
    passed: bool
    violations: List[str]
    detections: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    finding_codes: Optional[List[str]] = None

class PrivacyViolationError(Exception):
    pass

# Heuristic regex patterns
SSN_REGEX = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_REGEX = re.compile(r'\b(?:\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b')
# Basic check for 13-19 digits that could be a CC
CC_CANDIDATE_REGEX = re.compile(r'\b(?:\d[ -]*?){13,19}\b')

SENSITIVE_MARKERS_REGEX = re.compile(r'\b(confidential|internal only|proprietary)\b', re.IGNORECASE)
SECRET_KEYS_REGEX = re.compile(r'\b(api_key\s*=|secret\s*=|token\s*=|bearer\s+token|sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36})\b', re.IGNORECASE)

LAT_LON_REGEX = re.compile(r'\b-?\d{1,2}\.\d{4,},\s*-?\d{1,3}\.\d{4,}\b')

def is_valid_luhn(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    
    checksum = 0
    is_second = False
    for i in range(len(digits) - 1, -1, -1):
        d = digits[i]
        if is_second:
            d = d * 2
            if d > 9:
                d -= 9
        checksum += d
        is_second = not is_second
    return checksum % 10 == 0

def scan_task_packet(packet: TaskPacket) -> PrivacyReport:
    content = f"{packet.prompt}\n{packet.data}"
    meta = packet.privacy_metadata
    
    violations = []
    detections = []
    finding_codes = []
    
    # 1. PII Checks (SSN, Phone, Email, CC)
    has_pii = False
    
    if SSN_REGEX.search(content):
        has_pii = True
        detections.append("SSN pattern")
        if not meta.contains_pii:
            violations.append("Detected possible SSN pattern in packet content; metadata contains_pii=False.")
            finding_codes.extend(["ssn_pattern_detected", "metadata_privacy_conflict"])
            
    if EMAIL_REGEX.search(content):
        has_pii = True
        detections.append("Email pattern")
        if not meta.contains_pii:
            violations.append("Detected possible email address pattern in packet content; metadata contains_pii=False.")
            
    if PHONE_REGEX.search(content):
        has_pii = True
        detections.append("Phone pattern")
        if not meta.contains_pii:
            violations.append("Detected possible phone number pattern in packet content; metadata contains_pii=False.")
            
    for match in CC_CANDIDATE_REGEX.finditer(content):
        if is_valid_luhn(match.group()):
            has_pii = True
            detections.append("Credit Card pattern")
            if not meta.contains_pii:
                violations.append("Detected valid credit card number pattern in packet content; metadata contains_pii=False.")
            break
            
    # 2. Sensitive Markers
    if SENSITIVE_MARKERS_REGEX.search(content):
        detections.append("Sensitive marker")
        if not meta.contains_sensitive_content and meta.data_class == "public":
            violations.append("Detected sensitive keyword (e.g. CONFIDENTIAL) in packet content; metadata indicates public/non-sensitive.")
            
    # 3. Secrets / API Keys
    if SECRET_KEYS_REGEX.search(content):
        detections.append("Secret/API key pattern")
        if not meta.contains_sensitive_content:
            violations.append("Detected potential secret or API key pattern in packet content; metadata contains_sensitive_content=False.")
            
    # 4. Precise Location
    if LAT_LON_REGEX.search(content):
        detections.append("Precise location pattern")
        if not meta.contains_precise_location:
            violations.append("Detected precise coordinate pattern in packet content; metadata contains_precise_location=False.")
            
    # 5. External model allowed conflict
    # CR-002 only validates metadata/content consistency. Routing enforcement for acknowledged sensitive content is deferred to CR-004B.
    
    passed = len(violations) == 0
    return PrivacyReport(
        passed=passed,
        violations=violations,
        detections=detections,
        finding_codes=finding_codes if finding_codes else None
    )
