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
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret-at-least-32-characters-long-x
lk room join --identity tester --publish-mic gerdoo
```

## Notes

- `livekit.yaml` binds `::` on purpose. `mac-studio.local` has
  AAAA records only, so an IPv4-only listener is unreachable by name.
- `.env` holds the ElevenLabs and LiteLLM keys and is gitignored. Only the
  LiveKit key/secret is shared with the Jetson, which needs it to sign tokens.
- Unit tests: `python3 -m pytest tests/ -v`