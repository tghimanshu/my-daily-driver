
import { CalendarDays, Clock, MapPin } from "lucide-react"

export function CalendarWidget({ events }: { events: any[] }) {
    if (!events || events.length === 0) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground py-12">
                <CalendarDays className="h-16 w-16 opacity-20" />
                <div className="text-center">
                    <p className="text-sm font-medium">No upcoming events</p>
                    <p className="text-xs mt-1">Your calendar is clear 📅</p>
                </div>
            </div>
        )
    }

    const getEventColor = (index: number) => {
        const colors = [
            "border-l-purple-500 bg-purple-500/5",
            "border-l-blue-500 bg-blue-500/5",
            "border-l-cyan-500 bg-cyan-500/5",
            "border-l-green-500 bg-green-500/5",
            "border-l-pink-500 bg-pink-500/5",
        ]
        return colors[index % colors.length]
    }

    return (
        <div className="space-y-3">
            {events.slice(0, 5).map((event, index) => {
                const start = new Date(event.start.dateTime || event.start.date)
                const timeStr = start.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
                const isAllDay = !event.start.dateTime
                const isToday = start.toDateString() === new Date().toDateString()

                return (
                    <div
                        key={event.id}
                        className={`flex gap-3 p-3 rounded-lg border-l-4 hover:scale-[1.02] transition-all duration-200 group fade-in ${getEventColor(index)}`}
                        style={{ animationDelay: `${index * 0.05}s` }}
                    >
                        <div className="flex flex-col items-center justify-center rounded-lg bg-background/80 backdrop-blur-sm px-3 py-2 text-xs font-semibold min-w-[60px] text-center shadow-sm">
                            <span className="uppercase text-[10px] text-muted-foreground font-medium">
                                {start.toLocaleString('default', { month: 'short' })}
                            </span>
                            <span className="text-2xl font-bold leading-none mt-1">
                                {start.getDate()}
                            </span>
                            {isToday && (
                                <span className="text-[10px] text-primary font-semibold mt-1">TODAY</span>
                            )}
                        </div>
                        <div className="flex-1 py-0.5 min-w-0">
                            <p className="text-sm font-semibold leading-tight mb-2 group-hover:text-primary transition-colors truncate">
                                {event.summary}
                            </p>
                            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                                <div className="flex items-center gap-1.5">
                                    <Clock className="h-3.5 w-3.5 shrink-0" />
                                    <span className="font-medium">{isAllDay ? "All Day" : timeStr}</span>
                                </div>
                                {event.location && (
                                    <div className="flex items-center gap-1.5 truncate">
                                        <MapPin className="h-3.5 w-3.5 shrink-0" />
                                        <span className="truncate">{event.location}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )
            })}
        </div>
    )
}
