from typing import Callable

TOOLS: list[Callable] = []
TOOLS_BY_NAME: dict[str, Callable] = {}


def register_tool(func: Callable) -> Callable:
    TOOLS.append(func)
    TOOLS_BY_NAME[func.__name__] = func
    return func
