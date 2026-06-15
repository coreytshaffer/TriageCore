from __future__ import annotations

import base64
import csv
import json
import os
import platform
import re
import stat
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


SUPPORTED_KEY_ALGORITHMS = {"ed25519"}
ACTIVE_STATUS = "active"
REVOKED_STATUS = "revoked"
AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class AgentIdentityError(Exception):
    pass


class UnknownAgentError(AgentIdentityError):
    pass


class RevokedAgentError(AgentIdentityError):
    pass


class UnauthorizedCapabilityError(AgentIdentityError):
    pass


class UnsupportedKeyAlgorithmError(AgentIdentityError):
    pass


class PrivateKeyPermissionError(AgentIdentityError):
    pass


@dataclass
class AgentIdentityCheckReport:
    identity_count: int = 0
    key_count: int = 0
    missing_key_agent_ids: List[str] = field(default_factory=list)
    orphaned_key_agent_ids: List[str] = field(default_factory=list)
    malformed_registry: bool = False
    permission_warnings: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return (
            self.malformed_registry
            or bool(self.missing_key_agent_ids)
            or bool(self.orphaned_key_agent_ids)
        )


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    role: str
    public_key: str
    key_algorithm: str
    capabilities: List[str]
    public_key_fingerprint: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = ACTIVE_STATUS

    def __post_init__(self) -> None:
        if self.key_algorithm not in SUPPORTED_KEY_ALGORITHMS:
            raise UnsupportedKeyAlgorithmError(
                f"Unsupported key algorithm: {self.key_algorithm}"
            )

        computed_fingerprint = _fingerprint_public_key(self.public_key)
        if (
            self.public_key_fingerprint
            and self.public_key_fingerprint != computed_fingerprint
        ):
            raise AgentIdentityError(
                "public_key_fingerprint does not match the provided public_key."
            )
        if not self.public_key_fingerprint:
            object.__setattr__(self, "public_key_fingerprint", computed_fingerprint)

    def to_public_metadata(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_public_metadata(cls, metadata: Dict[str, object]) -> "AgentIdentity":
        return cls(
            agent_id=str(metadata["agent_id"]),
            role=str(metadata["role"]),
            public_key=str(metadata["public_key"]),
            public_key_fingerprint=str(metadata.get("public_key_fingerprint", "")),
            key_algorithm=str(metadata["key_algorithm"]),
            created_at=str(metadata["created_at"]),
            status=str(metadata["status"]),
            capabilities=[str(item) for item in metadata.get("capabilities", [])],
        )


class AgentIdentityRegistry:
    def __init__(self, ledger_dir: str | Path = ".triagecore") -> None:
        self.ledger_dir = Path(ledger_dir)
        self.identity_dir = self.ledger_dir / "identity"
        self.registry_path = self.identity_dir / "agents.json"
        self.keys_dir = self.identity_dir / "keys"
        self._identities: Dict[str, AgentIdentity] = {}
        self._loaded = False

    def register_identity(self, identity: AgentIdentity) -> None:
        self._ensure_loaded()
        self._identities[identity.agent_id] = identity

    def save(self) -> Path:
        self._ensure_loaded()
        self.identity_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.identity_dir / f".agents.{uuid.uuid4().hex}.tmp"
        try:
            self._write_registry(temp_path, self._identities)
            os.replace(temp_path, self.registry_path)
        finally:
            temp_path.unlink(missing_ok=True)
        return self.registry_path

    def generate_identity(
        self,
        agent_id: str,
        role: str,
        capabilities: List[str],
        *,
        key_algorithm: str = "ed25519",
        status: str = ACTIVE_STATUS,
    ) -> AgentIdentity:
        if key_algorithm not in SUPPORTED_KEY_ALGORITHMS:
            raise UnsupportedKeyAlgorithmError(
                f"Unsupported key algorithm: {key_algorithm}"
            )
        _validate_agent_id(agent_id)
        self._ensure_loaded()

        key_path = self._private_key_path(agent_id)
        if agent_id in self._identities or key_path.exists():
            raise AgentIdentityError(
                f"Agent identity '{agent_id}' already exists in the local registry."
            )

        self.identity_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        if key_algorithm == "ed25519":
            private_key = ed25519.Ed25519PrivateKey.generate()
        else:
            raise UnsupportedKeyAlgorithmError(
                f"Unsupported key algorithm: {key_algorithm}"
            )

        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        identity = AgentIdentity(
            agent_id=agent_id,
            role=role,
            public_key=public_key,
            key_algorithm=key_algorithm,
            capabilities=capabilities,
            status=status,
        )
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        candidate_identities = dict(self._identities)
        candidate_identities[agent_id] = identity
        key_temp_path = self.keys_dir / f".{agent_id}.{uuid.uuid4().hex}.tmp"
        registry_temp_path = self.identity_dir / f".agents.{uuid.uuid4().hex}.tmp"
        key_committed = False

        try:
            key_temp_path.write_bytes(private_key_bytes)
            harden_private_key_permissions(key_temp_path)
            self._write_registry(registry_temp_path, candidate_identities)
            os.replace(key_temp_path, key_path)
            key_committed = True
            os.replace(registry_temp_path, self.registry_path)
        except Exception as exc:
            if key_committed:
                key_path.unlink(missing_ok=True)
            key_temp_path.unlink(missing_ok=True)
            registry_temp_path.unlink(missing_ok=True)
            if isinstance(exc, AgentIdentityError):
                raise
            raise AgentIdentityError(
                f"Failed to initialize agent identity '{agent_id}'; partial files were cleaned up."
            ) from exc

        self._identities = candidate_identities
        return identity

    def load(self) -> Dict[str, AgentIdentity]:
        if not self.registry_path.exists():
            self._identities = {}
            self._loaded = True
            return self._identities

        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            metadata_items = payload["agents"]
            if not isinstance(metadata_items, list):
                raise TypeError("agents must be a list")

            identities: Dict[str, AgentIdentity] = {}
            for metadata in metadata_items:
                identity = AgentIdentity.from_public_metadata(metadata)
                if identity.agent_id in identities:
                    raise ValueError("duplicate agent_id")
                identities[identity.agent_id] = identity
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AgentIdentityError("Identity registry is malformed.") from exc

        self._identities = identities
        self._loaded = True
        return self._identities

    def revoke_identity(self, agent_id: str) -> AgentIdentity:
        self._ensure_loaded()
        identity = self.get_identity(agent_id)
        if identity.status == REVOKED_STATUS:
            return identity

        revoked_identity = AgentIdentity(
            agent_id=identity.agent_id,
            role=identity.role,
            public_key=identity.public_key,
            public_key_fingerprint=identity.public_key_fingerprint,
            key_algorithm=identity.key_algorithm,
            created_at=identity.created_at,
            status=REVOKED_STATUS,
            capabilities=identity.capabilities,
        )
        self._identities[agent_id] = revoked_identity
        self.save()
        return revoked_identity

    def check_consistency(self) -> AgentIdentityCheckReport:
        report = AgentIdentityCheckReport()
        identities: Dict[str, AgentIdentity] = {}

        if self.registry_path.exists():
            try:
                identities = dict(self.load())
            except AgentIdentityError:
                report.malformed_registry = True

        key_paths = sorted(self.keys_dir.glob("*.key")) if self.keys_dir.exists() else []
        report.identity_count = len(identities)
        report.key_count = len(key_paths)

        if not report.malformed_registry:
            identity_ids = set(identities)
            key_ids = {path.stem for path in key_paths}
            report.missing_key_agent_ids = sorted(identity_ids - key_ids)
            report.orphaned_key_agent_ids = sorted(key_ids - identity_ids)

        for key_path in key_paths:
            warning = check_private_key_permissions(key_path)
            if warning:
                report.permission_warnings.append(f"{key_path.name}: {warning}")

        return report

    def get_identity(self, agent_id: str) -> AgentIdentity:
        self._ensure_loaded()
        if agent_id not in self._identities:
            raise UnknownAgentError(f"Unknown agent identity: {agent_id}")
        return self._identities[agent_id]

    def require_authorized_capability(
        self,
        agent_id: str,
        capability: str,
    ) -> AgentIdentity:
        identity = self.get_identity(agent_id)
        if identity.status != ACTIVE_STATUS:
            raise RevokedAgentError(
                f"Agent identity '{agent_id}' is not active (status={identity.status})."
            )
        if capability not in identity.capabilities:
            raise UnauthorizedCapabilityError(
                f"Agent identity '{agent_id}' is not authorized for capability '{capability}'."
            )
        return identity

    def sign_payload(
        self,
        agent_id: str,
        capability: str,
        payload: Any,
        *,
        signature_algorithm: str = "ed25519",
    ) -> Dict[str, str]:
        if signature_algorithm not in SUPPORTED_KEY_ALGORITHMS:
            raise UnsupportedKeyAlgorithmError(
                f"Unsupported key algorithm: {signature_algorithm}"
            )

        identity = self.require_authorized_capability(agent_id, capability)
        private_key = self._load_private_key(agent_id, identity.key_algorithm)
        signed_at = datetime.now(timezone.utc).isoformat()
        payload_hash = canonical_payload_hash(payload)
        signature_fields = _signature_fields(
            agent_id=agent_id,
            capability=capability,
            payload_hash=payload_hash,
            signature_algorithm=signature_algorithm,
            signed_at=signed_at,
        )
        signature_bytes = private_key.sign(_canonical_json(signature_fields))
        return {
            **signature_fields,
            "signature": base64.b64encode(signature_bytes).decode("ascii"),
        }

    def verify_signed_payload(
        self,
        payload: Any,
        signature_metadata: Dict[str, str],
    ) -> bool:
        signature_algorithm = str(signature_metadata["signature_algorithm"])
        if signature_algorithm not in SUPPORTED_KEY_ALGORITHMS:
            raise UnsupportedKeyAlgorithmError(
                f"Unsupported key algorithm: {signature_algorithm}"
            )

        agent_id = str(signature_metadata["agent_id"])
        capability = str(signature_metadata["capability"])
        identity = self.require_authorized_capability(agent_id, capability)
        if identity.key_algorithm != signature_algorithm:
            return False

        expected_payload_hash = canonical_payload_hash(payload)
        if signature_metadata["payload_hash"] != expected_payload_hash:
            return False

        signature_fields = _signature_fields(
            agent_id=agent_id,
            capability=capability,
            payload_hash=str(signature_metadata["payload_hash"]),
            signature_algorithm=signature_algorithm,
            signed_at=str(signature_metadata["signed_at"]),
        )
        signature_bytes = base64.b64decode(signature_metadata["signature"])
        public_key = serialization.load_pem_public_key(
            identity.public_key.encode("utf-8")
        )
        try:
            public_key.verify(signature_bytes, _canonical_json(signature_fields))
        except InvalidSignature:
            return False
        return True

    def _private_key_path(self, agent_id: str) -> Path:
        _validate_agent_id(agent_id)
        return self.keys_dir / f"{agent_id}.key"

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @staticmethod
    def _write_registry(
        path: Path,
        identities: Dict[str, AgentIdentity],
    ) -> None:
        payload = {
            "agents": [
                identity.to_public_metadata()
                for identity in sorted(
                    identities.values(),
                    key=lambda item: item.agent_id,
                )
            ]
        }
        path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_private_key(
        self,
        agent_id: str,
        key_algorithm: str,
    ) -> ed25519.Ed25519PrivateKey:
        if key_algorithm not in SUPPORTED_KEY_ALGORITHMS:
            raise UnsupportedKeyAlgorithmError(
                f"Unsupported key algorithm: {key_algorithm}"
            )

        key_path = self._private_key_path(agent_id)
        if not key_path.exists():
            raise AgentIdentityError(
                f"Private key for agent identity '{agent_id}' was not found."
            )

        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(),
            password=None,
        )
        return private_key


