# start.py
import asyncio
from bot import main

if __name__ == "__main__":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        # На Linux/Unix этот шаг не нужен
        pass
    main()