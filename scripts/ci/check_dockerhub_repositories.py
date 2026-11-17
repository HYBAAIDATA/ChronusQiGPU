"""Fail closed before publishing internal images to Docker Hub.

DOCKER_USER is the Docker login/organization and destination namespace.
DOCKER_PAT is read from the environment only, never command-line arguments.
Both personal and organization tokens use the modern namespace-scoped API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class PublicationBlocked(RuntimeError):
    """A repository cannot be verified as an existing private destination."""


class NoCredentialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublicationBlocked("Docker Hub redirects are not permitted.")


def check_private_repository(namespace, repository, credential, *, open_request=None):
    if not namespace or not credential:
        raise PublicationBlocked("Set the DOCKER_USER variable and a replacement DOCKER_PAT secret.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", namespace):
        raise PublicationBlocked("DOCKER_USER must be a valid lowercase Docker Hub namespace.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", repository):
        raise PublicationBlocked("Invalid Docker Hub repository name.")
    if open_request is None:
        open_request = build_opener(NoCredentialRedirects()).open

    request = Request(
        "https://hub.docker.com/v2/auth/token",
        data=json.dumps({"identifier": namespace, "secret": credential}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with open_request(request, timeout=20) as response:
        access_token = json.load(response).get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise PublicationBlocked("Docker Hub did not return an authentication token.")

    request = Request(
        f"https://hub.docker.com/v2/namespaces/{namespace}/repositories/{repository}",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    with open_request(request, timeout=20) as response:
        destination = json.load(response)
    if destination.get("is_private") is not True:
        raise PublicationBlocked("Create the destination repository as private before publishing.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args(argv)
    try:
        check_private_repository(
            os.environ.get("DOCKER_USER", ""),
            args.repository,
            os.environ.get("DOCKER_PAT", ""),
        )
    except HTTPError as exc:
        # Never print response bodies, request objects, credentials or bearer tokens.
        print(f"Docker Hub preflight blocked (HTTP {exc.code}); check repository access and token permissions.", file=sys.stderr)
        return 1
    except PublicationBlocked as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (URLError, OSError, ValueError, TypeError, AttributeError):
        print("Docker Hub preflight blocked: connection or response validation failed.", file=sys.stderr)
        return 1
    print("Verified an existing private Docker Hub repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
