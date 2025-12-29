// Time Blocking Assistant - Suggests optimal time slots for tasks

export interface TimeSlot {
    start: Date;
    end: Date;
    durationMinutes: number;
    type: "free" | "busy" | "buffer";
}

export interface TimeBlockSuggestion {
    task: any;
    suggestedSlot: TimeSlot;
    reasoning: string[];
    energyMatch: number; // 0-10, how well this matches expected energy levels
}

/**
 * Find all free time slots in the calendar
 */
export function findFreeSlots(
    events: any[],
    startDate: Date = new Date(),
    endDate?: Date
): TimeSlot[] {
    const slots: TimeSlot[] = [];

    // Default to today, 8 AM - 10 PM
    const dayStart = new Date(startDate);
    dayStart.setHours(8, 0, 0, 0);

    const dayEnd = endDate || new Date(startDate);
    dayEnd.setHours(22, 0, 0, 0);

    // Sort events by start time
    const sortedEvents = events
        .filter((e) => e.start?.dateTime || e.start?.date)
        .sort((a, b) => {
            const aStart = new Date(a.start.dateTime || a.start.date);
            const bStart = new Date(b.start.dateTime || b.start.date);
            return aStart.getTime() - bStart.getTime();
        });

    let currentTime = dayStart;

    sortedEvents.forEach((event) => {
        const eventStart = new Date(event.start.dateTime || event.start.date);
        const eventEnd = new Date(event.end?.dateTime || event.end?.date || eventStart);

        // Skip events outside our range
        if (eventEnd < dayStart || eventStart > dayEnd) return;

        // If there's a gap before this event, that's a free slot
        if (eventStart > currentTime) {
            const durationMinutes = Math.floor(
                (eventStart.getTime() - currentTime.getTime()) / (1000 * 60)
            );

            // Only consider slots of 15+ minutes
            if (durationMinutes >= 15) {
                slots.push({
                    start: new Date(currentTime),
                    end: new Date(eventStart),
                    durationMinutes,
                    type: "free",
                });
            }
        }

        // Move current time to end of this event
        currentTime = new Date(Math.max(currentTime.getTime(), eventEnd.getTime()));
    });

    // Add final slot if there's time left in the day
    if (currentTime < dayEnd) {
        const durationMinutes = Math.floor(
            (dayEnd.getTime() - currentTime.getTime()) / (1000 * 60)
        );

        if (durationMinutes >= 15) {
            slots.push({
                start: new Date(currentTime),
                end: new Date(dayEnd),
                durationMinutes,
                type: "free",
            });
        }
    }

    return slots;
}

/**
 * Estimate task duration based on title and metadata
 */
export function estimateTaskDuration(task: any): number {
    // If task has explicit duration, use it
    if (task.duration) return task.duration;

    const title = (task.content || task.title || "").toLowerCase();

    // Quick tasks (< 30 min)
    const quickKeywords = [
        "email",
        "call",
        "reply",
        "check",
        "review",
        "quick",
        "send",
        "update",
    ];
    if (quickKeywords.some((kw) => title.includes(kw))) {
        return 20;
    }

    // Medium tasks (30-60 min)
    const mediumKeywords = [
        "write",
        "draft",
        "plan",
        "meeting",
        "discuss",
        "prepare",
    ];
    if (mediumKeywords.some((kw) => title.includes(kw))) {
        return 45;
    }

    // Long tasks (1-2 hours)
    const longKeywords = [
        "build",
        "develop",
        "create",
        "design",
        "implement",
        "project",
        "research",
    ];
    if (longKeywords.some((kw) => title.includes(kw))) {
        return 90;
    }

    // Default: 30 minutes
    return 30;
}

/**
 * Calculate energy level for a given time slot
 */
export function calculateSlotEnergy(
    slot: TimeSlot,
    energyPatterns?: any[]
): number {
    const hour = slot.start.getHours();
    const dayOfWeek = slot.start.getDay();

    // If we have historical energy patterns, use them
    if (energyPatterns && energyPatterns.length > 0) {
        const pattern = energyPatterns.find(
            (p) => p.hourOfDay === hour && p.dayOfWeek === dayOfWeek
        );
        if (pattern) {
            return pattern.energyScore / 10; // Convert 0-100 to 0-10
        }
    }

    // Default energy curve (typical person)
    // Morning peak: 9-11 AM
    if (hour >= 9 && hour < 11) return 9;
    // Mid-morning: 8-9 AM, 11-12 PM
    if ((hour >= 8 && hour < 9) || (hour >= 11 && hour < 12)) return 7;
    // After lunch dip: 1-3 PM
    if (hour >= 13 && hour < 15) return 5;
    // Afternoon recovery: 3-5 PM
    if (hour >= 15 && hour < 17) return 6;
    // Evening: 6-8 PM
    if (hour >= 18 && hour < 20) return 5;
    // Night: after 8 PM
    if (hour >= 20) return 4;
    // Early morning: before 8 AM
    return 6;
}

/**
 * Determine task energy requirement
 */
