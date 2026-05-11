# Voice + Model Chain Architecture

## Overview

AgencyOS voice conversations allow users to speak with department heads naturally. The system uses a tiered model chain to keep costs low while maintaining quality, and Whisper STT + TTS for voice I/O.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        Voice UI Layer                         │
│  ┌──────┐  ┌───────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Idle │→ │ Listening  │→ │ Thinking │→ │   Speaking     │  │
│  │  🎤  │  │ (pulsing) │  │ (spinner)│  │  (waveform)    │  │
│  └──────┘  └───────────┘  └──────────┘  └────────────────┘  │
└──────────────┬───────────────────────────────────┬───────────┘
               │ Audio blob                        │ Audio response
               ▼                                   ▲
┌──────────────────────┐            ┌──────────────────────────┐
│   STT: Whisper       │            │   TTS: OpenWebUI TTS     │
│   (local, via OWUI)  │            │   (ElevenLabs / local)   │
└──────────┬───────────┘            └──────────────┬───────────┘
           │ Text                                  │ Text
           ▼                                       ▲
┌──────────────────────────────────────────────────────────────┐
│                    Model Chain Router                         │
│                                                              │
│  ┌─────────────────┐   ┌──────────────┐  ┌───────────────┐  │
│  │  Local (Gemma 9B)│   │ Mid (Gemini) │  │Premium (Claude)│  │
│  │  ~80% of queries │   │ ~15% escal.  │  │ ~5% Chief only │  │
│  │  Intent, Q&A,    │   │ Proposals,   │  │ Cross-dept     │  │
│  │  conversation    │   │ reasoning    │  │ coordination   │  │
│  └────────┬────────┘   └──────┬───────┘  └──────┬────────┘  │
│           │                   │                  │            │
│           └───────────┬───────┘──────────────────┘            │
│                       ▼                                      │
│              ┌─────────────────┐                             │
│              │ Deterministic   │  No model needed            │
│              │ Tool Execution  │  CRM lookups, scheduling,   │
│              │                 │  data retrieval              │
│              └─────────────────┘                             │
└──────────────────────────────────────────────────────────────┘
```

## Voice Pipeline

### 1. STT — Speech to Text

Leverages OpenWebUI's existing Whisper integration:
- **Model:** `whisper-large-v3` (local via Ollama or faster-whisper)
- **Endpoint:** `POST /api/v1/audio/transcriptions` (already in OpenWebUI)
- **Latency target:** <1.5s for 10s of audio
- **Language:** Auto-detect, with user locale hint

```
Browser MediaRecorder → WebSocket/POST → Whisper → text
```

### 2. TTS — Text to Speech

Uses OpenWebUI's configurable TTS backend:
- **Primary:** ElevenLabs API (natural voices, ~$0.30/1K chars)
- **Fallback:** Local Piper TTS (free, slightly robotic)
- **Endpoint:** `POST /api/v1/audio/speech` (already in OpenWebUI)
- **Streaming:** Chunked audio for low time-to-first-byte

## Model Chain Router

### Tier Architecture

| Tier | Model | Use Case | % of Queries | Cost/1K tokens |
|------|-------|----------|-------------|----------------|
| **Local** | Gemma 9B (Ollama) | Intent classification, simple Q&A, conversation flow, greetings | ~80% | ~$0 (compute only) |
| **Mid** | Gemini 1.5 Flash/Pro | Complex reasoning, proposal drafting, document analysis | ~15% | ~$0.075-0.30 |
| **Premium** | Claude Opus/Sonnet | Chief AI cross-dept coordination, strategic decisions | ~5% | ~$3-15 |
| **Deterministic** | None | Tool calls (CRM read, schedule check, data lookup) | N/A | $0 |

### Escalation Logic

The local model (Gemma 9B) acts as the **first responder** and **intent classifier**:

```
User message
    │
    ▼
