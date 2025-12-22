"use client"

import { useState, useTransition, useEffect } from "react"
import { Check, Flame } from "lucide-react"
import { toggleHabit } from "@/app/actions/habits"
import { useRouter } from "next/navigation"

export function HabitTracker({ habits }: { habits: any[] }) {
    const router = useRouter()
    const [isPending, startTransition] = useTransition()
    const [showConfetti, setShowConfetti] = useState(false)

    const completed = habits.filter(h => h.completed).length
    const total = habits.length
    const progress = total > 0 ? (completed / total) * 100 : 0

    useEffect(() => {
        if (completed === total && total > 0) {
            setShowConfetti(true)
            setTimeout(() => setShowConfetti(false), 3000)
        }
    }, [completed, total])

    const handleToggle = (id: string) => {
        startTransition(async () => {
            await toggleHabit(id)
            router.refresh()
        })
    }

    return (
        <div className="space-y-4 relative">
            {showConfetti && (
                <div className="absolute -inset-4 pointer-events-none">
                    <div className="text-4xl animate-bounce">🎉</div>
                </div>
            )}

            {/* Progress bar */}
            <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-medium">Progress</span>
                    <span className="font-mono">{completed}/{total}</span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                        className="h-full gradient-success transition-all duration-500 ease-out"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            {habits.map((habit) => (
                <div key={habit.id} className="flex items-center justify-between group fade-in">
                    <div className="flex items-center gap-3">
                        <span className={`text-sm font-medium transition-all ${habit.completed
                                ? 'text-muted-foreground line-through'
                                : 'group-hover:text-primary'
                            }`}>
                            {habit.name}
                        </span>
                        {habit.streak && habit.streak > 2 && (
                            <div className="flex items-center gap-1 text-xs text-orange-500 font-semibold">
                                <Flame className="h-3 w-3" />
                                <span>{habit.streak}</span>
                            </div>
                        )}
                    </div>
                    <button
                        disabled={isPending}
                        onClick={() => handleToggle(habit.id)}
                        className={`flex h-7 w-7 items-center justify-center rounded-full border-2 transition-all duration-300 hover-lift ${habit.completed
                                ? "gradient-success border-transparent text-white scale-in"
                                : "border-muted-foreground/30 hover:border-primary hover:bg-primary/10"
                            }`}
                    >
                        {habit.completed && <Check className="h-4 w-4 scale-in" />}
                    </button>
                </div>
            ))}

            {habits.length === 0 && (
                <div className="text-center text-sm text-muted-foreground py-8">
                    No habits yet. Add some to get started! 🚀
                </div>
            )}
        </div>
    )
}
