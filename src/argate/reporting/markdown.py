from importlib.resources import files

from jinja2 import Environment, StrictUndefined

from argate.analysis.secrets import safe_text
from argate.models import EvaluationReport


def render_markdown(report: EvaluationReport) -> str:
    env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
    env.filters["cell"] = lambda value: safe_text(str(value)).replace("|", "\\|").replace("\n", " ")
    template = files("argate.reporting").joinpath("templates/report.md.j2").read_text(encoding="utf-8")
    return safe_text(env.from_string(template).render(report=report))
