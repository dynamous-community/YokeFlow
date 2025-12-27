# TODO-FUTURE - Post-Release Enhancements

This document tracks enhancements and features planned for **after** the initial YokeFlow release.

**Last Updated:** December 27, 2025 (v1.1.0)

**Note:** This document has been simplified for v1.1.0 to focus on future enhancements. Completed features are marked with ✅ but descriptions are now concise. For full implementation details, see the git history or [docs/review-system.md](docs/review-system.md).

---

## 🎯 POST-RELEASE PRIORITIES

### 1. Prompt Improvement System (Phase 4 of Review System)
**Status:** ✅ **COMPLETE** - Production ready (December 2025)

**Implemented Features:**
- Multi-project and single-project analysis
- Theme-based clustering (8 categories)
- Confidence scoring and prioritization
- Web UI dashboard with trigger controls
- Evidence tracking with session links

**Documentation:** See [docs/review-system.md](docs/review-system.md#phase-4-prompt-improvement-analyzer--new)

**Future Enhancements:**
- **Project-Type-Specific Prompts**: Tag projects by type (UI-focused, Mobile App, AI Agent, etc.) and generate scoped improvements
- ML-based semantic similarity clustering
- A/B testing for prompt changes
- Prompt version tracking and comparison
- **Automatic Proposal Application**: One-click apply with git integration, diff preview, and rollback capability
- **Impact Tracking**: Measure quality improvements after implementing changes (schema fields already exist)

**Priority:** Core feature complete - enhancements are LOW priority 

### 2. Multiple Spec Files Upload - Advanced Features
**Status:** ✅ Core feature complete - Advanced features deferred

**Advanced Features:**
1. **Database Metadata Storage**: Track spec file metadata in projects table (JSONB column)
2. **LLM-Based Primary File Detection**: Use Claude Haiku for content-based detection (~$0.001/project)
3. **Advanced Manifest Parsing**: YAML/TOML frontmatter with conditional includes
4. **Spec File Versioning**: Track changes across sessions with diff view
5. **Template Bundles**: Pre-packaged spec sets for common project types

**Priority:** MEDIUM (implement based on user feedback)
**Estimated Effort:** 16-23 hours

---

### 3. Spec File Generator - Companion Tool
**Status:** Concept phase - Standalone project

**Vision:** Interactive wizard that helps users create comprehensive specification files optimized for YokeFlow.

**Inspiration Sources:**
- **B-MAD** - Structured requirements gathering
- **SpecKit** - Template-based spec generation

**Core Concept:**
Instead of users starting with a blank file, guide them through a structured interview process that generates a complete, well-formatted spec file proven to work with YokeFlow.

---

## 📋 Proposed Features

### **Interview-Driven Spec Generation**

**Question Flow:**
```
1. Project Type
   ├─ SaaS Application
   ├─ E-commerce Site
   ├─ Mobile App Backends
   ├─ Data Dashboard
   └─ Custom...

2. Tech Stack Preferences
   ├─ Frontend: React/Vue/Angular/Next.js/None
   ├─ Backend: Node/Python/Go/Ruby/None
   ├─ Database: PostgreSQL/MySQL/MongoDB/None
   └─ Additional: Redis/WebSocket/etc.

3. Core Features (multi-select)
   ├─ User Authentication
   ├─ Payment Processing
   ├─ Real-time Updates
   ├─ File Uploads
   ├─ Admin Dashboard
   └─ API Integration...

4. User Roles & Permissions
   └─ Define: Admin, User, Guest, etc.

5. Data Models
   └─ Describe: Users, Products, Orders, etc.

6. UI/UX Requirements
   ├─ Style: Modern/Minimal/Corporate
   ├─ Responsive: Yes/No
   └─ Accessibility: WCAG 2.1 AA?

7. Non-Functional Requirements
   ├─ Performance targets
   ├─ Security requirements
   ├─ Scalability needs
   └─ Compliance (GDPR, HIPAA, etc.)
```

### **Template System**

**Built-in Templates:**
```
templates/
├── saas-starter/
│   ├── main.md
│   ├── api-design.md
│   └── database-schema.sql
├── ecommerce/
│   ├── main.md
│   ├── product-catalog.md
│   └── checkout-flow.md
├── dashboard/
│   ├── main.md
│   └── data-sources.md
└── api-service/
    ├── main.md
    └── endpoints.md
```

**Template Variables:**
- `{{project_name}}`
- `{{tech_stack}}`
- `{{features}}`
- `{{user_roles}}`
- `{{data_models}}`

### **Smart Generation Features**

**1. Progressive Disclosure**
- Start simple (project type, basic features)
- Expand with follow-up questions based on selections
- Example: If user selects "Payment Processing" → ask about payment providers

**2. Best Practices Injection**
- Auto-add security requirements for auth flows
- Suggest testing strategies based on tech stack
- Recommend accessibility features
- Include deployment considerations

**3. Example Code Snippets**
- Generate example API requests
- Create sample data models
- Provide UI component examples
- Include authentication flows

**4. Multi-File Output**
- Generate main.md + supporting files
- Organize by feature area
- Ready to upload to YokeFlow

**5. Spec Validation**
- Check for completeness
- Warn about missing critical details
- Suggest improvements
- Estimate project complexity

---

## 🎨 UI/UX Mockup

**Step-by-Step Wizard:**
```
┌─────────────────────────────────────────┐
│  YokeFlow Spec Generator                │
├─────────────────────────────────────────┤
│                                         │
│  Step 2 of 7: Choose Your Tech Stack   │
│                                         │
│  Frontend Framework:                    │
│  ○ React + TypeScript                   │
│  ⦿ Next.js (recommended for SaaS)       │
│  ○ Vue.js                               │
│  ○ Angular                              │
│  ○ None (Backend only)                  │
│                                         │
│  Backend:                               │
│  ⦿ Node.js + Express                    │
│  ○ Python + FastAPI                     │
│  ○ Go                                   │
│                                         │
│  [Back]              [Next: Features →] │
└─────────────────────────────────────────┘
```

**Live Preview:**
```
┌────────────────────┬────────────────────┐
│ Questions          │ Generated Spec     │
├────────────────────┼────────────────────┤
│ [Interview Form]   │ # My SaaS App      │
│                    │                    │
│ ✅ Project Type    │ ## Tech Stack      │
│ ✅ Tech Stack      │ - Next.js          │
│ → Features         │ - Node.js/Express  │
│   Data Models      │ - PostgreSQL       │
│   UI/UX            │                    │
│   Requirements     │ ## Features        │
│   Review           │ - User Auth        │
│                    │ - Payments         │
│                    │ ...                │
└────────────────────┴────────────────────┘
```

---

## 🛠️ Implementation Options

### **Option 1: Web-Based Tool (Standalone)**
- Separate Next.js application
- Hosted at specs.yokeflow.com
- No YokeFlow account needed
- Export .zip with all spec files
- "Upload to YokeFlow" button (API integration)

**Pros:**
- Accessible to everyone
- Marketing tool for YokeFlow
- Can be used independently
- Easier to maintain

**Cons:**
- Separate deployment
- Need to keep templates in sync

### **Option 2: Integrated in YokeFlow UI**
- New tab in YokeFlow: "Create → From Template"
- Part of project creation flow
- Auto-uploads generated specs

**Pros:**
- Seamless experience
- Single codebase
- Immediate project creation

**Cons:**
- Increases YokeFlow complexity
- Must be logged in to use

### **Option 3: CLI Tool**
- `npx @yokeflow/spec-generator`
- Interactive terminal wizard
- Generates files locally
- Upload manually to YokeFlow

**Pros:**
- Developer-friendly
- Lightweight
- Works offline

**Cons:**
- Limited to technical users
- No visual preview

**Recommendation:** Start with **Option 1** (standalone web tool), then integrate into YokeFlow UI in v2.0

---

## 📊 Estimated Effort

| Component | Effort | Notes |
|-----------|--------|-------|
| UI/UX Design | 8-12 hours | Wizard flow, question design |
| Template System | 12-16 hours | 5-7 starter templates |
| Question Engine | 16-24 hours | Logic, branching, validation |
| Preview/Export | 8-12 hours | Live preview, multi-file export |
| Integration | 4-8 hours | API to upload to YokeFlow |
| Documentation | 4-6 hours | User guide, template docs |
| **Total** | **52-78 hours** | **6-10 days of work** |

---

## 🎯 Success Metrics

**User Adoption:**
- % of new YokeFlow projects using generated specs
- Avg time to create spec (target: <10 minutes)
- Completion rate of wizard

**Quality:**
- % of generated projects that initialize successfully
- % of generated projects that complete without spec changes
- User satisfaction ratings

**Template Effectiveness:**
- Most popular templates
- Template completion rates
- Generated spec average quality score

---

## 🚀 MVP Feature Set

**Phase 1 (4-6 weeks):**
1. Basic wizard with 5 questions
2. 3 starter templates (SaaS, E-commerce, Dashboard)
3. Single-file output (main.md)
4. Download as .txt/.md
5. Copy to clipboard

**Phase 2 (2-3 weeks):**
1. Multi-file output (main + supporting files)
2. Live preview
3. Template variables system
4. 5 additional templates

**Phase 3 (2-3 weeks):**
1. YokeFlow API integration
2. "Upload to YokeFlow" button
3. Save/load draft specs
4. Community template sharing

---

## 💡 Advanced Features (Future)

**AI-Powered Enhancements:**
- Use Claude to analyze rough ideas → generate questions
- Auto-suggest features based on project type
- Validate spec completeness with AI
- Generate test scenarios automatically

**Collaboration:**
- Team spec creation (multiple stakeholders)
- Comment/review workflow
- Version comparison
- Approval process

**Learning:**
- Track which spec patterns lead to successful projects
- Auto-improve templates based on outcomes
- Suggest spec improvements based on YokeFlow session data

---

## 📚 Reference Projects to Study

**B-MAD (Behavioral Modeling and Design):**
- Structured requirements gathering
- Use case driven
- Behavior-focused specs

**SpecKit:**
- Template marketplace
- Component library
- Export to multiple formats

**PRP (Product Requirement Prompts):**
- Templates

---

**Priority:** MEDIUM-HIGH (v1.2 or standalone launch)

**Why Build This:**
- Lowers barrier to entry for YokeFlow
- Many users struggle with "blank page syndrome"
- Improves spec quality → better YokeFlow outcomes
- Marketing tool (can be free/public)
- Differentiator from competitors

**Why Wait:**
- Need real-world YokeFlow usage data first
- Learn which spec patterns work best
- Gather user feedback on pain points
- v1.0 must be stable first

---

**Recommendation:** Build as standalone tool after YokeFlow v1.0 release, once we have data on successful spec patterns.

### 4. UI Enhancements

**Session Logs Viewer** (Status: ✅ Complete - Polish optional)
- Current: TXT/JSONL viewing, download, tab filtering
- Future: Syntax highlighting, search/filter, side-by-side view, export to PDF/HTML

**Screenshots Gallery** (Status: ✅ Complete - Enhancements on wishlist)
- Current: Chronological gallery with lightbox
- Future: Filter/search, bulk download, side-by-side comparison, annotations, timeline view

**History Tab Metrics** (Status: ✅ Core complete - Advanced analytics deferred)
- Current: Token breakdown, cost, tool usage, model info
- Future: Performance metrics, visual timeline, session comparison, trend analysis

**Priority:** LOW-MEDIUM (current implementations meet needs)

### 5. Brownfield/Non-UI Codebase Support

**Challenges:**
- Current focus on greenfield projects with browser testing
- Need GitHub import capability
- Adapt testing strategy for non-UI code

**Priority:** MEDIUM-HIGH (expand use cases)

---

## 🔮 FUTURE ENHANCEMENTS

### Multi-User Support & Authentication
**Status:** Planning phase

**Current State:**
- Single-user JWT authentication in place
- Development mode for easy local testing

**Future Goals:**
- Multi-user support with user accounts
- Project permissions and sharing
- Team collaboration features
- API key management per user
- Role-based access control (admin/developer/viewer)
- Activity logs per user

**Priority:** HIGH (for production SaaS deployment)

### GitHub Integration Enhancements
**Status:** Ideas stage

**Potential Features:**
- Auto-create GitHub repositories for generated projects
- Push code directly to GitHub
- Create pull requests for review
- Integration with GitHub Issues
- Sync tasks with GitHub Projects
- CI/CD pipeline generation

**Priority:** MEDIUM

### Deployment Automation
**Status:** Ideas stage

**Potential Features:**
- One-click deployment to Vercel, Netlify, or Railway
- Digital Ocean integration for full-stack apps
- Docker image generation for deployments
- CI/CD pipeline creation
- Environment variable management across environments
- Automated testing before deployment

**Priority:** MEDIUM

### Docker Container Management
**Status:** ✅ Core features complete - Advanced monitoring deferred

**Implemented:**
- Container reuse, auto-cleanup on deletion, auto-stop on completion
- Dedicated /containers page with start/stop/delete controls
- API endpoints for container management

**Future:**
- Retention policies (keep stopped containers for X days)
- Periodic cleanup tasks
- Container health monitoring (CPU/memory tracking)
- Disk space alerts

**Priority:** MEDIUM (core features solve main issues)

---

## 🧪 TESTING & QUALITY ASSURANCE

### Comprehensive Test Suite Creation
**Status:** Needed for production confidence

**Current State:**
- ✅ `test_security.py` - 64 tests passing (blocklist validation)
- ⚠️ Other test suites removed as obsolete after major refactoring

**Future Goals:**
- **Unit Tests:**
  - Core modules (orchestrator, agent, database, quality_integration)
  - API endpoints (CRUD operations, WebSocket)
  - MCP tools (task management, bash_docker)
  - Review system (metrics, deep reviews)
  - Sandbox manager (Docker operations)

- **Integration Tests:**
  - End-to-end project workflow (create → initialize → code → complete)
  - Database operations with real PostgreSQL
  - Docker container lifecycle
  - Quality review triggers and execution
  - Session state management

- **UI Tests:**
  - Web UI component tests (Jest/React Testing Library)
  - E2E tests with Playwright
  - API integration tests from UI
  - WebSocket connection handling

- **Performance Tests:**
  - Session execution time benchmarks
  - Database query performance
  - API endpoint response times
  - Memory usage monitoring

- **Test Infrastructure:**
  - CI/CD integration (GitHub Actions)
  - Test coverage reporting
  - Automated test runs on PR
  - Performance regression detection

**Priority:** HIGH (before v1.1 release)

**Estimated Effort:** 40-60 hours

---

## 💡 RESEARCH & EXPLORATION

### Ideas Worth Investigating

1. **Agent Collaboration**
   - Multiple agents working on same project
   - Specialized agents for frontend/backend/testing
   - Agent-to-agent communication
   - Task delegation and coordination

2. **Advanced Testing**
   - AI-generated unit tests
   - Visual regression testing
   - Performance testing automation
   - Test coverage analysis
   - Automated bug detection

3. **Code Review Integration**
   - AI code review before commits
   - Style guide enforcement
   - Security vulnerability scanning
   - Best practices suggestions
   - Automated refactoring suggestions

4. **Custom Agent Templates**
   - User-defined agent behaviors
   - Project-specific prompts
   - Industry-specific templates (e-commerce, SaaS, etc.)
   - Template marketplace/sharing

5. **Incremental Development**
   - Modify existing codebases (not just greenfield)
   - Feature additions to generated projects
   - Bug fix sessions
   - Refactoring support
   - Legacy code modernization

6. **AI Model Selection & Optimization**
   - Automatic model selection based on task complexity
   - Cost optimization strategies
   - Hybrid approaches (multiple models per session)
   - Fine-tuned models for specific project types

7. **Real-time Collaboration**
   - Live session viewing for multiple users
   - Chat/comments during sessions
   - Manual intervention/steering during sessions
   - Collaborative spec editing

8. **Analytics & Insights**
   - Project success prediction
   - Time/cost estimation improvements
   - Pattern recognition across projects
   - Common failure modes analysis
   - Best practices recommendations

---

## 🐛 KNOWN ISSUES (To Address Post-Release)

### 1. Docker Desktop Stability on macOS
**Status:** Mitigated with watchdog

- Docker Desktop can crash during long-running sessions
- Workaround: `docker-watchdog.sh` auto-restarts Docker
- See [docs/PREVENTING_MAC_SLEEP.md](docs/PREVENTING_MAC_SLEEP.md)

**Future Solution:**
- Investigate alternative container runtimes (Podman, Colima)
- Improve Docker health monitoring
- Better error recovery mechanisms

**Priority:** LOW (workaround effective)

### 2. Database Connection Pool Exhaustion
**Status:** Monitoring

- Occasional connection pool exhaustion on long sessions
- May need to tune pool size or timeout settings

**Future Solution:**
- Dynamic connection pool sizing
- Better connection lifecycle management
- Connection leak detection

**Priority:** MEDIUM

---

## 📚 DOCUMENTATION NEEDS (Post-Release)

### High Priority
- [ ] Create deployment guide for production
- [ ] Create API documentation (OpenAPI/Swagger)
- [ ] Video tutorials for Web UI
- [ ] Troubleshooting guide expansion

### Medium Priority
- [ ] Create user guide for non-technical users
- [ ] Contributing guide for open source
- [ ] Migration guide for users of original autonomous-coding
- [ ] Best practices guide

### Low Priority
- [ ] Architecture diagrams
- [ ] Database schema visualization
- [ ] MCP protocol documentation
- [ ] Performance tuning guide

---

## 🚀 DEPLOYMENT ROADMAP

### Stage 3: Hosted Service (Future)
- [ ] Deploy to Digital Ocean or AWS
- [ ] Multi-user authentication
- [ ] Payment integration (if SaaS)
- [ ] Monitoring and alerting
- [ ] Production database backups
- [ ] CDN for static assets
- [ ] Load balancing
- [ ] Auto-scaling

---

**Note:** This is a living document. Priorities may change based on user feedback and production needs.
Items in this file are **not** blocking the initial release - they are enhancements for future versions.
