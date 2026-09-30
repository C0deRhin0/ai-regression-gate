import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import Field, ValidationError, field_validator, model_validator

from argate.models import Model, Severity


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently changing security/policy settings."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError("Configuration keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


class ProjectConfig(Model):
    name: str = "unnamed-project"


class ComponentConfig(Model):
    paths: list[str] = Field(min_length=1)
    tests: list[str] = Field(default_factory=list)


class TestGroupConfig(Model):
    command: str = Field(min_length=1)
    required: bool = False
    timeout_seconds: float = Field(default=120, gt=0, le=86400)
    component: str | None = None


class RiskRule(Model):
    paths: list[str] = Field(min_length=1)
    severity: Severity
    category: str
    description: str
    suggested_test: str = ""


class QualityGatesConfig(Model):
    require_all_required_tests: bool = True
    minimum_coverage: float | None = Field(default=None, ge=0, le=100)
    maximum_coverage_drop: float | None = Field(default=None, ge=0, le=100)
    block_on_high_risk_without_tests: bool = True
    mandatory_test_groups: list[str] = Field(default_factory=list)
    blocker_paths: list[str] = Field(default_factory=list)
    block_on_ai_unavailable: bool = False
    warnings_as_errors: bool = False


class CoverageConfig(Model):
    enabled: bool = False
    format: str = "cobertura"
    path: str = "coverage.xml"
    minimum: float | None = Field(default=None, ge=0, le=100)
    maximum_drop: float | None = Field(default=None, ge=0, le=100)
    baseline: float | None = Field(default=None, ge=0, le=100)
    baseline_path: str | None = None

    @field_validator("format")
    @classmethod
    def supported_format(cls, value):
        if value != "cobertura":
            raise ValueError("coverage format must be cobertura")
        return value


class AIConfig(Model):
    mode: str = "deterministic_only"
    provider: str = "openai_compatible"
    endpoint: str | None = None
    model: str | None = None
    api_key_env: str | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_payload_bytes: int = Field(default=32000, ge=256, le=1000000)
    allow_redacted_external: bool = False

    @model_validator(mode="after")
    def valid_provider(self):
        if self.mode not in {"deterministic_only", "local_llm", "external_llm"}:
            raise ValueError("invalid AI mode")
        if self.provider not in {"ollama", "openai_compatible"}:
            raise ValueError("invalid AI provider")
        if self.mode == "deterministic_only":
            return self
        if not self.model or not self.endpoint:
            raise ValueError("AI model and endpoint are required when AI is enabled")
        url = urlparse(self.endpoint)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
            raise ValueError("AI endpoint must be an HTTP URL without embedded credentials")
        if url.query or url.fragment:
            raise ValueError("AI endpoint cannot contain a query or fragment")
        if self.mode == "local_llm" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("local_llm endpoint must use a loopback host")
        if self.mode == "external_llm" and url.scheme != "https":
            raise ValueError("external_llm requires HTTPS")
        return self


class SecurityConfig(Model):
    sensitive_paths: list[str] = Field(default_factory=list)


class Config(Model):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    components: dict[str, ComponentConfig] = Field(default_factory=dict)
    test_groups: dict[str, TestGroupConfig] = Field(default_factory=dict)
    risk_rules: list[RiskRule] = Field(default_factory=list)
    quality_gates: QualityGatesConfig = Field(default_factory=QualityGatesConfig)
    coverage: CoverageConfig = Field(default_factory=CoverageConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @model_validator(mode="after")
    def references_exist(self):
        references = list(self.quality_gates.mandatory_test_groups)
        for component in self.components.values():
            references.extend(component.tests)
        unknown = set(references) - self.test_groups.keys()
        if unknown:
            raise ValueError("undefined test groups: " + ", ".join(sorted(unknown)))
        for group in self.test_groups.values():
            if group.component and group.component not in self.components:
                raise ValueError("test group references an undefined component")
        if not self.coverage.enabled and (
            self.quality_gates.minimum_coverage is not None
            or self.quality_gates.maximum_coverage_drop is not None
        ):
            raise ValueError("coverage must be enabled to enforce coverage gates")
        return self


def load_config(path: Path) -> Config:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        if not isinstance(data, dict):
            raise ValueError("configuration must be a YAML mapping")
        return Config.model_validate(data)
    except ValidationError as exc:
        locations = [".".join(str(part) for part in error["loc"]) or "configuration references"
                     for error in exc.errors(include_input=False, include_url=False)]
        raise ValueError(f"Invalid configuration at {path}; check fields: {', '.join(locations)}") from exc
    except (OSError, ValueError, yaml.YAMLError) as exc:
        # Validation errors may contain input values, including accidental credentials.
        raise ValueError(f"Invalid configuration at {path}; check the documented schema and references") from exc


def configuration_hash(config: Config) -> str:
    canonical = json.dumps(config.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
