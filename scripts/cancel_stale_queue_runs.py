#!/usr/bin/env python3
"""Cancel active merge-group CI only after its temporary branch is deleted (#1189)."""

import json
import os
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class Client:
    def __init__(self, repo, token, api_url="https://api.github.com"):
        self.base = f"{api_url}/repos/{repo}"
        self.token = token

    def request(self, path, method="GET"):
        request = Request(
            self.base + path,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
            method=method,
        )
        with urlopen(request, timeout=30) as response:
            data = response.read()
        return json.loads(data) if data else {}


def is_missing_ref_error(error):
    if error.code == 404:
        return True
    raise error


def cleanup(client):
    cancelled = []
    for status in ("queued", "in_progress"):
        # Collect before mutating: cancellation must not shift pagination.
        runs = []
        page = 1
        while True:
            query = urlencode(
                {"event": "merge_group", "status": status, "page": page, "per_page": 100}
            )
            batch = client.request("/actions/workflows/ci.yml/runs?" + query)["workflow_runs"]
            runs.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        for run in runs:
            branch = run.get("head_branch") or ""
            if not branch.startswith("gh-readonly-queue/"):
                continue
            try:
                client.request("/git/ref/heads/" + quote(branch, safe="/"))
            except HTTPError as error:
                if is_missing_ref_error(error):
                    client.request(f"/actions/runs/{int(run['id'])}/cancel", method="POST")
                    cancelled.append(run["id"])
    return cancelled


if __name__ == "__main__":
    print(
        json.dumps(
            {"cancelled": cleanup(Client(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"]))}
        )
    )