┌─────────────────────────┐
│ Gemma 9B: Classify      │
│ intent + complexity      │
│                         │
│ Outputs:                │
│  - intent: string       │
│  - complexity: 1-5      │
│  - needs_tool: bool     │
│  - department: string   │
│  - can_handle: bool     │
└────────┬────────────────┘
         │
    ┌────┴────────────────────────┐
    │                             │
    ▼ can_handle=true             ▼ can_handle=false
┌──────────────┐          ┌─────────────────┐
│ Gemma answers │          │ complexity ≤ 3?  │
│ directly      │          │                 │
└──────────────┘          └───┬─────────┬───┘
                              │ yes     │ no
                              ▼         ▼
                        ┌──────────┐ ┌──────────────┐
                        │ Gemini   │ │ Claude       │
                        │ handles  │ │ (Chief only) │
                        └──────────┘ └──────────────┘
```

**Escalation triggers (local → mid):**
- Complexity score ≥ 3
- Proposal drafting required
- Multi-step reasoning
- Document analysis / summarization
- Ambiguous intent after 1 retry

**Escalation triggers (mid → premium):**
- Cross-department coordination needed
- Strategic/executive-level decisions
- Chief AI chat (always premium)
- Risk level "critical" on proposals

### Deterministic Tool Layer

Actions that don't need a model at all:
- CRM data lookups (contact info, pipeline status)
- Calendar/schedule queries
- Invoice status checks
- Simple calculations
- Template-based responses (onboarding checklists, etc.)

These are routed directly by intent classification without ever hitting a mid/premium model.

## Sequence Diagrams

### Standard Department Voice Conversation

```
User          VoiceUI       Whisper      ModelRouter    Gemma9B      Department
 │               │             │             │            │             │
 │──[tap mic]──→│             │             │            │             │
 │               │──[listen]──│             │            │             │
 │──[speak]────→│             │             │            │             │
 │               │──[audio]──→│             │            │             │
 │               │             │──[text]───→│            │             │
 │               │             │             │──[classify]→│            │
 │               │             │             │            │──[intent]──│
 │               │             │             │            │             │
 │               │             │    can_handle=true       │             │
 │               │             │             │←──[response]│            │
 │               │             │             │──[TTS]────→│            │
 │               │←──────────[audio]─────────│            │             │
 │←──[speak]────│             │             │            │             │
```

### Escalated Conversation (Local → Mid)

```
User          VoiceUI       Whisper      ModelRouter    Gemma9B     Gemini
 │               │             │             │            │           │
 │──[speak]────→│──[audio]──→│──[text]───→│            │           │
 │               │             │             │──[classify]→│          │
 │               │             │             │            │           │
 │               │             │  can_handle=false, complexity=3     │
 │               │             │             │←──[escalate]│          │
 │               │             │             │──[full ctx]──────────→│
 │               │             │             │←──────[response]──────│
 │               │             │             │──[TTS]                │
 │←──[speak]────│←──[audio]──│             │            │           │
```

### Chief AI Cross-Department Coordination

```
User          VoiceUI       Whisper      ModelRouter    Claude     Dept_A   Dept_B
 │               │             │             │            │          │        │
 │──[speak]────→│──[audio]──→│──[text]───→│            │          │        │
 │               │             │             │──[premium]→│          │        │
 │               │             │             │            │──[query]→│        │
 │               │             │             │            │←[data]───│        │
 │               │             │             │            │──[query]──────→│
 │               │             │             │            │←[data]─────────│
 │               │             │             │←──[coordinated response]──│
 │               │             │             │──[TTS]                    │
 │←──[speak]────│←──[audio]──│             │            │          │        │
