"""Module entry point: ``python -m audioflow2mqtt``."""

import asyncio

from audioflow2mqtt.app import main

if __name__ == "__main__":
    asyncio.run(main())
