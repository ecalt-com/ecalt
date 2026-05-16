# ECALT — Product Roadmap

> **Stack**: React + Vite (Vercel) · FastAPI (Railway) · PostgreSQL (Supabase) · Firebase Auth  
> **Goal**: World-class learning product — great UX, strong SEO, viral growth loops, production-grade backend

---

## Status Key
- ✅ **Done**
- 🔴 **P0** — Fix now, blocking quality/trust
- 🟠 **P1** — High impact, next sprint
- 🟡 **P2** — Important, schedule soon
- 🟢 **P3** — Nice-to-have, backlog

---

## What's Already Shipped

| Area | Item |
|------|------|
| Auth | Firebase Google Sign-In, token verification via PyJWT+JWKS, auth flash fix |
| Backend | Full psycopg2 migration (no Supabase SDK), connection pool, RealDictCursor |
| AI | Step content generation with Claude (on-demand, cached in DB) |
| Progress | Per-user step tracking, completion overlay, toast feedback |
| Passport | Capability passport with badges, progress tracking, topic cloud |
| Onboarding | Interest picker shown after first sign-in |
| Performance | React.lazy code splitting, `HelmetProvider` + `PageMeta` per route |
| SEO | robots.txt, sitemap.xml, JSON-LD (Course + WebSite schema), OG meta tags |
| Security | CORS tightened to specific origins, health check with DB ping |

---

## 1. Retention & Re-engagement

These directly determine whether users come back. Each one is a day-1 user converting to a week-1 user.

| # | Task | Priority | Why it matters |
|---|------|----------|----------------|
| 1.1 | **"Continue where you left off"** card on Home | 🔴 P0 | Biggest retention lever — zero effort re-entry |
| 1.2 | **Streak counter** (days of consecutive learning) | 🟠 P1 | Habit formation; Duolingo's #1 retention mechanism |
| 1.3 | **Email capture on Home** ("Get weekly journey picks") | 🟠 P1 | Own your audience before launch |
| 1.4 | **"More like this"** related journeys at bottom of Journey page | 🟡 P2 | Reduces drop-off after finishing a journey |
| 1.5 | **Push/email notification for streak at risk** | 🟢 P3 | Re-engagement for churned users |

#### 1.1 — "Continue where you left off" (Home.tsx)
After sign-in, fetch the most recently touched in-progress journey and show a card above the hero input:
```tsx
// Fetch from GET /api/v1/passport — pick last_active journey
// Show: journey icon + title + "X of Y steps · Resume →"
// Only shown when user is authenticated and has in-progress journeys
```

#### 1.2 — Streak system
Add `last_active_date DATE` and `streak_days INT DEFAULT 0` to `users` table.  
On any `markStepComplete` call: if `last_active_date = today - 1`, increment streak; if `= today`, no-op; else reset to 1.  
Show on Home (below spark meter) and Passport header.

---

## 2. Viral & Sharing

These turn users into distribution channels. Each completed journey is a sharing opportunity.

| # | Task | Priority | Why it matters |
|---|------|----------|----------------|
| 2.1 | **Share journey as link** with dynamic OG preview | 🟠 P1 | Every shared link is a free ad impression |
| 2.2 | **Completion certificate** — downloadable/shareable image | 🟡 P2 | LinkedIn-shareable proof of learning |
| 2.3 | **"Built with ECALT"** footer on shared pages | 🟢 P3 | Product-led growth watermark |

#### 2.1 — Share button on Journey page
Already has a `Share2` icon imported — wire it up:
```tsx
// On click: navigator.share({ title, url }) || copy to clipboard
// URL: https://ecalt.vercel.app/journey/{id}
// The PageMeta og:image and og:title already set — sharing works immediately
```
The hard part is dynamic OG images per journey. Options:
- **Simple (now)**: One generic OG image. Already works since PageMeta sets og:title dynamically (social crawlers see it).
- **Better (later)**: Vercel Edge Function `GET /api/og?title=...` that renders an image using `@vercel/og`.

#### 2.2 — Completion certificate
Use the browser Canvas API to render a styled certificate PNG:
```
ECALT Capability Certificate
[User's name] has completed [Journey title]
[Date] · ecalt.vercel.app
```
Show "Download Certificate" button in the CompletionOverlay.

---

## 3. SEO — Remaining Gaps

| # | Task | Priority | Impact |
|---|------|----------|--------|
| 3.1 | **Create og-image.png** (1200×630) | 🔴 P0 | Referenced in HTML but file doesn't exist yet |
| 3.2 | **Dynamic sitemap endpoint** in backend | 🟠 P1 | AI-generated journeys indexed as long-tail SEO pages |
| 3.3 | **Prerendering** for static routes | 🟡 P2 | Crawlers get full HTML without JS execution |
| 3.4 | **Submit sitemap to Google Search Console** | 🟡 P2 | Faster indexing of all routes |
| 3.5 | **`hreflang`** for future i18n | 🟢 P3 | International SEO |

