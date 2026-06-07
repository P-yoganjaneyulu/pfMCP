import os
import sys
import json
import re
import logging
from datetime import timedelta
from pathlib import Path

project_root = os.path.abspath(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from mcp.types import TextContent, Tool, ImageContent, EmbeddedResource
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from src.utils.livekit.util import get_livekit_credentials

from livekit.api import LiveKitAPI, AccessToken, VideoGrants
from livekit.api.room_service import (
    CreateRoomRequest,
    DeleteRoomRequest,
    ListRoomsRequest,
    ListParticipantsRequest,
    RoomParticipantIdentity,
    UpdateParticipantRequest,
    MuteRoomTrackRequest,
    UpdateRoomMetadataRequest,
)
from livekit.api.ingress_service import (
    CreateIngressRequest,
    ListIngressRequest,
    UpdateIngressRequest,
    DeleteIngressRequest,
)
from livekit.api.egress_service import (
    RoomCompositeEgressRequest,
    WebEgressRequest,
    ParticipantEgressRequest,
    TrackCompositeEgressRequest,
    TrackEgressRequest,
    UpdateLayoutRequest,
    UpdateStreamRequest,
    ListEgressRequest,
    StopEgressRequest,
)
from livekit.api import (
    IngressInput,
    EncodingOptionsPreset,
    EncodedFileType,
    EncodedFileOutput,
    DirectFileOutput,
    StreamOutput,
    StreamProtocol,
    S3Upload,
    GCPUpload,
    AzureBlobUpload,
    AliOSSUpload,
)
from google.protobuf.json_format import MessageToDict

SERVICE_NAME = Path(__file__).parent.name

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(SERVICE_NAME)

# ── Shared schema constants ──────────────────────────────────────────────

S3_UPLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "access_key": {"type": "string", "description": "S3 access key"},
        "secret": {"type": "string", "description": "S3 secret key"},
        "region": {"type": "string", "description": "AWS region"},
        "endpoint": {"type": "string", "description": "Custom endpoint URL"},
        "bucket": {"type": "string", "description": "S3 bucket name"},
        "force_path_style": {"type": "boolean", "description": "Use path-style addressing"},
    },
    "description": "S3 upload configuration",
}

GCP_UPLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "credentials": {"type": "string", "description": "GCP service account JSON key"},
        "bucket": {"type": "string", "description": "GCS bucket name"},
    },
    "description": "GCP Cloud Storage upload configuration",
}

AZURE_UPLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "account_name": {"type": "string", "description": "Azure storage account name"},
        "account_key": {"type": "string", "description": "Azure storage account key"},
        "container_name": {"type": "string", "description": "Azure container name"},
    },
    "description": "Azure Blob Storage upload configuration",
}

ALIOSS_UPLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "access_key": {"type": "string", "description": "Aliyun OSS access key"},
        "secret": {"type": "string", "description": "Aliyun OSS secret key"},
        "region": {"type": "string", "description": "Aliyun region"},
        "endpoint": {"type": "string", "description": "Custom endpoint URL"},
        "bucket": {"type": "string", "description": "OSS bucket name"},
    },
    "description": "Aliyun OSS upload configuration",
}

FILE_OUTPUT_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "filepath": {"type": "string", "description": "Output file path"},
        "file_type": {
            "type": "string",
            "enum": ["DEFAULT_FILETYPE", "MP4", "OGG", "MP3"],
            "description": "File format",
        },
        "disable_manifest": {"type": "boolean", "description": "Disable manifest file"},
        "s3": S3_UPLOAD_SCHEMA,
        "gcp": GCP_UPLOAD_SCHEMA,
        "azure": AZURE_UPLOAD_SCHEMA,
        "aliOSS": ALIOSS_UPLOAD_SCHEMA,
    },
}

FILE_OUTPUTS_SCHEMA = {
    "type": "array",
    "items": FILE_OUTPUT_ITEM_SCHEMA,
    "description": "Advanced file output configurations (overrides filepath)",
}

STREAM_OUTPUTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "protocol": {
                "type": "string",
                "enum": ["DEFAULT_PROTOCOL", "RTMP", "SRT", "WEBSOCKET"],
                "description": "Streaming protocol",
            },
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Stream destination URLs",
            },
        },
    },
    "description": "Advanced stream output configurations (overrides stream_urls)",
}

