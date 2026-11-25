from importlib.metadata import entry_points

from .tool import Tool

GROUP = "axq.tools"


def load_tools() -> dict[str, Tool]:
    """Every installed tool, from this package or any other that declares the axq.tools entry point."""
    tools = {}
    for ep in entry_points(group=GROUP):
        cls = ep.load()
        tools[ep.name] = cls()
    return tools
