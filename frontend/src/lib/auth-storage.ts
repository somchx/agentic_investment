// Simple localStorage-backed token store. JWT is a bearer token, not a cookie,
// so we own reading/writing/clearing it and attaching it to requests ourselves.

const TOKEN_KEY = "iar_access_token"

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // ignore (e.g. storage disabled)
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // ignore
  }
}
