# Patch LM Studio model-agnostic labeling/dispatch.
#
# Run from the active TriageCore root:
#   cd "C:\Users\corey\.gemini\antigravity-ide\scratch\field-aware\triagecore"
#   python patch_lmstudio_model_agnostic.py
#
# Then relaunch:
#   $env:TRIAGE_MODEL="auto"
#   $env:TRIAGE_SUPERVISOR_BASE_URL="http://localhost:1234/v1"
#   python -m triage_core.cli desk

from pathlib import Path
import re


BACKENDS = Path("triage_core/backends.py")
APP = Path("triage_core/ui/app.py")


def patch_backends() -> None:
    text = BACKENDS.read_text(encoding="utf-8")
    BACKENDS.with_suffix(".py.bak_model_agnostic").write_text(text, encoding="utf-8")

    resolve_re = re.compile(
        r"    def resolve_model\(self, timeout: float = 1\.0\) -> str:\n"
        r"(?:        .*\n)+?"
        r"        return self\.model\n",
        re.MULTILINE,
    )

    new_resolve = """    def resolve_model(self, timeout: float = 1.0) -> str:
        # LM Studio control-plane mode should be model-agnostic. Its /v1/models
        # endpoint can expose cached or available model IDs, so do not treat the
        # first listed model as the supervisor identity.
        if self.name == "lmstudio" and self.model in _AUTO_MODEL_SENTINELS:
            return os.getenv("TRIAGE_LMSTUDIO_MODEL_ALIAS", "local-model")

        if self.model and self.model not in _AUTO_MODEL_SENTINELS:
            return self.model

        url = f"{self.base_url.rstrip('/')}/models"
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            resolved = _model_id_from_openai_models(response.json())
            if resolved:
                self.model = resolved
                return resolved
        except requests.exceptions.RequestException:
            pass
        except ValueError:
            pass

        self.model = self.model or "auto"
        return self.model
"""

    class_start = text.find("class OpenAICompatibleBackend:")
    ollama_start = text.find("class OllamaBackend:", class_start)
    if class_start == -1 or ollama_start == -1:
        raise SystemExit("Could not locate backend classes in triage_core/backends.py.")

    prefix = text[:class_start]
    middle = text[class_start:ollama_start]
    suffix = text[ollama_start:]

    patched_middle, count = resolve_re.subn(new_resolve, middle, count=1)
    if count != 1:
        raise SystemExit("Could not patch OpenAICompatibleBackend.resolve_model.")

    text = prefix + patched_middle + suffix

    old_ping_snippet = """            if response.status_code == 200 and self.model in _AUTO_MODEL_SENTINELS:
                try:
                    resolved = _model_id_from_openai_models(response.json())
                    if resolved:
                        self.model = resolved
                except ValueError:
                    pass
"""
    new_ping_snippet = """            if (
                response.status_code == 200
                and self.name != "lmstudio"
                and self.model in _AUTO_MODEL_SENTINELS
            ):
                try:
                    resolved = _model_id_from_openai_models(response.json())
                    if resolved:
                        self.model = resolved
                except ValueError:
                    pass
"""
    if old_ping_snippet in text:
        text = text.replace(old_ping_snippet, new_ping_snippet, 1)

    BACKENDS.write_text(text, encoding="utf-8")
    print(f"Patched {BACKENDS}")


def patch_app() -> None:
    text = APP.read_text(encoding="utf-8")
    APP.with_suffix(".py.bak_model_agnostic").write_text(text, encoding="utf-8")

    old = """        def _label_model(backend):
            return getattr(backend, "model", None) or "auto"
"""
    new = """        def _label_model(backend):
            model = getattr(backend, "model", None) or "auto"
            if (
                getattr(backend, "name", "") == "lmstudio"
                and model in {"", "auto", "loaded-model", "local-model"}
            ):
                return "auto (loaded in LM Studio)"
            return model
"""
    if old not in text:
        if "auto (loaded in LM Studio)" in text:
            print(f"{APP} already has model-agnostic label.")
            return
        raise SystemExit("Could not find _label_model block in triage_core/ui/app.py. Did the previous UI patch run?")

    APP.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Patched {APP}")


def main() -> None:
    if not BACKENDS.exists() or not APP.exists():
        raise SystemExit("Run this from the active TriageCore root, the folder containing triage_core/.")

    patch_backends()
    patch_app()

    print()
    print("Done. Relaunch TriageDesk after closing existing windows.")
    print("Expected label: Control Plane: LM Studio 🟢 · auto (loaded in LM Studio)")
    print("Chat payload model alias defaults to 'local-model' unless you set TRIAGE_LMSTUDIO_MODEL_ALIAS.")


if __name__ == "__main__":
    main()
