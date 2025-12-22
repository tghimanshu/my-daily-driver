"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface QuickActionProps {
  title: string;
  description: string;
  icon: string;
  onClick: () => void;
  color?: string;
}

const quickActions: QuickActionProps[] = [
  {
    title: "Add Task",
    description: "Create a new task",
    icon: "✅",
    onClick: () => console.log("Add task"),
    color: "from-blue-500 to-cyan-500",
  },
  {
    title: "Log Habit",
    description: "Mark habit complete",
    icon: "✨",
    onClick: () => console.log("Log habit"),
    color: "from-purple-500 to-pink-500",
  },
  {
    title: "New Event",
    description: "Schedule calendar event",
    icon: "📅",
    onClick: () => console.log("New event"),
    color: "from-green-500 to-emerald-500",
  },
  {
    title: "Quick Note",
    description: "Jot down an idea",
    icon: "📝",
    onClick: () => console.log("Quick note"),
    color: "from-orange-500 to-amber-500",
  },
  {
    title: "Focus Mode",
    description: "Start deep work",
    icon: "🎯",
    onClick: () => console.log("Focus mode"),
    color: "from-red-500 to-rose-500",
  },
  {
    title: "Break Time",
    description: "Take a breather",
    icon: "☕",
    onClick: () => console.log("Break time"),
    color: "from-teal-500 to-cyan-500",
  },
];

export function QuickActionsWidget() {
  const [currentPage, setCurrentPage] = useState(0);
  const itemsPerPage = 4;
  const totalPages = Math.ceil(quickActions.length / itemsPerPage);

  const displayedActions = quickActions.slice(
    currentPage * itemsPerPage,
    (currentPage + 1) * itemsPerPage
  );

  return (
    <Card className="glass">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <span className="text-xl">⚡</span>
          Quick Actions
        </CardTitle>
        <div className="flex gap-1">
          <button
            onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
            disabled={currentPage === 0}
            className="p-1 rounded-md hover:bg-accent disabled:opacity-30 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={() =>
              setCurrentPage((p) => Math.min(totalPages - 1, p + 1))
            }
            disabled={currentPage === totalPages - 1}
            className="p-1 rounded-md hover:bg-accent disabled:opacity-30 transition-colors"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {displayedActions.map((action, idx) => (
            <button
              key={idx}
              onClick={action.onClick}
              className="group relative overflow-hidden rounded-lg p-4 text-left transition-all hover-lift border border-border/50 hover:border-primary/50"
            >
              <div
                className={`absolute inset-0 bg-linear-to-br ${action.color} opacity-0 group-hover:opacity-10 transition-opacity`}
              />
              <div className="relative space-y-2">
                <div className="text-2xl">{action.icon}</div>
                <div>
                  <h4 className="font-semibold text-sm">{action.title}</h4>
                  <p className="text-xs text-muted-foreground">
                    {action.description}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
