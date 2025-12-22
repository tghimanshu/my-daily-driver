import { auth } from "@/auth";
import { DashboardShell } from "@/components/layout/DashboardShell";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchUpcomingEvents } from "@/lib/api/google-calendar";
import {
  Calendar,
  Clock,
  Video,
  MapPin,
  Users,
  ChevronRight,
} from "lucide-react";
import { format, addDays, startOfWeek, addWeeks, isSameDay } from "date-fns";

// Mock upcoming events
const upcomingEvents = [
  {
    id: 1,
    title: "Team Standup",
    time: "09:00 AM",
    duration: "15 min",
    type: "meeting",
    color: "bg-blue-500",
    attendees: 5,
    location: "Zoom",
    description: "Daily sync with the team",
  },
  {
    id: 2,
    title: "Client Presentation",
    time: "11:00 AM",
    duration: "1 hour",
    type: "meeting",
    color: "bg-purple-500",
    attendees: 8,
    location: "Conference Room A",
    description: "Q4 Project Review",
  },
  {
    id: 3,
    title: "Lunch with Sarah",
    time: "12:30 PM",
    duration: "1 hour",
    type: "personal",
    color: "bg-green-500",
    attendees: 2,
    location: "Downtown Cafe",
    description: "Catch up",
  },
  {
    id: 4,
    title: "Code Review",
    time: "02:00 PM",
    duration: "45 min",
    type: "work",
    color: "bg-orange-500",
    attendees: 3,
    location: "Zoom",
    description: "Review PR #234",
  },
  {
    id: 5,
    title: "Gym Session",
    time: "06:00 PM",
    duration: "1.5 hours",
    type: "personal",
    color: "bg-red-500",
    attendees: 1,
    location: "Fitness First",
    description: "Leg day",
  },
];

// Generate week view
const today = new Date();
const weekStart = startOfWeek(today, { weekStartsOn: 1 });
const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

// Mock events for week view
const weekEvents = weekDays.map((day, idx) => ({
  date: day,
  events:
    idx < 5 ? Math.floor(Math.random() * 5) + 1 : Math.floor(Math.random() * 2),
}));

export default async function CalendarPage() {
  const session = await auth();

  return (
    <DashboardShell>
      <div className="flex flex-col gap-8 pb-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">Calendar</h1>
            <p className="text-muted-foreground">
              {format(today, "EEEE, MMMM d, yyyy")}
            </p>
          </div>
          <div className="flex gap-2">
            <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
              + New Event
            </button>
          </div>
        </div>

        {/* Week View */}
        <Card className="glass">
          <CardHeader>
            <CardTitle>This Week</CardTitle>
            <CardDescription>Your schedule at a glance</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-7 gap-2">
              {weekDays.map((day, idx) => {
                const isToday = isSameDay(day, today);
                const eventCount = weekEvents[idx].events;
                return (
                  <div
                    key={idx}
                    className={`p-4 rounded-lg text-center space-y-2 cursor-pointer transition-all hover-lift ${
                      isToday ? "bg-primary text-primary-foreground" : "glass"
                    }`}
                  >
                    <div className="text-xs font-medium opacity-70">
                      {format(day, "EEE")}
                    </div>
                    <div className="text-2xl font-bold">{format(day, "d")}</div>
                    {eventCount > 0 && (
                      <div className="flex justify-center gap-1">
                        {Array.from(
                          { length: Math.min(eventCount, 3) },
                          (_, i) => (
                            <div
                              key={i}
                              className={`w-1.5 h-1.5 rounded-full ${
                                isToday ? "bg-primary-foreground" : "bg-primary"
                              }`}
                            />
                          )
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Today's Schedule */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Events List */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-2xl font-semibold">Today's Schedule</h2>
            <div className="space-y-3">
              {upcomingEvents.map((event, idx) => (
                <Card
                  key={event.id}
                  className="glass hover-lift group cursor-pointer fade-in"
                  style={{ animationDelay: `${idx * 50}ms` }}
                >
                  <CardContent className="p-6">
                    <div className="flex gap-4">
                      {/* Time & Color Indicator */}
                      <div className="flex flex-col items-center gap-2">
                        <div
                          className={`w-3 h-3 rounded-full ${event.color}`}
                        />
                        <div className="text-sm font-medium text-muted-foreground whitespace-nowrap">
                          {event.time}
                        </div>
                      </div>

                      {/* Event Details */}
                      <div className="flex-1 space-y-2">
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-semibold text-lg group-hover:text-primary transition-colors">
                              {event.title}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              {event.description}
                            </p>
                          </div>
                          <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
                        </div>

                        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Clock className="h-4 w-4" />
                            <span>{event.duration}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <MapPin className="h-4 w-4" />
                            <span>{event.location}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Users className="h-4 w-4" />
                            <span>
                              {event.attendees}{" "}
                              {event.attendees === 1 ? "person" : "people"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Quick Stats */}
            <Card className="glass gradient-primary border-0">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Calendar className="h-5 w-5" />
                  Today's Summary
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-white">
                <div className="flex justify-between">
                  <span className="text-white/80">Total Events</span>
                  <span className="font-semibold">{upcomingEvents.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/80">Meetings</span>
                  <span className="font-semibold">
                    {upcomingEvents.filter((e) => e.type === "meeting").length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/80">Total Time</span>
                  <span className="font-semibold">4.5 hrs</span>
                </div>
              </CardContent>
            </Card>

            {/* Upcoming This Week */}
            <Card className="glass">
              <CardHeader>
                <CardTitle className="text-base">Upcoming This Week</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {["Tomorrow", "Saturday", "Sunday"].map((day, idx) => (
                  <div
                    key={idx}
                    className="flex justify-between items-center py-2 border-b border-border/50 last:border-0"
                  >
                    <span className="text-sm text-muted-foreground">{day}</span>
                    <span className="text-sm font-medium">
                      {3 - idx} events
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Calendar Types */}
            <Card className="glass">
              <CardHeader>
                <CardTitle className="text-base">Calendar Types</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {[
                  { name: "Work", color: "bg-blue-500", count: 12 },
                  { name: "Personal", color: "bg-green-500", count: 8 },
                  { name: "Meetings", color: "bg-purple-500", count: 15 },
                ].map((cal, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2"
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${cal.color}`} />
                      <span className="text-sm">{cal.name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {cal.count} this week
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
