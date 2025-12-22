// Spotify API Integration

export interface SpotifyTrack {
  id: string;
  name: string;
  artists: Array<{
    name: string;
  }>;
  album: {
    name: string;
    images: Array<{
      url: string;
      height: number;
      width: number;
    }>;
  };
  duration_ms: number;
  external_urls: {
    spotify: string;
  };
}

export interface CurrentlyPlaying {
  is_playing: boolean;
  progress_ms: number;
  item: SpotifyTrack;
}

// Note: Spotify requires OAuth flow to get user token
// This is a placeholder showing how to fetch once you have a token
export async function fetchCurrentlyPlaying(
  accessToken?: string
): Promise<CurrentlyPlaying | null> {
  if (!accessToken) {
    console.warn("Spotify access token not available");
    return null;
  }

  try {
    const res = await fetch(
      "https://api.spotify.com/v1/me/player/currently-playing",
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        next: { revalidate: 30 }, // Cache for 30 seconds (music changes frequently)
      }
    );

    if (res.status === 204 || !res.ok) {
      // No track currently playing
      return null;
    }

    const data = await res.json();
    return data;
  } catch (e) {
    console.error("Spotify API Error:", e);
    return null;
  }
}

export async function fetchRecentTracks(
  accessToken?: string,
  limit = 10
): Promise<SpotifyTrack[]> {
  if (!accessToken) return [];

  try {
    const res = await fetch(
      `https://api.spotify.com/v1/me/player/recently-played?limit=${limit}`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        next: { revalidate: 300 },
      }
    );

    if (!res.ok) return [];

    const data = await res.json();
    return data.items?.map((item: any) => item.track) || [];
  } catch (e) {
    console.error("Spotify Recent Tracks Error:", e);
    return [];
  }
}

export async function fetchTopTracks(
  accessToken?: string,
  timeRange: "short_term" | "medium_term" | "long_term" = "medium_term"
): Promise<SpotifyTrack[]> {
  if (!accessToken) return [];

  try {
    const res = await fetch(
      `https://api.spotify.com/v1/me/top/tracks?time_range=${timeRange}&limit=20`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        next: { revalidate: 3600 }, // Cache for 1 hour
      }
    );

    if (!res.ok) return [];

    const data = await res.json();
    return data.items || [];
  } catch (e) {
    console.error("Spotify Top Tracks Error:", e);
    return [];
  }
}
