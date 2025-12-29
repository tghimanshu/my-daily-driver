// Daily Setup Orchestrator - Coordinates all integrations for intelligent daily briefing

import { fetchDailyTasks } from "./api/todoist";
import { fetchUpcomingEvents } from "./api/google-calendar";
import { fetchWeather } from "./api/weather";
import { fetchContributionData } from "./api/github";
import { rankPriorities, getTopPriorities, getQuickWins, PriorityFactors } from "./priority-engine";
import { suggestTimeBlocks, generateDailySchedule } from "./time-blocking";

export interface DailyBriefing {
    date: Date;
    summary: {
        totalTasks: number;
        totalEvents: number;
        completedHabits: number;
        weatherSummary: string;
        overallMood: "productive" | "busy" | "relaxed" | "challenging";
    };
    priorities: {
        top3: any[];
        quickWins: any[];
        mustDo: any[];
    };
    insights: {
        weatherImpact: string[];
        scheduleAdvice: string[];
        energyOptimization: string[];
        habitReminders: string[];
    };
    schedule: {
        suggestions: any[];
        conflicts: any[];
    };
    integrationStatus: {
        [key: string]: boolean;
    };
}

/**
 * Generate comprehensive daily briefing
 */
export async function generateDailyBriefing(
    accessToken?: string,
    habits?: any[],
    energyPatterns?: any[]
): Promise<DailyBriefing> {
    // Fetch all data in parallel
    const [tasksResult, eventsResult, weatherResult, contributionsResult] =
        await Promise.allSettled([
            fetchDailyTasks(),
            fetchUpcomingEvents(accessToken, 20),
            fetchWeather(),
            fetchContributionData(),
        ]);

    // Extract data with fallbacks
    const tasks = tasksResult.status === "fulfilled" ? tasksResult.value : [];
    const events = eventsResult.status === "fulfilled" ? eventsResult.value : [];
    const weather = weatherResult.status === "fulfilled" ? weatherResult.value : null;
    const contributions = contributionsResult.status === "fulfilled" ? contributionsResult.value : [];

    const habitsData = habits || [];

    // Integration status
    const integrationStatus = {
        todoist: tasksResult.status === "fulfilled",
        calendar: eventsResult.status === "fulfilled",
        weather: weatherResult.status === "fulfilled",
        github: contributionsResult.status === "fulfilled",
    };

    // Build priority factors
    const priorityFactors: PriorityFactors = {
        taskData: tasks,
        eventData: events,
        weatherData: weather,
        habitData: habitsData,
        githubData: contributions,
        energyPatterns,
    };

    // Calculate priorities
    const topPriorities = getTopPriorities(priorityFactors, 3);
    const quickWins = getQuickWins(priorityFactors);
    const allPriorities = rankPriorities(priorityFactors);
    const mustDo = allPriorities.filter((p) => p.urgency >= 8).slice(0, 5);

    // Generate time blocking suggestions
    const timeBlockSuggestions = suggestTimeBlocks(tasks, events, energyPatterns);

    // Generate insights
    const insights = generateInsights({
        tasks,
        events,
        weather,
        habits: habitsData,
        contributions,
        priorities: allPriorities,
    });

    // Determine overall mood
    const overallMood = determineOverallMood({
        taskCount: tasks.length,
        eventCount: events.length,
        urgentCount: mustDo.length,
        weather,
    });

    // Weather summary
    const weatherSummary = weather && weather.current
        ? `${Math.round(weather.current.temperature_2m)}°C, ${getWeatherDescription(
            weather.current.weather_code
        )}`
        : "Weather data unavailable";

    return {
        date: new Date(),
        summary: {
            totalTasks: tasks.length,
            totalEvents: events.length,
            completedHabits: habitsData.filter((h) => {
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const lastCompleted = h.lastCompletedAt ? new Date(h.lastCompletedAt) : null;
                return lastCompleted && lastCompleted >= today;
            }).length,
            weatherSummary,
            overallMood,
        },
        priorities: {
            top3: topPriorities,
            quickWins,
            mustDo,
        },
        insights,
        schedule: {
            suggestions: timeBlockSuggestions,
            conflicts: findScheduleConflicts(tasks, events),
        },
        integrationStatus,
    };
}

/**
 * Generate cross-integration insights
 */
