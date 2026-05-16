# ECALT — Improvement Plan

> **Stack**: React + Vite (Vercel) · FastAPI (Railway) · PostgreSQL (Supabase) · Firebase Auth  
> **Goal**: Production-grade quality + strong Google SEO visibility

---

## Priority Legend
- 🔴 **P0** — Fix now, blocking quality/trust
- 🟠 **P1** — High impact, do this sprint
- 🟡 **P2** — Important, schedule next
- 🟢 **P3** — Nice-to-have, backlog

---

## 1. SEO — Search Engine Optimization

### The Core Problem
ECALT is a React SPA. Google CAN crawl SPAs but runs a two-wave process: HTML is indexed immediately, JavaScript renders days later. Dynamic content fetched from the API (journey titles, descriptions) may never be indexed — or indexed weeks late. This kills rankings for the most valuable pages (`/journey/:id`).

### Fixes (in order)

| # | Task | Priority | Impact |
|---|------|----------|--------|
| 1.1 | Add `public/robots.txt` and `public/sitemap.xml` | 🔴 P0 | Crawl budget, discoverability |
| 1.2 | Create an OG image (`public/og-image.png`, 1200×630) | 🔴 P0 | Social sharing CTR |
| 1.3 | Add JSON-LD structured data to Home and Journey pages | 🟠 P1 | Rich results in Google |
| 1.4 | Add prerendering for key routes via `vite-plugin-prerender` | 🟠 P1 | Crawlers get full HTML immediately |
| 1.5 | Server-generate dynamic journey pages (`/journey/:id`) | 🟠 P1 | Long-tail keyword indexing |
| 1.6 | Add dynamic `<meta>` tags per route (title, description, OG) | 🟠 P1 | CTR from SERPs |
| 1.7 | Submit sitemap to Google Search Console | 🟡 P2 | Faster indexing |
| 1.8 | Add `hreflang` and language meta for future i18n | 🟢 P3 | International SEO |

#### 1.1 — robots.txt (add to `frontend/public/robots.txt`)
```
User-agent: *
Allow: /
Disallow: /api/

Sitemap: https://ecalt.vercel.app/sitemap.xml
```

#### 1.2 — sitemap.xml (add to `frontend/public/sitemap.xml`)
Static routes known at build time. Journey pages need dynamic generation.
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://ecalt.vercel.app/</loc><priority>1.0</priority></url>
  <url><loc>https://ecalt.vercel.app/journeys</loc><priority>0.9</priority></url>
  <url><loc>https://ecalt.vercel.app/journey/journey-dna</loc><priority>0.8</priority></url>
  <url><loc>https://ecalt.vercel.app/journey/journey-ml</loc><priority>0.8</priority></url>
  <url><loc>https://ecalt.vercel.app/journey/journey-rockets</loc><priority>0.8</priority></url>
  <url><loc>https://ecalt.vercel.app/journey/journey-music</loc><priority>0.8</priority></url>
  <url><loc>https://ecalt.vercel.app/journey/journey-climate</loc><priority>0.8</priority></url>
  <url><loc>https://ecalt.vercel.app/journey/journey-finance</loc><priority>0.8</priority></url>
</urlset>
```

#### 1.3 — JSON-LD Structured Data
Add to `<head>` via a React component. For journey pages use `Course` schema:
```json
{
  "@context": "https://schema.org",
  "@type": "Course",
  "name": "The Code of Life: DNA Decoded",
  "description": "From double helix to protein factories...",
  "provider": { "@type": "Organization", "name": "ECALT" },
  "hasCourseInstance": { "@type": "CourseInstance", "courseMode": "online" }
}
```

#### 1.4 — Prerendering
Install `vite-plugin-prerender` and prerender static routes at build time:
```ts
// vite.config.ts
import { PrerenderPlugin } from 'vite-plugin-prerender'
plugins: [PrerenderPlugin({ routes: ['/', '/journeys', '/journey/journey-dna', ...] })]
```
This gives crawlers full HTML without waiting for JS.

#### 1.5 — Backend sitemap endpoint
Add `GET /api/v1/sitemap.xml` that includes all curated + public AI-generated journeys dynamically. Vercel can fetch and cache this at build or on-demand.

#### 1.6 — Dynamic meta tags
Create a `<PageMeta>` component using `document.head` manipulation (or `react-helmet-async`) that sets `<title>`, `<meta name="description">`, `og:title`, `og:description`, `og:url` per route. Use the journey title and description on detail pages.

---

## 2. Backend — Industry Standards

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 2.1 | Database migrations with Alembic | 🔴 P0 | Replace raw SQL schema file |
| 2.2 | Error monitoring with Sentry | 🟠 P1 | Know about errors before users report |
| 2.3 | Structured JSON logging | 🟠 P1 | Essential for Railway log search |
| 2.4 | API rate limiting (slowapi) | 🟠 P1 | Prevent abuse on public endpoints |
| 2.5 | Request ID middleware | 🟡 P2 | Trace requests across logs |
| 2.6 | Background task queue (ARQ / Redis) | 🟡 P2 | Offload AI generation from request cycle |
| 2.7 | Response caching (Redis) | 🟡 P2 | Cache journey list, step content |
| 2.8 | OpenAPI schema validation tests | 🟡 P2 | Contract tests against FastAPI |
| 2.9 | DB connection health check in `/health` | 🟠 P1 | Railway uptime checks |
| 2.10 | Alembic migrations in CI/CD | 🟢 P3 | Auto-migrate on deploy |

#### 2.1 — Alembic migrations
```bash
pip install alembic
alembic init migrations
# replaces supabase_schema.sql — version-controlled, rollback-safe
```

#### 2.4 — Rate limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("")
@limiter.limit("30/minute")
async def spark(request: Request, ...):
```

#### 2.9 — Health check with DB ping
```python
@router.get("")
async def health():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "degraded"
    return {"status": "ok", "db": db_status, "ts": datetime.utcnow().isoformat()}
```

---

## 3. Frontend — Industry Standards

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 3.1 | Route-based code splitting (React.lazy) | 🔴 P0 | Current bundle is ~400KB monolithic |
| 3.2 | Error boundaries on every route | 🟠 P1 | Prevent full-page crashes |
| 3.3 | Skeleton loading states everywhere | 🟠 P1 | Perceived performance |
| 3.4 | `react-helmet-async` for dynamic meta | 🟠 P1 | SEO-required |
| 3.5 | `public/manifest.json` for PWA | 🟡 P2 | "Add to home screen" on mobile |
| 3.6 | Service worker for offline fallback | 🟡 P2 | Works on flaky connections |
| 3.7 | Accessibility audit (WCAG 2.1 AA) | 🟡 P2 | Screen readers, keyboard nav |
| 3.8 | Cypress E2E tests for critical flows | 🟡 P2 | Spark → Mission → Journey |
| 3.9 | Storybook for shared components | 🟢 P3 | Component documentation |

#### 3.1 — Code splitting (biggest quick win)
```tsx
// App.tsx
const Home     = lazy(() => import('./pages/Home'))
const Explore  = lazy(() => import('./pages/Explore'))
const Journey  = lazy(() => import('./pages/Journey'))
const Journeys = lazy(() => import('./pages/Journeys'))
const Passport = lazy(() => import('./pages/Passport'))

// Wrap routes with <Suspense fallback={<PageSkeleton />}>
```
Expected: 400KB bundle → 4 chunks of ~100KB, loaded on demand.

#### 3.2 — Error boundary
```tsx
class RouteErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(e) { return { error: e } }
  render() {
    if (this.state.error) return <ErrorPage />
    return this.props.children
  }
}
```

---

## 4. Security

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 4.1 | Move `ANTHROPIC_API_KEY` to Railway secrets (not .env file) | 🔴 P0 | Currently blank in .env |
| 4.2 | Tighten CORS — replace `allow_origins=["*"]` with specific domains | 🔴 P0 | Currently wide open |
| 4.3 | Add Content-Security-Policy header in `vercel.json` | 🟠 P1 | XSS protection |
| 4.4 | Add `X-Frame-Options`, `X-Content-Type-Options` headers | 🟠 P1 | Standard hardening |
| 4.5 | Enforce HTTPS redirect in FastAPI | 🟠 P1 | Railway auto-does this, but explicit is better |
| 4.6 | Rotate Supabase DB password to one without special chars | 🟡 P2 | Avoids URL-encoding foot guns |
| 4.7 | Add OWASP dependency scanning in CI | 🟢 P3 | Safety/pip-audit |

#### 4.2 — CORS fix (main.py)
```python
allow_origins=settings.allowed_origins  # already split from ALLOWED_ORIGINS env var
# Set in Railway: ALLOWED_ORIGINS=https://ecalt.vercel.app,https://www.ecalt.com
```

---

## 5. Core Web Vitals (Google Ranking Signals)

Google uses LCP, FID/INP, and CLS as ranking signals. Current estimated scores:

| Metric | Current (estimate) | Target | Fix |
|--------|-------------------|--------|-----|
| LCP | ~2.5s | < 2.5s | Preload fonts, lazy-load below-fold |
| INP | ~80ms | < 200ms | Already good |
| CLS | ~0 | < 0.1 | Already good |
| FCP | ~1.8s | < 1.8s | Code splitting, smaller initial bundle |
| TTFB | ~200ms | < 600ms | Railway cold starts — add keep-alive ping |

#### Quick wins
- Add `<link rel="preconnect">` for Anthropic/Firebase domains
- Use `font-display: swap` (already using Google Fonts — verify this)
- Add `loading="lazy"` to any images
- Preload critical CSS

---

## 6. Product Features (Growth)

| # | Feature | Priority | Why |
|---|---------|----------|-----|
| 6.1 | Share journey as link with OG preview | 🟠 P1 | Viral distribution |
| 6.2 | Email capture / waitlist on Home | 🟠 P1 | Build audience before launch |
| 6.3 | Journey completion certificate (shareable image) | 🟡 P2 | Social proof, LinkedIn sharing |
| 6.4 | "Continue where you left off" on Home | 🟡 P2 | Retention |
| 6.5 | Admin dashboard (journey analytics, user count) | 🟡 P2 | Operator visibility |
| 6.6 | Search across journeys | 🟡 P2 | Discovery UX |
| 6.7 | Streak system (daily learning) | 🟢 P3 | Engagement |
| 6.8 | Parent/family accounts | 🟢 P3 | Core brand promise |

---

## 7. CI/CD Pipeline

```
GitHub Actions:
  on: push to main
  jobs:
    1. lint + typecheck (tsc, eslint)
    2. backend tests (pytest)
    3. alembic migrate (on merge to main)
    4. deploy frontend → Vercel (auto via Vercel GitHub integration)
    5. deploy backend → Railway (auto via Railway GitHub integration)
```

---

## Recommended Execution Order

### Week 1 — Foundation (P0s)
1. `robots.txt` + `sitemap.xml` → submit to Google Search Console
2. OG image (`og-image.png`)
3. Code splitting (React.lazy) — biggest performance win
4. CORS: replace `*` with production domain
5. Alembic setup

### Week 2 — SEO & Visibility
1. JSON-LD structured data on Home + Journey pages
2. `react-helmet-async` for dynamic per-page meta
3. Prerendering for static routes
4. Health check endpoint with DB ping
5. Sentry error monitoring

### Week 3 — Polish
1. Error boundaries
2. Rate limiting on public endpoints
3. PWA manifest
4. Email capture on Home

### Week 4 — Growth
1. Share links with OG previews
2. Journey completion certificate
3. Search across journeys
4. Google Search Console data review + keyword analysis

---

## SEO Keyword Opportunities

ECALT's content naturally targets high-intent, low-competition long-tail keywords:

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
| Vercel Analytics | Real user performance metrics | Free |
| Sentry | Error tracking | Free tier |
| Lighthouse CI | Automated Core Web Vitals in CI | Free |
| Ahrefs / Semrush | Keyword research, backlink analysis | Paid |
