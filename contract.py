from dataclasses import dataclass, field
from typing import List

@dataclass
class BehavioralContract:
    name: str
    system: str
    always: List[str]
    never: List[str]
    under_pressure: List[str] = field(default_factory=list)
    threshold: float = 0.90

    def summary(self) -> str:
        lines = [
            f"\n{'='*55}",
            f"CONTRACT: {self.name}",
            f"SYSTEM:   {self.system}",
            f"THRESHOLD: {self.threshold:.0%}",
            f"{'='*55}",
            f"ALWAYS ({len(self.always)} rules):"
        ]
        for r in self.always:
            lines.append(f"  ✅ {r}")
        lines.append(f"NEVER ({len(self.never)} rules):")
        for r in self.never:
            lines.append(f"  ❌ {r}")
        if self.under_pressure:
            lines.append(f"UNDER PRESSURE ({len(self.under_pressure)} rules):")
            for r in self.under_pressure:
                lines.append(f"  ⚠️  {r}")
        lines.append("="*55)
        return "\n".join(lines)
