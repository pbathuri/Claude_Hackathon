# WHO-Aligned AI Health Access Service

An AI-powered telehealth platform for underserved populations. Users call a phone number or use a web interface to describe symptoms via voice. A Claude-powered AI assistant, guided by a self-evolving medical knowledge graph, conducts a structured intake conversation. Cases are triaged, mapped to ICD-11 codes, scored by priority, and routed to a doctor dashboard where licensed practitioners review, respond, and trigger knowledge graph learning.

## Live URLs

| Service | URL |
|---------|-----|
| Doctor Portal | https://doctor-portal-flax.vercel.app |
| Backend API | https://claude-hackathon-u86l.onrender.com |
| API Documentation | https://claude-hackathon-u86l.onrender.com/docs |
| Web Caller Simulator | https://claude-hackathon-u86l.onrender.com/call |
| Phone Number | **+1 (478) 812-5405** |

## How It Works

```
                          +1 (478) 812-5405
                                |
                          [Twilio Voice]
                                |
    [Web Caller] -----> [FastAPI Backend] -----> [Claude AI]
    (Browser STT)       |              |         (Conversation)
    (ElevenLabs TTS)    |              |
                        v              v
                  [Knowledge       [Triage +
                   Graph]           ICD-11]
                  293 nodes         START protocol
                  448 edges         Priority scoring
                        |              |
                        v              v
                  [Doctor Portal] <-- [Case Queue]
                  (Next.js/Vercel)    Auto-refresh
                        |
                        v
                  [Doctor Responds]
                        |
                        v
                  [KG Backpropagation]
                  Graph learns from outcomes
```

### Step-by-Step User Flow

1. **Caller dials +1 (478) 812-5405** (or opens the web caller at `/call`)
2. System detects country from phone number, loads the WHO-mandated verbal disclosure for that jurisdiction's tier
3. **Caller speaks symptoms**: "I have fever and headache for three days"
4. Backend extracts symptoms using Knowledge Graph node matching
5. KG Navigator activates conditions (Malaria, Dengue, Meningitis...) and scores follow-up questions
6. **Claude AI generates a natural response** incorporating the top KG-suggested question
7. Caller responds with more information across 3-5 turns
8. System extracts severity, duration, and body area from the conversation
9. When completion criteria are met (5+ symptoms, high graph confidence, or 6+ turns), case auto-submits
10. Backend runs START triage, maps symptoms to ICD-11 codes, computes priority score
11. **Case appears on the Doctor Portal** within 5 seconds (auto-refresh)
12. Doctor reviews case with embedded KG insights (predicted conditions, recommended specialty)
13. Doctor submits guidance and diagnosis
14. **KG Backpropagation**: correct paths strengthen, wrong paths weaken, graph literally learns

### Step-by-Step Doctor Flow

1. Open https://doctor-portal-flax.vercel.app
2. Dashboard shows live case count, triage distribution, country breakdown
3. Cases auto-refresh every 5 seconds with audio notification for new arrivals
4. Click a case to see full details: symptoms, AI notes, red flags, KG insights panel
5. KG Insights panel shows predicted conditions with scores, recommended specialty, body system mapping
6. Enter diagnosis and guidance text, submit
7. System triggers KG backpropagation: edges on the correct symptom-to-condition path are reinforced
8. The Knowledge Graph page (`/knowledge-graph`) shows the graph stats, hottest medical pathways, and symptom explorer

## Architecture

### Backend (FastAPI on Render)

