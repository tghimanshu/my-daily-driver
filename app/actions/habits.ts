
"use server"

import { auth } from "@/auth"
import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function fetchTodayHabits() {
    const session = await auth()
    if (!session?.user?.id) return []

    // For simplicity in this quick implementation, we just return a static list 
    // but check if they are "completed" in DB for today.
    // In a full app, you'd have a Habit definition table. 
    // Here, we'll just check if a Habit record exists with name+today+userId.

    const todayStart = new Date()
    todayStart.setHours(0, 0, 0, 0)

    // This is a simplified "Daily Log" approach using the Habit table itself as the log
    // A record exists = completed today? No, that's messy.
    // Let's stick to the schema: One Habit record per habit, updated 'lastCompletedAt'.

    const habits = await prisma.habit.findMany({
        where: { userId: session.user.id }
    })

    // If no habits exist, seed them
    if (habits.length === 0) {
        await prisma.habit.createMany({
            data: [
                { name: "Drink Water", userId: session.user.id },
                { name: "Read 10 pages", userId: session.user.id },
                { name: "Workout", userId: session.user.id },
                { name: "Meditate", userId: session.user.id },
            ]
        })
        return fetchTodayHabits()
    }

    return habits.map(h => ({
        ...h,
        completed: h.lastCompletedAt && h.lastCompletedAt >= todayStart
    }))
}

export async function toggleHabit(id: string) {
    const session = await auth()
    if (!session?.user?.id) return null

    const habit = await prisma.habit.findUnique({ where: { id } })
    if (!habit) return

    const todayStart = new Date()
    todayStart.setHours(0, 0, 0, 0)

    const isCompletedToday = habit.lastCompletedAt && habit.lastCompletedAt >= todayStart

    await prisma.habit.update({
        where: { id },
        data: {
            lastCompletedAt: isCompletedToday ? null : new Date() // Toggle off (null) or on (now)
        }
    })

    revalidatePath("/")
}
