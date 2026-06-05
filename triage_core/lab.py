import csv
import math
import os
import json
from typing import List, Dict, Any, Optional, Tuple


# ─── Scientific Metrics ───────────────────────────────────────────────────────

def calculate_scientific_metrics(records: List[Any]) -> Dict[str, Any]:
    """Calculate derived views and scientific metrics over historical task ledger records."""
    reviewed = [r for r in records if r.status == "reviewed"]
    accepted = [r for r in reviewed if r.accepted]
    
    accepted_yield_pct = 0.0
    if len(reviewed) > 0:
        accepted_yield_pct = (len(accepted) / len(reviewed)) * 100.0
        
    mean_review_burden = 0.0
    if len(reviewed) > 0:
        mean_review_burden = sum(r.human_review_minutes for r in reviewed) / len(reviewed)
        
    mean_tokens_accepted = 0.0
    if len(accepted) > 0:
        mean_tokens_accepted = sum(r.total_tokens for r in accepted) / len(accepted)
        
    mean_energy_accepted = 0.0
    if len(accepted) > 0:
        mean_energy_accepted = sum(r.energy_kwh_estimate for r in accepted) / len(accepted)
        
    mean_emissions_accepted = 0.0
    if len(accepted) > 0:
        mean_emissions_accepted = sum(r.emissions_gco2e_estimate for r in accepted) / len(accepted)
        
    mean_water_accepted = 0.0
    if len(accepted) > 0:
        mean_water_accepted = sum(getattr(r, "water_liters_estimate", 0.0) for r in accepted) / len(accepted)
        
    total_tokens = sum(r.total_tokens for r in records)
    total_wasted = sum(getattr(r, "wasted_tokens", 0) for r in records)
    
    token_efficiency_pct = 100.0
    if total_tokens > 0:
        token_efficiency_pct = (max(0, total_tokens - total_wasted) / total_tokens) * 100.0
        
    return {
        "total_runs": len(records),
        "total_reviewed": len(reviewed),
        "total_accepted": len(accepted),
        "accepted_yield_pct": accepted_yield_pct,
        "mean_review_burden_mins": mean_review_burden,
        "mean_tokens_per_accepted_task": mean_tokens_accepted,
        "mean_energy_kwh_per_accepted_task": mean_energy_accepted,
        "mean_emissions_gco2e_per_accepted_task": mean_emissions_accepted,
        "mean_water_liters_per_accepted_task": mean_water_accepted,
        "total_tokens": total_tokens,
        "total_wasted_tokens": total_wasted,
        "token_efficiency_pct": token_efficiency_pct
    }


# ─── Dataset Export ──────────────────────────────────────────────────────────

def export_tabular_dataset(records: List[Any], output_path: str):
    """Export all task records to a flat tabular dataset for machine learning."""
    fieldnames = [
        "task_id",
        "created_at",
        "runner",
        "backend_name",
        "model",
        "risk_level",
        "permission_profile",
        "total_tokens",
        "wasted_tokens",
        "elapsed_seconds",
        "energy_kwh",
        "emissions_gco2e",
        "human_review_required",
        "status",
        "accepted"
    ]
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            accepted_lbl = 0
            if r.status == "reviewed" and r.accepted:
                accepted_lbl = 1
                
            writer.writerow({
                "task_id": r.task_id,
                "created_at": r.created_at,
                "runner": r.runner or "unknown",
                "backend_name": r.backend_name or "unknown",
                "model": r.model or "unknown",
                "risk_level": r.risk_level or "unknown",
                "permission_profile": r.permission_profile or "unknown",
                "total_tokens": r.total_tokens,
                "wasted_tokens": getattr(r, "wasted_tokens", 0),
                "elapsed_seconds": r.elapsed_seconds,
                "energy_kwh": r.energy_kwh_estimate,
                "emissions_gco2e": r.emissions_gco2e_estimate,
                "human_review_required": 1 if r.human_review_required else 0,
                "status": r.status,
                "accepted": accepted_lbl
            })


# ─── Pure-Python Decision Tree Classifier ───────────────────────────────────