def _fingerprint_public_key(public_key: str) -> str:
    return sha256(public_key.encode("utf-8")).hexdigest()


def _validate_agent_id(agent_id: str) -> None:
    if not AGENT_ID_PATTERN.fullmatch(agent_id):
        raise AgentIdentityError(
            "agent_id must use only letters, numbers, dots, underscores, and hyphens."
        )


def harden_private_key_permissions(path: str | Path) -> None:
    key_path = Path(path)
    system = platform.system()

    if system == "Windows":
        try:
            whoami = subprocess.run(
                ["whoami", "/user", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                check=True,
            )
            row = next(csv.reader([whoami.stdout.strip()]))
            current_user_sid = row[-1]
            subprocess.run(
                [
                    "icacls",
                    str(key_path),
                    "/inheritance:r",
                    "/grant:r",
                    f"*{current_user_sid}:(F)",
                    "*S-1-5-18:(F)",
                    "*S-1-5-32-544:(F)",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError, StopIteration, IndexError) as exc:
            raise PrivateKeyPermissionError(
                "Failed to apply restrictive Windows permissions to the private key."
            ) from exc
        return

    if os.name == "posix":
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)


def check_private_key_permissions(path: str | Path) -> Optional[str]:
    key_path = Path(path)
    system = platform.system()

    if system == "Windows":
        try:
            result = subprocess.run(
                ["icacls", str(key_path)],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return "permissions could not be verified with icacls"

        acl_text = result.stdout.lower()
        if "(i)" in acl_text:
            return "permissions are inherited"
        broad_principals = ("everyone", "authenticated users", "builtin\\users")
        if any(principal in acl_text for principal in broad_principals):
            return "permissions include a broad Windows principal"
        return None

    if os.name == "posix":
        mode = stat.S_IMODE(key_path.stat().st_mode)
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            return f"mode {mode:04o} grants group or other access"
        return None

    return "permission verification is unsupported on this platform"


def canonical_payload_hash(payload: Any) -> str:
    return sha256(_canonical_json(payload)).hexdigest()


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _signature_fields(
    *,
    agent_id: str,
    capability: str,
    payload_hash: str,
    signature_algorithm: str,
    signed_at: str,
) -> Dict[str, str]:
    return {
        "agent_id": agent_id,
        "capability": capability,
        "payload_hash": payload_hash,
        "signature_algorithm": signature_algorithm,
        "signed_at": signed_at,
    }
