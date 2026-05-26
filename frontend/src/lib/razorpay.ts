let _scriptPromise: Promise<boolean> | null = null

export function loadRazorpayScript(): Promise<boolean> {
  if ((window as any).Razorpay) return Promise.resolve(true)
  if (_scriptPromise) return _scriptPromise
  _scriptPromise = new Promise(resolve => {
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve(true)
    script.onerror = () => { _scriptPromise = null; resolve(false) }
    document.body.appendChild(script)
  })
  return _scriptPromise
}

export interface RazorpayOrderResponse {
  razorpay_order_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

export interface RazorpaySubscriptionResponse {
  razorpay_subscription_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

export type RazorpayResponse = RazorpayOrderResponse | RazorpaySubscriptionResponse

export interface RazorpayOrderOptions {
  key: string
  amount: number
  currency: string
  order_id: string
  name: string
  description: string
  prefill?: { email?: string; contact?: string }
  handler: (response: RazorpayOrderResponse) => void
  modal?: { ondismiss?: () => void }
}

export interface RazorpaySubscriptionOptions {
  key: string
  amount: number
  currency: string
  subscription_id: string
  name: string
  description: string
  prefill?: { email?: string; contact?: string }
  handler: (response: RazorpaySubscriptionResponse) => void
  modal?: { ondismiss?: () => void }
}
