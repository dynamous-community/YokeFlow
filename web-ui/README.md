# Next.js Web UI for Autonomous Coding Agent

Modern React/Next.js web interface for the autonomous coding agent platform.

## Features (Production Ready - v2.0)

✅ **Authentication**
- JWT token-based authentication
- Development mode (auto-bypass when UI_PASSWORD not set)
- Secure login with password validation
- Logout functionality (hidden in dev mode)
- Protected routes and API calls

✅ **Project List**
- Grid view of all projects with search
- Real-time progress bars (tasks, tests, epics)
- Auto-refresh every 5 seconds
- Click to view project details

✅ **Project Creation**
- Real-time project name validation
- Drag & drop spec file upload
- Project name auto-fill from filename
- Model selection (Opus/Sonnet)
- Sandbox type selection (Docker/Local)
- Form validation with instant feedback
- Advanced options (collapsible)

✅ **Project Detail**
- Live WebSocket updates for real-time progress
- Five interactive tabs (Overview, History, Quality, Logs, Settings)
- Session timeline with status badges
- Smart session controls (Initialize/Start Coding/Stop)
- Project reset with confirmation dialog
- Delete project with confirmation
- Completion celebration banner
- Next task display
- Task detail modal with epic/task/test hierarchy
- Project details panel with environment editor

✅ **History Tab**
- Database-driven session metrics
- Test pass/fail counts per session
- Task completion tracking
- Duration and timestamp display
- Token usage breakdown (input/output separate)
- Expandable metrics with "more coming soon" note

✅ **Quality Tab**
- Quality trend chart (last 10 sessions)
- Summary cards with averages
- Quality score badges
- Deep review recommendations display
- Automated review system integration

✅ **Logs Tab**
- Complete session log viewer in browser
- List all sessions with proper naming (Initialization, Session #1, etc.)
- View TXT (human-readable) and JSONL (events) logs
- Download logs directly from UI
- Formatted timestamps for readability
- No filesystem access needed

✅ **Project Reset**
- Smart visibility (only after initialization)
- Confirmation dialog with preview
- Resets to post-initialization state
- Preserves complete roadmap
- Archives old logs

✅ **Environment Configuration**
- Visual .env editor in browser
- Required/optional variable detection
- Syntax validation
- Save directly from UI

✅ **UI/UX**
- Dark theme throughout
- Responsive design (mobile/tablet/desktop)
- Loading states and spinners
- Error handling with retry
- Breadcrumb navigation
- WebSocket connection indicator
- Real-time updates across all views
- Toast notifications (no more alert boxes)
- Confirmation dialogs for destructive actions
- Professional, modern interface

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **HTTP Client:** Axios
- **Real-time:** WebSocket (native)
- **Icons:** Lucide React
- **Date/Time:** date-fns

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- FastAPI backend running on port 8000

### Installation

```bash
# Install dependencies
npm install

# Configure environment (REQUIRED)
cp .env.local.example .env.local
```

**Important:** The `.env.local` file is **required** for the Next.js app to connect to the API server. The root `.env` file is for the Python backend only - Next.js cannot read it.

### Development

```bash
# Start dev server
npm run dev

# Open http://localhost:3000
```

### Environment Variables

The `.env.local` file contains browser-accessible environment variables:

```bash
# API Server URL (where FastAPI is running)
NEXT_PUBLIC_API_URL=http://localhost:8000

# WebSocket URL (same as API URL but with ws:// protocol)
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

For production deployment with HTTPS, update to:
```bash
NEXT_PUBLIC_API_URL=https://your-domain.com
NEXT_PUBLIC_WS_URL=wss://your-domain.com
```

## Project Structure

```
web-ui-next/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout with nav
│   │   ├── page.tsx                # Project list (home)
│   │   ├── create/
│   │   │   └── page.tsx            # Create project form
│   │   └── projects/
│   │       └── [id]/
│   │           ├── page.tsx        # Project detail
│   │           └── sessions/
│   │               └── [sessionId]/
│   │                   └── page.tsx  # Session logs
│   ├── components/
│   │   ├── ProgressBar.tsx         # Progress visualization
│   │   ├── ProjectCard.tsx         # Project grid item
│   │   ├── SessionTimeline.tsx     # Session history
│   │   └── Tabs.tsx                # Tab interface
│   └── lib/
│       ├── api.ts                  # API client
│       ├── types.ts                # TypeScript definitions
│       ├── utils.ts                # Helper functions
│       └── websocket.ts            # WebSocket hook
├── public/                         # Static assets
├── .env.local                      # Environment config
└── package.json
```

## License

Same as parent project (MIT)