```

## Cost Analysis

### Why This Pattern Keeps SaaS Margins Healthy

**Assumptions (per customer/month):**
- 500 voice interactions/month
- Average 3 turns per conversation = 1,500 model calls

**Cost breakdown:**

| Component | Volume | Unit Cost | Monthly Cost |
|-----------|--------|-----------|-------------|
| Gemma 9B (local) | 1,200 calls (80%) | ~$0 (GPU amortized) | ~$2.00 compute |
| Gemini Flash | 225 calls (15%) | ~$0.01/call avg | ~$2.25 |
| Claude | 75 calls (5%) | ~$0.15/call avg | ~$11.25 |
| Whisper (local) | 1,500 transcriptions | ~$0 (GPU amortized) | ~$1.50 compute |
| TTS (ElevenLabs) | 1,500 responses (~200 chars avg) | $0.30/1K chars | ~$9.00 |
| **Total** | | | **~$26.00/month** |

**At $499/mo starter plan:** ~95% gross margin on AI costs  
**At $999/mo growth plan:** ~97% gross margin on AI costs

**Compare to naive approach (all Claude):**
- 1,500 calls × $0.15 = $225/month → only 55% margin on starter plan

**The 80/15/5 split saves ~$200/customer/month** while maintaining quality where it matters.

### Scaling Economics

At 100 customers:
- Tiered approach: ~$2,600/month AI costs
- All-premium: ~$22,500/month AI costs
- **Savings: $19,900/month**

The local Gemma 9B model handles the "long tail" of simple interactions that don't need expensive reasoning. A single GPU server (~$200/month) can serve hundreds of customers' local-tier queries.

## Integration Points

### Existing Orchestrator (`services/orchestrator.py`)

The voice pipeline feeds into the existing `Orchestrator.route_message()`:

```python
# Voice-specific flow in orchestrator
async def route_voice_message(
    self,
    audio_text: str,          # From Whisper
    org_id: str,
    user_id: str,
    department_slug: str | None,
    chat_id: str | None,
    conversation_history: list[dict],
) -> dict:
    # 1. Intent classification via local model (Gemma)
    intent = await self.classify_intent(audio_text, conversation_history)
    
    # 2. Route based on classification
    if intent.needs_tool and not intent.needs_model:
        result = await self.execute_deterministic(intent)
    elif intent.can_handle_locally:
        result = await self.model_router.generate(tier="local", ...)
    elif department_slug is None:  # Chief AI
        result = await self.model_router.generate(tier="premium", ...)
    else:
        result = await self.model_router.generate(tier="mid", ...)
    
    # 3. Extract proposals if present
    proposals = self._extract_proposals(result["content"], ...)
    
    return {**result, "proposals": proposals, "tts_text": result["content"]}
```

### Existing ModelRouter (`services/model_router.py`)

No changes needed — the ModelRouter already supports tier-based routing with fallback chains. Voice just uses the same `generate()` method with the tier determined by the intent classifier.

### Voice UI Component (`VoiceMode.svelte`)

Integrates with the chat interface:

```
VoiceMode.svelte
  ├── Uses: /api/v1/audio/transcriptions (existing OpenWebUI endpoint)
  ├── Uses: /api/v1/audio/speech (existing OpenWebUI endpoint)
  ├── Calls: /api/agencyos/departments/{slug}/chat (existing AgencyOS endpoint)
  └── Updates: Chat message store (existing OpenWebUI store)
```

### WebSocket Integration

For real-time voice streaming (future enhancement):
- OpenWebUI already has Socket.IO set up
- Voice chunks can be streamed for faster STT
- TTS audio can be streamed back for lower latency
- Events: `voice:start`, `voice:chunk`, `voice:end`, `voice:response`

## Implementation Phases

### Phase 1: Voice UI Shell (Current)
- VoiceMode.svelte with visual states
- MediaRecorder integration
- Audio blob capture and playback

### Phase 2: STT/TTS Integration
- Connect to OpenWebUI's Whisper endpoint
- Connect to OpenWebUI's TTS endpoint
- End-to-end voice → text → response → audio

### Phase 3: Model Chain Intelligence
- Intent classifier prompt for Gemma 9B
- Escalation logic in orchestrator
- Deterministic tool routing

### Phase 4: Streaming & Polish
- WebSocket audio streaming
- Interrupt handling (user speaks while AI is responding)
- Voice activity detection (VAD) for auto-start/stop
- Conversation memory across voice turns
