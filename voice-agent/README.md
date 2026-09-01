# Gerdoo voice agent

Runs on the Mac. The Jetson only joins the room — see
`docs/superpowers/specs/2026-08-30-livekit-voice-agent-design.md`.

## Running

Two processes, two terminals:

```bash
livekit-server --config livekit.yaml
python3 agent.py dev
```

## Testing without the robot

```bash
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=<your-key>        # from your livekit.yaml
export LIVEKIT_API_SECRET=<your-secret>  # from your livekit.yaml
lk room join --identity tester --publish-mic gerdoo
```

## Notes

- `livekit.yaml` binds `::` on purpose. If your Mac's hostname has
  AAAA records only, an IPv4-only listener is unreachable by name.
  `livekit.yaml` is gitignored — copy it from `livekit.yaml.example`.
- `.env` holds the ElevenLabs and LiteLLM keys and is gitignored. Only the
  LiveKit key/secret is shared with the Jetson, which needs it to sign tokens.
- Unit tests: `python3 -m pytest tests/ -v`