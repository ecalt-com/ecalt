import type { HierarchyRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'

type Node = HierarchyRecipe['nodes'][number]

function Tree({ nodes, parentId }: { nodes: Node[]; parentId: string | null }) {
  const children = nodes.filter(n => n.parentId === parentId)
  if (children.length === 0) return null
  return (
    <ul className={parentId === null ? 'space-y-1' : 'space-y-1 pl-4 border-l border-slate-200 dark:border-slate-700/40 ml-1.5 mt-1'}>
      {children.map(node => (
        <li key={node.id}>
          <span className="text-sm text-slate-700 dark:text-slate-200 px-2 py-1 rounded-lg inline-block bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/40">
            {node.label}
          </span>
          <Tree nodes={nodes} parentId={node.id} />
        </li>
      ))}
    </ul>
  )
}

export default function HierarchyRenderer({ recipe }: { recipe: HierarchyRecipe }) {
  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <Tree nodes={recipe.nodes} parentId={null} />
    </VisualCard>
  )
}
