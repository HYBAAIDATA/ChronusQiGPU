"""Vercel build-time validation for the FastAPI entrypoint."""


def main():
    from app import app
    from fastapi import FastAPI

    if not isinstance(app, FastAPI):
        raise TypeError("Vercel entrypoint must export a FastAPI instance named 'app'")
    print(f"Validated FastAPI entrypoint with {len(app.routes)} routes")


if __name__ == "__main__":
    main()