PRESET_OPTIONS = [
    "H264_720P_30",
    "H264_720P_60",
    "H264_1080P_30",
    "H264_1080P_60",
    "PORTRAIT_H264_720P_30",
    "PORTRAIT_H264_720P_60",
    "PORTRAIT_H264_1080P_30",
    "PORTRAIT_H264_1080P_60",
]

STREAM_PROTOCOL_OPTIONS = ["DEFAULT_PROTOCOL", "RTMP", "SRT", "WEBSOCKET"]

# ── Helpers ──────────────────────────────────────────────────────────────


def _proto_to_dict(msg):
    return MessageToDict(msg, preserving_proto_field_name=True)


async def _create_api(user_id, api_key=None):
    url, key, secret = await get_livekit_credentials(user_id, api_key=api_key)
    return LiveKitAPI(url, key, secret)


_SENSITIVE_PATTERNS = [
    (re.compile(r'(?i)(access_key|secret_key|secret|api_key|api_secret|account_key|credentials)\s*"?\s*[:=]\s*"?\s*\S+'), r'\1=[REDACTED]'),
    (re.compile(r'(?i)(token|jwt|password|auth|private_key|client_secret|bearer|refresh_token)\s*"?\s*[:=]\s*"?\s*\S+'), r'\1=[REDACTED]'),
    (re.compile(r'(?:https?://)[^@\s]+@'), 'https://[REDACTED]@'),
]


def _sanitize_error(msg):
    for pattern, replacement in _SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg


_SENSITIVE_ARG_KEYS = {"access_key", "secret", "account_key", "credentials", "account_name", "token", "api_key", "api_secret", "private_key"}