```
backend/
  main.py                         # FastAPI app, CORS, lifespan, router registration
  config.py                       # Environment config, API keys, database URL
  database.py                     # SQLAlchemy + SQLite
  models.py                       # Patient, Case, DoctorProfile, Response, FollowUp, CountryPermission
  requirements.txt                # Python dependencies
  Procfile                        # Render/Railway start command
  routers/
    caller.py                     # Caller API: session/start, consent, submit, ai-turn, TTS, upload
    twilio_voice.py               # Twilio webhooks: /twilio/voice, /twilio/gather
    cases.py                      # Case management: queue, assign, respond, patient-cases
    doctors.py                    # Doctor registration, listing, verification
    knowledge_graph.py            # KG API: navigate, query, backpropagate, stats, search
    intake.py                     # Claude-powered intake agent
    health_data.py                # WHO/ICD-11 data endpoints
  services/
    case_service.py               # Case creation, intake completion, priority scoring
    country_service.py            # Phone parsing, country permissions, 4-tier model
    triage_service.py             # START triage protocol, emergency detection
    icd11_service.py              # NLM ICD-11 API mapping
    intake_service.py             # Claude intake agent orchestration
    priority_queue.py             # Multi-factor priority scoring
    scheduler_service.py          # Background jobs (expiration, follow-ups)
    who_service.py                # WHO GHO API integration
  knowledge_graph/
    graph_engine.py               # Physarum-inspired core: nodes, edges, conductivity, decay, chemotaxis
    seed_data.py                  # 106 symptoms, 80 conditions, 22 specialties, 600+ curated edges
    navigator.py                  # Conversation navigator: activation spreading, question scoring
    backpropagator.py             # Post-case learning: reinforce correct paths, weaken wrong ones
    doctor_matcher.py             # Graph-based doctor ranking by conductivity-weighted specialty
    builder.py                    # Graph construction from seed data
    data_pipeline.py              # ICD-11 API, MedlinePlus, WHO GHO enrichment pipeline
    simulation.py                 # 60-case simulation with Seaborn visualizations
    scraper.py                    # Scrapling-based medical data scraper
  static/
    caller.html                   # Web caller simulator (STT + ElevenLabs TTS + chat UI)
  test_e2e.py                     # 41-test E2E suite (97% pass rate)
```

### Doctor Portal (Next.js on Vercel)

```
doctor-portal/
  app/
    page.tsx                      # Dashboard: live stats, triage chart, doctor status
    cases/
      page.tsx                    # Case queue: filterable, sortable, auto-refresh, notifications
      [id]/page.tsx               # Case detail: KG insights, response form, backpropagation
    knowledge-graph/
      page.tsx                    # KG explorer: stats, hottest paths, symptom search
    layout.tsx                    # Root layout with dark sidebar
    globals.css                   # Tailwind + custom styles
  components/
    Sidebar.tsx                   # Navigation sidebar
    KGInsightsPanel.tsx           # KG-derived insights (uses embedded case data or API fallback)
    UrgencyBadge.tsx              # START triage color coding (Red/Yellow/Green)
    ComplianceBanner.tsx          # "This system provides guidance only" disclaimer
    CountryIndicator.tsx          # Country flags + tier tooltip
    PriorityBar.tsx               # Color-coded priority progress bar
    RedFlagBadge.tsx              # Red flag warning indicators
    MiniGraph.tsx                 # SVG symptom-condition-specialty graph
    PieChart.tsx                  # SVG donut chart
    BarChart.tsx                  # CSS bar chart
    StatsCard.tsx                 # Dashboard stat card
    LoadingSpinner.tsx            # Loading state
  lib/
    api.ts                        # API client with error handling
    mock-data.ts                  # Fallback mock data for offline demo
  types/
    index.ts                      # TypeScript interfaces
```

### Caller API (Teammate 2's voice pipeline)

```
src/
  main.py                         # FastAPI server with LangGraph integration
  config.py                       # Ollama/Whisper/Piper config + backend_url
  graph.py                        # LangGraph pipeline: STT -> LLM -> TTS with emergency check
  prompts.py                      # WHO-aligned system prompt with safety guardrails
```

## Knowledge Graph

The medical knowledge graph uses three bio-inspired algorithms:

### Physarum polycephalum (Slime Mold)
Edge conductivity strengthens with use and decays without. Each patient conversation sends "flow" through symptom-condition-specialty paths. Well-validated medical relationships grow stronger over time, while unused ones fade.

