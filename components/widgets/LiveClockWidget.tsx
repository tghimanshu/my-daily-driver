"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { format } from "date-fns";

export function LiveClockWidget() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  return (
    <Card className="glass gradient-primary border-0">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-white/90 flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Current Time
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          <div className="text-4xl font-bold text-white tabular-nums">
            {format(time, "HH:mm:ss")}
          </div>
          <div className="text-sm text-white/80">
            {format(time, "EEEE, MMMM d, yyyy")}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