export function getTaskEnergyRequirement(task: any): number {
    const title = (task.content || task.title || "").toLowerCase();

    // High energy tasks (7-10)
    const highEnergyKeywords = [
        "build",
        "create",
        "develop",
        "implement",
        "design",
        "write",
        "code",
        "analyze",
    ];
    if (highEnergyKeywords.some((kw) => title.includes(kw))) {
        return 8;
    }

    // Medium energy (4-6)
    const mediumEnergyKeywords = [
        "review",
        "plan",
        "organize",
        "prepare",
        "research",
        "meeting",
    ];
    if (mediumEnergyKeywords.some((kw) => title.includes(kw))) {
        return 5;
    }

    // Low energy (1-3)
    const lowEnergyKeywords = [
        "email",
        "check",
        "update",
        "send",
        "reply",
        "file",
        "archive",
    ];
    if (lowEnergyKeywords.some((kw) => title.includes(kw))) {
        return 2;
    }

    // Check task priority/metadata
    if (task.energyLevel) {
        if (task.energyLevel === "high") return 8;
        if (task.energyLevel === "medium") return 5;
        if (task.energyLevel === "low") return 2;
    }

    return 5; // Default: medium energy
}

/**
 * Suggest time blocks for tasks
 */
export function suggestTimeBlocks(
    tasks: any[],
    events: any[],
    energyPatterns?: any[]
): TimeBlockSuggestion[] {
    const suggestions: TimeBlockSuggestion[] = [];
    const freeSlots = findFreeSlots(events);

    // Sort tasks by priority (if available)
    const sortedTasks = [...tasks].sort((a, b) => {
        const aPriority = a.priority || 5;
        const bPriority = b.priority || 5;
        return aPriority - bPriority; // Lower number = higher priority in Todoist
    });

    sortedTasks.forEach((task) => {
        const taskDuration = estimateTaskDuration(task);
        const taskEnergyNeeded = getTaskEnergyRequirement(task);

        // Find the best matching slot
        let bestSlot: TimeSlot | null = null;
        let bestMatch = 0;

        freeSlots.forEach((slot) => {
            // Skip if slot is too short
            if (slot.durationMinutes < taskDuration) return;

            const slotEnergy = calculateSlotEnergy(slot, energyPatterns);

            // Calculate match score
            const energyMatch = 10 - Math.abs(slotEnergy - taskEnergyNeeded);
            const durationMatch = Math.min(10, (slot.durationMinutes / taskDuration) * 5);
            const timeProximity = 10 - Math.min(10, (slot.start.getTime() - new Date().getTime()) / (1000 * 60 * 60));

            const totalMatch = energyMatch * 0.5 + durationMatch * 0.3 + timeProximity * 0.2;

            if (totalMatch > bestMatch) {
                bestMatch = totalMatch;
                bestSlot = slot;
            }
        });

        if (bestSlot) {
            const reasoning: string[] = [];
            const slotEnergy = calculateSlotEnergy(bestSlot, energyPatterns);
            const energyMatchScore = 10 - Math.abs(slotEnergy - taskEnergyNeeded);

            // Add reasoning
            const slotTime = bestSlot.start.toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
            });
            reasoning.push(`Available ${bestSlot.durationMinutes}min slot at ${slotTime}`);

            if (energyMatchScore >= 8) {
                reasoning.push("Perfect energy match for this task type");
            } else if (energyMatchScore >= 6) {
                reasoning.push("Good energy level for this task");
            }

            if (slotEnergy >= 8 && taskEnergyNeeded >= 7) {
                reasoning.push("Peak productivity time - great for deep work");
            }

            if (bestSlot.durationMinutes > taskDuration * 1.5) {
                reasoning.push("Extra buffer time available if needed");
            }

            suggestions.push({
                task,
                suggestedSlot: {
                    ...bestSlot,
                    end: new Date(bestSlot.start.getTime() + taskDuration * 60 * 1000),
                },
                reasoning,
                energyMatch: energyMatchScore,
            });

            // Remove or split the used slot
            const slotIndex = freeSlots.indexOf(bestSlot);
            if (slotIndex >= 0) {
                freeSlots.splice(slotIndex, 1);

                // If there's remaining time in the slot, add it back
                const remainingStart = new Date(
                    bestSlot.start.getTime() + taskDuration * 60 * 1000 + 5 * 60 * 1000
                ); // 5 min buffer
                if (remainingStart < bestSlot.end) {
                    freeSlots.push({
                        start: remainingStart,
                        end: bestSlot.end,
                        durationMinutes: Math.floor(
                            (bestSlot.end.getTime() - remainingStart.getTime()) / (1000 * 60)
                        ),
                        type: "free",
                    });
                }
            }
        }
    });

    return suggestions;
}

/**
 * Generate a human-readable daily schedule
 */
export function generateDailySchedule(
    suggestions: TimeBlockSuggestion[]
): string {
    let schedule = "Suggested Schedule:\n\n";

    suggestions.forEach((suggestion, index) => {
        const startTime = suggestion.suggestedSlot.start.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        });
        const endTime = suggestion.suggestedSlot.end.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        });
        const taskTitle = suggestion.task.content || suggestion.task.title;

        schedule += `${startTime} - ${endTime}: ${taskTitle}\n`;
        schedule += `  💡 ${suggestion.reasoning.join(", ")}\n\n`;
    });

    return schedule;
}
