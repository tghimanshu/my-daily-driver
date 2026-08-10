# Low Level Design - My Daily Driver Dashboard

This document outlines the low-level design of the My Daily Driver Dashboard project.

Flow of the application:
1. User opens the dashboard in a web browser or as a PWA.
    - Only one instance of the dashboard is allowed to run at a time
    - The dashboard can have only one User logged in at a time
    - We can use a singleton pattern to ensure that only one instance of the dashboard is running at any given time.
2. The dashboard loads the user's data from the backend server.
    - The backend server is responsible for fetching data from various integrations (e.g., GitHub, LeetCode, Google Calendar, Hacker News) and aggregating it into a single response.
3. The dashboard displays the user's data in a customizable layout.
4. The userSettings are stored in the backend server and can be updated
5. We can use a Factory pattern to create different types of widgets based on the user's preferences and the data received from the backend server.
6. The dashboard allows the user to customize the layout and appearance of the widgets.
7. All oauth logins are doing in widgets and the access tokens are stored in the backend server for future use.

Initial Widgets
- GitHub Widget: Displays the user's GitHub contributions and repositories.
- LeetCode Widget: Displays the user's coding progress and challenges.
- Google Calendar Widget: Displays the user's calendar events and schedule.
- Hacker News Widget: Displays the latest news in the tech world.
- Daily Task Widget: Displays the user's tasks and to-dos in one place.

Either individual widget can track the streaks or the daily task widget can
integrate with the other widgets to track the streaks. The daily task widget can also be used to track the streaks of the other widgets. Like leet code questions/github contributions.
