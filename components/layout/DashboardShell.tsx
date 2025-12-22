import { Sidebar } from "@/components/layout/Sidebar";

interface DashboardShellProps {
  children: React.ReactNode;
}

export function DashboardShell({ children }: DashboardShellProps) {
  return (
    <div className="flex h-screen overflow-hidden relative">
      {/* Animated background gradient */}
      <div className="absolute inset-0 animated-gradient opacity-30 dark:opacity-20 pointer-events-none" />

      <aside className="hidden border-r md:block relative z-10 glass">
        <Sidebar />
      </aside>
      <main className="flex-1 overflow-y-auto p-6 md:p-8 lg:p-10 relative z-10">
        <div className="max-w-450 mx-auto">{children}</div>
      </main>
    </div>
  );
}
