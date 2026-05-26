import { createContext, useContext, useEffect, useState } from 'react'

interface PaymentConfig {
  stripePublishableKey: string
  razorpayKeyId: string
  loading: boolean
}

const PaymentConfigContext = createContext<PaymentConfig>({
  stripePublishableKey: '', razorpayKeyId: '', loading: true,
})

export function PaymentConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<PaymentConfig>({
    stripePublishableKey: '', razorpayKeyId: '', loading: true,
  })

  useEffect(() => {
    fetch('/api/v1/subscriptions/config')
      .then(r => r.json())
      .then(d => setConfig({
        stripePublishableKey: d.stripe_publishable_key ?? '',
        razorpayKeyId: d.razorpay_key_id ?? '',
        loading: false,
      }))
      .catch(() => setConfig(prev => ({ ...prev, loading: false })))
  }, [])

  return <PaymentConfigContext.Provider value={config}>{children}</PaymentConfigContext.Provider>
}

export const usePaymentConfig = () => useContext(PaymentConfigContext)
