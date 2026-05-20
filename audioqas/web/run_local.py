from __future__ import annotations

import uvicorn

from audioqas.logging import setup_logging


def main() -> None:
    setup_logging()
    uvicorn.run(
        "audioqas.web.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
