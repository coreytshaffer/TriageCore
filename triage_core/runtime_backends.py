"""Runtime backend profiles for efficiency evidence records."""
from dataclasses import dataclass
from typing import Any, Dict, Optional


SUPPORTED_BACKENDS = {"ollama", "llama_cpp", "generic_openai_compatible"}


@dataclass(frozen=True)
class RuntimeBackendProfile:
    name: str
    endpoint_kind: str
    server: Optional[str] = None
    model: Optional[str] = None
    model_file: Optional[str] = None
    quantization: Optional[str] = None
    context_size: Optional[int] = None
    threads: Optional[int] = None
    gpu_layers: Optional[int] = None
    batch_size: Optional[int] = None
    ubatch_size: Optional[int] = None
    device: Optional[str] = None
    build_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.name not in SUPPORTED_BACKENDS:
            raise ValueError(f"unsupported runtime backend: {self.name}")
        if not self.endpoint_kind:
            raise ValueError("endpoint_kind must be non-empty")
        if self.name == "ollama" and self.endpoint_kind != "ollama_api":
            raise ValueError("ollama profiles must use endpoint_kind=ollama_api")
        if self.name in {"llama_cpp", "generic_openai_compatible"}:
            if self.endpoint_kind != "openai_compatible":
                raise ValueError(
                    f"{self.name} profiles must use endpoint_kind=openai_compatible"
                )
        for field_name in (
            "context_size",
            "threads",
            "gpu_layers",
            "batch_size",
            "ubatch_size",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative when present")

    @classmethod
    def ollama(
        cls,
        model: str,
        context_size: Optional[int] = None,
        device: Optional[str] = None,
        build_metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeBackendProfile":
        return cls(
            name="ollama",
            endpoint_kind="ollama_api",
            server="ollama",
            model=model,
            context_size=context_size,
            device=device,
            build_metadata=build_metadata,
        )

    @classmethod
    def llama_cpp(
        cls,
        model_file: str,
        quantization: Optional[str] = None,
        context_size: Optional[int] = None,
        threads: Optional[int] = None,
        gpu_layers: Optional[int] = None,
        batch_size: Optional[int] = None,
        ubatch_size: Optional[int] = None,
        device: Optional[str] = None,
        build_metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeBackendProfile":
        return cls(
            name="llama_cpp",
            endpoint_kind="openai_compatible",
            server="llama-server",
            model_file=model_file,
            quantization=quantization,
            context_size=context_size,
            threads=threads,
            gpu_layers=gpu_layers,
            batch_size=batch_size,
            ubatch_size=ubatch_size,
            device=device,
            build_metadata=build_metadata,
        )

    @classmethod
    def generic_openai_compatible(
        cls,
        server: str,
        model: str,
        context_size: Optional[int] = None,
        device: Optional[str] = None,
        build_metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeBackendProfile":
        return cls(
            name="generic_openai_compatible",
            endpoint_kind="openai_compatible",
            server=server,
            model=model,
            context_size=context_size,
            device=device,
            build_metadata=build_metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "endpoint_kind": self.endpoint_kind,
            "server": self.server,
            "model": self.model,
            "model_file": self.model_file,
            "quantization": self.quantization,
            "context_size": self.context_size,
            "threads": self.threads,
            "gpu_layers": self.gpu_layers,
            "batch_size": self.batch_size,
            "ubatch_size": self.ubatch_size,
            "device": self.device,
            "build_metadata": self.build_metadata,
        }
