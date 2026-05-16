import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Explore from './pages/Explore'
import Journeys from './pages/Journeys'
import Journey from './pages/Journey'
import Passport from './pages/Passport'
import ComingSoon from './pages/ComingSoon'

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/journeys" element={<Journeys />} />
        <Route path="/journey/:id" element={<Journey />} />
        <Route path="/passport" element={<Passport />} />
        <Route
          path="/sign-in"
          element={<ComingSoon title="Sign In — Coming Soon" description="User accounts are on the way. Drop your email and we'll notify you." />}
        />
        <Route
          path="/get-started"
          element={<ComingSoon title="Early Access" description="Join the waitlist and be among the first to unlock a personalized learning passport." />}
        />
        <Route
          path="*"
          element={<ComingSoon title="Page not found" description="This page doesn't exist yet — but your next learning journey is just one question away." />}
        />
      </Routes>
    </BrowserRouter>
  )
}