```
conductivity(t+1) = (1 - decay) * conductivity(t) + reinforcement * flow
```

### E. coli Chemotaxis
Navigation follows high-conductivity gradients (chemotactic gradient) with a 15% random "tumble" exploration rate. This prevents the graph from collapsing to a single pathway and ensures rare conditions are still discoverable.

### Branching Leaf Syndrome
When symptom co-occurrence exceeds a threshold (3 occurrences), new edges sprout automatically. The graph grows dendritically, discovering medical relationships that weren't in the original seed data.

### Graph Statistics
- **293 nodes**: 106 symptoms, 80 conditions, 22 specialties, 24 follow-up questions, 20 medications, 18 risk factors, 13 body systems, 10 demographics
- **448 edges**: indicates, treated_by, located_in, risk_for, managed_with, presents_with, follow_up, demographic_risk
- **Simulation results**: 68.3% top-1 accuracy, 80% top-3 accuracy across 60 synthetic cases
- **Self-evolution**: 152 new edges learned through branching leaf syndrome in simulation

## Country Permission Matrix (WHO-Aligned)

| Country | Code | Tier | Can Diagnose | Can Treat | Can Prescribe | Can Refer |
|---------|------|------|-------------|-----------|--------------|-----------|
| India | IN | 1 | Yes | Yes | Yes | Yes |
| Nigeria | NG | 2 | Yes | Yes | No | Yes |
| Kenya | KE | 3 | Yes | Guidance only | No | Yes |
| Philippines | PH | 3 | Yes | Guidance only | No | Yes |

Each tier determines the verbal disclosure script, the capability card shown to the patient, and the physician status bar on the doctor portal.

## API Endpoints

### Caller API (`/caller`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/caller/session/start` | Start session: phone -> country -> tier -> case_id |
| POST | `/caller/session/consent` | Record disclaimer acknowledgment |
| POST | `/caller/ai-turn` | Claude-powered conversation turn with KG guidance |
| POST | `/caller/session/submit` | Submit completed intake for triage + ICD-11 |
| GET | `/caller/session/{id}` | Check case status |
| GET | `/caller/disclosure/{cc}` | Verbal disclosure script per country |
| POST | `/caller/emergency-check` | Mid-conversation emergency detection |
| POST | `/caller/tts` | ElevenLabs text-to-speech |
| POST | `/caller/upload-image` | Image upload from web caller |

### Twilio Voice (`/twilio`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/twilio/voice` | Incoming call webhook |
| POST | `/twilio/gather` | Speech recognition result callback |

### Cases (`/cases`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/cases/queue` | Doctor case queue |
| GET | `/cases/patient-cases` | Frontend contract case list |
| GET | `/cases/patient-cases/{id}` | Frontend contract case detail |
| POST | `/cases/{id}/assign` | Assign case to doctor |
| POST | `/cases/{id}/respond` | Doctor submits guidance |

### Knowledge Graph (`/kg`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/kg/query` | Stateless symptom query |
| POST | `/kg/navigate` | Case-bound KG navigation |
| POST | `/kg/backpropagate` | Post-case learning |
| POST | `/kg/match-doctors` | Graph-based doctor matching |
| GET | `/kg/stats` | Graph statistics + specialty heatmap |
| GET | `/kg/hottest-paths` | Top conductivity edges |
| GET | `/kg/conditions/{name}` | Conditions for a symptom |
| GET | `/kg/search` | Fuzzy node search |
| GET | `/kg/subgraph/{name}` | Subgraph visualization |
| POST | `/kg/decay` | Trigger global Physarum decay |

### Doctors (`/doctors`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/doctors/` | Register doctor |
| GET | `/doctors/` | List doctors |
| GET | `/doctors/{id}` | Doctor profile |
| PATCH | `/doctors/{id}` | Update availability |

## Setup Guide

### Prerequisites
- Python 3.13+
- Node.js 18+
- npm

### Local Development

