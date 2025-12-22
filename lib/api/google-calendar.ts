export interface CalendarEvent {
  id: string;
  summary: string;
  description?: string;
  start: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  end: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  location?: string;
  attendees?: Array<{
    email: string;
    displayName?: string;
    responseStatus: string;
  }>;
  hangoutLink?: string;
  htmlLink: string;
}

export async function fetchUpcomingEvents(
  accessToken?: string,
  maxResults = 10
): Promise<CalendarEvent[]> {
  if (!accessToken) {
    console.warn("Google Calendar access token not available");
    return [];
  }

  try {
    const timeMin = new Date().toISOString();
    const timeMax = new Date(
      Date.now() + 7 * 24 * 60 * 60 * 1000
    ).toISOString(); // Next 7 days

    const res = await fetch(
      `https://www.googleapis.com/calendar/v3/calendars/primary/events?` +
        `orderBy=startTime&singleEvents=true&timeMin=${timeMin}&timeMax=${timeMax}&maxResults=${maxResults}`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        next: { revalidate: 300 }, // Cache for 5 mins
      }
    );

    if (!res.ok) {
      console.error(
        `Google Calendar API Error: ${res.status} ${res.statusText}`
      );
      return [];
    }

    const data = await res.json();
    return data.items || [];
  } catch (e) {
    console.error("Google Calendar API Error:", e);
    return [];
  }
}

export async function fetchTodayEvents(
  accessToken?: string
): Promise<CalendarEvent[]> {
  if (!accessToken) return [];

  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const res = await fetch(
      `https://www.googleapis.com/calendar/v3/calendars/primary/events?` +
        `orderBy=startTime&singleEvents=true&timeMin=${today.toISOString()}&timeMax=${tomorrow.toISOString()}&maxResults=20`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        next: { revalidate: 300 },
      }
    );

    if (!res.ok) return [];
    const data = await res.json();
    return data.items || [];
  } catch (e) {
    console.error("Google Calendar API Error:", e);
    return [];
  }
}
