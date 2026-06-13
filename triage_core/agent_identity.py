from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Dict, List


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


def _fingerprint_public_key(public_key: str) -> str:
    return sha256(public_key.encode("utf-8")).hexdigest()
