from __future__ import annotations

import uvicorn

from config import MINIAPP_PORT


if __name__ == "__main__":
    uvicorn.run(
        "miniapp.app:app",
        host="127.0.0.1",
        port=MINIAPP_PORT,
        reload=False,
    )
