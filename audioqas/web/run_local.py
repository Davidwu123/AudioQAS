from __future__ import annotations

import os

import uvicorn

from audioqas.logging import setup_logging


def main() -> None:
    setup_logging()
    uvicorn.run(
        "audioqas.web.api:app",
        host=os.environ.get("AUDIOQAS_WEB_HOST", "127.0.0.1"),
        port=int(os.environ.get("AUDIOQAS_WEB_PORT", "8000")),
        reload=os.environ.get("AUDIOQAS_WEB_RELOAD", "1") != "0",
    )


if __name__ == "__main__":
    main()
