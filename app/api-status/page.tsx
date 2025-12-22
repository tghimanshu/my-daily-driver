import { DashboardShell } from "@/components/layout/DashboardShell";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Activity,
  Key,
} from "lucide-react";
import { checkAPIHealth } from "@/lib/api";

export default async function APIStatusPage() {
  const apiStatus = await checkAPIHealth();

  const apis = [
    {
      name: "Todoist",
      description: "Task management integration",
      status: apiStatus.todoist,
      icon: "✅",
      docs: "https://developer.todoist.com/rest/v2/",
    },
    {
      name: "GitHub",
      description: "Contribution tracking and activity",
      status: apiStatus.github,
      icon: "🐙",
      docs: "https://docs.github.com/en/rest",
    },
    {
      name: "Weather API",
      description: "Open-Meteo weather data",
      status: apiStatus.weather,
      icon: "🌤️",
      docs: "https://open-meteo.com/en/docs",
    },
    {
      name: "Google Calendar",
      description: "Calendar events synchronization",
      status: apiStatus.googleCalendar,
      icon: "📅",
      docs: "https://developers.google.com/calendar/api",
    },
    {
      name: "Spotify",
      description: "Music playback tracking",
      status: apiStatus.spotify,
      icon: "🎵",
      docs: "https://developer.spotify.com/documentation/web-api",
    },
  ];

  const connectedCount = Object.values(apiStatus).filter(Boolean).length;
  const totalCount = Object.values(apiStatus).length;

  return (
    <DashboardShell>
      <div className="flex flex-col gap-8 pb-8">
        {/* Header */}
        <div className="flex flex-col gap-2">
          <h1 className="text-4xl font-bold tracking-tight">
            API Integrations
          </h1>
          <p className="text-muted-foreground">
            Manage and monitor your external service connections
          </p>
        </div>

        {/* Status Overview */}
        <Card className="glass gradient-primary border-0">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Integration Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-6 text-white">
              <div className="text-center">
                <div className="text-4xl font-bold">
                  {connectedCount}/{totalCount}
                </div>
                <div className="text-sm text-white/80 mt-1">Connected</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-bold">{connectedCount}</div>
                <div className="text-sm text-white/80 mt-1">Active</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-bold">
                  {totalCount - connectedCount}
                </div>
                <div className="text-sm text-white/80 mt-1">Pending</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* API Cards */}
        <div className="grid gap-4 md:grid-cols-2">
          {apis.map((api, idx) => {
            const StatusIcon = api.status ? CheckCircle2 : XCircle;
            const statusColor = api.status ? "text-green-500" : "text-red-500";
            const statusBg = api.status ? "bg-green-500/10" : "bg-red-500/10";

            return (
              <Card
                key={idx}
                className="glass hover-lift fade-in"
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="text-3xl">{api.icon}</div>
                      <div>
                        <CardTitle className="text-lg">{api.name}</CardTitle>
                        <CardDescription>{api.description}</CardDescription>
                      </div>
                    </div>
                    <div className={`p-2 rounded-lg ${statusBg}`}>
                      <StatusIcon className={`h-5 w-5 ${statusColor}`} />
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Status</span>
                    <span className={`font-medium ${statusColor}`}>
                      {api.status ? "Connected" : "Not Connected"}
                    </span>
                  </div>

                  {!api.status && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/50">
                      <AlertCircle className="h-4 w-4 text-orange-500 mt-0.5" />
                      <div className="text-xs text-muted-foreground">
                        {api.name === "Google Calendar" ||
                        api.name === "Spotify"
                          ? "Requires OAuth authentication. Sign in to connect."
                          : "API key not configured. Add to environment variables."}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <a
                      href={api.docs}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 px-3 py-2 rounded-lg border border-border hover:bg-accent transition-colors text-xs font-medium text-center"
                    >
                      View Docs
                    </a>
                    {!api.status && (
                      <button className="flex-1 px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity text-xs font-medium">
                        Configure
                      </button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Environment Setup Guide */}
        <Card className="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Environment Setup
            </CardTitle>
            <CardDescription>
              Configure your API keys and tokens to enable integrations
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-lg bg-muted/50 font-mono text-sm space-y-2">
              <div className="text-muted-foreground"># Add to .env.local</div>
              <div>TODOIST_TOKEN=your_todoist_token_here</div>
              <div>GITHUB_TOKEN=your_github_token_here</div>
              <div>AUTH_GOOGLE_ID=your_google_client_id</div>
              <div>AUTH_GOOGLE_SECRET=your_google_client_secret</div>
            </div>

            <div className="space-y-2 text-sm">
              <h4 className="font-semibold">How to get API tokens:</h4>
              <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                <li>
                  <strong>Todoist:</strong> Settings → Integrations → API token
                </li>
                <li>
                  <strong>GitHub:</strong> Settings → Developer settings →
                  Personal access tokens
                </li>
                <li>
                  <strong>Google:</strong> Google Cloud Console → Create OAuth
                  2.0 credentials
                </li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}