def _redact_args(args):
    redacted = json.loads(json.dumps(args))

    def _redact(obj, depth=0):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if isinstance(v, str) and k in _SENSITIVE_ARG_KEYS and v:
                    obj[k] = "[REDACTED]"
                elif isinstance(v, (dict, list)):
                    _redact(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _redact(item, depth + 1)
        return obj
    return _redact(redacted)


def _resolve_room_name(args):
    room = args.get("room")
    room_name = args.get("room_name")
    if room is not None and room_name is not None and room != room_name:
        logger.warning(
            f"Both 'room' ({room}) and 'room_name' ({room_name}) provided; using 'room_name'"
        )
    return room_name if room_name is not None else room


def _validate_egress_outputs(args):
    has_shorthand = "filepath" in args or "stream_urls" in args
    has_advanced = "file_outputs" in args or "stream_outputs" in args
    return has_shorthand or has_advanced


def _apply_egress_outputs(req, args):
    has_advanced = "file_outputs" in args or "stream_outputs" in args
    if has_advanced:
        if "file_outputs" in args:
            for fo_dict in args["file_outputs"]:
                req.file_outputs.append(_dict_to_encoded_file_output(fo_dict))
        if "stream_outputs" in args:
            for so_dict in args["stream_outputs"]:
                req.stream_outputs.append(_dict_to_stream_output(so_dict))
    else:
        if "filepath" in args:
            fo = EncodedFileOutput(filepath=args["filepath"])
            req.file_outputs.append(fo)
        if "stream_urls" in args:
            protocol = StreamProtocol.Value(args.get("stream_protocol", "RTMP"))
            so = StreamOutput(protocol=protocol)
            so.urls.extend(args["stream_urls"])
            req.stream_outputs.append(so)


def create_server(user_id, api_key=None):
    server = Server("livekit-server")
    server.user_id = user_id
    server.api_key = api_key

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        logger.info(f"Listing tools for user: {server.user_id}")
        return [
            Tool(
                name="create_room",
                description="Create a new LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Room name (must be unique within the project)",
                        },
                        "empty_timeout": {
                            "type": "integer",
                            "description": "Seconds before the room is closed after the last participant leaves (default: 300)",
                        },
                        "max_participants": {
                            "type": "integer",
                            "description": "Maximum number of participants allowed in the room",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "JSON-encoded metadata for the room",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="delete_room",
                description="Delete a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Name of the room to delete",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                },
            ),
            Tool(
                name="list_rooms",
                description="List all LiveKit rooms",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of room names to filter by",
                        },
                    },
                },
            ),
            Tool(
                name="generate_join_token",
                description="Generate a JWT token for joining a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name the token grants access to",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Unique identity for the participant",
                        },
                        "name": {
                            "type": "string",
                            "description": "Display name for the participant",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "JSON-encoded metadata for the participant",
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Token time-to-live in seconds (default: 300)",
                        },
                        "can_publish": {
                            "type": "boolean",
                            "description": "Allowed to publish audio/video tracks (default: true)",
                        },
                        "can_subscribe": {
                            "type": "boolean",
                            "description": "Allowed to subscribe to tracks (default: true)",
                        },
                        "can_publish_data": {
                            "type": "boolean",
                            "description": "Allowed to publish data messages (default: true)",
                        },
                        "room_admin": {
                            "type": "boolean",
                            "description": "Grant room admin privileges (default: false)",
                        },
                        "ingress_admin": {
                            "type": "boolean",
                            "description": "Grant ingress admin privileges (default: false)",
                        },
                        "agent": {
                            "type": "boolean",
                            "description": "Allow this participant to act as an Agent worker (default: false)",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                    "required": ["identity"],
                },
            ),
            Tool(
                name="list_participants",
                description="List participants in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                },
            ),
            Tool(
                name="get_participant",
                description="Get details about a specific participant in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                    "required": ["identity"],
                },
            ),
            Tool(
                name="update_participant",
                description="Update metadata or permissions for a participant in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant to update",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "New JSON-encoded metadata for the participant",
                        },
                        "name": {
                            "type": "string",
                            "description": "New display name for the participant",
                        },
                        "attributes": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                            "description": "Key-value attributes to set on the participant",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                    "required": ["identity"],
                },
            ),
            Tool(
                name="remove_participant",
                description="Remove a participant from a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant to remove",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                    "required": ["identity"],
                },
            ),
            Tool(
                name="mute_participant_track",
                description="Mute or unmute a specific track of a participant in a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant",
                        },
                        "track_sid": {
                            "type": "string",
                            "description": "SID of the track to mute/unmute",
                        },
                        "muted": {
                            "type": "boolean",
                            "description": "True to mute the track, False to unmute",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                    "required": ["identity", "track_sid", "muted"],
                },
            ),
            Tool(
                name="update_room_metadata",
                description="Update metadata for a LiveKit room",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name (alias for room)",
                        },
                        "metadata": {
                            "type": "string",
                            "description": "New JSON-encoded metadata for the room",
                        },
                    },
                    "anyOf": [
                        {"required": ["room"]},
                        {"required": ["room_name"]},
                    ],
                    "required": ["metadata"],
                },
            ),
            Tool(
                name="start_ingress",
                description="Create a new LiveKit ingress",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input_type": {
                            "type": "string",
                            "enum": ["RTMP_INPUT", "WHIP_INPUT", "URL_INPUT"],
                            "description": "Ingress protocol type",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL to pull from (for URL_INPUT)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Human-readable name for the ingress",
                        },
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Target room name",
                        },
                        "participant_identity": {
                            "type": "string",
                            "description": "Identity of the participant in the room",
                        },
                        "participant_name": {
                            "type": "string",
                            "description": "Display name for the participant",
                        },
                        "enable_transcoding": {
                            "type": "boolean",
                            "description": "Enable transcoding (default: true)",
                        },
                    },
                    "required": ["input_type"],
                },
            ),
            Tool(
                name="list_ingress",
                description="List all LiveKit ingresses",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Filter by room name",
                        },
                        "ingress_id": {
                            "type": "string",
                            "description": "Filter by ingress ID",
                        },
                    },
                },
            ),
            Tool(
                name="start_room_composite_egress",
                description="Start recording a room composite egress to file or stream",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name to record",
                        },
                        "layout": {
                            "type": "string",
                            "description": "Layout preset name (e.g. speaker, grid)",
                        },
                        "audio_only": {
                            "type": "boolean",
                            "description": "Record audio only (cannot be combined with video_only)",
                        },
                        "video_only": {
                            "type": "boolean",
                            "description": "Record video only (cannot be combined with audio_only)",
                        },
                        "preset": {
                            "type": "string",
                            "enum": PRESET_OPTIONS,
                            "description": "Encoding quality preset",
                        },
                        "filepath": {
                            "type": "string",
                            "description": "Output file path (shorthand, overridden by file_outputs)",
                        },
                        "stream_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Stream destination URLs (shorthand, overridden by stream_outputs)",
                        },
                        "stream_protocol": {
                            "type": "string",
                            "enum": STREAM_PROTOCOL_OPTIONS,
                            "description": "Stream protocol for stream_urls shorthand (default: RTMP)",
                        },
                        "file_outputs": FILE_OUTPUTS_SCHEMA,
                        "stream_outputs": STREAM_OUTPUTS_SCHEMA,
                    },
                    "required": ["room_name"],
                },
            ),
            Tool(
                name="list_egress",
                description="List all LiveKit egresses",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Filter by room name",
                        },
                        "egress_id": {
                            "type": "string",
                            "description": "Filter by egress ID",
                        },
                        "active": {
                            "type": "boolean",
                            "description": "Only show active egresses",
                        },
                    },
                },
            ),
            Tool(
                name="stop_egress",
                description="Stop a LiveKit egress",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "egress_id": {
                            "type": "string",
                            "description": "ID of the egress to stop",
                        },
                    },
                    "required": ["egress_id"],
                },
            ),
            Tool(
                name="delete_ingress",
                description="Delete a LiveKit ingress",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ingress_id": {
                            "type": "string",
                            "description": "ID of the ingress to delete",
                        },
                    },
                    "required": ["ingress_id"],
                },
            ),
            Tool(
                name="update_layout",
                description="Update the layout of an active room composite egress",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "egress_id": {
                            "type": "string",
                            "description": "ID of the active egress to update",
                        },
                        "layout": {
                            "type": "string",
                            "description": "New layout preset name (e.g. speaker, grid)",
                        },
                    },
                    "required": ["egress_id", "layout"],
                },
            ),
            Tool(
                name="update_ingress",
                description="Update an existing LiveKit ingress",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ingress_id": {
                            "type": "string",
                            "description": "ID of the ingress to update",
                        },
                        "name": {
                            "type": "string",
                            "description": "New human-readable name for the ingress",
                        },
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "New target room name",
                        },
                        "participant_identity": {
                            "type": "string",
                            "description": "New identity for the participant in the room",
                        },
                        "participant_name": {
                            "type": "string",
                            "description": "New display name for the participant",
                        },
                        "enable_transcoding": {
                            "type": "boolean",
                            "description": "Enable transcoding",
                        },
                    },
                    "required": ["ingress_id"],
                },
            ),
            Tool(
                name="start_web_egress",
                description="Start recording a web page URL to file or stream",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Web page URL to record",
                        },
                        "audio_only": {
                            "type": "boolean",
                            "description": "Record audio only (cannot be combined with video_only)",
                        },
                        "video_only": {
                            "type": "boolean",
                            "description": "Record video only (cannot be combined with audio_only)",
                        },
                        "await_start_signal": {
                            "type": "boolean",
                            "description": "Wait for start signal before recording",
                        },
                        "preset": {
                            "type": "string",
                            "enum": PRESET_OPTIONS,
                            "description": "Encoding quality preset",
                        },
                        "filepath": {
                            "type": "string",
                            "description": "Output file path (shorthand, overridden by file_outputs)",
                        },
                        "stream_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Stream destination URLs (shorthand, overridden by stream_outputs)",
                        },
                        "stream_protocol": {
                            "type": "string",
                            "enum": STREAM_PROTOCOL_OPTIONS,
                            "description": "Stream protocol for stream_urls shorthand (default: RTMP)",
                        },
                        "file_outputs": FILE_OUTPUTS_SCHEMA,
                        "stream_outputs": STREAM_OUTPUTS_SCHEMA,
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="start_participant_egress",
                description="Start recording a specific participant in a room to file or stream",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "identity": {
                            "type": "string",
                            "description": "Identity of the participant to record",
                        },
                        "screen_share": {
                            "type": "boolean",
                            "description": "Record screen share instead of the main video",
                        },
                        "preset": {
                            "type": "string",
                            "enum": PRESET_OPTIONS,
                            "description": "Encoding quality preset",
                        },
                        "filepath": {
                            "type": "string",
                            "description": "Output file path (shorthand, overridden by file_outputs)",
                        },
                        "stream_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Stream destination URLs (shorthand, overridden by stream_outputs)",
                        },
                        "stream_protocol": {
                            "type": "string",
                            "enum": STREAM_PROTOCOL_OPTIONS,
                            "description": "Stream protocol for stream_urls shorthand (default: RTMP)",
                        },
                        "file_outputs": FILE_OUTPUTS_SCHEMA,
                        "stream_outputs": STREAM_OUTPUTS_SCHEMA,
                    },
                    "required": ["room_name", "identity"],
                },
            ),
            Tool(
                name="start_track_composite_egress",
                description="Start recording a track composite egress to file or stream",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name to record",
                        },
                        "audio_track_id": {
                            "type": "string",
                            "description": "Audio track SID to include in the composite",
                        },
                        "video_track_id": {
                            "type": "string",
                            "description": "Video track SID to include in the composite",
                        },
                        "preset": {
                            "type": "string",
                            "enum": PRESET_OPTIONS,
                            "description": "Encoding quality preset",
                        },
                        "filepath": {
                            "type": "string",
                            "description": "Output file path (shorthand, overridden by file_outputs)",
                        },
                        "stream_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Stream destination URLs (shorthand, overridden by stream_outputs)",
                        },
                        "stream_protocol": {
                            "type": "string",
                            "enum": STREAM_PROTOCOL_OPTIONS,
                            "description": "Stream protocol for stream_urls shorthand (default: RTMP)",
                        },
                        "file_outputs": FILE_OUTPUTS_SCHEMA,
                        "stream_outputs": STREAM_OUTPUTS_SCHEMA,
                    },
                    "required": ["room_name"],
                },
            ),
            Tool(
                name="start_track_egress",
                description="Start recording a specific track to file or websocket",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room name (alias for room_name)",
                        },
                        "room_name": {
                            "type": "string",
                            "description": "Room name",
                        },
                        "track_id": {
                            "type": "string",
                            "description": "Track SID to record",
                        },
                        "filepath": {
                            "type": "string",
                            "description": "Output file path",
                        },
                        "websocket_url": {
                            "type": "string",
                            "description": "Websocket URL to stream the track to",
                        },
                    },
                    "required": ["room_name", "track_id"],
                },
            ),
            Tool(
                name="update_stream",
                description="Add or remove stream URLs from an active egress",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "egress_id": {
                            "type": "string",
                            "description": "ID of the active egress to update",
                        },
                        "add_output_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Stream URLs to add",
                        },
                        "remove_output_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Stream URLs to remove",
                        },
                    },
                    "required": ["egress_id"],
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict | None
    ) -> list[TextContent | ImageContent | EmbeddedResource]:
        logger.info(
            f"User {server.user_id} calling tool: {name} with arguments: {_redact_args(arguments)}"
        )

        if arguments is None:
            arguments = {}

        try:
            api = await _create_api(server.user_id, api_key=server.api_key)
        except ValueError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

        async with api as lk:
            try:
                if name == "create_room":
                    return await _handle_create_room(lk, arguments)
                elif name == "delete_room":
                    return await _handle_delete_room(lk, arguments)
                elif name == "list_rooms":
                    return await _handle_list_rooms(lk, arguments)
                elif name == "generate_join_token":
                    return await _handle_generate_join_token(arguments, api_key=server.api_key)
                elif name == "list_participants":
                    return await _handle_list_participants(lk, arguments)
                elif name == "get_participant":
                    return await _handle_get_participant(lk, arguments)
                elif name == "update_participant":
                    return await _handle_update_participant(lk, arguments)
                elif name == "remove_participant":
                    return await _handle_remove_participant(lk, arguments)
                elif name == "mute_participant_track":
                    return await _handle_mute_participant_track(lk, arguments)
                elif name == "update_room_metadata":
                    return await _handle_update_room_metadata(lk, arguments)
                elif name == "start_ingress":
                    return await _handle_start_ingress(lk, arguments)
                elif name == "list_ingress":
                    return await _handle_list_ingress(lk, arguments)
                elif name == "start_room_composite_egress":
                    return await _handle_start_room_composite_egress(lk, arguments)
                elif name == "list_egress":
                    return await _handle_list_egress(lk, arguments)
                elif name == "stop_egress":
                    return await _handle_stop_egress(lk, arguments)
                elif name == "delete_ingress":
                    return await _handle_delete_ingress(lk, arguments)
                elif name == "update_layout":
                    return await _handle_update_layout(lk, arguments)
                elif name == "update_ingress":
                    return await _handle_update_ingress(lk, arguments)
                elif name == "start_web_egress":
                    return await _handle_start_web_egress(lk, arguments)
                elif name == "start_participant_egress":
                    return await _handle_start_participant_egress(lk, arguments)
                elif name == "start_track_composite_egress":
                    return await _handle_start_track_composite_egress(lk, arguments)
                elif name == "start_track_egress":
                    return await _handle_start_track_egress(lk, arguments)
                elif name == "update_stream":
                    return await _handle_update_stream(lk, arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                sanitized_msg = _sanitize_error(str(e))
                logger.error(
                    f"Error calling LiveKit API for tool {name}: {sanitized_msg}"
                )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": f"LiveKit API error: {sanitized_msg}"}),
                    )
                ]

    return server


