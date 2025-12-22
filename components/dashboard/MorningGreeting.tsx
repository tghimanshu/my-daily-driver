
"use client"

import { useEffect, useState } from "react"

export function MorningGreeting() {
    const [greeting, setGreeting] = useState("Good morning")
    const [dateStr, setDateStr] = useState("")
    const [time, setTime] = useState("")
    const [emoji, setEmoji] = useState("👋")

    useEffect(() => {
        const updateTime = () => {
            const now = new Date()
            const hours = now.getHours()

            if (hours < 12) {
                setGreeting("Good morning")
                setEmoji("🌅")
            } else if (hours < 18) {
                setGreeting("Good afternoon")
                setEmoji("☀️")
            } else {
                setGreeting("Good evening")
                setEmoji("🌙")
            }

            setDateStr(now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }))
            setTime(now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }))
        }

        updateTime()
        const interval = setInterval(updateTime, 1000)
        return () => clearInterval(interval)
    }, [])

    return (
        <div className="fade-in">
            <div className="flex items-center gap-3 mb-2">
                <span className="text-4xl animate-wave inline-block">{emoji}</span>
                <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-gradient-accent">
                    {greeting}
                </h2>
            </div>
            <div className="flex items-center gap-3 text-muted-foreground">
                <p className="font-medium text-lg">{dateStr}</p>
                <span className="text-muted-foreground/50">•</span>
                <p className="font-mono text-lg tabular-nums">{time}</p>
            </div>
        </div>
    )
}
