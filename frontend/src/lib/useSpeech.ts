// Browser speech: read-aloud (speechSynthesis, runs on the device: nothing is
// sent anywhere) and voice input (SpeechRecognition, which in Chrome sends audio
// to Google's speech service, so callers keep it off for children).
import { useCallback, useEffect, useRef, useState } from 'react'
import { markdownToSpeech, splitSentences } from './speechText'

export const speechSynthesisSupported = () => typeof window !== 'undefined' && 'speechSynthesis' in window

type RecognitionCtor = new () => {
  lang: string; interimResults: boolean; continuous: boolean
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null
  onend: (() => void) | null; onerror: (() => void) | null
  start(): void; stop(): void
}
const recognitionCtor = (): RecognitionCtor | null => {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}
export const speechRecognitionSupported = () => recognitionCtor() !== null

export type ReadState = 'idle' | 'playing' | 'paused'
export const SPEEDS = [0.8, 1, 1.2] as const

/** Read `markdown` aloud sentence by sentence; stops when unmounted or the text changes. */
export function useReadAloud(markdown: string) {
  const [state, setState] = useState<ReadState>('idle')
  const [rate, setRate] = useState<(typeof SPEEDS)[number]>(1)
  const token = useRef(0)          // bumping it abandons the utterance chain in flight

  const stop = useCallback(() => {
    token.current++
    if (speechSynthesisSupported()) window.speechSynthesis.cancel()
    setState('idle')
  }, [])

  useEffect(() => stop, [stop, markdown])

  const speakFrom = useCallback((sentences: string[], i: number, r: number, mine: number) => {
    if (mine !== token.current) return
    if (i >= sentences.length) { setState('idle'); return }
    const u = new SpeechSynthesisUtterance(sentences[i])
    u.rate = r
    u.lang = document.documentElement.lang || navigator.language || 'en'
    u.onend = () => speakFrom(sentences, i + 1, r, mine)
    u.onerror = () => { if (mine === token.current) setState('idle') }
    window.speechSynthesis.speak(u)
  }, [])

  const play = useCallback(() => {
    if (!speechSynthesisSupported()) return
    if (state === 'paused') { window.speechSynthesis.resume(); setState('playing'); return }
    const sentences = splitSentences(markdownToSpeech(markdown))
    if (!sentences.length) return
    window.speechSynthesis.cancel()
    const mine = ++token.current
    setState('playing')
    speakFrom(sentences, 0, rate, mine)
  }, [markdown, rate, state, speakFrom])

  const pause = useCallback(() => {
    if (!speechSynthesisSupported()) return
    window.speechSynthesis.pause(); setState('paused')
  }, [])

  const cycleRate = useCallback(() => {
    setRate(r => SPEEDS[(SPEEDS.indexOf(r) + 1) % SPEEDS.length])
    if (state !== 'idle') stop()   // the new speed applies from the next play
  }, [state, stop])

  return { state, rate, play, pause, stop, cycleRate, supported: speechSynthesisSupported() }
}

/** Dictation into a text field. `onText` receives the running transcript. */
export function useDictation(onText: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const rec = useRef<InstanceType<RecognitionCtor> | null>(null)

  const stop = useCallback(() => { rec.current?.stop(); setListening(false) }, [])
  useEffect(() => () => { rec.current?.stop() }, [])

  const start = useCallback(() => {
    const Ctor = recognitionCtor()
    if (!Ctor || listening) return
    const r = new Ctor()
    r.lang = document.documentElement.lang || navigator.language || 'en-US'
    r.interimResults = true
    r.continuous = false
    r.onresult = (e) => {
      let text = ''
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript
      onText(text)
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    rec.current = r
    setListening(true)
    r.start()
  }, [listening, onText])

  return { listening, start, stop, supported: speechRecognitionSupported() }
}
