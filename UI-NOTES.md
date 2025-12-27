# UI Philosophy

## Our Focus: The Agent, Not the UI

This project is **primarily focused on the autonomous coding agent system**. The web UI is a **minimal, functional implementation** that prioritizes user experience (UX) and information display over visual polish.

### What the UI Is

- ✅ **Functional**: Provides all necessary controls and information
- ✅ **UX-focused**: Clear information hierarchy, intuitive workflows
- ✅ **Complete**: Full API coverage, real-time updates, comprehensive features
- ✅ **Built by Claude Code**: Demonstrates the agent's capabilities

### What the UI Is Not

- ❌ **Polished**: No custom color palettes, animations, or visual refinements
- ❌ **Production-grade UI/UX**: Not professionally designed
- ❌ **Cosmetically optimized**: No effort on gradients, transitions, or micro-interactions

## Future UI Development

### Our Planned Enhancements (See TODO.md)

All planned UI improvements focus on **exposing more useful information**:
- Task detail views (show individual tasks and tests)
- Additional metrics on History tab (performance, model stats, timelines)
- Test coverage reports (post-initialization analysis)
- Quality insights (more detailed session analysis)

**We have NO plans for cosmetic improvements** like:
- Theme refinements
- Animation polish
- Custom color palettes
- Advanced transitions
- Visual design overhaul

### Fork and Improve!

**Users are encouraged to fork this project** and improve the UI as they see fit. The web UI is built with modern, standard tools:
- **Next.js 16** (React framework with App Router)
- **TypeScript** (full type safety)
- **Tailwind CSS v4** (utility-first styling)
- **Axios** (API client)
- **WebSocket** (real-time updates)

The codebase is well-structured for UI improvements:
- Clear component hierarchy (`web-ui/src/components/`)
- Centralized API client (`web-ui/src/lib/api.ts`)
- Type definitions (`web-ui/src/lib/types.ts`)
- Reusable utilities (`web-ui/src/lib/utils.ts`)

## Current State

**What Works:**
- ✅ Real-time progress monitoring
- ✅ Session history with metrics
- ✅ Quality dashboard with trend charts
- ✅ Project creation and management
- ✅ Environment configuration
- ✅ Project reset with confirmation
- ✅ Live WebSocket updates
- ✅ Completion celebration banner

**Known Limitations:**
- Basic visual design (default Tailwind styling)
- No custom animations or transitions
- Limited mobile optimization
- Dark/light mode partially implemented (some panels in light mode need updates)

## Philosophy

> "The best UI for an autonomous coding agent is one that gets out of the way and lets you monitor progress. Our UI does exactly that—nothing more, nothing less."

The autonomous coding agent is the star of this project. The UI is simply the control panel.


