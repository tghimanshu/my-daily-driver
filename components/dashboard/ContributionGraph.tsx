"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { ActivityCalendar } from "react-activity-calendar";
import { Tooltip } from "react-tooltip";
import * as React from "react";

interface ContributionDay {
  date: string;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
}

interface Props {
  data?: ContributionDay[];
  isRealData?: boolean;
}

export function ContributionGraph({ data, isRealData = false }: Props) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const generateMockData = (): ContributionDay[] => {
    const days: ContributionDay[] = [];
    const today = new Date();
    for (let i = 364; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const count = Math.floor(Math.random() * 10);
      const level: 0 | 1 | 2 | 3 | 4 = count === 0
        ? 0
        : count < 3
        ? 1
        : count < 5
        ? 2
        : count < 8
        ? 3
        : 4;
      days.push({
        date: date.toISOString().split("T")[0],
        count,
        level,
      });
    }
    return days;
  };

  const activityData = data && data.length > 0 ? data : generateMockData();
  const totalCount = activityData.reduce((sum, day) => sum + day.count, 0);
  const avgCount = (totalCount / activityData.length).toFixed(1);

  if (!mounted)
    return (
      <div className="h-50 w-full animate-pulse rounded-xl bg-muted/50" />
    );

  return (
    <div className="w-full overflow-hidden rounded-xl border bg-card p-6 text-card-foreground shadow-sm hover-lift fade-in glass">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-bold tracking-tight">Your Activity</h2>
            {!isRealData && (
              <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                Demo Data
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {isRealData
              ? "Your GitHub contributions over the last year"
              : "Sample contribution data to showcase the layout"}
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-primary">{totalCount}</div>
          <div className="text-xs text-muted-foreground">Total</div>
        </div>
      </div>
      <div className="flex justify-center overflow-x-auto pb-2">
        <ActivityCalendar
          data={activityData}
          colorScheme={resolvedTheme === "dark" ? "dark" : "light"}
          theme={{
            light: ["#f0f0f5", "#c4b5fd", "#a78bfa", "#8b5cf6", "#7c3aed"],
            dark: ["#1a1625", "#4c1d95", "#6d28d9", "#7c3aed", "#9333ea"],
          }}
          blockSize={13}
          blockMargin={5}
          fontSize={12}
          showWeekdayLabels={true}
          style={{
            color: "var(--muted-foreground)",
          }}
        />
      </div>
    </div>
  );
}
