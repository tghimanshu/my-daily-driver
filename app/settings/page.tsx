import { auth } from "@/auth";
import { DashboardShell } from "@/components/layout/DashboardShell";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Bell,
  Lock,
  Palette,
  Globe,
  Database,
  Zap,
  Moon,
  Sun,
  Monitor,
} from "lucide-react";

export default async function SettingsPage() {
  const session = await auth();

  const settingsSections = [
    {
      title: "Appearance",
      icon: Palette,
      description: "Customize how your dashboard looks",
      settings: [
        {
          name: "Theme",
          description: "Choose your preferred color scheme",
          type: "theme",
        },
        {
          name: "Accent Color",
          description: "Select your favorite accent color",
          type: "color",
        },
        {
          name: "Font Size",
          description: "Adjust text size for comfort",
          type: "slider",
        },
      ],
    },
    {
      title: "Notifications",
      icon: Bell,
      description: "Manage your notification preferences",
      settings: [
        {
          name: "Task Reminders",
          description: "Get notified about upcoming tasks",
          type: "toggle",
          enabled: true,
        },
        {
          name: "Habit Reminders",
          description: "Daily habit completion reminders",
          type: "toggle",
          enabled: true,
        },
        {
          name: "Calendar Alerts",
          description: "Event notifications before they start",
          type: "toggle",
          enabled: false,
        },
        {
          name: "Email Digest",
          description: "Weekly summary of your progress",
          type: "toggle",
          enabled: true,
        },
      ],
    },
    {
      title: "Integrations",
      icon: Zap,
      description: "Connect your favorite tools",
      settings: [
        {
          name: "Google Calendar",
          description: "Sync your events",
          type: "connected",
          connected: true,
        },
        {
          name: "Todoist",
          description: "Import your tasks",
          type: "connected",
          connected: true,
        },
        {
          name: "GitHub",
          description: "Track your contributions",
          type: "connected",
          connected: false,
        },
        {
          name: "Spotify",
          description: "Show what you're listening to",
          type: "connected",
          connected: false,
        },
      ],
    },
    {
      title: "Privacy & Security",
      icon: Lock,
      description: "Keep your data safe",
      settings: [
        {
          name: "Two-Factor Authentication",
          description: "Add an extra layer of security",
          type: "setup",
        },
        {
          name: "Data Export",
          description: "Download all your data",
          type: "button",
        },
        {
          name: "Delete Account",
          description: "Permanently delete your account",
          type: "danger",
        },
      ],
    },
    {
      title: "Data & Storage",
      icon: Database,
      description: "Manage your data preferences",
      settings: [
        {
          name: "Auto-save",
          description: "Automatically save your changes",
          type: "toggle",
          enabled: true,
        },
        {
          name: "Sync Across Devices",
          description: "Keep data in sync",
          type: "toggle",
          enabled: true,
        },
        {
          name: "Cache Duration",
          description: "How long to store local data",
          type: "select",
        },
      ],
    },
  ];

  return (
    <DashboardShell>
      <div className="flex flex-col gap-8 pb-8">
        {/* Header */}
        <div className="flex flex-col gap-2">
          <h1 className="text-4xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account preferences and integrations
          </p>
        </div>

        {/* Theme Quick Switch */}
        <Card className="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="h-5 w-5" />
              Quick Theme Switch
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {[
                { name: "Light", icon: Sun, value: "light" },
                { name: "Dark", icon: Moon, value: "dark" },
                { name: "System", icon: Monitor, value: "system" },
              ].map((theme) => {
                const Icon = theme.icon;
                return (
                  <button
                    key={theme.value}
                    className="flex flex-col items-center gap-2 p-6 rounded-lg glass hover-lift border-2 border-transparent hover:border-primary transition-all group"
                  >
                    <Icon className="h-8 w-8 text-muted-foreground group-hover:text-primary transition-colors" />
                    <span className="text-sm font-medium">{theme.name}</span>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Settings Sections */}
        {settingsSections.map((section, idx) => {
          const Icon = section.icon;
          return (
            <Card
              key={idx}
              className="glass fade-in"
              style={{ animationDelay: `${idx * 100}ms` }}
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Icon className="h-5 w-5" />
                  {section.title}
                </CardTitle>
                <CardDescription>{section.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {section.settings.map((setting, settingIdx) => (
                  <div
                    key={settingIdx}
                    className="flex items-center justify-between py-3 border-b border-border/50 last:border-0"
                  >
                    <div className="flex-1">
                      <h4 className="font-medium">{setting.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {setting.description}
                      </p>
                    </div>
                    <div className="ml-4">
                      {setting.type === "toggle" && (
                        <button
                          className={`relative w-12 h-6 rounded-full transition-colors ${
                            "enabled" in setting && setting.enabled
                              ? "bg-primary"
                              : "bg-muted"
                          }`}
                        >
                          <div
                            className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
                              "enabled" in setting && setting.enabled
                                ? "translate-x-6"
                                : ""
                            }`}
                          />
                        </button>
                      )}
                      {setting.type === "connected" && (
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-medium ${
                            "connected" in setting && setting.connected
                              ? "bg-green-500/10 text-green-500"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {"connected" in setting && setting.connected
                            ? "Connected"
                            : "Not Connected"}
                        </span>
                      )}
                      {setting.type === "button" && (
                        <button className="px-4 py-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors text-sm font-medium">
                          Export
                        </button>
                      )}
                      {setting.type === "danger" && (
                        <button className="px-4 py-2 rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors text-sm font-medium">
                          Delete
                        </button>
                      )}
                      {setting.type === "setup" && (
                        <button className="px-4 py-2 rounded-lg border border-border hover:bg-accent transition-colors text-sm font-medium">
                          Setup
                        </button>
                      )}
                      {(setting.type === "theme" ||
                        setting.type === "color" ||
                        setting.type === "slider" ||
                        setting.type === "select") && (
                        <button className="px-4 py-2 rounded-lg border border-border hover:bg-accent transition-colors text-sm font-medium">
                          Customize
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          );
        })}

        {/* About Section */}
        <Card className="glass border-primary/20">
          <CardHeader>
            <CardTitle>About Daily Driver</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div className="flex justify-between">
              <span>Version</span>
              <span className="font-medium text-foreground">1.0.0</span>
            </div>
            <div className="flex justify-between">
              <span>Last Updated</span>
              <span className="font-medium text-foreground">
                December 20, 2025
              </span>
            </div>
            <div className="flex justify-between">
              <span>License</span>
              <span className="font-medium text-foreground">MIT</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
