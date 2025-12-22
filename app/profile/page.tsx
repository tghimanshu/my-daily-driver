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
  User,
  Mail,
  Calendar,
  Award,
  Target,
  TrendingUp,
  Activity,
  Flame,
} from "lucide-react";

export default async function ProfilePage() {
  const session = await auth();

  // Mock user data
  const userData = {
    name: "Alex Johnson",
    email: "alex.johnson@example.com",
    joinDate: "January 2024",
    avatar: "AJ",
    bio: "Product designer and productivity enthusiast. Building better habits one day at a time.",
    location: "San Francisco, CA",
    timezone: "PST (UTC-8)",
  };

  const achievements = [
    {
      id: 1,
      title: "Early Bird",
      description: "Completed morning routine 30 days in a row",
      icon: "🌅",
      earned: true,
      date: "Dec 1, 2025",
    },
    {
      id: 2,
      title: "Task Master",
      description: "Completed 500 tasks",
      icon: "✅",
      earned: true,
      date: "Nov 15, 2025",
    },
    {
      id: 3,
      title: "Meditation Guru",
      description: "45-day meditation streak",
      icon: "🧘",
      earned: true,
      date: "Dec 10, 2025",
    },
    {
      id: 4,
      title: "Consistency King",
      description: "85% habit completion for a month",
      icon: "👑",
      earned: true,
      date: "Oct 30, 2025",
    },
    {
      id: 5,
      title: "Week Warrior",
      description: "Perfect week of habit completion",
      icon: "⚔️",
      earned: false,
    },
    {
      id: 6,
      title: "Century Club",
      description: "100-day habit streak",
      icon: "💯",
      earned: false,
    },
  ];

  const stats = [
    {
      label: "Total Tasks",
      value: "847",
      icon: Target,
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
    },
    {
      label: "Current Streak",
      value: "23 days",
      icon: Flame,
      color: "text-orange-500",
      bgColor: "bg-orange-500/10",
    },
    {
      label: "Habits Tracked",
      value: "12",
      icon: Activity,
      color: "text-green-500",
      bgColor: "bg-green-500/10",
    },
    {
      label: "Focus Score",
      value: "87%",
      icon: TrendingUp,
      color: "text-purple-500",
      bgColor: "bg-purple-500/10",
    },
  ];

  const recentActivity = [
    {
      id: 1,
      action: "Completed morning workout",
      time: "2 hours ago",
      icon: "💪",
    },
    { id: 2, action: "Finished 3 tasks", time: "4 hours ago", icon: "✅" },
    {
      id: 3,
      action: "Meditated for 20 minutes",
      time: "6 hours ago",
      icon: "🧘",
    },
    { id: 4, action: "Read for 30 minutes", time: "Yesterday", icon: "📚" },
    { id: 5, action: "Attended team meeting", time: "Yesterday", icon: "👥" },
  ];

  return (
    <DashboardShell>
      <div className="flex flex-col gap-8 pb-8">
        {/* Header */}
        <div className="flex flex-col gap-2">
          <h1 className="text-4xl font-bold tracking-tight">Profile</h1>
          <p className="text-muted-foreground">
            Your personal information and achievements
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column - Profile Card */}
          <div className="space-y-6">
            <Card className="glass">
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center space-y-4">
                  {/* Avatar */}
                  <div className="w-24 h-24 rounded-full bg-linear-to-br from-primary to-purple-400 flex items-center justify-center text-3xl font-bold text-white">
                    {userData.avatar}
                  </div>

                  {/* Name & Email */}
                  <div className="space-y-1">
                    <h2 className="text-2xl font-bold">{userData.name}</h2>
                    <p className="text-sm text-muted-foreground flex items-center gap-1 justify-center">
                      <Mail className="h-3 w-3" />
                      {userData.email}
                    </p>
                  </div>

                  {/* Bio */}
                  <p className="text-sm text-muted-foreground">
                    {userData.bio}
                  </p>

                  {/* Info */}
                  <div className="w-full space-y-2 pt-4 border-t border-border">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Location</span>
                      <span className="font-medium">{userData.location}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Timezone</span>
                      <span className="font-medium">{userData.timezone}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        Member Since
                      </span>
                      <span className="font-medium">{userData.joinDate}</span>
                    </div>
                  </div>

                  {/* Edit Button */}
                  <button className="w-full px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
                    Edit Profile
                  </button>
                </div>
              </CardContent>
            </Card>

            {/* Stats Cards */}
            {stats.map((stat, idx) => {
              const Icon = stat.icon;
              return (
                <Card key={idx} className="glass hover-lift">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">
                          {stat.label}
                        </p>
                        <p className="text-2xl font-bold mt-1">{stat.value}</p>
                      </div>
                      <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                        <Icon className={`h-6 w-6 ${stat.color}`} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Right Column - Achievements & Activity */}
          <div className="lg:col-span-2 space-y-6">
            {/* Achievements */}
            <Card className="glass">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Award className="h-5 w-5" />
                  Achievements
                </CardTitle>
                <CardDescription>
                  Unlock achievements by building consistent habits
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  {achievements.map((achievement, idx) => (
                    <div
                      key={achievement.id}
                      className={`p-4 rounded-lg border-2 transition-all fade-in ${
                        achievement.earned
                          ? "border-primary/50 bg-primary/5 hover-lift"
                          : "border-border/50 bg-muted/20 opacity-50"
                      }`}
                      style={{ animationDelay: `${idx * 50}ms` }}
                    >
                      <div className="flex items-start gap-3">
                        <div className="text-3xl">{achievement.icon}</div>
                        <div className="flex-1">
                          <h4 className="font-semibold">{achievement.title}</h4>
                          <p className="text-sm text-muted-foreground mt-1">
                            {achievement.description}
                          </p>
                          {achievement.earned && (
                            <p className="text-xs text-primary mt-2">
                              Earned {achievement.date}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Recent Activity */}
            <Card className="glass">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Recent Activity
                </CardTitle>
                <CardDescription>
                  Your latest actions and achievements
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {recentActivity.map((activity, idx) => (
                    <div
                      key={activity.id}
                      className="flex items-center gap-4 p-3 rounded-lg hover:bg-accent/50 transition-colors fade-in"
                      style={{ animationDelay: `${idx * 50}ms` }}
                    >
                      <div className="text-2xl">{activity.icon}</div>
                      <div className="flex-1">
                        <p className="text-sm font-medium">{activity.action}</p>
                        <p className="text-xs text-muted-foreground">
                          {activity.time}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Progress Overview */}
            <Card className="glass gradient-primary border-0">
              <CardHeader>
                <CardTitle className="text-white">
                  Your Progress Journey
                </CardTitle>
                <CardDescription className="text-white/80">
                  You've come a long way!
                </CardDescription>
              </CardHeader>
              <CardContent className="text-white space-y-3">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-3xl font-bold">11</div>
                    <div className="text-sm text-white/80">Months Active</div>
                  </div>
                  <div>
                    <div className="text-3xl font-bold">4</div>
                    <div className="text-sm text-white/80">Achievements</div>
                  </div>
                  <div>
                    <div className="text-3xl font-bold">847</div>
                    <div className="text-sm text-white/80">Tasks Done</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
