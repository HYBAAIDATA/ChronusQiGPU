"""Command-line entry point for the experimental GA API."""

from __future__ import annotations


def main() -> None:
    import uvicorn

    uvicorn.run("ga.api:create_app", factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
