
"use client"

import {
    Label,
    PolarGrid,
    PolarRadiusAxis,
    RadialBar,
    RadialBarChart,
    ResponsiveContainer,
} from "recharts"
import { useTheme } from "next-themes"

export function ProductivityChart({ score = 50 }: { score?: number }) {
    const { theme } = useTheme()

    // Determine color based on score
    const getScoreColor = (score: number) => {
        if (score >= 80) return "var(--chart-3)" // Green for high
        if (score >= 50) return "var(--chart-1)" // Purple for medium
        return "var(--chart-2)" // Blue for low
    }

    const chartData = [
        { name: "score", value: score, fill: getScoreColor(score) },
    ]

    const shouldGlow = score >= 70

    return (
        <div className={`h-[200px] w-full flex items-center justify-center fade-in ${shouldGlow ? 'glow-primary' : ''}`}>
            <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart
                    innerRadius="70%"
                    outerRadius="100%"
                    barSize={12}
                    data={chartData}
                    startAngle={90}
                    endAngle={-270}
                >
                    <defs>
                        <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={getScoreColor(score)} stopOpacity={1} />
                            <stop offset="100%" stopColor={getScoreColor(score)} stopOpacity={0.6} />
                        </linearGradient>
                    </defs>
                    <PolarGrid gridType="circle" radialLines={false} stroke="none" className="first:fill-muted last:fill-background" />
                    <RadialBar
                        background
                        dataKey="value"
                        cornerRadius={30}
                        fill="url(#scoreGradient)"
                    />
                    <PolarRadiusAxis tick={false} tickLine={false} axisLine={false}>
                        <Label
                            content={({ viewBox }) => {
                                if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                                    return (
                                        <text
                                            x={viewBox.cx}
                                            y={viewBox.cy}
                                            textAnchor="middle"
                                            dominantBaseline="middle"
                                        >
                                            <tspan
                                                x={viewBox.cx}
                                                y={viewBox.cy}
                                                className="fill-foreground text-5xl font-bold"
                                            >
                                                {score}
                                            </tspan>
                                            <tspan
                                                x={viewBox.cx}
                                                y={(viewBox.cy || 0) + 28}
                                                className="fill-muted-foreground text-xs font-medium"
                                            >
                                                FOCUS SCORE
                                            </tspan>
                                        </text>
                                    )
                                }
                            }}
                        />
                    </PolarRadiusAxis>
                </RadialBarChart>
            </ResponsiveContainer>
        </div>
    )
}
