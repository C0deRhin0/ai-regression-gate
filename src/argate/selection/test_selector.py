from argate.config import Config
from argate.models import TestGroup


def select_tests(config: Config, affected: list[str], recommendations: list[str] | None = None) -> list[TestGroup]:
    reasons: dict[str, list[str]] = {}

    def add(name, reason):
        reasons.setdefault(name, []).append(reason)

    for name, group in config.test_groups.items():
        if group.required:
            add(name, "Configured required group")
        if group.component in affected:
            add(name, f"Component {group.component} changed")
    for component in affected:
        for name in config.components[component].tests:
            add(name, f"Component {component} changed")
    for name in config.quality_gates.mandatory_test_groups:
        add(name, "Policy mandatory group")
    for name in recommendations or []:
        if name in config.test_groups:
            add(name, "AI advisory recommendation")
    return [TestGroup(
        name=name, command=config.test_groups[name].command,
        required=config.test_groups[name].required or name in config.quality_gates.mandatory_test_groups,
        timeout_seconds=config.test_groups[name].timeout_seconds,
        component=config.test_groups[name].component, reasons=list(dict.fromkeys(reasons[name])),
    ) for name in sorted(reasons)]
