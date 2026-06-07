import os
import logging

from src.auth.factory import create_auth_client

logger = logging.getLogger(__name__)


async def get_livekit_credentials(user_id, api_key=None):
    url = os.environ.get("LIVEKIT_URL")
    api_key_val = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")

    if url and api_key_val and api_secret:
        return url, api_key_val, api_secret

    auth_client = create_auth_client(api_key=api_key)
    creds = auth_client.get_user_credentials("livekit", user_id)

    if not creds:
        raise ValueError(
            "LiveKit credentials not found. "
            "Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET environment variables "
            "or configure credentials through the auth system."
        )

    if isinstance(creds, str):
        raise ValueError(
            "LiveKit requires a URL, API key, and API secret. "
            "The credential store returned a single value."
        )

    url = creds.get("LIVEKIT_URL") or creds.get("url")
    api_key_val = creds.get("LIVEKIT_API_KEY") or creds.get("api_key")
    api_secret = creds.get("LIVEKIT_API_SECRET") or creds.get("api_secret")

    if not all([url, api_key_val, api_secret]):
        raise ValueError(
            "LiveKit credentials are incomplete. "
            "Provide LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET."
        )

    return url, api_key_val, api_secret
