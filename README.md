# Daily Driver - Professional Life Dashboard 🚀

A modern, beautiful, and professional dashboard to manage your daily life with amazing widgets, analytics, and productivity tracking.

![Dashboard](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

### 📊 **Multiple Professional Pages**

- **Dashboard** - Your personal command center with real-time widgets
- **Analytics** - Comprehensive charts and insights about your productivity
- **Habits** - Track and build consistent daily habits with streaks
- **Calendar** - Manage your schedule with beautiful calendar views
- **Settings** - Customize your experience and integrations
- **Profile** - View your achievements and personal statistics

### 🎨 **Amazing Widgets**

- **Live Clock** - Real-time clock with date display
- **Quick Actions** - Fast access to common tasks
- **Weather Widget** - Current weather conditions
- **Habit Tracker** - Track daily habit completion
- **Task List** - Manage your to-do items
- **Contribution Graph** - GitHub-style activity visualization
- **Productivity Chart** - Focus score tracking
- **Calendar Widget** - Upcoming events at a glance
- **Music Widget** - Currently playing track
- **Goal Progress** - Weekly goal tracking
- **Focus Sessions** - Time-boxed productivity sessions

### 🎯 **Professional Features**

- ✅ **Responsive Design** - Works perfectly on all devices
- 🌓 **Dark/Light Mode** - Beautiful themes for any preference
- 🎨 **Glassmorphism UI** - Modern, sleek design with backdrop blur
- ✨ **Smooth Animations** - Professional transitions and effects
- 📱 **Mobile-First** - Optimized mobile navigation with slide-out menu
- 🔄 **Real-time Updates** - Live data synchronization
- 🎪 **Gradient Accents** - Eye-catching color gradients
- 🌈 **Advanced Charts** - Beautiful data visualizations with Recharts

### 🔌 **Integrations**

- 📅 **Google Calendar** - Sync your events
- ✅ **Todoist** - Import tasks
- 🐙 **GitHub** - Track contributions
- 🎵 **Spotify** - Music widget
- 🌤️ **Weather API** - Real-time weather

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm
- PostgreSQL or SQLite database
- API keys for integrations (optional but recommended)

### Installation

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your API keys (see API_INTEGRATION.md)

# Initialize database
npx prisma migrate dev

# Run development server
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to see your dashboard!

### API Setup (Recommended)

For full functionality, set up your API integrations. See [API_INTEGRATION.md](./API_INTEGRATION.md) for detailed instructions.

**Quick start:**

1. Get your [Todoist token](https://todoist.com/app/settings/integrations) - for tasks
2. Get your [GitHub token](https://github.com/settings/tokens) - for contributions
3. Weather API works out of the box (no key needed!)
4. Optional: Set up Google Calendar OAuth for calendar sync

Check integration status at: [http://localhost:3000/api-status](http://localhost:3000/api-status)

## 🛠️ Tech Stack

- **Framework**: Next.js 16 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS with custom design system
- **Database**: Prisma ORM (PostgreSQL/SQLite)
- **Authentication**: NextAuth.js
- **Charts**: Recharts
- **UI Components**: Custom components with shadcn/ui patterns
- **Icons**: Lucide React
- **Date Handling**: date-fns

## 📱 Pages Overview

### Dashboard (`/`)

Your main hub with all essential widgets and quick actions. Includes weather, tasks, calendar, habits, and contribution graph.

### Analytics (`/analytics`)

Detailed insights with:

- Weekly productivity charts
- Habit completion rates
- 6-month progress overview
- Performance insights and trends

### Habits (`/habits`)

Manage your daily habits with:

- Category-based organization
- Streak tracking with fire icons
- Progress bars and completion rates
- Achievement celebrations

### Calendar (`/calendar`)

Beautiful calendar interface with:

- Week view at a glance
- Today's schedule with details
- Event categories and color coding
- Quick event creation

### Settings (`/settings`)

Customize everything:

- Theme selection (Light/Dark/System)
- Notification preferences
- Integration management
- Privacy and security settings
- Data export options

### Profile (`/profile`)

Your personal space:

- User information and avatar
- Achievement badges
- Recent activity feed
- Progress statistics

## 🎨 Design System

The app features a professional design system with:

- **Colors**: OKLCH color space for perceptually uniform colors
- **Typography**: Inter font family with proper hierarchy
- **Spacing**: Consistent 8px grid system
- **Animations**: Smooth, performant CSS animations
- **Components**: Reusable, accessible UI components

### Available Utility Classes

```css
/* Glassmorphism */
.glass - Semi-transparent card with backdrop blur

/* Gradients */
.gradient-primary, .gradient-secondary, .gradient-accent
.gradient-warm, .gradient-cool, .gradient-success

/* Animations */
.hover-lift - Smooth lift effect on hover
.fade-in - Fade in animation
.scale-in - Scale in animation
.animate-float - Floating animation

/* Effects */
.glow-primary - Primary color glow
.shadow-glow - Soft shadow glow;
```

## 🔐 Security

- Secure authentication with NextAuth.js
- Environment variables for API keys
- Data encryption at rest
- CSRF protection
- Secure session management

## 📈 Performance

- Server-side rendering for fast initial loads
- Optimized images and assets
- Code splitting and lazy loading
- Efficient data fetching with parallel requests
- Minimal bundle size

## 📦 Project Structure

```
my-daily-driver/
├── app/                      # Next.js app directory
│   ├── actions/             # Server actions
│   ├── analytics/           # Analytics page
│   ├── api/                 # API routes
│   ├── calendar/            # Calendar page
│   ├── habits/              # Habits page
│   ├── profile/             # Profile page
│   ├── settings/            # Settings page
│   ├── globals.css          # Global styles
│   ├── layout.tsx           # Root layout
│   └── page.tsx             # Dashboard page
├── components/              # React components
│   ├── dashboard/          # Dashboard widgets
│   ├── layout/             # Layout components
│   ├── ui/                 # UI primitives
│   └── widgets/            # Advanced widgets
├── lib/                    # Utility functions
│   └── api/               # API integrations
├── prisma/                # Database schema
└── public/                # Static assets
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

MIT License - feel free to use this project for personal or commercial purposes.

## 🙏 Acknowledgments

- Design inspiration from modern productivity apps
- Icons from Lucide React
- Charts from Recharts library
- UI patterns from shadcn/ui
- Community feedback and contributions

---

**Built with ❤️ for productivity enthusiasts**

Start building better habits and achieving your goals today! 🎯
