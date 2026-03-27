from brains.commands.graph import register_graph_commands
from brains.commands.health import register_health_commands
from brains.commands.mcp import register_mcp_commands
from brains.commands.pdf import register_pdf_commands
from brains.commands.research import register_research_commands
from brains.commands.tasks import register_task_commands
from brains.commands.vault import register_vault_commands

__all__ = [
    "register_graph_commands",
    "register_health_commands",
    "register_mcp_commands",
    "register_pdf_commands",
    "register_research_commands",
    "register_task_commands",
    "register_vault_commands",
]
