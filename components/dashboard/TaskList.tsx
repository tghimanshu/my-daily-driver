
"use client"

import { AlertCircle, CheckCircle2, Circle } from "lucide-react"

export function TaskList({ tasks }: { tasks: any[] }) {
    if (!tasks || tasks.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground py-12">
                <div className="text-center space-y-2">
                    <Circle className="h-12 w-12 mx-auto opacity-20" />
                    <p>No tasks for today. You're free! 🎉</p>
                </div>
            </div>
        )
    }

    const getPriorityColor = (priority: number) => {
        if (priority === 4) return "text-red-500 border-l-red-500" // Urgent
        if (priority === 3) return "text-orange-500 border-l-orange-500" // High
        if (priority === 2) return "text-blue-500 border-l-blue-500" // Medium
        return "text-muted-foreground border-l-border" // Low
    }

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-4">
                <span className="font-medium">Today's Tasks</span>
                <span className="px-2 py-1 bg-primary/10 text-primary rounded-full font-semibold">
                    {tasks.length}
                </span>
            </div>

            {tasks.slice(0, 6).map((task, index) => (
                <div
                    key={task.id}
                    className={`flex items-start gap-3 border-l-2 pl-3 pb-3 hover:bg-accent/50 -ml-4 pl-4 pr-2 py-2 rounded-r-lg transition-all duration-200 group fade-in ${getPriorityColor(task.priority || 1)}`}
                    style={{ animationDelay: `${index * 0.05}s` }}
                >
                    <button className="mt-1 hover:scale-110 transition-transform">
                        <Circle className="h-4 w-4" />
                    </button>
                    <div className="flex-1 space-y-1 min-w-0">
                        <p className="text-sm font-medium leading-tight group-hover:text-primary transition-colors">
                            {task.content}
                        </p>
                        {task.description && (
                            <p className="text-xs text-muted-foreground line-clamp-1">{task.description}</p>
                        )}
                    </div>
                    {task.due?.string && (
                        <div className="flex items-center gap-1 shrink-0">
                            {task.is_overdue && <AlertCircle className="h-3 w-3 text-red-500" />}
                            <span className={`text-xs whitespace-nowrap ${task.is_overdue ? 'text-red-500 font-semibold' : 'text-muted-foreground'}`}>
                                {task.due.string}
                            </span>
                        </div>
                    )}
                </div>
            ))}

            {tasks.length > 6 && (
                <div className="text-center pt-2">
                    <span className="text-xs text-muted-foreground">
                        +{tasks.length - 6} more tasks
                    </span>
                </div>
            )}
        </div>
    )
}
