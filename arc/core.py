"""Parsing, classification and range arithmetic using Decimal."""
import json
import re
from decimal import Decimal
from pathlib import Path

BANNER = "Estimates are heuristic ranges from declared assumptions on synthetic fixtures. They are not promises or guaranteed outcomes."
SEGMENTATION = "Split responsibility text on semicolons only; preserve source line and allocate its percentage equally."
RESIDUAL = "A human remains accountable for exceptions, approvals, oversight and relationships. This tool cannot conclude that a role can be fully replaced."


class RoleFormatError(ValueError):
    """Invalid role description schema."""


class TimeSplitError(RoleFormatError):
    """Invalid time percentages."""


def rules():
    return json.loads(Path(__file__).with_name("rules.json").read_text(encoding="utf-8"))


def parse(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    role = {"title": "", "weekly_hours": "", "synthetic": False, "tools": [], "responsibilities": []}
    section = None
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# ") and not role["title"]:
            role["title"] = line[2:]
        elif line == "Synthetic: yes":
            role["synthetic"] = True
        elif line.startswith("Weekly hours: "):
            role["weekly_hours"] = line.removeprefix("Weekly hours: ")
        elif line in ("## Tools", "## Responsibilities"):
            section = line[3:]
        elif section == "Tools" and line.startswith("- "):
            role["tools"].append(line[2:])
        elif section == "Responsibilities":
            match = re.fullmatch(r"- (\d+(?:\.\d+)?)%: (.+)", line)
            if not match:
                raise RoleFormatError(f"Line {number}: expected '- percentage%: responsibility'")
            percent, task = match.groups()
            role["responsibilities"].append({"text": task, "percent": percent, "source_line": number})
        else:
            raise RoleFormatError(f"Line {number}: unrecognized field")
    try:
        hours = Decimal(role["weekly_hours"])
        if not hours.is_finite() or hours <= 0:
            raise ValueError()
    except (ValueError, ArithmeticError):
        raise RoleFormatError("Weekly hours must be a finite positive number") from None
    if not role["title"] or not role["synthetic"] or not role["tools"] or not role["responsibilities"]:
        raise RoleFormatError("Require title, Synthetic: yes, tools and responsibilities; only fictional roles are accepted")
    if sum(Decimal(r["percent"]) for r in role["responsibilities"]) != 100:
        raise TimeSplitError("Responsibility percentages must sum to 100")
    return role


def decompose(role):
    tasks = []
    for responsibility in role["responsibilities"]:
        parts = [p.strip() for p in responsibility["text"].split(";")]
        if any(not p for p in parts):
            raise RoleFormatError(f"Line {responsibility['source_line']}: empty task segment")
        for part in parts:
            tasks.append({"id": f"T{len(tasks) + 1:03}", "text": part,
                          "source_line": responsibility["source_line"],
                          "percent": str(Decimal(responsibility["percent"]) / len(parts))})
    return tasks


def classify(tasks, config=None):
    config = config or rules()
    result = []
    for task in tasks:
        text = task["text"].lower()
        fired = {key: [term for term in config[key] if term in text]
                 for key in ("judgment", "routine", "assistance", "structured")}
        if fired["judgment"]:
            category = "hybrid" if fired["assistance"] else "human-judgment"
        elif fired["assistance"]:
            category = "hybrid"
        elif fired["routine"] and fired["structured"]:
            category = "automatable"
        else:
            category = "human-judgment"
        result.append({**task, "classification": category, "firing_rules": fired,
                       "rationale": "Judgment prevents automatic decisions; assistance requires human review." if fired["judgment"] else
                       "Assistance requires human review." if category == "hybrid" else
                       "Routine action with declared structured rules." if category == "automatable" else
                       "Insufficient evidence of deterministic structured work; retain human ownership."})
    return result


def decimal_text(value):
    return format(value.quantize(Decimal("0.000001")), "f")


def estimate(role, tasks, config=None):
    config = config or rules()
    result = []
    total = [Decimal(0), Decimal(0)]
    eligible_hours = Decimal(0)
    for task in tasks:
        hours = Decimal(role["weekly_hours"]) * Decimal(task["percent"]) / 100
        fractions = config["savings"][task["classification"]]
        savings = [hours * Decimal(f) for f in fractions]
        total = [a + b for a, b in zip(total, savings)]
        if task["classification"] != "human-judgment":
            eligible_hours += hours
        result.append({**task, "weekly_hours": decimal_text(hours), "savings_fraction": fractions,
                       "savings_hours": [decimal_text(v) for v in savings]})
    assert total[1] <= eligible_hours <= Decimal(role["weekly_hours"])
    return {"tasks": result, "savings_hours": [decimal_text(v) for v in total],
            "residual_hours": [decimal_text(Decimal(role["weekly_hours"]) - total[1]),
                               decimal_text(Decimal(role["weekly_hours"]) - total[0])],
            "eligible_hours_cap": decimal_text(eligible_hours), "assumptions": config["assumptions"]}


def propose(tasks, config=None):
    config = config or rules()
    candidates = [t for t in tasks if t["classification"] == "automatable"]
    candidates.sort(key=lambda t: (-Decimal(t["savings_hours"][0]) / config["complexity"][t["classification"]], t["id"]))
    phases = [{"id": "P0", "task_id": None, "title": "Validate inputs and access in a human-supervised pilot",
               "dependencies": [], "risks": ["Poor data quality", "Missing access permission"],
               "measure": ["Baseline minutes per task", "Exception rate", "Accuracy"], "value_over_complexity": None}]
    for index, task in enumerate(candidates, 1):
        phases.append({"id": f"P{index}", "task_id": task["id"], "title": task["text"],
                       "dependencies": ["P0"], "complexity": config["complexity"]["automatable"],
                       "value_over_complexity": decimal_text(Decimal(task["savings_hours"][0]) / config["complexity"]["automatable"]),
                       "risks": ["Rule drift", "Exceptions still require a human", "Adoption may reduce savings"],
                       "measure": ["Observed time saved versus baseline", "Error and exception rates", "Human review time" ]})
    return {"ordering_rule": "Prerequisites first, then descending low weekly savings hours divided by complexity; task ID breaks ties.", "phases": phases}


def report(role):
    config = rules()
    model = estimate(role, classify(decompose(role), config), config)
    stays = [{"task_id": t["id"], "text": t["text"], "reason": t["rationale"]}
             for t in model["tasks"] if t["classification"] != "automatable"]
    stays.append({"task_id": None, "text": "Exception review, approvals and ongoing automation oversight", "reason": "Human accountability remains even for routine workflows; oversight is included in unsaved time, not added to the declared split."})
    return {"honesty_banner": BANNER, "stays_human": stays, "residual_role": RESIDUAL,
            "title": role["title"], "synthetic": True, "tools": role["tools"],
            "segmentation_rule": SEGMENTATION, "classification_rules": config, **model,
            "proposal": propose(model["tasks"], config)}


def json_output(value):
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def markdown(data):
    def safe(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace(chr(0x2014), "-")
    lines = ["> " + BANNER, "", "## What stays human", ""]
    lines += ["- " + safe(item["text"]) + ": " + safe(item["reason"]) for item in data["stays_human"]]
    lines += ["", RESIDUAL, "", "# " + safe(data["title"]), "", "Fictional synthetic role.", "",
              "Weekly savings hours: " + " to ".join(data["savings_hours"]),
              "Residual weekly hours: " + " to ".join(data["residual_hours"]), "", "## Tasks", "",
              "| Task | Source line | Class | Hours | Savings hours | Rationale and firing rules |",
              "| --- | --- | --- | --- | --- | --- |"]
    for t in data["tasks"]:
        lines.append("| " + " | ".join(safe(v) for v in (t["text"], t["source_line"], t["classification"], t["weekly_hours"], " to ".join(t["savings_hours"]), t["rationale"] + " " + json.dumps(t["firing_rules"], sort_keys=True))) + " |")
    lines += ["", "## Assumptions", "", *["- " + a for a in data["assumptions"]], "", "## Segmentation", "", SEGMENTATION,
              "", "## Classification rules", "", "```json", json_output(data["classification_rules"]).rstrip(), "```", "", "## Implementation proposal", "", data["proposal"]["ordering_rule"]]
    for phase in data["proposal"]["phases"]:
        lines += ["", "### " + phase["id"] + ": " + safe(phase["title"]),
                  "Dependencies: " + (", ".join(phase["dependencies"]) or "none"),
                  "Value over complexity: " + str(phase["value_over_complexity"]),
                  "Risks: " + "; ".join(phase["risks"]), "Measure: " + "; ".join(phase["measure"])]
    return "\n".join(lines) + "\n"
