// Todoist API Integration

export interface TodoistTask {
  id: string;
  content: string;
  description: string;
  completed: boolean;
  priority: number;
  due?: {
    date: string;
    datetime?: string;
    string: string;
  };
  labels: string[];
  project_id: string;
}

export async function fetchDailyTasks(): Promise<TodoistTask[]> {
  const token = process.env.TODOIST_TOKEN;
  if (!token) {
    console.warn("Todoist token not configured");
    return [];
  }

  try {
    // Fetch tasks due today or overdue
    const res = await fetch(
      "https://api.todoist.com/rest/v2/tasks?filter=today|overdue",
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        next: { revalidate: 300 }, // Cache for 5 mins
      }
    );

    if (!res.ok) {
      console.error(`Todoist API Error: ${res.status} ${res.statusText}`);
      return [];
    }

    const tasks = await res.json();
    console.log(tasks);
    return tasks;
  } catch (e) {
    console.error("Todoist API Error:", e);
    return [];
  }
}

export async function fetchAllTasks(): Promise<TodoistTask[]> {
  const token = process.env.TODOIST_TOKEN;
  if (!token) return [];

  try {
    const res = await fetch("https://api.todoist.com/rest/v2/tasks", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      next: { revalidate: 600 },
    });

    if (!res.ok) return [];
    const tasks = await res.json();
    return tasks;
  } catch (e) {
    console.error("Todoist API Error:", e);
    return [];
  }
}

export async function getTaskStats() {
  const tasks = await fetchAllTasks();

  return {
    total: tasks.length,
    completed: tasks.filter((t) => t.completed).length,
    highPriority: tasks.filter((t) => t.priority >= 3).length,
    dueToday: tasks.filter((t) => {
      if (!t.due) return false;
      const today = new Date().toISOString().split("T")[0];
      return t.due.date === today;
    }).length,
  };
}
