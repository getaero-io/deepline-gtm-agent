"""Root entrypoint for the Deepline GTM native v2 broker."""

from managed_agent.server import UVICORN_LOG_CONFIG, app


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        log_config=UVICORN_LOG_CONFIG,
    )
