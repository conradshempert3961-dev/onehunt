from __future__ import annotations

import uvicorn

from config import MINIAPP_HOST, MINIAPP_PORT


if __name__ == "__main__":
    uvicorn.run(
        "miniapp.app:app",
        host=MINIAPP_HOST,
        port=MINIAPP_PORT,
        reload=False,
    )
