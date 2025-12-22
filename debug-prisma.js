
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
    try {
        console.log('Checking Habit model...');
        console.log('Prisma keys:', Object.keys(prisma));
        // @ts-ignore
        const habits = await prisma.habit.findMany();
        console.log('Habits found:', habits.length);
    } catch (e) {
        console.error('Error accessing Habit model:', e);
        process.exit(1);
    } finally {
        await prisma.$disconnect();
    }
}

main();
