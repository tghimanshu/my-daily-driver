
export function calculateScore(tasks: any[], events: any[], ghEvents: any[]) {
    let score = 50; // Base score for showing up

    // Add points for tasks
    if (tasks) score += tasks.length * 10

    // Add points for upcoming meetings (preparedness)
    if (events) score += events.length * 5

    // Add points for code
    if (ghEvents) score += ghEvents.length * 5

    return Math.min(score, 100)
}