async def _handle_create_room(lk, args):
    req = CreateRoomRequest(name=args["name"])
    if "empty_timeout" in args:
        req.empty_timeout = args["empty_timeout"]
    if "max_participants" in args:
        req.max_participants = args["max_participants"]
    if "metadata" in args:
        req.metadata = args["metadata"]

    result = await lk.room.create_room(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_delete_room(lk, args):
    room = _resolve_room_name(args)
    req = DeleteRoomRequest(room=room)
    await lk.room.delete_room(req)
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "deleted",
                    "room": room,
                },
                indent=2,
            ),
        )
    ]


async def _handle_list_rooms(lk, args):
    req = ListRoomsRequest()
    if "names" in args and args["names"]:
        req.names.extend(args["names"])

    result = await lk.room.list_rooms(req)
    rooms = [_proto_to_dict(r) for r in result.rooms]
    return [
        TextContent(
            type="text",
            text=json.dumps({"rooms": rooms}, indent=2),
        )
    ]


async def _handle_generate_join_token(args, api_key=None):
    url, api_key_val, api_secret = await get_livekit_credentials("resolve", api_key=api_key)

    room = _resolve_room_name(args)
    if not room:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "room or room_name is required to generate a join token"}),
            )
        ]

    token = AccessToken(api_key_val, api_secret)
    token.with_identity(args["identity"])
    token.with_name(args.get("name", ""))
    token.with_metadata(args.get("metadata", ""))
    token.with_ttl(timedelta(seconds=min(args.get("ttl", 300), 86400)))

    grants = VideoGrants(
        room_join=True,
        room=room,
        can_publish=args.get("can_publish", True),
        can_subscribe=args.get("can_subscribe", True),
        can_publish_data=args.get("can_publish_data", True),
        room_admin=args.get("room_admin", False),
        ingress_admin=args.get("ingress_admin", False),
        agent=args.get("agent", False),
    )
    token.with_grants(grants)

    jwt = token.to_jwt()
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "token": jwt,
                    "room": room,
                    "identity": args["identity"],
                    "url": url,
                },
                indent=2,
            ),
        )
    ]


