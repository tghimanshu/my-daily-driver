"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Target, TrendingUp } from "lucide-react";

interface Goal {
  id: number;
  title: string;
  current: number;
  target: number;
  unit: string;
  color: string;
  icon: string;
}

const goals: Goal[] = [
  {
    id: 1,
    title: "Daily Tasks",
    current: 12,
    target: 15,
    unit: "tasks",
    color: "bg-blue-500",
    icon: "✅",
  },
  {
    id: 2,
    title: "Reading Time",
    current: 45,
    target: 60,
    unit: "min",
    color: "bg-purple-500",
    icon: "📚",
  },
  {
    id: 3,
    title: "Exercise",
    current: 3,
    target: 5,
    unit: "days",
    color: "bg-green-500",
    icon: "💪",
  },
  {
    id: 4,
    title: "Learning",
    current: 8,
    target: 10,
    unit: "hours",
    color: "bg-orange-500",
    icon: "🎓",
  },
];

export function GoalProgressWidget() {
  return (
    <Card className="glass">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5" />
          Weekly Goals
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {goals.map((goal) => {
          const percentage = Math.min((goal.current / goal.target) * 100, 100);
          const isCompleted = goal.current >= goal.target;

          return (
            <div key={goal.id} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{goal.icon}</span>
                  <span className="font-medium">{goal.title}</span>
                </div>
                <span className="text-muted-foreground">
                  {goal.current}/{goal.target} {goal.unit}
                </span>
              </div>
              <div className="relative h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className={`h-full ${goal.color} transition-all duration-500 relative`}
                  style={{ width: `${percentage}%` }}
                >
                  {isCompleted && (
                    <div className="absolute inset-0 animate-pulse opacity-50" />
                  )}
                </div>
              </div>
              {isCompleted && (
                <div className="flex items-center gap-1 text-xs text-green-500">
                  <TrendingUp className="h-3 w-3" />
                  <span>Goal achieved! 🎉</span>
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
