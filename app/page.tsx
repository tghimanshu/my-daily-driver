import { auth } from "@/auth";
import { fetchTodayHabits } from "@/app/actions/habits";
import { fetchContributionData } from "@/lib/api/github";
import { fetchWeather } from "@/lib/api/weather";
import { calculateScore } from "@/lib/scorometer";
import { generateDailyBriefing, getSmartGreeting } from "@/lib/daily-setup";

import { DashboardShell } from "@/components/layout/DashboardShell";
import { ContributionGraph } from "@/components/dashboard/ContributionGraph";
import { MorningBriefing } from "@/components/dashboard/MorningBriefing";
import { WeatherWidget } from "@/components/dashboard/WeatherWidget";
import { ProductivityChart } from "@/components/dashboard/ProductivityChart";
import { HabitTracker } from "@/components/dashboard/HabitTracker";
import { TaskList } from "@/components/dashboard/TaskList";
import { CalendarWidget } from "@/components/dashboard/CalendarWidget";
import { MusicWidget } from "@/components/dashboard/MusicWidget";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QuickActionsWidget } from "@/components/widgets/QuickActionsWidget";
import { LiveClockWidget } from "@/components/widgets/LiveClockWidget";
import { GoalProgressWidget } from "@/components/widgets/GoalProgressWidget";
import { FocusSessionsWidget } from "@/components/widgets/FocusSessionsWidget";

export default async function Home() {
  const session = await auth();

  // Fetch habits and contributions data
  const [habitsResult, contributionsResult, weatherResult] = await Promise.allSettled([
    fetchTodayHabits(),
    fetchContributionData(),
    fetchWeather(),
  ]);

  const habitsData = habitsResult.status === "fulfilled" ? habitsResult.value : [];
  const contributionsData = contributionsResult.status === "fulfilled" ? contributionsResult.value : [];
  const weather = weatherResult.status === "fulfilled" ? weatherResult.value : null;

  // Generate comprehensive daily briefing (fetches all integrations)
  const briefing = await generateDailyBriefing(
    // @ts-ignore - AccessToken is added in session callback
    session?.accessToken,
    habitsData
  );

  // Generate smart greeting
  const greeting = getSmartGreeting(briefing);

  // For backwards compatibility, extract individual data
  const tasksData = briefing.priorities.top3
    .filter((p) => p.type === "task")
    .map((p) => p.metadata);
  const eventsData = briefing.priorities.top3
    .filter((p) => p.type === "event")
    .map((p) => p.metadata);

  const score = calculateScore(tasksData, eventsData, []);

  return (
    <DashboardShell>
      <div className="flex flex-col gap-8 pb-8">
        {/* Morning Briefing - New comprehensive view */}
        <MorningBriefing briefing={briefing} greeting={greeting} />

        {/* Top Row: Quick Glance Stats */}
        <div className="grid gap-4 md:grid-cols-4 stagger">
          {/* Weather Card */}
          <Card className="col-span-1 gradient-cool border-0 hover-lift fade-in glow-accent">
            <CardContent className="p-6 h-full">
              <WeatherWidget data={weather} />
            </CardContent>
          </Card>

          {/* Productivity Score */}
          <Card className="col-span-1 md:col-span-1 glass hover-lift fade-in">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Focus Score
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 pb-4">
              <ProductivityChart score={score} />
            </CardContent>
          </Card>

          {/* Habits */}
          <Card className="col-span-1 md:col-span-2 glass hover-lift fade-in">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="text-2xl">✨</span>
                Daily Habits
              </CardTitle>
            </CardHeader>
            <CardContent>
              <HabitTracker habits={habitsData} />
            </CardContent>
          </Card>
        </div>

        {/* Middle Row: Contribution Graph */}
        <section className="fade-in-slow">
          <ContributionGraph
            data={contributionsData}
            isRealData={contributionsData.length > 0}
          />
        </section>

        {/* Bottom Row: Integrations */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 stagger">
          <Card className="col-span-1 min-h-100 glass hover-lift fade-in">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                <span className="text-xl">✅</span>
                Tasks
                {tasksData.length > 0 && (
                  <span className="ml-auto text-xs font-normal text-muted-foreground">
                    {tasksData.length} tasks
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <TaskList tasks={tasksData} />
            </CardContent>
          </Card>

          <Card className="col-span-1 min-h-100 glass hover-lift fade-in">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                <span className="text-xl">📅</span>
                Calendar
                {eventsData.length > 0 && (
                  <span className="ml-auto text-xs font-normal text-muted-foreground">
                    {eventsData.length} events
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CalendarWidget events={eventsData} />
            </CardContent>
          </Card>

          <Card className="col-span-1 min-h-100 overflow-hidden p-0 bg-black border-0 hover-lift fade-in">
            {/* No header or padding for music widget to look immersive */}
            <MusicWidget />
          </Card>
        </div>

        {/* New Advanced Widgets Row */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 stagger">
          <LiveClockWidget />
          <div className="lg:col-span-2">
            <QuickActionsWidget />
          </div>
          <GoalProgressWidget />
        </div>

        {/* Focus Sessions */}
        <div className="grid gap-4 lg:grid-cols-2">
          <FocusSessionsWidget />
          <Card className="glass gradient-accent border-0">
            <CardHeader>
              <CardTitle className="text-white">Daily Insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-white">
              <div className="flex items-center gap-3 p-3 bg-white/10 rounded-lg">
                <span className="text-2xl">🎯</span>
                <div>
                  <p className="font-medium">Most Productive Hour</p>
                  <p className="text-sm text-white/80">9:00 AM - 10:00 AM</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/10 rounded-lg">
                <span className="text-2xl">⚡</span>
                <div>
                  <p className="font-medium">Focus Streak</p>
                  <p className="text-sm text-white/80">5 days of deep work</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/10 rounded-lg">
                <span className="text-2xl">🌟</span>
                <div>
                  <p className="font-medium">Top Habit</p>
                  <p className="text-sm text-white/80">
                    Meditation - 90% completion
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}