async def _handle_list_participants(lk, args):
    room = _resolve_room_name(args)
    req = ListParticipantsRequest(room=room)
    result = await lk.room.list_participants(req)
    participants = [_proto_to_dict(p) for p in result.participants]
    return [
        TextContent(
            type="text",
            text=json.dumps({"participants": participants}, indent=2),
        )
    ]


async def _handle_get_participant(lk, args):
    room = _resolve_room_name(args)
    req = RoomParticipantIdentity(room=room, identity=args["identity"])
    result = await lk.room.get_participant(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_update_participant(lk, args):
    room = _resolve_room_name(args)
    req = UpdateParticipantRequest(room=room, identity=args["identity"])
    if "metadata" in args:
        req.metadata = args["metadata"]
    if "name" in args:
        req.name = args["name"]
    if "attributes" in args and args["attributes"]:
        req.attributes.update(args["attributes"])

    result = await lk.room.update_participant(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_remove_participant(lk, args):
    room = _resolve_room_name(args)
    req = RoomParticipantIdentity(room=room, identity=args["identity"])
    await lk.room.remove_participant(req)
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "removed",
                    "room": room,
                    "identity": args["identity"],
                },
                indent=2,
            ),
        )
    ]


async def _handle_mute_participant_track(lk, args):
    req = MuteRoomTrackRequest(
        room=_resolve_room_name(args),
        identity=args["identity"],
        track_sid=args["track_sid"],
        muted=args["muted"],
    )
    result = await lk.room.mute_published_track(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_update_room_metadata(lk, args):
    req = UpdateRoomMetadataRequest(room=_resolve_room_name(args), metadata=args["metadata"])
    result = await lk.room.update_room_metadata(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


def _dict_to_s3_upload(d):
    upload = S3Upload()
    if "access_key" in d:
        upload.access_key = d["access_key"]
    if "secret" in d:
        upload.secret = d["secret"]
    if "region" in d:
        upload.region = d["region"]
    if "endpoint" in d:
        upload.endpoint = d["endpoint"]
    if "bucket" in d:
        upload.bucket = d["bucket"]
    if "force_path_style" in d:
        upload.force_path_style = d["force_path_style"]
    return upload


def _dict_to_gcp_upload(d):
    upload = GCPUpload()
    if "credentials" in d:
        upload.credentials = d["credentials"]
    if "bucket" in d:
        upload.bucket = d["bucket"]
    return upload


def _dict_to_azure_upload(d):
    upload = AzureBlobUpload()
    if "account_name" in d:
        upload.account_name = d["account_name"]
    if "account_key" in d:
        upload.account_key = d["account_key"]
    if "container_name" in d:
        upload.container_name = d["container_name"]
    return upload


def _dict_to_alioss_upload(d):
    upload = AliOSSUpload()
    if "access_key" in d:
        upload.access_key = d["access_key"]
    if "secret" in d:
        upload.secret = d["secret"]
    if "region" in d:
        upload.region = d["region"]
    if "endpoint" in d:
        upload.endpoint = d["endpoint"]
    if "bucket" in d:
        upload.bucket = d["bucket"]
    return upload


def _dict_to_encoded_file_output(d):
    fo = EncodedFileOutput()
    if "filepath" in d:
        fo.filepath = d["filepath"]
    if "file_type" in d:
        fo.file_type = EncodedFileType.Value(d["file_type"])
    if "disable_manifest" in d:
        fo.disable_manifest = d["disable_manifest"]
    if "s3" in d and d["s3"]:
        fo.s3.CopyFrom(_dict_to_s3_upload(d["s3"]))
    if "gcp" in d and d["gcp"]:
        fo.gcp.CopyFrom(_dict_to_gcp_upload(d["gcp"]))
    if "azure" in d and d["azure"]:
        fo.azure.CopyFrom(_dict_to_azure_upload(d["azure"]))
    if "aliOSS" in d and d["aliOSS"]:
        fo.aliOSS.CopyFrom(_dict_to_alioss_upload(d["aliOSS"]))
    return fo


def _dict_to_stream_output(d):
    so = StreamOutput()
    if "protocol" in d:
        so.protocol = StreamProtocol.Value(d["protocol"])
    if "urls" in d and d["urls"]:
        so.urls.extend(d["urls"])
    return so


async def _handle_start_ingress(lk, args):
    input_type = IngressInput.Value(args["input_type"])
    req = CreateIngressRequest(input_type=input_type)
    if "url" in args:
        req.url = args["url"]
    if "name" in args:
        req.name = args["name"]
    room_name = _resolve_room_name(args)
    if room_name:
        req.room_name = room_name
    if "participant_identity" in args:
        req.participant_identity = args["participant_identity"]
    if "participant_name" in args:
        req.participant_name = args["participant_name"]
    if "enable_transcoding" in args:
        req.enable_transcoding = args["enable_transcoding"]

    result = await lk.ingress.create_ingress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_list_ingress(lk, args):
    req = ListIngressRequest()
    room_name = _resolve_room_name(args)
    if room_name:
        req.room_name = room_name
    if "ingress_id" in args:
        req.ingress_id = args["ingress_id"]

    result = await lk.ingress.list_ingress(req)
    items = [_proto_to_dict(i) for i in result.items]
    return [TextContent(type="text", text=json.dumps({"ingresses": items}, indent=2))]


async def _handle_start_room_composite_egress(lk, args):
    audio_only = args.get("audio_only", False)
    video_only = args.get("video_only", False)

    if audio_only and video_only:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "audio_only and video_only cannot both be true"}, indent=2
                ),
            )
        ]

    if not _validate_egress_outputs(args):
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "At least one output destination is required: filepath, stream_urls, file_outputs, or stream_outputs"
                    },
                    indent=2,
                ),
            )
        ]

    room_name = _resolve_room_name(args)
    req = RoomCompositeEgressRequest(room_name=room_name)

    if "layout" in args:
        req.layout = args["layout"]
    if audio_only:
        req.audio_only = True
    if video_only:
        req.video_only = True
    if "preset" in args:
        req.preset = EncodingOptionsPreset.Value(args["preset"])

    _apply_egress_outputs(req, args)

    result = await lk.egress.start_room_composite_egress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_list_egress(lk, args):
    req = ListEgressRequest()
    room_name = _resolve_room_name(args)
    if room_name:
        req.room_name = room_name
    if "egress_id" in args:
        req.egress_id = args["egress_id"]
    if "active" in args:
        req.active = args["active"]

    result = await lk.egress.list_egress(req)
    items = [_proto_to_dict(i) for i in result.items]
    return [TextContent(type="text", text=json.dumps({"egresses": items}, indent=2))]