class DecisionNode:
    def __init__(
        self,
        feature: Optional[str] = None,
        children: Optional[Dict[str, "DecisionNode"]] = None,
        label: Optional[int] = None,
        prob: Optional[float] = None
    ):
        self.feature = feature
        self.children = children or {}
        self.label = label  # 1 (success/accepted) or 0 (failure/rejected)
        self.prob = prob    # Probability of success (1) at this node

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision tree node to a serializable dictionary."""
        if self.feature is None:
            return {
                "label": self.label,
                "prob": self.prob
            }
        return {
            "feature": self.feature,
            "label": self.label,
            "prob": self.prob,
            "children": {val: child.to_dict() for val, child in self.children.items()}
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecisionNode":
        """Reconstruct decision tree node from a serialized dictionary."""
        if "feature" not in d:
            return cls(label=d["label"], prob=d["prob"])
        children = {val: cls.from_dict(child) for val, child in d["children"].items()}
        return cls(feature=d["feature"], label=d["label"], prob=d["prob"], children=children)


def entropy(y: List[int]) -> float:
    if not y:
        return 0.0
    p1 = sum(y) / len(y)
    p0 = 1.0 - p1
    ent = 0.0
    if p1 > 0:
        ent -= p1 * math.log2(p1)
    if p0 > 0:
        ent -= p0 * math.log2(p0)
    return ent


def split_data(X: List[Dict[str, Any]], y: List[int], feature: str) -> Dict[Any, Tuple[List[Dict[str, Any]], List[int]]]:
    splits = {}
    for xi, yi in zip(X, y):
        val = xi.get(feature)
        if val not in splits:
            splits[val] = ([], [])
        splits[val][0].append(xi)
        splits[val][1].append(yi)
    return splits


def information_gain(y: List[int], splits: Dict[Any, Tuple[List[Dict[str, Any]], List[int]]]) -> float:
    parent_ent = entropy(y)
    total = len(y)
    if total == 0:
        return 0.0
    weighted_child_ent = 0.0
    for child_X, child_y in splits.values():
        weighted_child_ent += (len(child_y) / total) * entropy(child_y)
    return parent_ent - weighted_child_ent


class LightweightDecisionTree:
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self.root: Optional[DecisionNode] = None

    def fit(self, X: List[Dict[str, Any]], y: List[int], features: List[str]):
        """Train the decision tree classifier using ID3/CART approach."""
        self.root = self._build_tree(X, y, features, depth=0)

    def _build_tree(self, X: List[Dict[str, Any]], y: List[int], features: List[str], depth: int) -> DecisionNode:
        if not y:
            return DecisionNode(label=1, prob=1.0)
            
        prob = sum(y) / len(y)
        label = 1 if prob >= 0.5 else 0
        
        # Base cases
        if len(set(y)) == 1 or not features or depth >= self.max_depth:
            return DecisionNode(label=label, prob=prob)
            
        # Find best feature to split on
        best_gain = -1.0
        best_feature = None
        best_splits = None
        
        for feature in features:
            splits = split_data(X, y, feature)
            gain = information_gain(y, splits)
            if gain > best_gain:
                best_gain = gain
                best_feature = feature
                best_splits = splits
                
        if best_gain <= 0.0 or not best_feature:
            return DecisionNode(label=label, prob=prob)
            
        # Recurse
        remaining_features = [f for f in features if f != best_feature]
        children = {}
        for val, (child_X, child_y) in best_splits.items():
            children[str(val)] = self._build_tree(child_X, child_y, remaining_features, depth + 1)
            
        return DecisionNode(feature=best_feature, children=children, label=label, prob=prob)

    def predict(self, sample: Dict[str, Any]) -> Tuple[int, float]:
        """Predict the label and probability of success for a sample."""
        if not self.root:
            return 1, 1.0
        return self._predict_node(self.root, sample)

    def _predict_node(self, node: DecisionNode, sample: Dict[str, Any]) -> Tuple[int, float]:
        if node.feature is None:
            return node.label, node.prob
            
        val = str(sample.get(node.feature))
        if val in node.children:
            return self._predict_node(node.children[val], sample)
            
        return node.label, node.prob

    def serialize(self) -> Dict[str, Any]:
        """Serialize model to a dictionary representation."""
        if not self.root:
            return {}
        return self.root.to_dict()

    def deserialize(self, data: Dict[str, Any]):
        """Load model from serialized dictionary representation."""
        if not data:
            self.root = None
        else:
            self.root = DecisionNode.from_dict(data)

    def render_tree_text(self) -> str:
        """Render a readable text visualization of the learned tree."""
        if not self.root:
            return "Empty Tree"
        return self._render_node_text(self.root, indent="")

    def _render_node_text(self, node: DecisionNode, indent: str) -> str:
        if node.feature is None:
            return f"{indent}|-- Predict: {node.label} (P(Success)={node.prob * 100:.1f}%)\n"
        lines = [f"{indent}|-- Split on: {node.feature}\n"]
        for val, child in node.children.items():
            lines.append(f"{indent}    [{val}]\n")
            lines.append(self._render_node_text(child, indent + "        "))
        return "".join(lines)
