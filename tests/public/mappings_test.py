"""Public mapping tests."""
from finance_utils.common import get_mappings_conflicts
from tests.helper import PublicConfig


def test_no_conflicts_in_mapping() -> None:
    """Check that no conflicts are in mapping."""
    conflicts = get_mappings_conflicts(PublicConfig.CONFIG)
    conflicts_as_str = "\n".join(conflicts)
    assert len(conflicts) == 0, f"Multiple conflicts: {conflicts_as_str}"
