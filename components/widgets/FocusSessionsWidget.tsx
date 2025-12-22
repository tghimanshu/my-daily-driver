"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Zap, CheckCircle2 } from "lucide-react";

interface FocusSession {
  id: number;
  title: string;
  duration: string;
  completed: boolean;
  time: string;
}

const sessions: FocusSession[] = [
  {
    id: 1,
    title: "Morning Deep Work",
    duration: "90 min",
    completed: true,
    time: "08:00 AM",
  },
  {
    id: 2,
    title: "Code Review",
    duration: "45 min",
    completed: true,
    time: "11:00 AM",
  },
  {
    id: 3,
    title: "Afternoon Focus",
    duration: "60 min",
    completed: false,
    time: "02:00 PM",
  },
  {
    id: 4,
    title: "Learning Time",
    duration: "30 min",
    completed: false,
    time: "04:00 PM",
  },
];

export function FocusSessionsWidget() {
  const completedSessions = sessions.filter((s) => s.completed).length;
  const totalDuration = sessions.reduce(
    (acc, s) => acc + parseInt(s.duration),
    0
  );

  return (
    <Card className="glass">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-orange-500" />
            Focus Sessions
          </div>
          <span className="text-sm font-normal text-muted-foreground">
            {completedSessions}/{sessions.length} completed
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`flex items-center gap-3 p-3 rounded-lg border transition-all hover-lift ${
              session.completed
                ? "border-green-500/20 bg-green-500/5"
                : "border-border/50"
            }`}
          >
            <div
              className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                session.completed ? "bg-green-500" : "bg-muted"
              }`}
            >
              {session.completed ? (
                <CheckCircle2 className="h-4 w-4 text-white" />
              ) : (
                <span className="text-xs font-medium text-muted-foreground">
                  {session.duration.split(" ")[0]}m
                </span>
              )}
            </div>
            <div className="flex-1">
              <h4
                className={`font-medium text-sm ${
                  session.completed ? "line-through text-muted-foreground" : ""
                }`}
              >
                {session.title}
              </h4>
              <p className="text-xs text-muted-foreground">
                {session.time} • {session.duration}
              </p>
            </div>
          </div>
        ))}

        <div className="pt-3 border-t border-border/50">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Total Focus Time</span>
            <span className="font-semibold">{totalDuration} minutes</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
