// Mã lỗi backend gắn vào URL (/login?error=...) → key thông báo trong messages/vi.json
const LOGIN_ERRORS: Record<string, string> = {
  not_allowed: "login.notAllowed",
  oauth_failed: "login.oauthFailed",
}

export function loginErrorKey(code: string | null): string | null {
  if (!code) return null
  return LOGIN_ERRORS[code] ?? null
}
