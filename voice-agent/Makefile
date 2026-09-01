# Gerdoo voice agent — bring the Mac side up and down.
#
# Two processes make a conversation possible: the LiveKit server (rooms/SFU)
# and the agent worker (STT -> LLM -> TTS). Both run here, never on the Jetson;
# the robot only joins a room. See ../docs/superpowers/specs/.
#
#   make check    what is missing before anything will work
#   make up       start both, in the background
#   make status   what is running
#   make logs     follow both logs
#   make join     talk to the agent from this Mac, no robot involved
#   make down     stop both
#
# Credentials live in .env (gitignored). Copy .env.example if it is missing.

SHELL := /bin/bash
.DEFAULT_GOAL := help

RUN  := run
LOGS := logs
SERVER_PID := $(RUN)/server.pid
AGENT_PID  := $(RUN)/agent.pid
SERVER_LOG := $(LOGS)/server.log
AGENT_LOG  := $(LOGS)/agent.log
PORT := 7880

# Load .env into the environment of every recipe that needs it. `set -a` marks
# everything sourced afterwards for export, which is how the agent and the lk
# CLI pick up credentials without them ever appearing on a command line.
LOADENV := set -a; . ./.env; set +a;

.PHONY: help check up down restart server agent agent-dev status logs console join test voices clean

help:
	@echo "Gerdoo voice agent"
	@echo
	@echo "  make check     preflight — env, dependencies, port"
	@echo "  make up        start the LiveKit server and the agent"
	@echo "  make status    show what is running"
	@echo "  make logs      follow both logs (ctrl-C to stop watching)"
	@echo "  make console   talk to the agent using this Mac's mic and speakers"
	@echo "  make join      open LiveKit Meet in a browser, joined to the room"
	@echo "  make voices    list the ElevenLabs voices on your account"
	@echo "  make agent-dev run the agent in the foreground with hot reload"
	@echo "  make test      run the unit tests"
	@echo "  make down      stop both"

# ---------------------------------------------------------------------------

