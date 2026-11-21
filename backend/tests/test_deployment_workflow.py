"""Static safety regression: PR checks may never invoke Render deployment hooks."""

import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"


def job(name):
    text = WORKFLOW.read_text()
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"Missing workflow job {name}"
    return match.group(1)


def condition(block):
    match = re.search(r"^    if: >-\n((?:      .*\n)+)", block, re.MULTILINE)
    assert match
    return " ".join(match.group(1).split())


@pytest.mark.parametrize("service", ["backend", "ml"])
def test_only_main_push_can_deploy(service):
    block = job(f"trigger-{service}-deployment")
    assert condition(block) == (
        "github.event_name == 'push' && github.ref == 'refs/heads/main' && "
        f"needs.detect-deploy-changes.outputs.{service} == 'true'"
    )
    assert "DEPLOY_REF: ${{ github.sha }}" in block
    assert "pull_request" not in block and "merge_group" not in block
    # Existing CI prerequisites still gate deployment through implicit success().
    for check in ("lint-ml", "lint-backend", "lint-mobile", "test-ml", "test-backend"):
        assert f"      - {check}" in block


@pytest.mark.parametrize("service", ["backend", "ml"])
def test_verification_requires_successful_corresponding_deployment(service):
    block = job(f"verify-{service}-deployment")
    assert condition(block) == (
        "always() && github.event_name == 'push' && github.ref == 'refs/heads/main' && "
        f"needs.trigger-{service}-deployment.result == 'success'"
    )
    assert f"needs: [trigger-{service}-deployment]" in block
    assert "EXPECTED_COMMIT: ${{ github.sha }}" in block


def test_pull_requests_and_merge_groups_keep_validation():
    text = WORKFLOW.read_text()
    assert "  pull_request:" in text and "  merge_group:" in text
    for name in ("lint-ml", "lint-backend", "lint-mobile", "test-ml", "test-backend"):
        assert "    if:" not in job(name)


def test_mobile_regressions_run_with_pr_checks():
    block = job("lint-mobile")
    assert "    if:" not in block
    assert "run: npm test -- --runInBand" in block
    assert "working-directory: mobile" in block
