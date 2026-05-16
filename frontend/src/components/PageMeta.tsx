import { Helmet } from 'react-helmet-async'

interface PageMetaProps {
  title?: string
  description?: string
  ogImage?: string
  canonicalPath?: string
  jsonLd?: object
}

const BASE_URL = 'https://ecalt.vercel.app'
const DEFAULT_OG_IMAGE = `${BASE_URL}/og-image.png`
const DEFAULT_DESCRIPTION =
  'Ask any question, get a personalized AI-powered learning journey. ECALT turns curiosity into capability for kids, families, and lifelong learners.'

export default function PageMeta({
  title,
  description = DEFAULT_DESCRIPTION,
  ogImage = DEFAULT_OG_IMAGE,
  canonicalPath,
  jsonLd,
}: PageMetaProps) {
  const fullTitle = title ? `${title} — ECALT` : 'ECALT — Turn Curiosity Into Capability'
  const canonical = canonicalPath ? `${BASE_URL}${canonicalPath}` : BASE_URL

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={canonical} />

      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:url" content={canonical} />
      <meta property="og:type" content="website" />

      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />

      {jsonLd && (
        <script type="application/ld+json">
          {JSON.stringify(jsonLd)}
        </script>
      )}
    </Helmet>
  )
}