check:
	@ok=1; \
	if [ ! -f .env ]; then \
	  echo "MISSING  .env          — run: cp .env.example .env"; ok=0; \
	else \
	  echo "found    .env"; \
	  $(LOADENV) \
	  for v in LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET ELEVEN_API_KEY ELEVEN_VOICE_ID LITELLM_BASE_URL LITELLM_API_KEY LITELLM_MODEL; do \
	    if [ -z "$${!v}" ]; then echo "MISSING  $$v        — set it in .env"; ok=0; \
	    else echo "set      $$v"; fi; \
	  done; \
	fi; \
	command -v livekit-server >/dev/null && echo "found    livekit-server" \
	  || { echo "MISSING  livekit-server — brew install livekit"; ok=0; }; \
	command -v lk >/dev/null && echo "found    lk" \
	  || echo "note     lk not found — only needed for 'make join'"; \
	python3 -c "import livekit.agents, livekit.plugins.elevenlabs, livekit.plugins.openai, livekit.plugins.silero, dotenv" 2>/dev/null \
	  && echo "found    python deps" \
	  || { echo "MISSING  python deps  — pip3 install livekit-agents livekit-plugins-elevenlabs livekit-plugins-openai livekit-plugins-silero python-dotenv"; ok=0; }; \
	if lsof -nP -iTCP:$(PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  echo "note     port $(PORT) already in use (server may already be up)"; \
	else echo "free     port $(PORT)"; fi; \
	echo; \
	[ $$ok -eq 1 ] && echo "ready — run 'make up'" \
	  || { echo "not ready — fix the MISSING lines above"; exit 1; }

# ---------------------------------------------------------------------------

up: check server agent
	@echo
	@$(MAKE) --no-print-directory status
	@echo
	@echo "Say \"Gerdoo, baba\" to the robot, or run 'make join' to test from here."

server:
	@mkdir -p $(RUN) $(LOGS)
	@if lsof -nP -iTCP:$(PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  echo "server   already listening on $(PORT), leaving it alone"; \
	else \
	  nohup livekit-server --config livekit.yaml > $(SERVER_LOG) 2>&1 & echo $$! > $(SERVER_PID); \
	  sleep 2; \
	  if lsof -nP -iTCP:$(PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	    echo "server   started (pid $$(cat $(SERVER_PID)))"; \
	  else \
	    echo "server   FAILED to start — last lines of $(SERVER_LOG):"; \
	    tail -15 $(SERVER_LOG); exit 1; \
	  fi; \
	fi

# `start` rather than `dev`: dev mode forks a reloader, so the recorded pid
# would not be the process actually doing the work and 'make down' would leave
# an orphan holding the room.
agent:
	@mkdir -p $(RUN) $(LOGS)
	@if [ -f $(AGENT_PID) ] && kill -0 $$(cat $(AGENT_PID)) 2>/dev/null; then \
	  echo "agent    already running (pid $$(cat $(AGENT_PID)))"; \
	else \
	  $(LOADENV) nohup python3 agent.py start > $(AGENT_LOG) 2>&1 & echo $$! > $(AGENT_PID); \
	  sleep 4; \
	  if kill -0 $$(cat $(AGENT_PID)) 2>/dev/null; then \
	    echo "agent    started (pid $$(cat $(AGENT_PID)))"; \
	  else \
	    echo "agent    FAILED to start — last lines of $(AGENT_LOG):"; \
	    tail -20 $(AGENT_LOG); exit 1; \
	  fi; \
	fi

# Foreground, with hot reload. Use this while editing agent.py.
agent-dev:
	@$(LOADENV) python3 agent.py dev

down:
	@for f in $(AGENT_PID) $(SERVER_PID); do \
	  if [ -f $$f ]; then \
	    pid=$$(cat $$f); \
	    if kill -0 $$pid 2>/dev/null; then kill $$pid && echo "stopped  pid $$pid"; \
	    else echo "stale    $$f (not running)"; fi; \
	    rm -f $$f; \
	  fi; \
	done; \
	pkill -f "livekit-server --config livekit.yaml" 2>/dev/null && echo "stopped  stray livekit-server" || true; \
	pkill -f "agent.py start" 2>/dev/null && echo "stopped  stray agent" || true; \
	echo "down"

restart: down up

status:
	@if lsof -nP -iTCP:$(PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  echo "server   UP    port $(PORT)"; else echo "server   DOWN"; fi
	@if [ -f $(AGENT_PID) ] && kill -0 $$(cat $(AGENT_PID)) 2>/dev/null; then \
	  echo "agent    UP    pid $$(cat $(AGENT_PID))"; \
	  grep -q "registered worker" $(AGENT_LOG) 2>/dev/null \
	    && echo "         registered with the server" \
	    || echo "         WARNING: no 'registered worker' in $(AGENT_LOG) yet"; \
	else echo "agent    DOWN"; fi

logs:
	@tail -f $(SERVER_LOG) $(AGENT_LOG)

# The pipeline test. Runs a private agent session against this Mac's own mic
# and speakers — no server, no room, no robot. If STT, the LLM or TTS is
# misconfigured, it fails here, where nothing else can be blamed.
#
# Ctrl-C to leave. This is a separate agent instance; the one started by
# `make up` keeps running and is unaffected.
console:
	@$(LOADENV) python3 agent.py console

# The room test. Opens LiveKit Meet in a browser, joined to the same room the
# robot uses — the closest thing to the real path without the robot.
#
# `lk` cannot publish a live microphone (no --publish-mic flag exists; it only
# publishes files), so a browser is the only way to speak into a room from here.
join:
	@$(LOADENV) LIVEKIT_URL=ws://localhost:$(PORT) \
	  lk room join --identity tester --open meet gerdoo

voices:
	@python3 list_voices.py

test:
	@python3 -m pytest tests/ -v

clean: down
	@rm -rf $(RUN) $(LOGS)
	@echo "removed run/ and logs/"
