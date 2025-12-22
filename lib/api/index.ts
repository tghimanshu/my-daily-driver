// Unified API Service - Aggregates data from all sources

import { fetchDailyTasks, getTaskStats } from "./todoist";
import { fetchUpcomingEvents, fetchTodayEvents } from "./google-calendar";
import { fetchWeather, fetchWeatherByCity } from "./weather";
import {
  fetchGitHubActivity,
  fetchContributionData,
  fetchGitHubStats,
} from "./github";
import { fetchCurrentlyPlaying, fetchRecentTracks } from "./spotify";

export interface DashboardData {
  tasks: any[];
  events: any[];
  weather: any;
  githubActivity: any[];
  contributions: any[];
  githubStats: any;
  currentTrack: any;
  taskStats: any;
}

export async function fetchAllDashboardData(
  accessToken?: string,
  spotifyToken?: string
): Promise<DashboardData> {
  try {
    // Fetch all data in parallel for better performance
    const [
      tasks,
      events,
      weather,
      githubActivity,
      contributions,
      githubStats,
      currentTrack,
      taskStats,
    ] = await Promise.allSettled([
      fetchDailyTasks(),
      fetchUpcomingEvents(accessToken, 10),
      fetchWeather(),
      fetchGitHubActivity(),
      fetchContributionData(),
      fetchGitHubStats(),
      fetchCurrentlyPlaying(spotifyToken),
      getTaskStats(),
    ]);

    return {
      tasks: tasks.status === "fulfilled" ? tasks.value : [],
      events: events.status === "fulfilled" ? events.value : [],
      weather: weather.status === "fulfilled" ? weather.value : null,
      githubActivity:
        githubActivity.status === "fulfilled" ? githubActivity.value : [],
      contributions:
        contributions.status === "fulfilled" ? contributions.value : [],
      githubStats:
        githubStats.status === "fulfilled" ? githubStats.value : null,
      currentTrack:
        currentTrack.status === "fulfilled" ? currentTrack.value : null,
      taskStats: taskStats.status === "fulfilled" ? taskStats.value : null,
    };
  } catch (e) {
    console.error("Error fetching dashboard data:", e);
    return {
      tasks: [],
      events: [],
      weather: null,
      githubActivity: [],
      contributions: [],
      githubStats: null,
      currentTrack: null,
      taskStats: null,
    };
  }
}

export async function fetchAnalyticsData(accessToken?: string) {
  try {
    const [taskStats, events, contributions] = await Promise.allSettled([
      getTaskStats(),
      fetchUpcomingEvents(accessToken, 50),
      fetchContributionData(),
    ]);

    return {
      taskStats: taskStats.status === "fulfilled" ? taskStats.value : null,
      events: events.status === "fulfilled" ? events.value : [],
      contributions:
        contributions.status === "fulfilled" ? contributions.value : [],
    };
  } catch (e) {
    console.error("Error fetching analytics data:", e);
    return {
      taskStats: null,
      events: [],
      contributions: [],
    };
  }
}

// Helper function to check API health
export async function checkAPIHealth() {
  const checks = {
    todoist: !!process.env.TODOIST_TOKEN,
    github: !!process.env.GITHUB_TOKEN,
    weather: true, // Open-Meteo doesn't require API key
    googleCalendar: false, // Requires OAuth token from session
    spotify: false, // Requires OAuth token from session
  };

  return checks;
}
