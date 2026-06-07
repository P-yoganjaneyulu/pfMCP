# LiveKit Server

pfMCP server implementation for managing **LiveKit** rooms, participants, and access tokens.

---

### Prerequisites

- Python 3.11+
- A LiveKit server (self-hosted or [LiveKit Cloud](https://cloud.livekit.io))
- LiveKit API credentials

---

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIVEKIT_URL` | Yes | LiveKit server URL (e.g., `http://localhost:7880` or `wss://my-project.livekit.cloud`) |
| `LIVEKIT_API_KEY` | Yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | Yes | LiveKit API secret |

---

### Supported Tools (Phase 1)

| Tool | Description |
|------|-------------|
| `create_room` | Create a new LiveKit room |
| `delete_room` | Delete a LiveKit room |
| `list_rooms` | List all LiveKit rooms |
| `generate_join_token` | Generate a JWT token for joining a room |
| `list_participants` | List participants in a room |
| `get_participant` | Get details about a specific participant |
| `update_participant` | Update participant metadata or permissions |
| `remove_participant` | Remove a participant from a room |
| `mute_participant_track` | Mute or unmute a participant's track |
| `update_room_metadata` | Update metadata for a LiveKit room |

---

### Run

#### Local Development

```bash
./start_sse_dev_server.sh
```

Or via stdio:

```bash
python src/servers/local.py --server=livekit
```

---

### Notes

- LiveKit credentials are resolved server-side and never exposed to tool callers.
- For local development, set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in your `.env` file.
- Make sure your `.env` file contains an `ANTHROPIC_API_KEY` if using external LLM test clients.

---

### Upcoming Tools

- **Ingress** — Start, list, update, and delete media ingress
- **Egress** — Room composite, participant, track, and web egress
- **Webhooks** — Webhook event validation and processing
- **Data APIs** — Send data, publish text/bytes/RPC to rooms
- **Agent Dispatch** — Create, list, and delete agent dispatches
- **SIP** — Trunk and dispatch rule management
- **Analytics** — LiveKit Cloud analytics queries

---

### Resources

- [LiveKit Docs](https://docs.livekit.io)
- [LiveKit Python API Reference](https://docs.livekit.io/reference/python/v1/)
