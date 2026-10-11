"""PyInstaller entry point for the Forge Fitness Windows executable."""

import os
from multiprocessing import freeze_support

from backend.app import app


if __name__ == "__main__":
    freeze_support()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
