# Asterisk Visual Dialplan Designer — UX Architecture Proposal

Open source replacement for [Apstel Visual Dialplan](https://www.apstel.com/features/) (discontinued). A browser-based drag-and-drop call flow designer for Asterisk.

## What It Is

A visual editor where you design Asterisk call flows by dragging, dropping, and connecting components. The output is a call flow diagram that an admin implements in the actual dialplan via CLI. The app never touches the Asterisk server directly.

**Workflow:**
```
Designer builds flow visually → exports diagram / dialplan snippets
→ Admin reads the flow → implements in extensions.conf via CLI
→ Admin runs `dialplan reload`
```

An optional **integration server** can connect to a live Asterisk instance to import existing dialplans or push changes, but it's not required. The core app is a static SPA that runs entirely in the browser.

## What It Is Not

- Not a PBX admin panel (FreePBX, Elastix, FusionPBX)
- Not a runtime call manager — it doesn't handle live calls
- Not tied to any specific Asterisk installation or framework

---

## Inspiration: Apstel Visual Dialplan

What Apstel offered (and we aim to replace):

| Feature | Apstel | This Project |
|---------|--------|--------------|
| Drag-and-drop flow editor | Yes | Yes |
| Component library (IVR, Queue, Dial, etc.) | Yes, proprietary | Yes, open source |
| Database integrations (MySQL, PostgreSQL) | Yes | Planned (via integration server) |
| FreePBX/Elastix compatibility | Yes | Agnostic — works with any Asterisk |
| ASR/TTS components | Yes | Planned |
| Export to dialplan | Unclear | Yes — snippets + full conf |
| License | Commercial, discontinued | Open source (MIT or Apache-2.0) |
| Runtime | Desktop app (Windows) | Browser SPA — runs anywhere |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │  Flow Canvas  │  │  Component       │  │  Properties Panel    │ │
│  │  (React Flow) │  │  Library Panel   │  │  (per-node config)   │ │
│  └──────┬───────┘  └────────┬─────────┘  └──────────┬────────────┘ │
│         │                   │                        │              │
│         └───────────┬───────┴────────────────────────┘              │
│                     │                                               │
│              ┌──────┴──────┐                                        │
│              │   Zustand    │  (flow graph + undo/redo + projects) │
│              └──────┬──────┘                                        │
│                     │                                               │
│              ┌──────┴──────┐                                        │
│              │  localStorage│  (save/load projects offline)         │
│              └─────────────┘                                        │
│                     │                                               │
│              ┌──────┴──────┐  (optional)                           │
│              │ Export       │                                        │
│              │ .drawio      │                                        │
│              │ .conf        │                                        │
│              │ .png / .svg  │                                        │
│              │ .json        │                                        │
│              └─────────────┘                                        │
└─────────────────────────────────────────────────────────────────────┘
                      │
                      │ optional — integration server
                      │
┌─────────────────────┼───────────────────────────────────────────────┐
│              ┌──────┴──────┐                                        │
│              │ Integration  │  (FastAPI / Flask / Express — your    │
│              │ Server       │   choice, self-hosted, open source)   │
│              └──────┬──────┘                                        │
│                     │                                               │
│    ┌────────────────┼────────────────────┐                          │
│    │                │                    │                          │
│    ▼                ▼                    ▼                          │
│ ┌────────┐   ┌───────────┐   ┌────────────────┐                   │
│ │Asterisk│   │  Database  │   │ Import .conf   │                   │
│ │  AMI   │   │  (MySQL,   │   │ Parse existing │                   │
│ │  ARI   │   │  Postgres) │   │ dialplans      │                   │
│ └────────┘   └───────────┘   └────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key point:** The SPA works standalone. No server, no login, no install. Open index.html in a browser and start designing. The integration server is a separate, optional project.

---

## Tech Stack

All open source, all free:

| Layer | Tool | License | Why |
|-------|------|---------|-----|
| **Flow editor** | [React Flow](https://reactflow.dev/) | MIT | Drag-and-drop node editor with handles, zoom, pan, minimap. Built for exactly this. |
| **Auto layout** | [ELK.js](https://github.com/kieler/elkjs) | EPL-2.0 | Automatic hierarchical layout. One click to auto-arrange a messy graph. |
| **Frontend** | React 18 + TypeScript + Vite | MIT | React Flow requires React. Vite builds fast, outputs small bundles. |
| **UI components** | [shadcn/ui](https://ui.shadcn.com/) | MIT | Clean components, copy-pasted into the project (no runtime dependency). |
| **State** | [Zustand](https://github.com/pmndrs/zustand) | MIT | Flow state, undo/redo, project management. Lightweight. |
| **Persistence** | localStorage + JSON export/import | — | No server needed. Projects saved in the browser or exported as `.json` files. |
| **Code preview** | [CodeMirror 6](https://codemirror.net/) | MIT | Read-only preview of generated dialplan snippets. |
| **Integration server** (optional) | FastAPI / Flask / Express | MIT | Self-hosted. Connects to Asterisk AMI, imports `.conf` files, pushes changes. |

---

## Component Library

The heart of the app. Each component is a React Flow node with typed input/output handles and a configuration form.

### Call Flow Components

| Component | Inputs | Outputs | Description |
|-----------|--------|---------|-------------|
| **Inbound** | — | 1 (call enters) | Entry point. Configures: DID pattern, trunk name, caller ID handling. |
| **Answer** | 1 | 1 | Answer the channel. Optional: delay before answer. |
| **Hangup** | 1 | — | End the call. Configures: hangup cause code. |
| **Playback** | 1 | 1 | Play an audio file. Configures: filename, language. |
| **Background** | 1 | 1 + per-digit | Play audio, accept DTMF. Outputs: one handle per expected digit. |
| **Read** | 1 | 1 (valid) + 1 (timeout) | Read DTMF input. Configures: max digits, timeout, retries, prompt file. |
| **Set Variable** | 1 | 1 | Set a channel variable. Configures: variable name, value/expression. |
| **GotoIf** | 1 | 2 (true/false) | Conditional branch. Configures: expression. |
| **Switch** | 1 | N (per case) | Multi-way branch. Configures: variable, case values. |

### Telephony Components

| Component | Inputs | Outputs | Description |
|-----------|--------|---------|-------------|
| **Dial** | 1 | 3 (answered, busy, no-answer) | Dial a destination. Configures: tech/resource, timeout, options, caller ID. |
| **Queue** | 1 | 2 (answered, timeout) | Send to a call queue. Configures: queue name, timeout, announce files. |
| **Voicemail** | 1 | 1 | Send to voicemail. Configures: mailbox, options (busy/unavail greeting). |
| **Transfer** | 1 | 1 | Blind/attended transfer. Configures: destination, type. |
| **Park** | 1 | 1 | Park the call. Configures: parking lot. |
| **Conference** | 1 | 1 | Enter a conference bridge. Configures: room number, PIN, options. |
| **MixMonitor** | 1 | 1 | Start/stop recording. Configures: filename pattern, options. |

### IVR Components

| Component | Inputs | Outputs | Description |
|-----------|--------|---------|-------------|
| **Menu** | 1 | N (per option) + 1 (invalid) + 1 (timeout) | Full IVR menu. Configures: prompt, valid options, retries, timeout. |
| **Announce** | 1 | 1 | Play announcement then continue. Configures: file list, interruptible. |
| **SayDigits** | 1 | 1 | Speak a number. Configures: source variable. |
| **SayDateTime** | 1 | 1 | Speak date/time. Configures: format, timezone. |

### Advanced Components

| Component | Inputs | Outputs | Description |
|-----------|--------|---------|-------------|
| **AGI** | 1 | 1 (success) + 1 (failure) | Run an AGI script. Configures: script path, arguments. |
| **HTTP Request** | 1 | 1 (success) + 1 (failure) | CURL + JSON_DECODE. Configures: URL, method, response variable mapping. |
| **Database Lookup** | 1 | 1 (found) + 1 (not found) | func_odbc or CURL to DB API. Configures: query, result variable. |
| **Set CDR** | 1 | 1 | Set CDR fields. Configures: field name, value. |
| **Subroutine** | 1 | 1 (return) | Gosub to a reusable sub-flow. Configures: target sub-flow. |
| **Return** | 1 | — | Return from a subroutine. |
| **Label** | 1 | 1 | Named label for Goto targets. Configures: label name. |
| **Comment** | — | — | Non-functional annotation node. Configures: text, color. |

### Grouping

| Component | Description |
|-----------|-------------|
| **Context Group** | Visual container that represents a `[context]`. Child nodes become extensions within it. |
| **Sub-flow** | Reusable group of components. Becomes a `Gosub()` target. Configures: name, arguments. |

---

## Node Design

Each component node in React Flow has:

```
┌──────────────────────────────┐
│ ● input handle(s)           │
├──────────────────────────────┤
│  [icon]  Component Name      │
│  Brief config summary        │
│  e.g. "Dial SIP/trunk, 30s" │
├──────────────────────────────┤
│ ○ output handle(s)          │
│   labeled: "answered"        │
│   labeled: "busy"            │
│   labeled: "no-answer"       │
└──────────────────────────────┘
```

**Color coding by category:**

| Category | Color | Examples |
|----------|-------|---------|
| Call flow | Blue (`#dae8fc`) | Inbound, Answer, Hangup, GotoIf |
| Telephony | Green (`#d5e8d4`) | Dial, Queue, Transfer, Park |
| IVR / Audio | Yellow (`#fff2cc`) | Menu, Playback, Read, SayDigits |
| Integration | Purple (`#e1d5e7`) | AGI, HTTP Request, Database Lookup |
| Utility | Gray (`#f5f5f5`) | Set Variable, Label, Comment, Set CDR |

---

## UI Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│ [☰] Asterisk Flow Designer    [Project ▼]   [Undo] [Redo]   [Export ▼]   │
├──────────┬─────────────────────────────────────────────┬───────────────────┤
│          │                                             │                   │
│ Component│              Flow Canvas                    │   Properties      │
│ Library  │                                             │   Panel           │
│          │  ┌──────────┐       ┌──────────┐           │                   │
│ ┌──────┐ │  │ Inbound  │──────▶│ Answer   │           │ ┌───────────────┐ │
│ │Inbnd │ │  │ DID: _X. │       │          │           │ │ Dial          │ │
│ ├──────┤ │  └──────────┘       └────┬─────┘           │ ├───────────────┤ │
│ │Answer│ │                          │                  │ │ Tech: SIP     │ │
│ ├──────┤ │                     ┌────▼─────┐           │ │ Resource:     │ │
│ │ Dial │ │                     │ Menu     │           │ │ [trunk/num  ] │ │
│ ├──────┤ │                     │ prompt:  │           │ │ Timeout: [30] │ │
│ │ Menu │ │                     │ welcome  │           │ │ CallerID:     │ │
│ ├──────┤ │                     └┬───┬───┬─┘           │ │ [${CALLERID}] │ │
│ │Queue │ │                      │   │   │             │ │ Options: [tT] │ │
│ ├──────┤ │                      1   2   *             │ │               │ │
│ │ Read │ │                      │   │   │             │ │ Outputs:      │ │
│ ├──────┤ │              ┌───────┘   │   └──────┐      │ │ ● Answered    │ │
│ │ AGI  │ │              ▼           ▼          ▼      │ │ ● Busy        │ │
│ ├──────┤ │         ┌────────┐ ┌────────┐ ┌────────┐  │ │ ● No Answer   │ │
│ │ HTTP │ │         │ Queue  │ │  Dial  │ │Hangup  │  │ │ ● Congestion  │ │
│ ├──────┤ │         │ sales  │ │operator│ │        │  │ └───────────────┘ │
│ │ ...  │ │         └────────┘ └────────┘ └────────┘  │                   │
│ └──────┘ │                                             │                   │
│          │  ┌─── Minimap ───┐                         │                   │
│          │  │ [  ·  ]       │                         │                   │
│          │  └───────────────┘                         │                   │
├──────────┴─────────────────────────────────────────────┴───────────────────┤
│ [Dialplan Preview]  Generated extensions.conf snippet (read-only)         │
│ ┌────────────────────────────────────────────────────────────────────────┐ │
│ │ [inbound-main]                                                        │ │
│ │ exten => _X.,1,Answer()                                               │ │
│ │  same => n,Background(welcome)                                        │ │
│ │  same => n,WaitExten(5)                                               │ │
│ │ exten => 1,1,Queue(sales)                                             │ │
│ │ exten => 2,1,Dial(SIP/operator,30,tT)                                │ │
│ │ exten => *,1,Hangup()                                                 │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### Panel behavior

- **Component Library** (left): drag components onto the canvas. Searchable. Grouped by category.
- **Flow Canvas** (center): React Flow. Drag to connect output handles → input handles. Zoom, pan, minimap.
- **Properties Panel** (right): appears when a node is selected. Form fields for that component's configuration.
- **Dialplan Preview** (bottom): live-generated `extensions.conf` snippet. Updates as you edit the flow. Read-only, copy-to-clipboard.

---

## Project Management

Projects are self-contained JSON files. No server, no account.

### Save/Load

- **localStorage**: auto-saves the current project. Survives browser refresh.
- **Export `.json`**: download the full project (flow graph + component configs) as a file.
- **Import `.json`**: load a previously exported project.
- **Multiple projects**: project switcher in the toolbar. Each project is independent.

### Export formats

| Format | Use Case |
|--------|----------|
| **`.json`** | Full project — reimport into the editor later |
| **`.conf`** | Generated `extensions.conf` snippet — copy into your Asterisk config |
| **`.drawio`** | Open in draw.io for further diagram editing or documentation |
| **`.png` / `.svg`** | Static image for docs, wikis, Slack |

### Project file structure

```json
{
  "name": "Main IVR",
  "version": "1.0",
  "created": "2026-03-17T00:00:00Z",
  "modified": "2026-03-17T12:00:00Z",
  "nodes": [
    {
      "id": "node-1",
      "type": "inbound",
      "position": {"x": 100, "y": 50},
      "data": {
        "didPattern": "_X.",
        "trunkName": "didww-inbound",
        "callerIdHandling": "filter-digits"
      }
    },
    {
      "id": "node-2",
      "type": "menu",
      "position": {"x": 100, "y": 200},
      "data": {
        "prompt": "welcome",
        "options": ["1", "2", "*"],
        "timeout": 5,
        "retries": 3
      }
    }
  ],
  "edges": [
    {"source": "node-1", "sourceHandle": "out", "target": "node-2", "targetHandle": "in"}
  ],
  "globals": {
    "TRUNK_OUT": "didww-outbound"
  }
}
```

---

## Dialplan Code Generation

The bottom panel generates `extensions.conf` syntax in real time from the visual flow.

### Generation rules

Each **Context Group** node becomes a `[context]` section. Nodes inside it become extensions and priorities.

```
Context Group "inbound-main"
  └─ Inbound (_X.) → Answer → Menu (welcome, options: 1,2,*)
       ├─ 1 → Queue (sales)
       ├─ 2 → Dial (SIP/operator, 30s)
       └─ * → Hangup
```

Generates:

```ini
[inbound-main]
exten => _X.,1,Answer()
 same => n,Background(welcome)
 same => n,WaitExten(5)

exten => 1,1,Queue(sales)

exten => 2,1,Dial(SIP/operator,30,tT)

exten => *,1,Hangup()
```

### What it handles

- Sequential nodes → `same => n` priority chaining
- Branch nodes (GotoIf, Switch, Menu) → separate `exten =>` lines per branch
- Sub-flows → `Gosub(sub-flow-name,s,1)` + separate `[sub-flow-name]` context
- Context Groups → `[context-name]` sections
- Variables → `Set()` applications with the configured name=value
- HTTP calls → `Set(response=${CURL(url)})` + `Set(var=${JSON_DECODE(response,key)})`

### What it doesn't handle (yet)

- Optimization (e.g., collapsing redundant Set() calls)
- AEL or Lua output (extensions.conf only for now)
- Full validation against a running Asterisk (that's the integration server's job)

---

## Optional Integration Server

A separate, self-hosted service. Not required for the core editor.

### What it does

| Feature | Description |
|---------|-------------|
| **Import existing dialplan** | Parse `.conf` files → project JSON. Load an existing Asterisk setup into the visual editor. |
| **Push to Asterisk** | Write generated `.conf` to the server, run `dialplan reload`. |
| **AMI bridge** | Connect to Asterisk Manager Interface for live channel state, originate calls for testing. |
| **Database proxy** | Query MySQL/PostgreSQL from the editor (for DB Lookup component configuration). |

### Architecture

Any language, any framework. A reference implementation in Python (FastAPI) or Node (Express):

```
GET  /api/dialplan/import          → parse .conf files → return project JSON
POST /api/dialplan/deploy          → receive .conf content → write + reload
GET  /api/asterisk/channels        → AMI: list active channels
POST /api/asterisk/originate       → AMI: originate a test call
GET  /api/db/query                 → proxy a DB query for the DB Lookup component
```

### Security

- Authentication required (API key or JWT)
- Deploy requires elevated permissions
- No shell injection — `dialplan reload` is a hardcoded AMI command
- DB proxy uses parameterized queries only, read-only by default
- The integration server is optional and self-hosted — you control who has access

---

## Tech Stack

All open source, all free:

| Layer | Tool | License |
|-------|------|---------|
| **Flow editor** | [React Flow](https://reactflow.dev/) | MIT |
| **Auto layout** | [ELK.js](https://github.com/kieler/elkjs) | EPL-2.0 |
| **Frontend** | React 18 + TypeScript + Vite | MIT |
| **UI components** | [shadcn/ui](https://ui.shadcn.com/) | MIT |
| **State + undo/redo** | [Zustand](https://github.com/pmndrs/zustand) | MIT |
| **Code preview** | [CodeMirror 6](https://codemirror.net/) | MIT |
| **Persistence** | localStorage + file export | — |
| **Integration server** (optional) | FastAPI / Express / your choice | MIT |

**Deployment:** Static files. Host on GitHub Pages, Netlify, any CDN, or just open `index.html` locally. Zero server cost for the core editor.

---

## File Structure

```
asterisk-flow-designer/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   │
│   ├── store/
│   │   ├── flow-store.ts          # Zustand: nodes, edges, undo/redo
│   │   └── project-store.ts       # Zustand: save/load/export projects
│   │
│   ├── components/
│   │   ├── Canvas.tsx             # React Flow wrapper
│   │   ├── ComponentLibrary.tsx   # Left panel: draggable component list
│   │   ├── PropertiesPanel.tsx    # Right panel: selected node config form
│   │   ├── DialplanPreview.tsx    # Bottom panel: generated .conf (CodeMirror)
│   │   ├── Toolbar.tsx            # Top: project switcher, undo/redo, export
│   │   └── ExportDialog.tsx       # Export format picker
│   │
│   ├── nodes/                     # Custom React Flow node types
│   │   ├── InboundNode.tsx
│   │   ├── AnswerNode.tsx
│   │   ├── HangupNode.tsx
│   │   ├── DialNode.tsx
│   │   ├── MenuNode.tsx
│   │   ├── QueueNode.tsx
│   │   ├── PlaybackNode.tsx
│   │   ├── ReadNode.tsx
│   │   ├── GotoIfNode.tsx
│   │   ├── SwitchNode.tsx
│   │   ├── AGINode.tsx
│   │   ├── HTTPRequestNode.tsx
│   │   ├── DatabaseLookupNode.tsx
│   │   ├── SetVariableNode.tsx
│   │   ├── SubroutineNode.tsx
│   │   ├── CommentNode.tsx
│   │   └── ContextGroupNode.tsx
│   │
│   ├── generators/
│   │   ├── conf-generator.ts      # Flow graph → extensions.conf syntax
│   │   ├── drawio-generator.ts    # Flow graph → .drawio XML
│   │   └── image-generator.ts     # Flow graph → PNG/SVG via React Flow export
│   │
│   ├── properties/                # Per-component property forms
│   │   ├── InboundProperties.tsx
│   │   ├── DialProperties.tsx
│   │   ├── MenuProperties.tsx
│   │   ├── QueueProperties.tsx
│   │   └── ...
│   │
│   └── utils/
│       ├── layout.ts              # ELK.js auto-layout config
│       ├── validation.ts          # Flow validation (disconnected nodes, cycles, etc.)
│       └── types.ts               # TypeScript types for components and flow graph
│
├── integration-server/            # Optional — separate project
│   ├── requirements.txt           # or package.json
│   ├── server.py                  # FastAPI / Express
│   ├── parser.py                  # .conf → project JSON
│   └── ami.py                     # Asterisk Manager Interface bridge
│
└── dist/                          # Built SPA — deploy anywhere
```

---

## Implementation Phases

### Phase 1: Parser + visual import (MVP)

**Goal:** Paste your existing dialplan, see it as a visual graph. Instant value, no manual redrawing.

1. Dialplan parser (Python, standalone module — no Asterisk dependency)
   - Input: `.conf` text (paste into textarea or upload files)
   - Output: project JSON (nodes + edges + component configs)
   - Handles: `[context]`, `exten =>`, `same => n`, `include =>`, `#include`, `[globals]`
   - Extracts edges from `Goto()`, `GotoIf()`, `Gosub()`, `include =>`
   - Classifies steps: noop, variable, playback, dial, agi, branch, http
   - Detects dynamic Goto targets (`Goto(${var},s,1)`)
2. React Flow canvas rendering the parsed graph
3. Auto-layout (ELK.js) — imported flows arranged automatically
4. Properties panel — click a node, see its parsed config (read-only at this stage)
5. Basic validation: broken Goto targets, unreachable contexts, undefined variables
6. Export: `.json` (reimport later), `.png`/`.svg` (documentation)

**Value:** "Paste your `extensions.conf`, get a visual map of your call flow." This is the hook — every Asterisk admin has a dialplan they've never fully visualized. The parser does half the work; React Flow does the other half.

### Phase 2: Visual editor + code generation

**Goal:** Edit the imported flow visually. Design new flows from scratch. Generate dialplan.

1. Drag-and-drop from component library (start with 5-6 core nodes: Inbound, Answer, Dial, Menu, Hangup, Playback)
2. Properties panel becomes editable — configure each component via forms
3. `conf-generator.ts` — live dialplan preview in bottom panel (flow → `.conf`)
4. Save/load to localStorage
5. Export as `.conf` (generated dialplan snippets)
6. Round-trip: import `.conf` → edit visually → export `.conf` → diff against original

**Value:** The full design loop. Import, tweak, export. Or start from scratch.

### Phase 3: Full component library + polish

**Goal:** Cover all common Asterisk applications. Production-quality tool.

1. Add remaining components: Queue, Read, GotoIf, Switch, Voicemail, Transfer, Park, Conference, MixMonitor, AGI, HTTP Request, Database Lookup, Set Variable, Set CDR, Subroutine, Label, Comment
2. Context Group nodes (visual containers for `[context]` sections)
3. Sub-flow support (reusable component groups)
4. Undo/redo
5. Multiple projects with project switcher
6. Component search/filter in library panel
7. Keyboard shortcuts (delete, copy/paste, undo/redo)
8. Export to `.drawio`

**Value:** Can design any Asterisk call flow, not just simple IVRs.

### Phase 4: Integration server (optional)

**Goal:** Connect to a live Asterisk for import/deploy/test.

1. Serve the parser as an API endpoint (paste `.conf` in browser → POST to server → get project JSON)
2. File-based import: point at a directory of `.conf` files on the server
3. Deploy endpoint → write generated `.conf` + `dialplan reload`
4. AMI bridge → show live channel state, originate test calls
5. Database proxy → configure DB Lookup components against real data

**Value:** Full round-trip workflow for teams managing Asterisk installations.
