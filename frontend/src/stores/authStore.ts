import { create } from 'zustand'
import {
  signIn, signOut, signUp, confirmSignUp,
  resendSignUpCode, resetPassword, confirmResetPassword,
  fetchAuthSession,
} from 'aws-amplify/auth'

export interface AuthUser {
  username: string
  email: string
  employeeId: string
  displayName: string
  role: string
  groups: string[]
  sub: string
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  loading: boolean
  error: string | null

  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  register: (params: RegisterParams) => Promise<void>
  verify: (username: string, code: string) => Promise<void>
  resendCode: (username: string) => Promise<void>
  forgotPassword: (username: string) => Promise<void>
  resetPass: (username: string, code: string, newPassword: string) => Promise<void>
  refreshSession: () => Promise<string | null>
  clearError: () => void
}

export interface RegisterParams {
  username: string
  password: string
  email: string
  employeeId: string
  displayName: string
}

function parseGroups(session: Awaited<ReturnType<typeof fetchAuthSession>>): string[] {
  try {
    const payload = session.tokens?.idToken?.payload as Record<string, unknown>
    const groups = payload?.['cognito:groups']
    return Array.isArray(groups) ? (groups as string[]) : []
  } catch { return [] }
}

function roleFromGroups(groups: string[]): string {
  if (groups.includes('admins')) return 'admin'
  if (groups.includes('directors')) return 'director'
  if (groups.includes('managers')) return 'manager'
  if (groups.includes('reviewers')) return 'reviewer'
  return 'user'
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  loading: false,
  error: null,

  login: async (username, password) => {
    set({ loading: true, error: null })
    try {
      await signIn({ username, password })
      const session = await fetchAuthSession()
      const idToken = session.tokens?.idToken
      const payload = idToken?.payload as Record<string, unknown>
      const groups = parseGroups(session)
      set({
        token: idToken?.toString() ?? null,
        user: {
          username: (payload['cognito:username'] as string) || username,
          email: (payload['email'] as string) || '',
          employeeId: (payload['custom:employee_id'] as string) || '',
          displayName: (payload['custom:display_name'] as string) || username,
          sub: (payload['sub'] as string) || '',
          groups,
          role: roleFromGroups(groups),
        },
        loading: false,
      })
    } catch (e: unknown) {
      set({ loading: false, error: (e as Error).message })
      throw e
    }
  },

  logout: async () => {
    await signOut()
    set({ user: null, token: null })
  },

  register: async ({ username, password, email, employeeId, displayName }) => {
    set({ loading: true, error: null })
    try {
      await signUp({
        username,
        password,
        options: {
          userAttributes: {
            email,
            'custom:employee_id': employeeId,
            'custom:display_name': displayName,
            preferred_username: username,
          },
        },
      })
      set({ loading: false })
    } catch (e: unknown) {
      set({ loading: false, error: (e as Error).message })
      throw e
    }
  },

  verify: async (username, code) => {
    set({ loading: true, error: null })
    try {
      await confirmSignUp({ username, confirmationCode: code })
      set({ loading: false })
    } catch (e: unknown) {
      set({ loading: false, error: (e as Error).message })
      throw e
    }
  },

  resendCode: async (username) => {
    await resendSignUpCode({ username })
  },

  forgotPassword: async (username) => {
    set({ loading: true, error: null })
    try {
      await resetPassword({ username })
      set({ loading: false })
    } catch (e: unknown) {
      set({ loading: false, error: (e as Error).message })
      throw e
    }
  },

  resetPass: async (username, code, newPassword) => {
    set({ loading: true, error: null })
    try {
      await confirmResetPassword({ username, confirmationCode: code, newPassword })
      set({ loading: false })
    } catch (e: unknown) {
      set({ loading: false, error: (e as Error).message })
      throw e
    }
  },

  refreshSession: async () => {
    try {
      const session = await fetchAuthSession({ forceRefresh: true })
      const token = session.tokens?.idToken?.toString() ?? null
      if (token) {
        const groups = parseGroups(session)
        const payload = session.tokens?.idToken?.payload as Record<string, unknown>
        set((s) => ({
          token,
          user: s.user ? {
            ...s.user,
            groups,
            role: roleFromGroups(groups),
            email: (payload['email'] as string) || s.user.email,
          } : null,
        }))
      }
      return token
    } catch { return null }
  },

  clearError: () => set({ error: null }),
}))
