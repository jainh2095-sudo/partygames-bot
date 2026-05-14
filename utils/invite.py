from __future__ import annotations

import discord

from config import settings


def recommended_permissions() -> discord.Permissions:
    permissions = discord.Permissions.none()
    permissions.view_channel = True
    permissions.send_messages = True
    permissions.embed_links = True
    permissions.read_message_history = True
    permissions.create_private_threads = True
    permissions.manage_threads = True
    permissions.use_external_emojis = True
    return permissions


def invite_url(client_id: int | None = None) -> str:
    if settings.public_invite_url:
        return settings.public_invite_url
    resolved_id = client_id or settings.application_id
    if not resolved_id:
        return ""
    return discord.utils.oauth_url(
        resolved_id,
        permissions=recommended_permissions(),
        scopes=("bot", "applications.commands"),
    )


def permission_summary() -> str:
    return (
        "`View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, "
        "`Create Private Threads`, `Manage Threads`, `Use External Emojis`"
    )
