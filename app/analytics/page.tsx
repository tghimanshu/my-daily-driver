"use client";
import { auth } from "@/auth";
import { DashboardShell } from "@/components/layout/DashboardShell";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Award,
  Calendar,
} from "lucide-react";

// Mock data - replace with real data from your database
const productivityData = [
  { date: "Mon", tasks: 12, habits: 5, focus: 85 },
  { date: "Tue", tasks: 15, habits: 6, focus: 92 },
  { date: "Wed", tasks: 10, habits: 4, focus: 78 },
  { date: "Thu", tasks: 18, habits: 7, focus: 95 },
  { date: "Fri", tasks: 14, habits: 6, focus: 88 },
  { date: "Sat", tasks: 8, habits: 5, focus: 82 },
  { date: "Sun", tasks: 6, habits: 4, focus: 75 },
];

const habitCompletionData = [
  { name: "Morning Routine", value: 85, color: "#8b5cf6" },
  { name: "Exercise", value: 70, color: "#3b82f6" },
  { name: "Reading", value: 60, color: "#06b6d4" },
  { name: "Meditation", value: 90, color: "#10b981" },
  { name: "Learning", value: 55, color: "#f59e0b" },
];

const monthlyProgress = [
  { month: "Jan", completed: 145, failed: 15 },
  { month: "Feb", completed: 168, failed: 12 },
  { month: "Mar", completed: 182, failed: 18 },
  { month: "Apr", completed: 195, failed: 10 },
  { month: "May", completed: 210, failed: 8 },
  { month: "Jun", completed: 225, failed: 5 },
];

const statsCards = [
  {
    title: "Tasks Completed",
    value: "847",
    change: "+12.5%",
    trend: "up",
    icon: Target,
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
  },
  {
    title: "Habit Streak",
    value: "23 days",
    change: "+3 days",
    trend: "up",
    icon: Award,
    color: "text-purple-500",
    bgColor: "bg-purple-500/10",
  },
  {
    title: "Focus Score",
    value: "87%",
    change: "+5%",
    trend: "up",
    icon: Activity,
    color: "text-green-500",
    bgColor: "bg-green-500/10",
  },
  {
    title: "Weekly Goals",
    value: "18/20",
    change: "-2",
    trend: "down",
    icon: Calendar,
    color: "text-orange-500",
    bgColor: "bg-orange-500/10",
  },
];

export default async function AnalyticsPage() {
  const session = await auth();

  return (
    <DashboardShell>
      <div className="flex flex-col gap-8 pb-8">
        {/* Header */}
        <div className="flex flex-col gap-2">
          <h1 className="text-4xl font-bold tracking-tight">Analytics</h1>
          <p className="text-muted-foreground">
            Track your productivity, habits, and personal growth
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {statsCards.map((stat) => {
            const Icon = stat.icon;
            const TrendIcon = stat.trend === "up" ? TrendingUp : TrendingDown;
            return (
              <Card key={stat.title} className="glass hover-lift">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {stat.title}
                  </CardTitle>
                  <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                    <Icon className={`h-4 w-4 ${stat.color}`} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <div
                    className={`flex items-center gap-1 text-xs ${
                      stat.trend === "up" ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    <TrendIcon className="h-3 w-3" />
                    <span>{stat.change} from last week</span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Charts Row 1 */}
        <div className="grid gap-4 md:grid-cols-2">
          {/* Weekly Productivity */}
          <Card className="glass">
            <CardHeader>
              <CardTitle>Weekly Productivity</CardTitle>
              <CardDescription>
                Your task completion and focus metrics
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={productivityData}>
                  <defs>
                    <linearGradient id="colorTasks" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorFocus" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="tasks"
                    stroke="#8b5cf6"
                    fillOpacity={1}
                    fill="url(#colorTasks)"
                  />
                  <Area
                    type="monotone"
                    dataKey="focus"
                    stroke="#3b82f6"
                    fillOpacity={1}
                    fill="url(#colorFocus)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Habit Completion Rate */}
          <Card className="glass">
            <CardHeader>
              <CardTitle>Habit Completion Rate</CardTitle>
              <CardDescription>
                How consistently you're building habits
              </CardDescription>
            </CardHeader>
            <CardContent className="flex justify-center">
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={habitCompletionData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}%`}
                  >
                    {habitCompletionData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Charts Row 2 */}
        <div className="grid gap-4">
          {/* Monthly Progress */}
          <Card className="glass">
            <CardHeader>
              <CardTitle>6-Month Progress Overview</CardTitle>
              <CardDescription>
                Your completed vs. failed tasks over time
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={monthlyProgress}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend />
                  <Bar
                    dataKey="completed"
                    fill="#10b981"
                    radius={[8, 8, 0, 0]}
                  />
                  <Bar dataKey="failed" fill="#ef4444" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Insights Section */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="glass gradient-cool border-0">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Peak Performance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-white/90">
                You're most productive on <strong>Thursdays</strong> with an
                average of 18 tasks completed.
              </p>
            </CardContent>
          </Card>

          <Card className="glass gradient-primary border-0">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Award className="h-5 w-5" />
                Best Streak
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-white/90">
                Your best habit streak was <strong>45 days</strong> for
                meditation in March.
              </p>
            </CardContent>
          </Card>

          <Card className="glass gradient-success border-0">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Target className="h-5 w-5" />
                Improvement Area
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-white/90">
                Try increasing your <strong>weekend productivity</strong> to
                maintain momentum.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

