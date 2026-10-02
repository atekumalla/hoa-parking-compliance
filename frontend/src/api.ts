// Thin fetch wrapper around the FastAPI backend. All calls are relative
// (/api/...) so this works unmodified in dev (Vite proxy) and prod (same
// FastAPI process serves both).

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    let body: unknown = text
    try {
      body = JSON.parse(text)
    } catch {
      // not JSON — keep as plain text
    }
    // FastAPI always wraps HTTPException content as {"detail": ...} — unwrap
    // that one level so callers get back exactly what the server raised
    // (a plain string message, or a structured object like duplicate info).
    const detail = body && typeof body === 'object' && 'detail' in (body as Record<string, unknown>)
      ? (body as Record<string, unknown>).detail
      : body
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

export const api = {
  // Auth
  authStatus: () => request<{ configured: boolean; authenticated: boolean }>('/api/auth/status'),
  logout: () => request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),

  // Admin (shared passcode gating destructive actions)
  adminStatus: () => request<{ configured: boolean; authenticated: boolean }>('/api/admin/status'),
  adminLogin: (passcode: string) =>
    request<{ ok: boolean }>('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ passcode }),
    }),
  adminLogout: () => request<{ ok: boolean }>('/api/admin/logout', { method: 'POST' }),

  // Links
  links: () => request<{ sheet_url: string; drive_url: string }>('/api/links'),
  refreshData: () => request<{ ok: boolean; last_loaded: string }>('/api/data/refresh', { method: 'POST' }),

  // Add Vehicle
  todayEntries: () => request<{ entries: TodayEntry[] }>('/api/today-entries'),
  knownVehicles: () => request<{ vehicles: KnownVehicle[] }>('/api/known-vehicles'),
  violationStatus: (plate: string) =>
    request<ViolationStatus>(`/api/violation-status?plate=${encodeURIComponent(plate)}`),
  analyzePhoto: (photo: File) => {
    const form = new FormData()
    form.append('photo', photo)
    return request<AnalyzeResult>('/api/analyze-photo', { method: 'POST', body: form })
  },
  createEntry: (form: FormData) => request<CreateEntryResult>('/api/entries', { method: 'POST', body: form }),
  deleteEntry: (timestamp: string, licensePlate: string, photoUrl?: string | null) => {
    const params = new URLSearchParams({ timestamp, license_plate: licensePlate })
    if (photoUrl) params.set('photo_url', photoUrl)
    return request<{ ok: boolean }>(`/api/entries?${params}`, { method: 'DELETE' })
  },

  // Scoreboard
  scoreboard: () => request<ScoreboardData>('/api/scoreboard'),

  // Vehicle History
  historyOptions: () => request<HistoryOptions>('/api/vehicle-history/options'),
  historySearch: (params: Record<string, string>) =>
    request<{ groups: HistoryGroup[] }>(`/api/vehicle-history/search?${new URLSearchParams(params)}`),
  exportPhotos: (licensePlate: string, make: string, model: string) => {
    const params = new URLSearchParams({ license_plate: licensePlate, make, model })
    return request<{ ok: boolean; folder_url: string; message: string }>(
      `/api/vehicle-history/export-photos?${params}`,
      { method: 'POST' },
    )
  },

  // Storage
  storageUsage: (refresh = false) => request<StorageUsage>(`/api/storage/usage${refresh ? '?refresh=true' : ''}`),
  storageFolders: (refresh = false) =>
    request<{ folders: FolderInfo[] }>(`/api/storage/folders${refresh ? '?refresh=true' : ''}`),
  deleteMonth: (folderId: string) =>
    request<{ deleted: number; failed: number }>(`/api/storage/delete-month?folder_id=${encodeURIComponent(folderId)}`, {
      method: 'POST',
    }),
  storageRange: (start: string, end: string) =>
    request<{ files: StorageFile[]; total_size_human: string }>(
      `/api/storage/range?start=${start}&end=${end}`,
    ),
  deleteRange: (fileIds: string[]) =>
    request<{ deleted: number; failed: number }>('/api/storage/delete-range', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fileIds),
    }),
}

export interface TodayEntry {
  timestamp: string
  time: string
  license_plate: string
  tag_number: string
  make: string
  model: string
  warned: boolean
  towed: boolean
  needs_warning: boolean
  can_tow: boolean
  days_30: number
  photo_url: string | null
}

export interface KnownVehicle {
  label: string
  license_plate: string
  tag_number: string
  make: string
  model: string
}

export interface ViolationStatus {
  license_plate: string
  unique_days_parked: number
  last_seen: string | null
  exceeds_limit: boolean
  has_been_warned_before: boolean
  warned_in_current_period: boolean
  warning_date: string | null
  can_tow: boolean
  needs_warning: boolean
  status_message: string
}

export interface AnalyzeResult {
  license_plate: string | null
  make: string | null
  model: string | null
  color: string | null
  confidence_notes: string | null
  tag_number: string | null
}

export interface CreateEntryResult {
  ok: boolean
  license_plate: string
  photo_url: string | null
  photo_upload_warning: string | null
}

export interface TagStat {
  tag_number: string
  times_used: number
  unique_days: number
  last_seen: string
  plates: string
}

export interface UnwarnedVehicle {
  license_plate: string
  tag_number: string
  days_30: number
  last_seen: string | null
  over_limit: boolean
}

export interface ScoreboardVehicle {
  license_plate: string
  total_entries: number
  last_seen: string | null
  tag_number: string
  make: string
  model: string
  warned: boolean
  last_warned_date: string | null
  towed: boolean
  towed_date: string | null
  unique_days_parked: number
}

export interface ScoreboardData {
  top_tags_90d: TagStat[]
  unwarned: UnwarnedVehicle[]
  vehicles: ScoreboardVehicle[]
}

export interface HistoryOptions {
  plates: string[]
  tags: string[]
  makes: string[]
  models: string[]
}

export interface HistoryEntry {
  timestamp: string
  tag_number: string
  make: string
  model: string
  warned: string
  warned_date: string
  towed: string
  towed_date: string
  photo_url: string | null
}

export interface HistoryGroup {
  license_plate: string
  total_entries: number
  total_warnings: number
  total_tows: number
  first_seen: string
  last_seen: string
  make: string
  model: string
  entries: HistoryEntry[]
}

export interface StorageUsage {
  used_bytes: number
  used_human: string
  file_count: number
  error?: string
}

export interface FolderInfo {
  name: string
  id: string
  file_count: number
  total_size: string
}

export interface StorageFile {
  id: string
  name: string
  size?: string
  createdTime?: string
  folder_name?: string
}