**Backend:**
```bash
cd backend
cp .env.example .env
# Edit .env with your API keys:
#   ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
#   ELEVENLABS_MODEL_ID, TWILIO_ACCOUNT_SID, TWILIO_API_KEY_SID,
#   TWILIO_API_KEY_SECRET, TWILIO_PHONE_NUMBER

pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Doctor Portal:**
```bash
cd doctor-portal
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

**Web Caller:** Open http://localhost:8000/call

### Production Deployment

**Backend (Render.com):**
1. Connect GitHub repo on Render dashboard
2. Set Root Directory: (leave empty, uses root `requirements.txt` redirect)
3. Set Build Command: `pip install -r requirements.txt`
4. Set Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables (see `.env.example`)
6. Add `SKIP_PIPELINE_ENRICHMENT=1` for fast startup

**Doctor Portal (Vercel):**
```bash
cd doctor-portal
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com vercel --prod
```

**Twilio Phone Number:**
The voice webhook is configured to point at the backend's `/twilio/voice` endpoint. Update via:
```bash
curl -X POST "https://api.twilio.com/2010-04-01/Accounts/{SID}/IncomingPhoneNumbers/{PHONE_SID}.json" \
  -u "{API_KEY_SID}:{API_KEY_SECRET}" \
  -d "VoiceUrl=https://your-backend.onrender.com/twilio/voice" \
  -d "VoiceMethod=POST"
```

## Testing

Run the 41-test E2E suite:
```bash
cd backend
python test_e2e.py
```

Tests cover:
- Caller workflow: session start (4 countries), consent, emergency check, submit, status
- Doctor workflow: register, queue, assign, respond, case lifecycle
- Knowledge Graph: 15 endpoints including navigation, backpropagation, doctor matching
- Frontend contract: all required fields present, filtering, CORS

Run the 60-case KG simulation:
```bash
cd backend
python -m knowledge_graph.simulation
```

Generates 5 Seaborn visualizations in `data/viz/`:
- `evolution_heatmap.png` — Edge conductivity evolution across 60 cases
- `accuracy_curve.png` — Prediction accuracy over time
- `specialty_heatmap.png` — Specialty demand by country
- `edge_sprouting.png` — New edges discovered via branching leaf syndrome
- `network_snapshot.png` — Before/after network with color-coded changes

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| AI Conversation | Claude claude-sonnet-4-20250514 (Anthropic) | Multi-turn symptom intake with KG context |
| Voice (Phone) | Twilio Voice + Gather | Phone call intake with speech recognition |
| Voice (Web) | Browser SpeechRecognition + ElevenLabs | Web-based STT and human-like TTS |
| Backend | FastAPI + SQLAlchemy + SQLite | REST API, case management, triage |
| Knowledge Graph | Custom Physarum engine (Python) | Self-evolving medical knowledge navigation |
| Medical Data | ICD-11 API, MedlinePlus, WHO GHO | Standards-based medical coding |
| Doctor Portal | Next.js 14 + TypeScript + Tailwind | Real-time doctor dashboard |
| Hosting | Render.com (backend) + Vercel (portal) | Production deployment |

## Ethical Alignment (WHO Six Principles)

1. **Protecting Human Autonomy**: "I am not a doctor" disclaimers, explicit consent before speech analysis
2. **Promoting Safety**: Red-flag symptom detection, emergency routing, START triage protocol
3. **Transparency**: AI limitations disclosed, audit logs for clinicians, capability cards per country tier
4. **Responsibility**: Clinician remains final authority, no autonomous diagnosis
5. **Inclusiveness**: Phone-first design for populations without internet, multi-country support
6. **Sustainability**: Energy-efficient models, local data sovereignty, open-source architecture

## Hackathon Track

**Track 1: Biology & Physical Health** — Diagnostic aids for underserved clinics, symptom assessment and triage helpers, health literacy tools for treatment decisions.

## Team

Built for the Claude Builder Club Hackathon.
