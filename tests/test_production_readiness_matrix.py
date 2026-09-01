from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = REPO_ROOT / "docs" / "PRODUCTION_CONTRACT.md"
MATRIX = REPO_ROOT / "docs" / "PRODUCTION_READINESS_MATRIX.md"

VALID_STATES = {"DONE", "PARTIAL", "MISSING", "BLOCKED"}
REQUIRED_MUST_COUNT = 20


def _must_requirements() -> list[str]:
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    requirements: list[str] = []
    in_must = False
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped == "### MUST":
            in_must = True
            continue
        if not in_must:
            continue
        if stripped == "```text":
            in_code = True
            continue
        if in_code and stripped == "```":
            break
        if in_code and stripped:
            requirements.append(stripped)
    return requirements


def _matrix_requirements() -> dict[str, str]:
    rows = [
        line
        for line in MATRIX.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and "|" in line[1:]
    ]
    requirements: dict[str, str] = {}
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Requisito", "---"}:
            continue
        requirements[cells[0]] = cells[1]
    return requirements


def _gate_verdict() -> str:
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if line.startswith("VERDICTO PROVISIONAL:"):
            token = line.split(":", 1)[1].strip()
            assert token in {"READY", "NOT_READY"}, f"invalid verdict token: {token}"
            return token
    raise AssertionError("production gate verdict not found")


def test_matrix_document_exists() -> None:
    assert MATRIX.exists()
    assert MATRIX.read_text(encoding="utf-8")


def test_matrix_requirement_states_are_valid() -> None:
    states = set(_matrix_requirements().values())
    assert states, "matrix must classify at least one requirement"
    assert states.issubset(VALID_STATES)


def test_matrix_classifies_exactly_twenty_requirements() -> None:
    assert len(_matrix_requirements()) == REQUIRED_MUST_COUNT


def test_matrix_covers_all_must_requirements() -> None:
    must_requirements = _must_requirements()
    assert len(must_requirements) == REQUIRED_MUST_COUNT
    normalized_matrix = MATRIX.read_text(encoding="utf-8").lower()
    missing = [
        requirement
        for requirement in must_requirements
        if requirement.lower() not in normalized_matrix
    ]
    assert missing == [], f"MUST requirements missing from matrix: {missing}"


def test_matrix_gate_verdict_is_valid_token() -> None:
    assert _gate_verdict() in {"READY", "NOT_READY"}