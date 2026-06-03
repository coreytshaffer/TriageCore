from dataclasses import dataclass, asdict
from typing import List
import json

@dataclass
class HandoffPacket:
    title: str
    summary: str
    context: str
    target_files: List[str]
    constraints: List[str]
    acceptance_criteria: List[str]
    test_commands: List[str]
    safety_notes: List[str]
    recommended_backend: str
    recommended_permission_profile: str
    risk_level: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        md = f"# {self.title}\n\n"
        md += f"## Summary\n{self.summary}\n\n"
        md += f"## Context\n{self.context}\n\n"
        
        md += "## Target Files\n"
        for f in self.target_files:
            md += f"- {f}\n"
        md += "\n"
        
        md += "## Constraints\n"
        for c in self.constraints:
            md += f"- {c}\n"
        md += "\n"
        
        md += "## Acceptance Criteria\n"
        for a in self.acceptance_criteria:
            md += f"- [ ] {a}\n"
        md += "\n"
        
        md += "## Test Commands\n"
        for t in self.test_commands:
            md += f"- `{t}`\n"
        md += "\n"
        
        md += "## Safety Notes\n"
        for s in self.safety_notes:
            md += f"- ⚠️ {s}\n"
        md += "\n"
        
        md += "## Execution Profile\n"
        md += f"- **Recommended Backend**: {self.recommended_backend}\n"
        md += f"- **Permission Profile**: {self.recommended_permission_profile}\n"
        md += f"- **Risk Level**: {self.risk_level}\n"
        
        return md
