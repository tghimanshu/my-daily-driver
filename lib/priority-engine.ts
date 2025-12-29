// Priority Engine - Smart task and event prioritization
// Uses cross-integration data to rank daily priorities

export interface PriorityItem {
  id: string;
  type: "task" | "event" | "habit" | "github";
  title: string;
  description?: string;
  score: number; // 0-100
  urgency: number; // 0-10
  importance: number; // 0-10
  reasoning: string[];
  suggestedTime?: {
    start: string;
    end: string;
  };
  metadata?: any;
}

export interface PriorityFactors {
  taskData: any[];
  eventData: any[];
  weatherData: any;
  habitData: any[];
  githubData: any[];
  energyPatterns?: any[];
}

/**
 * Calculate priority score based on multiple factors
 */
export function calculatePriority(
  item: any,
  type: "task" | "event" | "habit" | "github",
  factors: PriorityFactors
): PriorityItem {
  const reasoning: string[] = [];
  let urgency = 5;
  let importance = 5;

  // Factor 1: Time-based urgency
  if (type === "task" && item.due) {
    const dueDate = new Date(item.due.date || item.due.datetime);
    const now = new Date();
    const hoursUntilDue = (dueDate.getTime() - now.getTime()) / (1000 * 60 * 60);

    if (hoursUntilDue < 2) {
      urgency = 10;
      reasoning.push("Due in less than 2 hours!");
    } else if (hoursUntilDue < 6) {
      urgency = 8;
      reasoning.push("Due today within 6 hours");
    } else if (hoursUntilDue < 24) {
      urgency = 6;
      reasoning.push("Due later today");
    }
  }

  if (type === "event") {
    const startTime = new Date(item.start?.dateTime || item.start?.date);
    const now = new Date();
    const hoursUntilStart =
      (startTime.getTime() - now.getTime()) / (1000 * 60 * 60);

    if (hoursUntilStart < 1) {
      urgency = 10;
      reasoning.push("Starting in less than an hour");
    } else if (hoursUntilStart < 3) {
      urgency = 8;
      reasoning.push("Starting soon");
    }
  }

  // Factor 2: Priority/importance from source
  if (type === "task" && item.priority) {
    // Todoist uses 1-4, where 1 is highest
    importance = Math.max(1, 11 - item.priority * 2);
    if (item.priority === 1) {
      reasoning.push("Marked as P1 (highest priority)");
    }
  }

  // Factor 3: Habit streak protection
  if (type === "habit") {
    const streak = item.streak || 0;
    if (streak >= 7) {
      importance = 9;
      urgency = 8;
      reasoning.push(`Protect your ${streak}-day streak! 🔥`);
    } else if (streak >= 3) {
      importance = 7;
      reasoning.push(`Keep building your ${streak}-day streak`);
    }
  }

  // Factor 4: Weather impact
  if (factors.weatherData && type === "task") {
    const taskTitle = (item.content || item.title || "").toLowerCase();
    const isOutdoorTask =
      taskTitle.includes("outdoor") ||
      taskTitle.includes("walk") ||
      taskTitle.includes("run") ||
      taskTitle.includes("errand") ||
      taskTitle.includes("shopping") ||
      taskTitle.includes("park");

    if (isOutdoorTask) {
      const temp = factors.weatherData.current?.temperature_2m;
      const weatherCode = factors.weatherData.current?.weather_code;

      // Good weather (0 = clear sky, 1-3 = partly cloudy)
      if (weatherCode <= 3 && temp >= 15 && temp <= 30) {
        importance += 2;
        reasoning.push("Perfect weather for outdoor activities! ☀️");
      }
      // Bad weather (rain, snow, etc.)
      else if (weatherCode >= 50) {
        importance -= 2;
        reasoning.push("Consider postponing - weather is poor 🌧️");
      }
    }
  }

  // Factor 5: Calendar conflicts
  if (type === "task") {
    const hasUpcomingMeetings = factors.eventData.some((event) => {
      const eventStart = new Date(event.start?.dateTime || event.start?.date);
      const now = new Date();
      const hoursUntil = (eventStart.getTime() - now.getTime()) / (1000 * 60 * 60);
      return hoursUntil > 0 && hoursUntil < 4;
    });

    if (hasUpcomingMeetings) {
      reasoning.push("Do this before your upcoming meetings");
      urgency += 1;
    }
  }

  // Factor 6: GitHub PR urgency
  if (type === "github" && item.type === "pullRequest") {
    const createdAt = new Date(item.created_at);
    const ageInDays =
      (new Date().getTime() - createdAt.getTime()) / (1000 * 60 * 60 * 24);

    if (ageInDays > 3) {
      importance = 8;
      reasoning.push("PR has been open for 3+ days");
    }
  }

  // Calculate final score
  const score = Math.min(100, urgency * 5 + importance * 5);

  return {
    id: item.id || `${type}-${Math.random()}`,
    type,
    title: item.content || item.title || item.summary || item.name || "Untitled",
    description: item.description || item.location,
    score,
    urgency: Math.min(10, urgency),
    importance: Math.min(10, importance),
    reasoning,
    metadata: item,
  };
}

