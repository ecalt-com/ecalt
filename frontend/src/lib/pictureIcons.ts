import {
  Apple, Bird, Car, Cat, Dog, Fish, Flower2, Heart, Home, Moon, Rocket, Sailboat, Star, Sun, TreePine, Umbrella,
  type LucideIcon,
} from 'lucide-react'

// Picture passwords (backend/plans/school-courses, decision D1): a student's
// secret is 3 of these 16 icons in order. The backend stores only indices, so
// this order must never change — append, don't reorder.
export const PICTURE_ICONS: { name: string; Icon: LucideIcon; color: string }[] = [
  { name: 'Sun', Icon: Sun, color: 'text-amber-500' },
  { name: 'Moon', Icon: Moon, color: 'text-indigo-500' },
  { name: 'Star', Icon: Star, color: 'text-yellow-500' },
  { name: 'Heart', Icon: Heart, color: 'text-rose-500' },
  { name: 'Tree', Icon: TreePine, color: 'text-emerald-600' },
  { name: 'Flower', Icon: Flower2, color: 'text-pink-500' },
  { name: 'Fish', Icon: Fish, color: 'text-sky-500' },
  { name: 'Bird', Icon: Bird, color: 'text-cyan-600' },
  { name: 'Cat', Icon: Cat, color: 'text-orange-500' },
  { name: 'Dog', Icon: Dog, color: 'text-amber-700' },
  { name: 'Apple', Icon: Apple, color: 'text-red-500' },
  { name: 'Car', Icon: Car, color: 'text-blue-600' },
  { name: 'Rocket', Icon: Rocket, color: 'text-violet-600' },
  { name: 'Boat', Icon: Sailboat, color: 'text-teal-600' },
  { name: 'House', Icon: Home, color: 'text-lime-700' },
  { name: 'Umbrella', Icon: Umbrella, color: 'text-fuchsia-600' },
]
