
"use client"

import { Cloud, CloudRain, CloudSun, Droplets, Sun, Wind } from "lucide-react"

export function WeatherWidget({ data }: { data?: any }) {
    if (!data) return (
        <div className="flex flex-col h-full justify-between animate-pulse">
            <div className="h-12 w-24 bg-muted rounded" />
            <div className="h-4 w-16 bg-muted rounded" />
        </div>
    )

    const getWeatherGradient = (code: number) => {
        if (code === 0) return "gradient-warm" // Clear
        if (code <= 3) return "gradient-cool" // Partly cloudy
        return "gradient-secondary" // Rainy/cloudy
    }

    const getWeatherIcon = (code: number) => {
        if (code === 0) return <Sun className="h-12 w-12 text-amber-400 animate-pulse" />
        if (code <= 2) return <CloudSun className="h-12 w-12 text-yellow-400" />
        if (code === 3) return <Cloud className="h-12 w-12 text-gray-400" />
        return <CloudRain className="h-12 w-12 text-blue-400" />
    }

    return (
        <div className="flex flex-col justify-between h-full fade-in">
            <div className="flex items-start justify-between">
                <div>
                    <div className="text-5xl font-bold shimmer mb-1">{data.temp}°</div>
                    <div className="text-sm text-muted-foreground capitalize">{data.desc}</div>
                </div>
                <div className="scale-in">
                    {getWeatherIcon(data.code)}
                </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                <div className="flex items-center gap-2 glass px-3 py-2 rounded-lg">
                    <Droplets className="h-4 w-4 text-blue-400" />
                    <span className="font-medium">12%</span>
                </div>
                <div className="flex items-center gap-2 glass px-3 py-2 rounded-lg">
                    <Wind className="h-4 w-4 text-cyan-400" />
                    <span className="font-medium">8mph</span>
                </div>
            </div>
        </div>
    )
}