/**
 * Rank all items from all integrations
 */
export function rankPriorities(factors: PriorityFactors): PriorityItem[] {
  const allItems: PriorityItem[] = [];

  // Process tasks
  factors.taskData.forEach((task) => {
    allItems.push(calculatePriority(task, "task", factors));
  });

  // Process events (only upcoming ones within next 8 hours)
  const now = new Date();
  factors.eventData.forEach((event) => {
    const eventStart = new Date(event.start?.dateTime || event.start?.date);
    const hoursUntil = (eventStart.getTime() - now.getTime()) / (1000 * 60 * 60);

    if (hoursUntil > 0 && hoursUntil < 8) {
      allItems.push(calculatePriority(event, "event", factors));
    }
  });

  // Process habits (only incomplete ones today)
  factors.habitData.forEach((habit) => {
    const lastCompleted = habit.lastCompletedAt
      ? new Date(habit.lastCompletedAt)
      : null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const completedToday =
      lastCompleted && lastCompleted.getTime() >= today.getTime();

    if (!completedToday) {
      allItems.push(calculatePriority(habit, "habit", factors));
    }
  });

  // Sort by score (highest first)
  return allItems.sort((a, b) => b.score - a.score);
}

/**
 * Get top N priorities
 */
export function getTopPriorities(
  factors: PriorityFactors,
  count: number = 3
): PriorityItem[] {
  const ranked = rankPriorities(factors);
  return ranked.slice(0, count);
}

/**
 * Get quick wins (easy, high-impact tasks)
 */
export function getQuickWins(factors: PriorityFactors): PriorityItem[] {
  const ranked = rankPriorities(factors);

  return ranked
    .filter((item) => {
      // Tasks that are important but not super urgent
      return (
        item.type === "task" &&
        item.importance >= 6 &&
        item.urgency <= 7 &&
        // Assume tasks without time estimates are quick
        !item.metadata?.duration
      );
    })
    .slice(0, 3);
}

/**
 * Categorize priorities by time of day
 */
export function categorizePrioritiesByTime(
  priorities: PriorityItem[]
): {
  morning: PriorityItem[];
  afternoon: PriorityItem[];
  evening: PriorityItem[];
  anytime: PriorityItem[];
} {
  const result = {
    morning: [] as PriorityItem[],
    afternoon: [] as PriorityItem[],
    evening: [] as PriorityItem[],
    anytime: [] as PriorityItem[],
  };

  priorities.forEach((item) => {
    // Habits with specific times
    if (item.type === "habit" && item.metadata?.timeOfDay) {
      const timeSlot = item.metadata.timeOfDay;
      if (result[timeSlot]) {
        result[timeSlot].push(item);
      } else {
        result.anytime.push(item);
      }
    }
    // Events based on their start time
    else if (item.type === "event" && item.metadata?.start) {
      const hour = new Date(
        item.metadata.start.dateTime || item.metadata.start.date
      ).getHours();
      if (hour < 12) result.morning.push(item);
      else if (hour < 17) result.afternoon.push(item);
      else result.evening.push(item);
    }
    // Everything else goes to anytime
    else {
      result.anytime.push(item);
    }
  });

  return result;
}
