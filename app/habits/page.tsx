import { auth } from "@/auth";
import { DashboardShell } from "@/components/layout/DashboardShell";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchTodayHabits } from "@/app/actions/habits";
import {
  Flame,
  Trophy,
  Target,
  TrendingUp,
  Calendar,
  CheckCircle2,
} from "lucide-react";

// Mock data for demonstration
const habitCategories = [
  {
    name: "Health & Fitness",
    icon: "💪",
    habits: [
      {
        id: 1,
        name: "Morning Workout",
        streak: 23,
        target: 30,
        completed: true,
      },
      { id: 2, name: "10k Steps", streak: 15, target: 30, completed: false },
      {
        id: 3,
        name: "Drink 8 Glasses of Water",
        streak: 28,
        target: 30,
        completed: true,
      },
    ],
  },
  {
    name: "Personal Growth",
    icon: "📚",
    habits: [
      {
        id: 4,
        name: "Read 30 Minutes",
        streak: 18,
        target: 30,
        completed: true,
      },
      {
        id: 5,
        name: "Learn New Skill",
        streak: 12,
        target: 30,
        completed: false,
      },
      { id: 6, name: "Journal", streak: 20, target: 30, completed: false },
    ],
  },
  {
    name: "Mindfulness",
    icon: "🧘",
    habits: [
      { id: 7, name: "Meditation", streak: 45, target: 60, completed: true },
      {
        id: 8,
        name: "Gratitude Practice",
        streak: 30,
        target: 30,
        completed: true,
      },
      {
        id: 9,
        name: "No Social Media Before 10am",
        streak: 8,
        target: 30,
        completed: true,
      },
    ],
  },
  {
    name: "Productivity",
    icon: "⚡",
    habits: [
      {
        id: 10,
        name: "Plan Tomorrow",
        streak: 25,
        target: 30,
        completed: false,
      },
      { id: 11, name: "Inbox Zero", streak: 5, target: 30, completed: false },
      {
        id: 12,
        name: "Deep Work Session",
        streak: 14,
        target: 30,
        completed: true,
      },
    ],
  },
];

const overallStats = {
  totalHabits: 12,
  completedToday: 7,
  longestStreak: 45,
  completionRate: 85,
};

export default async function HabitsPage() {
  const session = await auth();
  const habits = await fetchTodayHabits().catch(() => []);

  return (
    <DashboardShell>
      <div className="flex flex-col gap-8 pb-8">
        {/* Header */}
        <div className="flex flex-col gap-2">
          <h1 className="text-4xl font-bold tracking-tight">Habits</h1>
          <p className="text-muted-foreground">
            Build consistency and track your daily habits
          </p>
        </div>

        {/* Overview Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card className="glass hover-lift gradient-primary border-0">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-white/90">
                Today's Progress
              </CardTitle>
              <CheckCircle2 className="h-5 w-5 text-white" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {overallStats.completedToday}/{overallStats.totalHabits}
              </div>
              <p className="text-xs text-white/80 mt-1">Habits completed</p>
            </CardContent>
          </Card>

          <Card className="glass hover-lift gradient-warm border-0">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-white/90">
                Longest Streak
              </CardTitle>
              <Flame className="h-5 w-5 text-white" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {overallStats.longestStreak} days
              </div>
              <p className="text-xs text-white/80 mt-1">Meditation habit</p>
            </CardContent>
          </Card>

          <Card className="glass hover-lift gradient-success border-0">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-white/90">
                Completion Rate
              </CardTitle>
              <Target className="h-5 w-5 text-white" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {overallStats.completionRate}%
              </div>
              <p className="text-xs text-white/80 mt-1">This month</p>
            </CardContent>
          </Card>

          <Card className="glass hover-lift gradient-cool border-0">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-white/90">
                Active Habits
              </CardTitle>
              <Trophy className="h-5 w-5 text-white" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {overallStats.totalHabits}
              </div>
              <p className="text-xs text-white/80 mt-1">Total tracking</p>
            </CardContent>
          </Card>
        </div>

        {/* Habit Categories */}
        {habitCategories.map((category, idx) => (
          <div
            key={idx}
            className="space-y-4 fade-in"
            style={{ animationDelay: `${idx * 100}ms` }}
          >
            <div className="flex items-center gap-3">
              <span className="text-3xl">{category.icon}</span>
              <h2 className="text-2xl font-semibold">{category.name}</h2>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {category.habits.map((habit) => (
                <Card
                  key={habit.id}
                  className="glass hover-lift group cursor-pointer"
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base">{habit.name}</CardTitle>
                      {habit.completed && (
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {/* Streak */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Flame className="h-4 w-4 text-orange-500" />
                        <span className="text-sm text-muted-foreground">
                          Current Streak
                        </span>
                      </div>
                      <span className="font-semibold">{habit.streak} days</span>
                    </div>

                    {/* Progress Bar */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>Progress</span>
                        <span>
                          {Math.round((habit.streak / habit.target) * 100)}%
                        </span>
                      </div>
                      <div className="h-2 bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full bg-linear-to-r from-primary to-purple-400 transition-all duration-500 group-hover:scale-105"
                          style={{
                            width: `${Math.min(
                              (habit.streak / habit.target) * 100,
                              100
                            )}%`,
                          }}
                        />
                      </div>
                      <div className="text-xs text-muted-foreground text-right">
                        Goal: {habit.target} days
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))}

        {/* Add New Habit CTA */}
        <Card className="glass border-dashed hover-lift cursor-pointer group">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Target className="h-8 w-8 text-primary" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Add New Habit</h3>
            <p className="text-sm text-muted-foreground text-center max-w-sm">
              Start building a new habit today. Consistency is key to personal
              growth.
            </p>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
