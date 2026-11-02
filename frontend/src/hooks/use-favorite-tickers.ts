import { useCallback, useEffect, useState } from "react"

const STORAGE_KEY = "reasoncheck.favorite-tickers"

function readFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

function writeFavorites(favorites: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...favorites]))
  } catch {
    // Per-device convenience only -- a blocked/full/private-mode storage
    // just means favorites don't persist this session, not a hard failure.
  }
}

// Per-device "starred" tickers -- not synced anywhere, not shown to other
// users, just a local convenience (same category as a remembered UI tab),
// which is exactly what localStorage is for per this project's own
// artifact-storage conventions.
export function useFavoriteTickers() {
  const [favorites, setFavorites] = useState<Set<string>>(() => readFavorites())

  useEffect(() => {
    writeFavorites(favorites)
  }, [favorites])

  const isFavorite = useCallback((ticker: string) => favorites.has(ticker.toUpperCase()), [favorites])

  const toggleFavorite = useCallback((ticker: string) => {
    const t = ticker.toUpperCase()
    setFavorites((prev) => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t)
      else next.add(t)
      return next
    })
  }, [])

  return { favorites, isFavorite, toggleFavorite }
}
