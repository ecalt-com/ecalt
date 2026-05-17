import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

interface ConstellationNode {
  id: string
  domain: string
  mastery: number
  concept_count: number
  x: number
  y: number
}

interface ConstellationLink {
  source: string
  target: string
  weight: number
}

interface ConstellationData {
  nodes: ConstellationNode[]
  links: ConstellationLink[]
}

interface Props {
  data: ConstellationData
  mini?: boolean
}

const DOMAIN_COLORS: Record<string, string> = {
  biology:     '#10b981',
  physics:     '#8b5cf6',
  chemistry:   '#06b6d4',
  math:        '#f59e0b',
  history:     '#f97316',
  technology:  '#3b82f6',
  psychology:  '#ec4899',
  philosophy:  '#a855f7',
  arts:        '#f43f5e',
  language:    '#14b8a6',
  economics:   '#eab308',
  engineering: '#6366f1',
  astronomy:   '#64748b',
  medicine:    '#22c55e',
}

export default function ConstellationMap({ data, mini = false }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return

    const size = mini ? 180 : 400
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    svg.attr('viewBox', `0 0 400 400`).attr('width', size).attr('height', size)

    // Background glow filter
    const defs = svg.append('defs')
    const filter = defs.append('filter').attr('id', 'glow')
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur')
    const feMerge = filter.append('feMerge')
    feMerge.append('feMergeNode').attr('in', 'coloredBlur')
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    const g = svg.append('g')

    // Links
    g.selectAll('line')
      .data(data.links)
      .enter()
      .append('line')
      .attr('x1', d => {
        const n = data.nodes.find(n => n.id === d.source)
        return n?.x ?? 200
      })
      .attr('y1', d => {
        const n = data.nodes.find(n => n.id === d.source)
        return n?.y ?? 200
      })
      .attr('x2', d => {
        const n = data.nodes.find(n => n.id === d.target)
        return n?.x ?? 200
      })
      .attr('y2', d => {
        const n = data.nodes.find(n => n.id === d.target)
        return n?.y ?? 200
      })
      .attr('stroke', '#4c1d95')
      .attr('stroke-width', d => Math.max(0.5, d.weight * 2))
      .attr('stroke-opacity', d => Math.min(0.6, d.weight + 0.2))

    // Node groups
    const nodeG = g.selectAll('g.node')
      .data(data.nodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${d.x},${d.y})`)

    // Outer ring (mastery indicator)
    nodeG.append('circle')
      .attr('r', d => Math.max(8, d.mastery * 28 + 8))
      .attr('fill', 'none')
      .attr('stroke', d => DOMAIN_COLORS[d.domain] ?? '#8b5cf6')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.3)

    // Star core
    nodeG.append('circle')
      .attr('r', d => Math.max(4, d.mastery * 12 + 4))
      .attr('fill', d => DOMAIN_COLORS[d.domain] ?? '#8b5cf6')
      .attr('fill-opacity', 0.85)
      .attr('filter', 'url(#glow)')

    if (!mini) {
      // Label
      nodeG.append('text')
        .attr('y', d => Math.max(4, d.mastery * 12 + 4) + 14)
        .attr('text-anchor', 'middle')
        .attr('fill', '#94a3b8')
        .attr('font-size', '9px')
        .attr('font-family', 'system-ui, sans-serif')
        .text(d => d.domain)

      // Tooltip via title
      nodeG.append('title')
        .text(d => `${d.domain}\nMastery: ${Math.round(d.mastery * 100)}%\nConcepts: ${d.concept_count}`)
    }

    // Pulse animation on strongest nodes
    if (!mini) {
      nodeG.filter(d => d.mastery >= 0.5)
        .select('circle:nth-child(2)')
        .append('animate')
        .attr('attributeName', 'r')
        .attr('values', (d: ConstellationNode) => {
          const base = Math.max(4, d.mastery * 12 + 4)
          return `${base};${base + 2};${base}`
        })
        .attr('dur', '3s')
        .attr('repeatCount', 'indefinite')
    }
  }, [data, mini])

  return <svg ref={svgRef} className="overflow-visible" />
}
