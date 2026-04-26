import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Verify from './pages/Verify'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Review from './pages/Review'
import Audit from './pages/Audit'
import Analytics from './pages/Analytics'
import Manage from './pages/Manage'
import Policies from './pages/Policies'
import Health from './pages/Health'
import Logs from './pages/Logs'
import LlmAsJudge from './pages/LlmAsJudge'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/verify" element={<Verify />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/app" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/review/:claimId" element={<Review />} />
          <Route path="/audit/:claimId" element={<Audit />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/manage" element={<Manage />} />
          <Route path="/policies" element={<Policies />} />
          <Route path="/health" element={<Health />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/llmasjudge" element={<LlmAsJudge />} />
        </Route>
      </Route>
    </Routes>
  )
}
