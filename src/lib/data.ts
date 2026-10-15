import { useEffect, useState } from 'react';
import type { PlayerDoc, TeamDoc, TeamsIndex } from './types';

// Where the site lives (e.g. "/nfl-app" on GitHub Pages, "" locally).
const BASE = process.env.EXPO_PUBLIC_BASE_URL ?? '';

// Keep each file in memory so going back and forth between screens is instant.
const cache = new Map<string, Promise<unknown>>();

function load<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const p = fetch(`${BASE}/data/${path}`).then((r) => {
      if (!r.ok) throw new Error(`Couldn't load ${path} (${r.status})`);
      return r.json();
    });
    p.catch(() => cache.delete(path)); // allow a retry after a failure
    cache.set(path, p);
  }
  return cache.get(path) as Promise<T>;
}

function useJson<T>(path: string | null) {
  const [state, setState] = useState<{ path?: string; data?: T; error?: string }>({});
  useEffect(() => {
    if (!path) return;
    let alive = true;
    load<T>(path)
      .then((data) => alive && setState({ path, data }))
      .catch((e: Error) => alive && setState({ path, error: e.message }));
    return () => {
      alive = false;
    };
  }, [path]);
  // Only hand back the result for the file asked for now (e.g. right after switching teams).
  return state.path === path ? { data: state.data, error: state.error } : {};
}

export const useTeams = () => useJson<TeamsIndex>('teams.json');
export const useTeam = (abbr?: string) =>
  useJson<TeamDoc>(abbr ? `teams/${abbr.toUpperCase()}.json` : null);
export const usePlayer = (id?: string) => useJson<PlayerDoc>(id ? `players/${id}.json` : null);