function generateInsights(data: {
    tasks: any[];
    events: any[];
    weather: any;
    habits: any[];
    contributions: any[];
    priorities: any[];
}): DailyBriefing["insights"] {
    const insights: DailyBriefing["insights"] = {
        weatherImpact: [],
        scheduleAdvice: [],
        energyOptimization: [],
        habitReminders: [],
    };

    // Weather insights
    if (data.weather && data.weather.current) {
        const temp = data.weather.current.temperature_2m;
        const weatherCode = data.weather.current.weather_code;

        if (weatherCode <= 3 && temp >= 18 && temp <= 28) {
            insights.weatherImpact.push("Perfect weather today! Great for outdoor tasks or walks between meetings.");
        } else if (weatherCode >= 50) {
            insights.weatherImpact.push("Rainy weather expected. Focus on indoor tasks and remote meetings.");
        } else if (temp < 10) {
            insights.weatherImpact.push("Cold day ahead. Dress warmly for any outdoor activities.");
        } else if (temp > 30) {
            insights.weatherImpact.push("Hot day! Stay hydrated and consider early morning or evening for outdoor tasks.");
        }

        // Check for outdoor tasks
        const outdoorTasks = data.tasks.filter((t) => {
            const title = (t.content || "").toLowerCase();
            return (
                title.includes("outdoor") ||
                title.includes("walk") ||
                title.includes("run") ||
                title.includes("errand") ||
                title.includes("shopping")
            );
        });

        if (outdoorTasks.length > 0 && weatherCode >= 50) {
            insights.weatherImpact.push(`Consider rescheduling ${outdoorTasks.length} outdoor task(s) due to poor weather.`);
        }
    }

    // Schedule insights
    const now = new Date();
    const upcomingEvents = data.events.filter((e) => {
        const start = new Date(e.start?.dateTime || e.start?.date);
        const hoursUntil = (start.getTime() - now.getTime()) / (1000 * 60 * 60);
        return hoursUntil > 0 && hoursUntil < 4;
    });

    if (upcomingEvents.length > 0) {
        const nextEvent = upcomingEvents[0];
        const startTime = new Date(nextEvent.start.dateTime || nextEvent.start.date);
        const hoursUntil = (startTime.getTime() - now.getTime()) / (1000 * 60 * 60);

        if (hoursUntil < 1) {
            insights.scheduleAdvice.push(
                `Meeting "${nextEvent.summary}" starts in ${Math.round(hoursUntil * 60)} minutes!`
            );
        } else {
            insights.scheduleAdvice.push(
                `You have ${upcomingEvents.length} meeting(s) in the next 4 hours. Complete quick tasks now.`
            );
        }
    }

    if (data.events.length >= 5) {
        insights.scheduleAdvice.push("Heavy meeting day! Schedule breaks to avoid burnout.");
    } else if (data.events.length === 0) {
        insights.scheduleAdvice.push("No meetings today - perfect for deep focus work!");
    }

    // Energy optimization
    const highPriorityTasks = data.priorities.filter(
        (p) => p.type === "task" && p.importance >= 7
    );

    if (highPriorityTasks.length > 0) {
        const currentHour = new Date().getHours();
        if (currentHour >= 9 && currentHour < 12) {
            insights.energyOptimization.push(
                "You're in peak morning hours (9-12 AM) - tackle your most important tasks now!"
            );
        } else if (currentHour >= 13 && currentHour < 15) {
            insights.energyOptimization.push(
                "Post-lunch dip (1-3 PM) - good time for lighter tasks, meetings, or organizational work."
            );
        } else if (currentHour >= 15 && currentHour < 17) {
            insights.energyOptimization.push(
                "Afternoon recovery (3-5 PM) - second window for focused work before EOD."
            );
        }
    }

    // GitHub activity insights
    if (data.contributions.length > 0) {
        const recentCommits = data.contributions.filter((c) => {
            const commitDate = new Date(c.date);
            const daysAgo = (now.getTime() - commitDate.getTime()) / (1000 * 60 * 60 * 24);
            return daysAgo <= 7;
        });

        const totalContributions = recentCommits.reduce((sum, c) => sum + c.count, 0);

        if (totalContributions > 0) {
            insights.energyOptimization.push(
                `You've made ${totalContributions} contribution(s) this week. Keep the momentum going!`
            );
        }
    }

    // Habit reminders
    const incompleteHabits = data.habits.filter((h) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const lastCompleted = h.lastCompletedAt ? new Date(h.lastCompletedAt) : null;
        return !lastCompleted || lastCompleted < today;
    });

    incompleteHabits.forEach((habit) => {
        const streak = habit.streak || 0;
        if (streak >= 7) {
            insights.habitReminders.push(`🔥 Protect your ${streak}-day "${habit.name}" streak!`);
        } else if (streak >= 3) {
            insights.habitReminders.push(`Keep building: "${habit.name}" (${streak} days)`);
        } else {
            insights.habitReminders.push(`Don't forget: "${habit.name}"`);
        }
    });

    return insights;
}

