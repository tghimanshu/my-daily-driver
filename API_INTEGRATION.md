# API Integration Guide

This guide will help you connect your Daily Driver dashboard to real external services.

## 🔑 Required API Keys

### 1. Todoist (Task Management)

**What you get:** Import your tasks, track completion, and manage your to-do list.

**Setup:**

1. Go to [Todoist Settings](https://todoist.com/app/settings/integrations)
2. Scroll to "Developer" section
3. Copy your API token
4. Add to `.env.local`:
   ```
   TODOIST_TOKEN=your_token_here
   ```

**Free Tier:** Yes ✅

---

### 2. GitHub (Contribution Tracking)

**What you get:** Activity graph, contribution data, and repository statistics.

**Setup:**

1. Go to [GitHub Settings](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes:
   - `read:user`
   - `repo` (for private repos) or `public_repo` (for public only)
4. Generate and copy the token
5. Add to `.env.local`:
   ```
   GITHUB_TOKEN=ghp_your_token_here
   ```

**Free Tier:** Yes ✅

---

### 3. Google Calendar (OAuth Required)

**What you get:** Sync calendar events, see upcoming meetings, and manage your schedule.

**Setup:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:3000/api/auth/callback/google`
5. Copy Client ID and Client Secret
6. Add to `.env.local`:
   ```
   AUTH_GOOGLE_ID=your_client_id
   AUTH_GOOGLE_SECRET=your_client_secret
   ```

**Important:** Add these scopes in `auth.ts`:

```typescript
scope: "openid email profile https://www.googleapis.com/auth/calendar.readonly";
```

**Free Tier:** Yes ✅

---

### 4. Weather API (Open-Meteo)

**What you get:** Real-time weather data, temperature, and conditions.

**Setup:** No API key needed! Open-Meteo is free and doesn't require authentication. ✅

The weather integration works out of the box. You can customize the location in the code:

```typescript
// In your page
const weather = await fetchWeather(37.7749, -122.4194); // San Francisco
// Or by city
const weather = await fetchWeatherByCity("New York");
```

**Free Tier:** Yes ✅ (No limits for personal use)

---

### 5. Spotify (Optional - OAuth Required)

**What you get:** Currently playing track, recent listens, and top tracks.

**Setup:**

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app
3. Add redirect URI: `http://localhost:3000/api/auth/callback/spotify`
4. Copy Client ID and Client Secret
5. Add Spotify provider to `auth.ts`:
   ```typescript
   Spotify({
     clientId: process.env.SPOTIFY_CLIENT_ID!,
     clientSecret: process.env.SPOTIFY_CLIENT_SECRET!,
   });
   ```

**Free Tier:** Yes ✅

---

## 🚀 Quick Setup

1. **Copy the example environment file:**

   ```bash
   cp .env.example .env.local
   ```

2. **Fill in your API keys:**

   ```env
   # Required for basic functionality
   TODOIST_TOKEN=your_todoist_token
   GITHUB_TOKEN=your_github_token

   # Required for Google Calendar
   AUTH_GOOGLE_ID=your_google_client_id
   AUTH_GOOGLE_SECRET=your_google_client_secret

   # Optional for Spotify
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

3. **Restart the development server:**

   ```bash
   npm run dev
   ```

4. **Check API Status:**
   Visit [http://localhost:3000/api-status](http://localhost:3000/api-status) to verify your integrations.

---

## 📊 What Each API Provides

| API                 | Features                                                                               | Status Check      |
| ------------------- | -------------------------------------------------------------------------------------- | ----------------- |
| **Todoist**         | • Daily tasks<br>• Task completion<br>• Priority levels<br>• Labels & projects         | ✅ Token-based    |
| **GitHub**          | • Contribution graph<br>• Recent activity<br>• Repository stats<br>• Commit history    | ✅ Token-based    |
| **Google Calendar** | • Upcoming events<br>• Today's schedule<br>• Event details<br>• Attendees              | 🔐 OAuth required |
| **Weather**         | • Current temperature<br>• Weather conditions<br>• Humidity & wind<br>• Location-based | ✅ No auth needed |
| **Spotify**         | • Currently playing<br>• Recent tracks<br>• Top songs<br>• Playback control            | 🔐 OAuth required |

---

## 🔒 Security Best Practices

1. **Never commit `.env.local`** - It's already in `.gitignore`
2. **Use environment variables** - Never hardcode API keys
3. **Rotate tokens regularly** - Update keys every few months
4. **Minimal permissions** - Only request scopes you need
5. **Monitor usage** - Check your API quotas regularly

---

## 🐛 Troubleshooting

### API not working?

1. **Check API Status Page:** Visit `/api-status` to see which APIs are connected
2. **Verify Environment Variables:** Make sure `.env.local` has correct values
3. **Restart Server:** After changing `.env.local`, restart with `npm run dev`
4. **Check Console:** Look for error messages in the terminal

### Common Issues:

**"Invalid token"**

- Token may have expired or been revoked
- Generate a new token from the service
- Make sure there are no extra spaces in `.env.local`

**"Insufficient permissions"**

- Check that you granted the required scopes
- Regenerate token with correct permissions

**"Rate limit exceeded"**

- You've hit the API's rate limit
- Wait a few minutes and try again
- Consider caching data longer

---

## 📈 Data Caching

The app uses Next.js's built-in caching to reduce API calls:

- **Tasks:** 5 minutes
- **Calendar:** 5 minutes
- **Weather:** 30 minutes
- **GitHub:** 10-60 minutes
- **Spotify:** 30 seconds

You can adjust these in the respective API files under `lib/api/`.

---

## 🎯 Next Steps

1. ✅ Set up required APIs (Todoist, GitHub)
2. ✅ Configure OAuth for Google Calendar
3. ✅ Test each integration on `/api-status`
4. ✅ Customize settings in `/settings`
5. ✅ Enjoy your personalized dashboard!

---

## 💡 Tips

- Start with **Todoist** and **GitHub** (easiest to set up)
- Add **Google Calendar** once you're comfortable with OAuth
- **Weather** works immediately without setup
- **Spotify** is optional but adds a nice touch

---

Need help? Check the [main README](./README.md) or visit the API documentation links above.