#### 3.1 — OG Image (urgent)
The HTML references `/og-image.png` but the file doesn't exist. Create it:
- Use Figma / Canva / any tool: 1200×630px, dark background, ECALT logo, tagline "Turn Curiosity Into Capability"
- Export as PNG → place at `frontend/public/og-image.png`
- Test at: https://developers.facebook.com/tools/debug/

#### 3.2 — Dynamic sitemap
Backend adds `GET /api/v1/sitemap.xml` returning all curated + public AI journeys.  
Vercel `vercel.json` fetches it at build time or uses a rewrite:
```json
{ "source": "/sitemap.xml", "destination": "/api/sitemap.xml" }
```

---

## 4. UX Polish

| # | Task | Priority | Why it matters |
|---|------|----------|----------------|
| 4.1 | **Error boundaries** on every route | 🔴 P0 | One React crash = blank page for all users |
| 4.2 | **Keyboard shortcut**: press `/` focuses curiosity input | 🟠 P1 | Power users love this; makes the product feel fast |
| 4.3 | **Empty state on Journeys** page when search returns nothing | 🟠 P1 | Dead ends feel broken |
| 4.4 | **Mobile StepNode experience** review | 🟠 P1 | Expanded step content UX on small screens |
| 4.5 | **Page transition animation** (fade/slide between routes) | 🟡 P2 | Makes app feel premium |
| 4.6 | **Back-navigation scroll restoration** | 🟡 P2 | Journey → back → Journeys resets scroll |
| 4.7 | **Accessibility audit** (ARIA, keyboard nav, focus traps) | 🟡 P2 | Screen readers; also a trust signal |
| 4.8 | **Feedback on AI step content** ("Was this helpful? 👍 👎") | 🟡 P2 | Improves content quality over time |

#### 4.1 — Error boundary (quick)
```tsx
// src/components/ErrorBoundary.tsx
class ErrorBoundary extends Component<{children: ReactNode}, {error: Error | null}> {
  state = { error: null }
  static getDerivedStateFromError(e: Error) { return { error: e } }
  render() {
    if (this.state.error) return <ErrorPage />
    return this.props.children
  }
}
// Wrap each <Route element={...}> in App.tsx
```

#### 4.2 — Keyboard shortcut
```tsx
// In Home.tsx, add to useEffect:
const handleKey = (e: KeyboardEvent) => {
  if (e.key === '/' && document.activeElement?.tagName !== 'INPUT') {
    e.preventDefault()
    inputRef.current?.focus()
  }
}
document.addEventListener('keydown', handleKey)
```

---

## 5. Backend Hardening

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 5.1 | **Rate limiting** on public endpoints (slowapi) | 🔴 P0 | Spark endpoint is abusable without it |
| 5.2 | **Sentry error monitoring** | 🟠 P1 | Know about crashes before users report |
| 5.3 | **Step content pre-warming** | 🟠 P1 | Background generate all steps after journey creation |
| 5.4 | **Response caching headers** | 🟡 P2 | Journey list rarely changes — 60s CDN cache |
| 5.5 | **Alembic migrations** | 🟡 P2 | Schema versioning, safe rollbacks |
| 5.6 | **Structured JSON logging** | 🟡 P2 | Railway log search needs structured output |
| 5.7 | **Request ID middleware** | 🟡 P2 | Trace requests across logs |
| 5.8 | **DB connection health in Railway uptime check** | ✅ Done | `/health` now pings DB |

#### 5.1 — Rate limiting (add now)
```bash
pip install slowapi
```
```python
# main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# spark.py endpoint:
@router.post("")
@limiter.limit("30/minute")
async def spark(request: Request, ...):
```

#### 5.2 — Sentry
```bash
pip install sentry-sdk[fastapi]
```
```python
# main.py
import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
```
Add `SENTRY_DSN` to Railway env vars (free tier covers 5k errors/month).

#### 5.3 — Step content pre-warming
After `POST /api/v1/explore` creates a journey, fire a background task that calls `generate_step_content` for each step:
```python
# FastAPI BackgroundTasks
background_tasks.add_task(warm_journey_steps, journey.id, journey.steps)
```
Users get instant content on first expand instead of waiting 3–4 seconds.

---

