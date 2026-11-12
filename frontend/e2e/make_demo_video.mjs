// Stitch the recorded demo parts (e2e/demo.authed.spec.ts) into one video with
// title cards (#22). Needs ffmpeg. Output: e2e/recordings/ecalt-schools-demo.mp4
//
//   npx playwright test e2e/demo.authed.spec.ts && node e2e/make_demo_video.mjs
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'

const ROOT = path.resolve('e2e/.output')
const WORK = path.join(ROOT, 'demo', 'video')
const OUT = path.resolve('e2e/recordings/ecalt-schools-demo.mp4')
const W = 1280, H = 800

const parts = [
  { dir: 'demo.authed-1-teacher', title: 'Teachers turn their own material into a course',
    sub: 'Upload a document → the AI drafts an outline from it → builds each step, fact-checked against the source → the teacher reviews, previews and publishes' },
  { dir: 'demo.authed-student-2-student', title: 'Students sign in with a class code and PIN',
    sub: 'No email addresses. They open their assigned course, read the lesson and ask the tutor, which answers from the lesson' },
  { dir: 'demo.authed-3-teacher', title: 'Teachers see how every student is doing',
    sub: 'Progress across the class, students who need attention, and each student\'s tutor questions' },
]

const ff = (...args) => execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...args])
fs.rmSync(WORK, { recursive: true, force: true })
fs.mkdirSync(WORK, { recursive: true })
fs.mkdirSync(path.dirname(OUT), { recursive: true })

const card = (title, sub) => `<!doctype html><html><body style="margin:0;width:${W}px;height:${H}px;display:flex;
  flex-direction:column;justify-content:center;align-items:center;background:#080b14;color:#f1f5f9;
  font-family:Inter,Helvetica,Arial,sans-serif;text-align:center">
  <div style="font-size:15px;letter-spacing:.3em;color:#a78bfa;margin-bottom:22px">ECALT FOR SCHOOLS</div>
  <div style="font-size:44px;font-weight:700;max-width:1000px;line-height:1.2">${title}</div>
  ${sub ? `<div style="font-size:21px;color:#94a3b8;max-width:900px;margin-top:22px;line-height:1.5">${sub}</div>` : ''}
</body></html>`

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: W, height: H } })
async function titleClip(name, title, sub, seconds) {
  await page.setContent(card(title, sub))
  const png = path.join(WORK, `${name}.png`)
  await page.screenshot({ path: png })
  const mp4 = path.join(WORK, `${name}.mp4`)
  ff('-loop', '1', '-i', png, '-t', String(seconds), '-r', '30', '-vf', `scale=${W}:${H},format=yuv420p`,
    '-c:v', 'libx264', '-preset', 'veryfast', mp4)
  return mp4
}

const clips = [await titleClip('00-intro', 'From a teacher\'s document to a class learning from it', 'A walkthrough recorded on the ECALT dev environment', 4)]
for (const [i, p] of parts.entries()) {
  const dir = fs.readdirSync(ROOT).find((d) => d.startsWith(p.dir))
  const webm = dir && path.join(ROOT, dir, 'video.webm')
  if (!webm || !fs.existsSync(webm)) throw new Error(`no recording for ${p.dir} — run the demo spec first`)
  clips.push(await titleClip(`${i + 1}-title`, p.title, p.sub, 4))
  const mp4 = path.join(WORK, `${i + 1}-part.mp4`)
  ff('-i', webm, '-r', '30', '-vf', `scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x080b14,format=yuv420p`,
    '-c:v', 'libx264', '-preset', 'veryfast', '-an', mp4)
  clips.push(mp4)
}
clips.push(await titleClip('99-outro', 'Every step is grounded in the school\'s own material', 'Teachers stay in control · students sign in without email · each school\'s data stays separate', 4))
await browser.close()

const list = path.join(WORK, 'list.txt')
fs.writeFileSync(list, clips.map((c) => `file '${c}'`).join('\n'))
ff('-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', '-movflags', '+faststart', OUT)
const secs = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', OUT]).toString().trim()
console.log(`wrote ${OUT} (${Math.round(Number(secs))} s)`)
