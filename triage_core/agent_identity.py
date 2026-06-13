from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


SUPPORTED_KEY_ALGORITHMS = {"ed25519"}
ACTIVE_STATUS = "active"
REVOKED_STATUS = "revoked"


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

    def register_identity(self, identity: AgentIdentity) -> None:
        self._identities[identity.agent_id] = identity

    def save(self) -> Path:
        self.identity_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "agents": [
                identity.to_public_metadata()
                for identity in sorted(
                    self._identities.values(),
                    key=lambda item: item.agent_id,
                )
            ]
        }
        self.registry_path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
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
        self.register_identity(identity)
        self.save()

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path.write_bytes(private_key_bytes)
        return identity

    def load(self) -> Dict[str, AgentIdentity]:
        if not self.registry_path.exists():
            self._identities = {}
            return self._identities

        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self._identities = {}
        for metadata in payload.get("agents", []):
            identity = AgentIdentity.from_public_metadata(metadata)
            self._identities[identity.agent_id] = identity
        return self._identities

    def get_identity(self, agent_id: str) -> AgentIdentity:
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
        return self.keys_dir / f"{agent_id}.key"

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