## 6. Security

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 6.1 | **Content-Security-Policy header** in vercel.json | 🟠 P1 | XSS protection |
| 6.2 | **`X-Frame-Options`, `X-Content-Type-Options`** headers | 🟠 P1 | Standard hardening |
| 6.3 | **Add `ANTHROPIC_API_KEY`** to Railway secrets | 🔴 P0 | Currently blank — AI features don't work in prod |
| 6.4 | **OWASP dependency scanning** in CI | 🟢 P3 | `pip audit`, `npm audit` |

#### 6.1 & 6.2 — Security headers in vercel.json
```json
"headers": [
  {
    "source": "/(.*)",
    "headers": [
      { "key": "X-Frame-Options", "value": "DENY" },
      { "key": "X-Content-Type-Options", "value": "nosniff" },
      { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
      { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self' 'unsafe-inline' https://apis.google.com; connect-src 'self' https://*.firebaseapp.com https://*.googleapis.com https://ecalt-production.up.railway.app; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com;" }
    ]
  }
]
```

---

## 7. Performance (Core Web Vitals)

| Metric | Current | Target | Fix |
|--------|---------|--------|-----|
| LCP | ~2.5s | < 2.5s | Preload fonts, pre-warm step content |
| FCP | ~1.8s | < 1.8s | Code splitting ✅ Done |
| CLS | ~0 | < 0.1 | Already good |
| INP | ~80ms | < 200ms | Already good |
| TTFB | ~200ms | < 600ms | Railway cold starts — keep-alive ping |

#### Quick wins
- `<link rel="preconnect" href="https://apis.google.com">` in index.html
- `loading="lazy"` on any `<img>` tags
- Railway keep-alive: ping `/health` every 5 min from a cron service (prevents cold starts)

---

## 8. Product Features (Growth)

| # | Feature | Priority | Why |
|---|---------|----------|-----|
| 8.1 | **Admin analytics page** (journey views, completions, DAU) | 🟡 P2 | Operator visibility |
| 8.2 | **Search across journeys** (Journeys page already has it; add to Home) | 🟡 P2 | Discovery |
| 8.3 | **Journey rating** (1-5 stars after completion) | 🟡 P2 | Surface best content |
| 8.4 | **"Suggest a journey"** form | 🟢 P3 | Community-driven content |
| 8.5 | **Parent/family accounts** | 🟢 P3 | Core brand promise |
| 8.6 | **i18n** (Hindi as first expansion) | 🟢 P3 | Massive TAM in India |

---

## 9. CI/CD Pipeline

```
GitHub Actions — on push to main:
  1. lint + typecheck   (eslint, tsc --noEmit)
  2. backend tests      (pytest)
  3. deploy frontend    → Vercel (auto via GitHub integration)
  4. deploy backend     → Railway (auto via GitHub integration)
```

---

## Recommended Execution Order

### This week (P0 blockers)
1. **Add `ANTHROPIC_API_KEY` to Railway** — AI features are broken in prod without it
2. **Create og-image.png** — referenced but missing; embarrassing on social share
3. **Error boundaries** — one component crash = blank white page
4. **Rate limiting** on spark endpoint — open to abuse right now
5. **"Continue where you left off"** card on Home — highest retention impact

### Next sprint (P1 — growth)
1. Share journey as link (already works — just add the button)
2. Streak counter (backend + home UI)
3. Email capture on Home
4. Sentry setup
5. Step content pre-warming (background tasks after explore)
6. Security headers in vercel.json
7. Keyboard shortcut `/` on Home

### Following sprint (P2 — polish)
1. Completion certificate download
2. "More like this" related journeys
3. Dynamic sitemap endpoint
4. Page transition animations
5. Journey rating system
6. Alembic migrations

---

## SEO Keyword Opportunities

| Target keyword | Page | Monthly volume (est.) |
|---------------|------|----------------------|
| "how does DNA work explained" | /journey/journey-dna | 8k |
| "machine learning explained simply" | /journey/journey-ml | 22k |
| "how do rockets work" | /journey/journey-rockets | 18k |
| "music theory for beginners" | /journey/journey-music | 40k |
| "AI learning platform for kids" | / | 1.2k |
| "curiosity-driven learning" | / | 800 |
| "personalized learning journey" | / | 3k |

**Key insight**: Each AI-generated journey from `/explore` is a potential long-tail SEO page. Once indexed, "How do black holes form — learning journey" captures zero-competition traffic. Consider making top AI-generated journeys publicly accessible (no auth required) so crawlers can index them.

---

## Tools to Set Up

| Tool | Purpose | Cost |
|------|---------|------|
| Google Search Console | Index monitoring, keyword data | Free |
| Sentry | Error tracking | Free tier (5k errors/mo) |
| Vercel Analytics | Real user performance metrics | Free |
| Lighthouse CI | Automated Core Web Vitals in CI | Free |
