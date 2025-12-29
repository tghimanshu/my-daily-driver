"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Clock,
    CheckCircle2,
    Calendar,
    CloudSun,
    Zap,
    Target,
    AlertCircle,
    TrendingUp,
    Flame
} from "lucide-react";

interface MorningBriefingProps {
    briefing: {
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
    };
    greeting: string;
}

export function MorningBriefing({ briefing, greeting }: MorningBriefingProps) {
    const { summary, priorities, insights } = briefing;

    // Mood colors and icons
    const moodConfig = {
        productive: { color: "text-green-500", bg: "bg-green-500/10", icon: "✨" },
        busy: { color: "text-amber-500", bg: "bg-amber-500/10", icon: "⚡" },
        relaxed: { color: "text-blue-500", bg: "bg-blue-500/10", icon: "☀️" },
        challenging: { color: "text-red-500", bg: "bg-red-500/10", icon: "🎯" },
    };

    const mood = moodConfig[summary.overallMood];

    return (
        <div className="space-y-6">
            {/* Header Greeting */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 dark:from-purple-400 dark:to-pink-400 bg-clip-text text-transparent">
                        {greeting}
                    </h1>
                    <p className="text-muted-foreground mt-2">
                        {new Date().toLocaleDateString("en-US", {
                            weekday: "long",
                            year: "numeric",
                            month: "long",
                            day: "numeric",
                        })}
                    </p>
                </div>
                <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${mood.bg}`}>
                    <span className="text-2xl">{mood.icon}</span>
                    <span className={`font-semibold capitalize ${mood.color}`}>
                        {summary.overallMood} Day
                    </span>
                </div>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="glass hover-lift">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <CheckCircle2 className="h-5 w-5 text-blue-500" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold">{summary.totalTasks}</p>
                            <p className="text-xs text-muted-foreground">Tasks Today</p>
                        </div>
                    </CardContent>
                </Card>

                <Card className="glass hover-lift">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/10">
                            <Calendar className="h-5 w-5 text-purple-500" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold">{summary.totalEvents}</p>
                            <p className="text-xs text-muted-foreground">Meetings</p>
                        </div>
                    </CardContent>
                </Card>

                <Card className="glass hover-lift">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-orange-500/10">
                            <Flame className="h-5 w-5 text-orange-500" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold">{summary.completedHabits}</p>
                            <p className="text-xs text-muted-foreground">Habits Done</p>
                        </div>
                    </CardContent>
                </Card>

                <Card className="glass hover-lift">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/10">
                            <CloudSun className="h-5 w-5 text-cyan-500" />
                        </div>
                        <div>
                            <p className="text-sm font-semibold">{summary.weatherSummary.split(",")[0]}</p>
                            <p className="text-xs text-muted-foreground">{summary.weatherSummary.split(",")[1]?.trim() || "Today"}</p>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Top Priorities */}
            <Card className="glass border-purple-500/20">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Target className="h-5 w-5 text-purple-500" />
                        Top 3 Priorities
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {priorities.top3.length > 0 ? (
                        priorities.top3.map((item, index) => (
                            <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors">
                                <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold ${index === 0 ? "bg-yellow-500 text-white" :
                                        index === 1 ? "bg-gray-400 text-white" :
                                            "bg-amber-700 text-white"
                                    }`}>
                                    {index + 1}
                                </div>
                                <div className="flex-1">
                                    <p className="font-medium">{item.title}</p>
                                    <div className="flex flex-wrap gap-2 mt-1">
                                        {item.reasoning.map((reason: string, i: number) => (
                                            <span key={i} className="text-xs text-muted-foreground">
                                                💡 {reason}
                                            </span>
                                        ))}
                                    </div>
                                    <div className="flex gap-2 mt-2">
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-500">
                                            Urgency: {item.urgency}/10
                                        </span>
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500">
                                            Importance: {item.importance}/10
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))
                    ) : (
                        <p className="text-muted-foreground text-center py-4">No priorities identified for today</p>
                    )}
                </CardContent>
            </Card>

            {/* Insights Grid */}
            <div className="grid md:grid-cols-2 gap-4">
                {/* Quick Wins */}
                {priorities.quickWins.length > 0 && (
                    <Card className="glass">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base">
                                <Zap className="h-4 w-4 text-yellow-500" />
                                Quick Wins
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {priorities.quickWins.slice(0, 3).map((item: any, index: number) => (
                                <div key={index} className="flex items-center gap-2 text-sm">
                                    <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                                    <span>{item.title}</span>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                )}

                {/* Schedule Advice */}
                {insights.scheduleAdvice.length > 0 && (
                    <Card className="glass">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base">
                                <Clock className="h-4 w-4 text-blue-500" />
                                Schedule Insights
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {insights.scheduleAdvice.map((advice, index) => (
                                <p key={index} className="text-sm text-muted-foreground">
                                    📅 {advice}
                                </p>
                            ))}
                        </CardContent>
                    </Card>
                )}

                {/* Weather Impact */}
                {insights.weatherImpact.length > 0 && (
                    <Card className="glass">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base">
                                <CloudSun className="h-4 w-4 text-cyan-500" />
                                Weather Impact
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {insights.weatherImpact.map((impact, index) => (
                                <p key={index} className="text-sm text-muted-foreground">
                                    🌤️ {impact}
                                </p>
                            ))}
                        </CardContent>
                    </Card>
                )}

                {/* Energy Optimization */}
                {insights.energyOptimization.length > 0 && (
                    <Card className="glass">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base">
                                <TrendingUp className="h-4 w-4 text-green-500" />
                                Energy Tips
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            {insights.energyOptimization.map((tip, index) => (
                                <p key={index} className="text-sm text-muted-foreground">
                                    ⚡ {tip}
                                </p>
                            ))}
                        </CardContent>
                    </Card>
                )}
            </div>

            {/* Habit Reminders */}
            {insights.habitReminders.length > 0 && (
                <Card className="glass border-orange-500/20">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Flame className="h-5 w-5 text-orange-500" />
                            Habit Reminders
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex flex-wrap gap-2">
                            {insights.habitReminders.map((reminder, index) => (
                                <div
                                    key={index}
                                    className="px-3 py-2 rounded-lg bg-orange-500/10 text-orange-500 text-sm font-medium"
                                >
                                    {reminder}
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Must Do (Urgent) */}
            {priorities.mustDo.length > 0 && (
                <Card className="glass border-red-500/20">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <AlertCircle className="h-5 w-5 text-red-500" />
                            Urgent Items
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {priorities.mustDo.map((item: any, index: number) => (
                            <div
                                key={index}
                                className="flex items-center justify-between p-3 rounded-lg bg-red-500/5 border border-red-500/20"
                            >
                                <div>
                                    <p className="font-medium">{item.title}</p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        {item.reasoning.join(" • ")}
                                    </p>
                                </div>
                                <span className="text-red-500 font-bold">!</span>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