async def _handle_stop_egress(lk, args):
    req = StopEgressRequest(egress_id=args["egress_id"])
    result = await lk.egress.stop_egress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_delete_ingress(lk, args):
    req = DeleteIngressRequest(ingress_id=args["ingress_id"])
    result = await lk.ingress.delete_ingress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_update_layout(lk, args):
    req = UpdateLayoutRequest(egress_id=args["egress_id"], layout=args["layout"])
    result = await lk.egress.update_layout(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_update_ingress(lk, args):
    req = UpdateIngressRequest(ingress_id=args["ingress_id"])
    if "name" in args:
        req.name = args["name"]
    room_name = _resolve_room_name(args)
    if room_name:
        req.room_name = room_name
    if "participant_identity" in args:
        req.participant_identity = args["participant_identity"]
    if "participant_name" in args:
        req.participant_name = args["participant_name"]
    if "enable_transcoding" in args:
        req.enable_transcoding = args["enable_transcoding"]

    result = await lk.ingress.update_ingress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_start_web_egress(lk, args):
    audio_only = args.get("audio_only", False)
    video_only = args.get("video_only", False)

    if audio_only and video_only:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "audio_only and video_only cannot both be true"}, indent=2
                ),
            )
        ]

    if not _validate_egress_outputs(args):
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "At least one output destination is required: filepath, stream_urls, file_outputs, or stream_outputs"
                    },
                    indent=2,
                ),
            )
        ]

    req = WebEgressRequest(url=args["url"])

    if audio_only:
        req.audio_only = True
    if video_only:
        req.video_only = True
    if "await_start_signal" in args:
        req.await_start_signal = args["await_start_signal"]
    if "preset" in args:
        req.preset = EncodingOptionsPreset.Value(args["preset"])

    _apply_egress_outputs(req, args)

    result = await lk.egress.start_web_egress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_start_participant_egress(lk, args):
    if not _validate_egress_outputs(args):
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "At least one output destination is required: filepath, stream_urls, file_outputs, or stream_outputs"
                    },
                    indent=2,
                ),
            )
        ]

    room_name = _resolve_room_name(args)
    req = ParticipantEgressRequest(
        room_name=room_name, identity=args["identity"]
    )

    if "screen_share" in args:
        req.screen_share = args["screen_share"]
    if "preset" in args:
        req.preset = EncodingOptionsPreset.Value(args["preset"])

    _apply_egress_outputs(req, args)

    result = await lk.egress.start_participant_egress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_start_track_composite_egress(lk, args):
    if not _validate_egress_outputs(args):
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "At least one output destination is required: filepath, stream_urls, file_outputs, or stream_outputs"
                    },
                    indent=2,
                ),
            )
        ]

    room_name = _resolve_room_name(args)
    req = TrackCompositeEgressRequest(room_name=room_name)

    if "audio_track_id" in args:
        req.audio_track_id = args["audio_track_id"]
    if "video_track_id" in args:
        req.video_track_id = args["video_track_id"]
    if "preset" in args:
        req.preset = EncodingOptionsPreset.Value(args["preset"])

    _apply_egress_outputs(req, args)

    result = await lk.egress.start_track_composite_egress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_start_track_egress(lk, args):
    has_shorthand = "filepath" in args or "websocket_url" in args

    if not has_shorthand:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "At least one output destination is required: filepath or websocket_url"
                    },
                    indent=2,
                ),
            )
        ]

    room_name = _resolve_room_name(args)
    req = TrackEgressRequest(room_name=room_name, track_id=args["track_id"])

    if "filepath" in args:
        req.file.CopyFrom(DirectFileOutput(filepath=args["filepath"]))
    if "websocket_url" in args:
        req.websocket_url = args["websocket_url"]

    result = await lk.egress.start_track_egress(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


async def _handle_update_stream(lk, args):
    req = UpdateStreamRequest(egress_id=args["egress_id"])
    if "add_output_urls" in args and args["add_output_urls"]:
        req.add_output_urls.extend(args["add_output_urls"])
    if "remove_output_urls" in args and args["remove_output_urls"]:
        req.remove_output_urls.extend(args["remove_output_urls"])

    result = await lk.egress.update_stream(req)
    return [TextContent(type="text", text=json.dumps(_proto_to_dict(result), indent=2))]


server = create_server


def get_initialization_options(server_instance: Server) -> InitializationOptions:
    return InitializationOptions(
        server_name="livekit-server",
        server_version="2.0.0",
        capabilities=server_instance.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )
