# Graph Report - .  (2026-05-23)

## Corpus Check
- Corpus is ~32,268 words - fits in a single context window. You may not need a graph.

## Summary
- 424 nodes · 722 edges · 34 communities (21 shown, 13 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 57 edges (avg confidence: 0.84)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Journey & Step Cards|Journey & Step Cards]]
- [[_COMMUNITY_Auth Gate & Sign-In Flow|Auth Gate & Sign-In Flow]]
- [[_COMMUNITY_Mission Cards & Session State|Mission Cards & Session State]]
- [[_COMMUNITY_Frontend Dependencies|Frontend Dependencies]]
- [[_COMMUNITY_Onboarding & WhatsApp Opt-In|Onboarding & WhatsApp Opt-In]]
- [[_COMMUNITY_App Shell & Routing|App Shell & Routing]]
- [[_COMMUNITY_Home Page & Curiosity Input|Home Page & Curiosity Input]]
- [[_COMMUNITY_TypeScript Config|TypeScript Config]]
- [[_COMMUNITY_SEO, Meta & Constellation|SEO, Meta & Constellation]]
- [[_COMMUNITY_Cosmic Landing Page|Cosmic Landing Page]]
- [[_COMMUNITY_Admin Panel|Admin Panel]]
- [[_COMMUNITY_Proxy & Deploy Config|Proxy & Deploy Config]]
- [[_COMMUNITY_Next.js App Router Pages|Next.js App Router Pages]]
- [[_COMMUNITY_Node TypeScript Config|Node TypeScript Config]]
- [[_COMMUNITY_Vercel Config|Vercel Config]]
- [[_COMMUNITY_Next.js Root Layout|Next.js Root Layout]]
- [[_COMMUNITY_CSS Theming & Dark Mode|CSS Theming & Dark Mode]]
- [[_COMMUNITY_Spark Answer Display|Spark Answer Display]]
- [[_COMMUNITY_Coming Soon Placeholder|Coming Soon Placeholder]]
- [[_COMMUNITY_Spark Meter|Spark Meter]]
- [[_COMMUNITY_Frontend Docs & Robots|Frontend Docs & Robots]]
- [[_COMMUNITY_Markdown Renderer Concept|Markdown Renderer Concept]]
- [[_COMMUNITY_Spark Meter Concept|Spark Meter Concept]]
- [[_COMMUNITY_Journey Filter & Search|Journey Filter & Search]]
- [[_COMMUNITY_Next.js Config|Next.js Config]]
- [[_COMMUNITY_PostCSS Config|PostCSS Config]]
- [[_COMMUNITY_Tailwind Config|Tailwind Config]]
- [[_COMMUNITY_Vite Config|Vite Config]]
- [[_COMMUNITY_Budget Exhaustion Pattern|Budget Exhaustion Pattern]]

## God Nodes (most connected - your core abstractions)
1. `useAuth()` - 45 edges
2. `request()` - 23 edges
3. `compilerOptions` - 17 edges
4. `clsx` - 13 edges
5. `Journey` - 13 edges
6. `useSubscription()` - 13 edges
7. `HomeCosmic()` - 13 edges
8. `Home()` - 11 edges
9. `ConversationInterface()` - 10 edges
10. `getUserProfile()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Email Capture (UI-only)` --semantically_similar_to--> `Hardcoded Plan Features (Known Quirk)`  [INFERRED] [semantically similar]
  src/pages/Home.tsx → CLAUDE.md
- `CompletionOverlay()` --conceptually_related_to--> `Capability Passport Concept`  [INFERRED]
  src/pages/Journey.tsx → CLAUDE.md
- `Font Preconnect (Inter, Garamond, Playfair, SpaceMono)` --conceptually_related_to--> `HomeCosmic()`  [INFERRED]
  index.html → src/pages/HomeCosmic.tsx
- `Learn()` --implements--> `Auth-Gating Pattern`  [INFERRED]
  src/pages/Learn.tsx → CLAUDE.md
- `Profile()` --implements--> `Auth-Gating Pattern`  [INFERRED]
  src/pages/Profile.tsx → CLAUDE.md

## Hyperedges (group relationships)
- **API Proxy Pattern (Vite dev, Vercel prod, Next.js)** — concept_vite_proxy, concept_vercel_rewrites, concept_next_proxy [INFERRED 0.85]
- **App Bootstrap Chain: main.tsx → App.tsx → AppShell → Routes** — src_main_tsx, src_app_tsx, concept_appshell, concept_lazy_routes [EXTRACTED 1.00]
- **Explore Flow: CuriosityInput → ExplorePage → StepNode rendering** — components_curiosityinput_tsx, app_explore_page_tsx, concept_optimistic_step_toggle [INFERRED 0.85]
- **WhatsApp Opt-In Flow (OnboardingModal + WhatsAppNudgeBanner + optInWhatsApp API)** — components_onboardingmodal_onboardingmodal, learn_whatsappnudgebanner_whatsappnudgebanner, lib_api_optinwhatsapp [EXTRACTED 0.95]
- **Budget Exhaustion Handling (ConversationInterface + StepNode + UpgradePrompt)** — learn_conversationinterface_conversationinterface, components_stepnode_stepnode, components_upgradeprompt_upgradeprompt [EXTRACTED 0.95]
- **Learn Page Panel Trio (TodaysSpark + ConversationInterface + KnowledgeUniverse)** — learn_todaysspark_todaysspark, learn_conversationinterface_conversationinterface, learn_knowledgeuniverse_knowledgeuniverse [INFERRED 0.95]
- **Optimistic Step Toggle Pattern (Journey + Explore + API)** — pages_journey_togglestep, pages_explore_togglestep, claude_md_optimistic_update_pattern [INFERRED 0.90]
- **Auth-Gated Page Redirect Pattern (Learn + Explore + Profile)** — pages_learn_learn, pages_explore_explore, pages_profile_profile [INFERRED 0.90]
- **Mind Signature Generation and Public Verification Flow** — pages_mindsignature_mindsignature, pages_mindsignature_handlegenerate, pages_verify_verify [INFERRED 0.85]

## Communities (34 total, 13 thin omitted)

### Community 0 - "Journey & Step Cards"
Cohesion: 0.07
Nodes (48): Optimistic Update Pattern, difficultyStyle, JourneyCard(), JourneyCardProps, StepNodeProps, typeConfig, FILTERS, askSpark() (+40 more)

### Community 1 - "Auth Gate & Sign-In Flow"
Cohesion: 0.07
Nodes (43): GateModal(), GateModalProps, GoogleSignInButton(), GoogleSignInButtonProps, StepNode(), MESSAGES, UpgradePrompt(), UpgradePromptProps (+35 more)

### Community 2 - "Mission Cards & Session State"
Cohesion: 0.07
Nodes (37): Auth-Gating Pattern, Anonymous Session ID Pattern, DIFFICULTY_COLOR, MissionCard(), MissionCardProps, TYPE_CONFIG, Capability Passport Concept, Spark Rate Limiting (5 free sparks) (+29 more)

### Community 3 - "Frontend Dependencies"
Cohesion: 0.06
Nodes (30): dependencies, d3, firebase, lucide-react, react, react-dom, react-helmet-async, react-router-dom (+22 more)

### Community 4 - "Onboarding & WhatsApp Opt-In"
Cohesion: 0.11
Nodes (25): COUNTRY_CODES, guessDefaultCode(), OnboardingModal(), TOPICS, WhatsApp Opt-In Flow, COUNTRY_CODES, guessCode(), WhatsAppNudgeBanner() (+17 more)

### Community 5 - "App Shell & Routing"
Cohesion: 0.08
Nodes (20): ErrorBoundary, State, AppShell (Provider Tree + Routing), Lazy-loaded Routes with Suspense, React Context Provider Tree, Manual Scroll Restoration (SPA Pattern), Sentry Error Tracking Init, Admin (+12 more)

