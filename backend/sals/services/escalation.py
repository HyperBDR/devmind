"""
L1/L2 support tier classification for escalation analysis.

Groups are classified by assignment_group name.
Update L1_GROUPS / L2_GROUPS when team names change.
"""

L1_GROUPS = frozenset({
    "一线运维A组",
    "一线运维B组",
})

L2_GROUPS = frozenset({
    "二线运维团队",
})


def classify_group(name: str) -> str:
    """Return 'L1', 'L2', or 'unclassified'."""
    if name in L1_GROUPS:
        return "L1"
    if name in L2_GROUPS:
        return "L2"
    return "unclassified"
