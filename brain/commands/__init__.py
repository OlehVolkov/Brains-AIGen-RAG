from brain.commands.health import register_health_commands
from brain.commands.mcp import register_mcp_commands
from brain.commands.pdf import register_pdf_commands
from brain.commands.research import register_research_commands
from brain.commands.vault import register_vault_commands

__all__ = [
    "register_health_commands",
    "register_mcp_commands",
    "register_pdf_commands",
    "register_research_commands",
    "register_vault_commands",
]