/**
 * Determine overall mood/vibe for the day
 */
function determineOverallMood(data: {
    taskCount: number;
    eventCount: number;
    urgentCount: number;
    weather: any;
}): "productive" | "busy" | "relaxed" | "challenging" {
    // Challenging: Many urgent items or bad conditions
    if (data.urgentCount >= 5 || (data.taskCount >= 15 && data.eventCount >= 5)) {
        return "challenging";
    }

    // Busy: Many tasks or events
    if (data.taskCount >= 10 || data.eventCount >= 4) {
        return "busy";
    }

    // Relaxed: Few commitments and good weather
    if (data.taskCount <= 5 && data.eventCount <= 2) {
        return "relaxed";
    }

    // Productive: Balanced workload
    return "productive";
}

/**
 * Find potential scheduling conflicts
 */
function findScheduleConflicts(tasks: any[], events: any[]): any[] {
    const conflicts: any[] = [];

    // Check for tasks due during meetings
    tasks.forEach((task) => {
        if (!task.due) return;

        const dueTime = new Date(task.due.datetime || task.due.date);

        events.forEach((event) => {
            const eventStart = new Date(event.start?.dateTime || event.start?.date);
            const eventEnd = new Date(event.end?.dateTime || event.end?.date || eventStart);

            if (dueTime >= eventStart && dueTime <= eventEnd) {
                conflicts.push({
                    type: "task_during_meeting",
                    task: task.content,
                    event: event.summary,
                    time: dueTime,
                });
            }
        });
    });

    // Check for back-to-back meetings (no buffer)
    for (let i = 0; i < events.length - 1; i++) {
        const currentEnd = new Date(
            events[i].end?.dateTime || events[i].end?.date || events[i].start?.dateTime
        );
        const nextStart = new Date(events[i + 1].start?.dateTime || events[i + 1].start?.date);

        const gapMinutes = (nextStart.getTime() - currentEnd.getTime()) / (1000 * 60);

        if (gapMinutes < 5) {
            conflicts.push({
                type: "no_buffer",
                event1: events[i].summary,
                event2: events[i + 1].summary,
                message: "No buffer between meetings",
            });
        }
    }

    return conflicts;
}

/**
 * Get weather description from code
 */
function getWeatherDescription(code: number): string {
    if (code === 0) return "Clear sky";
    if (code <= 3) return "Partly cloudy";
    if (code <= 48) return "Foggy";
    if (code <= 67) return "Rainy";
    if (code <= 77) return "Snowy";
    if (code <= 82) return "Showers";
    if (code <= 99) return "Thunderstorms";
    return "Unknown";
}

/**
 * Get a motivational greeting based on time of day and briefing data
 */
export function getSmartGreeting(briefing: DailyBriefing): string {
    const hour = new Date().getHours();
    const { overallMood } = briefing.summary;

    let timeGreeting = "Hello";
    if (hour < 12) timeGreeting = "Good morning";
    else if (hour < 17) timeGreeting = "Good afternoon";
    else timeGreeting = "Good evening";

    let moodMessage = "Himanshu";
    // if (overallMood === "productive") {
    //     moodMessage = "Let's have a productive day!";
    // } else if (overallMood === "busy") {
    //     moodMessage = "It's a busy day, but you've got this!";
    // } else if (overallMood === "relaxed") {
    //     moodMessage = "Enjoy your relatively light day!";
    // } else {
    // }
    // moodMessage = "Today's packed, but tackle it one step at a time.";

    return `${timeGreeting}, ${moodMessage}!`;
}