### Community 6 - "Home Page & Curiosity Input"
Cohesion: 0.12
Nodes (15): FEATURED, HOW_IT_WORKS, CuriosityInputProps, PLACEHOLDERS, QUICK_PICKS, AUTH_LINKS, Navigation(), PUBLIC_LINKS (+7 more)

### Community 7 - "TypeScript Config"
Cohesion: 0.10
Nodes (20): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+12 more)

### Community 8 - "SEO, Meta & Constellation"
Cohesion: 0.11
Nodes (16): PageMetaProps, Mind Signature Concept, ConstellationData, ConstellationLink, ConstellationMap(), ConstellationNode, DOMAIN_COLORS, Props (+8 more)

### Community 9 - "Cosmic Landing Page"
Cohesion: 0.16
Nodes (17): Light Delay as Learning Gap Metaphor, Font Preconnect (Inter, Garamond, Playfair, SpaceMono), Open Graph Meta Tags, HTML Entry Root (index.html), CustomCursor(), FIELD_DATA, FIELD_TAGS, HomeCosmic() (+9 more)

### Community 10 - "Admin Panel"
Cohesion: 0.16
Nodes (13): Hardcoded Plan Features (Known Quirk), Admin(), AIConfig, DailyUsage, INTERACTION_LABELS, ModelOption, PLAN_FEATURES, PLAN_ICONS (+5 more)

### Community 11 - "Proxy & Deploy Config"
Cohesion: 0.20
Nodes (7): PageMeta Component, Next.js App Router alongside Vite/React SPA, Next.js API Proxy Rewrites, Vercel API Proxy Rewrites, Vercel Security Headers (CSP, X-Frame, etc.), Vite Dev Proxy for /api, vercel.json (Deployment Config)

### Community 12 - "Next.js App Router Pages"
Cohesion: 0.20
Nodes (10): src/app/explore/page.tsx, src/app/journey/[id]/page.tsx, src/app/layout.tsx (Next.js Root Layout), src/app/page.tsx (Next.js Home Page), CuriosityInput Component, GateModal Component, Cycling Placeholder Animation (CuriosityInput), Hardcoded Featured Journeys (static data) (+2 more)

### Community 13 - "Node TypeScript Config"
Cohesion: 0.22
Nodes (8): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, strict, include

### Community 14 - "Vercel Config"
Cohesion: 0.33
Nodes (5): buildCommand, headers, installCommand, outputDirectory, rewrites

### Community 15 - "Next.js Root Layout"
Cohesion: 0.40
Nodes (3): inter, metadata, viewport

## Ambiguous Edges - Review These
- `usePageTitle()` → `Journeys()`  [AMBIGUOUS]
  src/pages/Journeys.tsx · relation: calls

## Knowledge Gaps
- **188 isolated node(s):** `composite`, `skipLibCheck`, `module`, `moduleResolution`, `allowSyntheticDefaultImports` (+183 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `usePageTitle()` and `Journeys()`?**
  _Edge tagged AMBIGUOUS (relation: calls) - confidence is low._
- **Why does `useAuth()` connect `Auth Gate & Sign-In Flow` to `Journey & Step Cards`, `Mission Cards & Session State`, `Onboarding & WhatsApp Opt-In`, `App Shell & Routing`, `Home Page & Curiosity Input`, `SEO, Meta & Constellation`, `Cosmic Landing Page`, `Admin Panel`?**
  _High betweenness centrality (0.210) - this node is a cross-community bridge._
- **Why does `clsx` connect `Mission Cards & Session State` to `Journey & Step Cards`, `Auth Gate & Sign-In Flow`, `Frontend Dependencies`, `Onboarding & WhatsApp Opt-In`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `dependencies` connect `Frontend Dependencies` to `Mission Cards & Session State`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `clsx` (e.g. with `JourneyCard()` and `OnboardingModal()`) actually correct?**
  _`clsx` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `composite`, `skipLibCheck`, `module` to the rest of the system?**
  _195 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Journey & Step Cards` be split into smaller, more focused modules?**
  _Cohesion score 0.07297726070861978 - nodes in this community are weakly interconnected._