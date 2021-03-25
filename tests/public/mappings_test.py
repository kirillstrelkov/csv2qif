from tests.helper import PublicConfig
from finance_utils.common import get_mappings_conflicts


def test_no_conflicts_in_mapping():
    conflicts = get_mappings_conflicts(PublicConfig.CONFIG)
    conflicts_as_str = "\n".join(conflicts)
    assert len(conflicts) == 0, f"Multiple conflicts: {conflicts_as_str}"
