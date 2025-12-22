This execution plan breaks down the development of your Life Dashboard into five logical phases. By following this order, you’ll tackle the difficult "Identity" problem first before moving on to individual widgets.

---

## Phase 1: Foundation & Identity (Week 1)

The goal is to set up a secure environment that can hold multiple "Keys" (OAuth tokens) at once.

1. **Project Init:**
* Initialize Next.js 15 (App Router) + Tailwind + shadcn/ui.
* Install **Auth.js (NextAuth.js)**.


2. **Multi-Provider OAuth Setup:**
* Register apps in **Google Cloud Console**, **GitHub Developer Settings**, and **Todoist App Console**.
* **The "Master" Auth Configuration:** Configure Auth.js to request specific "Scopes" up front (e.g., `calendar.readonly`, `repo`, `task:read`).
* **Database:** Connect **Supabase** or **Prisma** to store these encrypted tokens so you don't have to log in to every service every time you open the dashboard.



---

## Phase 2: The "Bento Grid" Layout (Week 1.5)

Don't build logic yet—build the shell.

1. **Dashboard Shell:** Create a responsive grid layout. Use shadcn’s `Card` component as the base for every widget.
2. **Sidebar/Navigation:** Add a sidebar to switch between "Personal," "Work," and "Social Analytics" views.
3. **Skeleton States:** Use shadcn `Skeleton` components so the dashboard looks "full" while the APIs are fetching data in the background.

---

## Phase 3: High-Utility Integrations (Week 2)

Focus on the APIs that are easy to use and provide high value.

1. **GitHub & Todoist (The Easiest):**
* **GitHub:** Fetch your last 5 commits or active Pull Requests.
* **Todoist:** Use their REST API to fetch "Today's" tasks. Use a checkbox that actually pings the API to mark tasks as complete.


2. **Google Calendar:**
* Render a "Timeline" view of your day.
* *Pro-tip:* Use `date-fns` to format the API's ISO strings into readable "Starting in 10 mins" labels.


3. **Notion Database:**
* Connect your "Reading List" or "Daily Journal" database.
* Fetch the data using the Notion SDK and display it in a simple shadcn `Table`.



---

## Phase 4: Analytics & Media (Week 3)

This is where complexity increases due to token refresh and data permissions.

1. **YouTube Music (The "Vibe" Widget):**
* Since there's no official API for "Now Playing," use a **YouTube Data API** search to show your most recent liked videos or playlists.


2. **YouTube Studio & Insta Analytics:**
* **YT Analytics API:** Pull `views`, `subscriberCount`, and `revenue` (if applicable). Use **Recharts** (which fits shadcn's style) to plot your growth over the last 30 days.
* **Instagram Graph API:** This requires your account to be a "Creator" or "Business" account linked to a Facebook page. Pull your latest post engagement metrics.



---

## Phase 5: Polishing & Optimization (Week 4)

1. **Auto-Refresh:** Implement `swr` or `React Query` with a `refreshInterval` (e.g., every 5 minutes) so the dashboard stays live without a page refresh.
2. **Caching:** Use Next.js **Incremental Static Regeneration (ISR)** for the analytics widgets (YT/Insta) so you don't hit rate limits by calling them every single second.
3. **Dark Mode:** Use `next-themes` to ensure your dashboard looks great at night.

---

## Critical "Watch-Outs" for 2025:

* **Token Expiration:** Google and Meta tokens expire. You must implement a "Refresh Token" rotation in your `auth.ts` file, or your widgets will break every 60 minutes.
* **Rate Limits:** Instagram is very strict. Cache your Instagram data for at least 1 hour.
* **Environment Variables:** Never commit your `.env` file to GitHub. Use Vercel's environment variable management.

**Would you like me to generate the `auth.ts` file that specifically handles the token rotation for Google and Todoist?**I