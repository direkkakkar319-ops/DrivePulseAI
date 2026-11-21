#!/usr/bin/env python3
"""Trigger a Render deploy hook and verify the resulting deploy through Render's API."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

POLL_SECONDS = 30
DEPLOY_TIMEOUT_SECONDS = 2 * 60 * 60
IN_PROGRESS = {
    "created",
    "queued",
    "build_in_progress",
    "update_in_progress",
    "pre_deploy_in_progress",
}
FAILED = {
    "build_failed",
    "update_failed",
    "pre_deploy_failed",
    "canceled",
    "deactivated",
}


def fail(message: str) -> None:
    print(f"::error::{message}")
    raise SystemExit(1)


def write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        fail("GITHUB_OUTPUT is not available.")
    with open(output_path, "a", encoding="utf-8") as output_file:
        output_file.write(f"{name}={value}\n")


def request(url: str, *, method: str = "GET", api_key: str | None = None):
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = Request(url, method=method, headers=headers)
    try:
        with urlopen(req, timeout=30) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()
    except (TimeoutError, URLError) as error:
        fail(
            f"Render request failed: {error.reason if isinstance(error, URLError) else error}"
        )


def service_id_from_hook(hook_url: str) -> str:
    parsed = urlparse(hook_url)
    if parsed.scheme != "https" or parsed.hostname != "api.render.com":
        fail("The Render deploy-hook secret is not a valid Render HTTPS hook URL.")
    match = re.fullmatch(r"/deploy/(srv-[A-Za-z0-9]+)", parsed.path)
    if not match:
        fail("Could not read a Render service ID from the deploy-hook URL.")
    return match.group(1)


def trigger() -> None:
    hook_url = os.environ.get("RENDER_DEPLOY_HOOK", "").strip()
    deploy_ref = os.environ.get("DEPLOY_REF", "").strip()
    if not os.environ.get("RENDER_API_KEY", "").strip():
        fail(
            "The RENDER_API_KEY repository secret is required to verify deployment status."
        )
    if not hook_url:
        fail("The required Render deploy-hook secret is not configured.")
    if not deploy_ref:
        fail("The workflow did not provide a commit to deploy.")

    service_id = service_id_from_hook(hook_url)
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    parsed_hook = urlparse(hook_url)
    query = [
        (key, value) for key, value in parse_qsl(parsed_hook.query) if key != "ref"
    ]
    query.append(("ref", deploy_ref))
    commit_hook_url = urlunparse(parsed_hook._replace(query=urlencode(query)))
    status, response_body = request(commit_hook_url, method="POST")
    if status not in (200, 202):
        fail(f"Render rejected the deploy-hook request with HTTP {status}.")

    deploy_id = ""
    if status == 200:
        try:
            payload = json.loads(response_body)
            deploy_id = payload["deploy"]["id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            fail(
                "Render accepted the request but did not return the expected deploy ID."
            )
        print(
            f"Render accepted deployment {deploy_id} for {service_id} at {deploy_ref}."
        )
    else:
        print("Render queued the deployment behind another in-progress deployment.")

    write_output("service_id", service_id)
    write_output("deploy_id", deploy_id)
    write_output("deploy_started_at", started_at)


def api_get(url: str, api_key: str):
    status, body = request(url, api_key=api_key)
    if status != 200:
        fail(
            f"Render API request failed with HTTP {status}; check RENDER_API_KEY permissions."
        )
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        fail("Render API returned an invalid JSON response.")


def find_queued_deploy(
    service_id: str, api_key: str, started_at: str, expected_commit: str
):
    params = urlencode({"limit": "20", "createdAfter": started_at})
    url = f"https://api.render.com/v1/services/{service_id}/deploys?{params}"
    for item in api_get(url, api_key):
        deploy = item.get("deploy", {})
        commit = deploy.get("commit") or {}
        if commit.get("id") == expected_commit:
            return deploy
    return None


def check_health(url: str) -> bool:
    try:
        with urlopen(
            Request(url, headers={"Accept": "application/json"}), timeout=15
        ) as response:
            return 200 <= response.status < 300
    except (HTTPError, TimeoutError, URLError):
        return False


def verify() -> None:
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    deploy_id = os.environ.get("RENDER_DEPLOY_ID", "").strip()
    started_at = os.environ.get("DEPLOY_STARTED_AT", "").strip()
    expected_commit = os.environ.get("EXPECTED_COMMIT", "").strip()
    health_urls = [
        url.strip()
        for url in os.environ.get("HEALTH_URLS", "").split(",")
        if url.strip()
    ]

    if not api_key:
        fail(
            "The RENDER_API_KEY repository secret is required to verify deployment status."
        )
    if not service_id or not started_at or not expected_commit or not health_urls:
        fail("Deployment verification is missing required workflow inputs.")

    deploy_url = f"https://api.render.com/v1/services/{service_id}/deploys"
    deadline = time.monotonic() + DEPLOY_TIMEOUT_SECONDS
    deploy = None

    while time.monotonic() < deadline:
        if deploy_id:
            deploy = api_get(f"{deploy_url}/{deploy_id}", api_key)
        else:
            deploy = find_queued_deploy(
                service_id, api_key, started_at, expected_commit
            )

        if deploy:
            actual_commit = (deploy.get("commit") or {}).get("id")
            if actual_commit != expected_commit:
                fail(
                    "Render is deploying commit "
                    f"{actual_commit or 'unknown'}, expected {expected_commit}."
                )

            state = deploy.get("status", "unknown")
            print(f"Render deploy {deploy.get('id', 'unknown')} status: {state}")
            if state == "live":
                break
            if state in FAILED:
                fail(f"Render deployment failed with status: {state}.")
            if state not in IN_PROGRESS:
                fail(f"Render returned an unexpected deployment status: {state}.")
        else:
            print("Waiting for Render to create the queued deployment record.")

        time.sleep(POLL_SECONDS)
    else:
        fail("Render deployment did not reach a terminal state within two hours.")

    for url in health_urls:
        for attempt in range(1, 19):
            if check_health(url):
                print(f"Service health check passed: {url}")
                break
            print(f"Waiting for service health ({attempt}/18): {url}")
            time.sleep(10)
        else:
            fail(f"Deployment is live, but the health check failed: {url}")

    print("Render deployment is live and its health checks passed.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"trigger", "verify"}:
        fail("Usage: render_deploy.py {trigger|verify}")
    trigger() if sys.argv[1] == "trigger" else verify()
