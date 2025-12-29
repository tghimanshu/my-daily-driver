"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BarChart2,
  Settings,
  LogOut,
  User,
  Target,
  Calendar as CalendarIcon,
  Menu,
  X,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Habits", href: "/habits", icon: Target },
  { name: "Calendar", href: "/calendar", icon: CalendarIcon },
  { name: "Analytics", href: "/analytics", icon: BarChart2 },
  { name: "API Status", href: "/api-status", icon: Zap },
  { name: "Settings", href: "/settings", icon: Settings },
  { name: "Profile", href: "/profile", icon: User },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const SidebarContent = () => (
    <>
      <div className="flex h-16 items-center border-b px-6 justify-between">
        <h1 className="text-xl font-bold tracking-tight bg-linear-to-r from-primary to-purple-400 bg-clip-text text-transparent">
          My Daily Driver
        </h1>
        <button className="md:hidden" onClick={() => setMobileMenuOpen(false)}>
          <X className="h-6 w-6" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-3">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all hover:scale-[1.02] hover-lift",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-lg"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-5 w-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="border-t p-4">
        <div className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-accent transition-colors cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-linear-to-br from-primary to-purple-400 flex items-center justify-center text-white text-xs font-bold">
            AJ
          </div>
          <div className="flex-1">
            <p className="line-clamp-1 font-medium">Alex Johnson</p>
            <p className="text-xs text-muted-foreground">View Profile</p>
          </div>
          <LogOut className="h-4 w-4 hover:text-destructive cursor-pointer" />
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile Menu Button */}
      <button
        className="fixed top-4 left-4 z-50 md:hidden p-2 rounded-lg glass hover-lift"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
      >
        <Menu className="h-6 w-6" />
      </button>

      {/* Desktop Sidebar */}
      <div className="hidden md:flex h-full w-64 flex-col border-r bg-card/80 backdrop-blur-xl text-card-foreground">
        <SidebarContent />
      </div>

      {/* Mobile Sidebar */}
      {mobileMenuOpen && (
        <>
          <div
            className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 md:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 w-64 flex-col border-r bg-card text-card-foreground z-50 md:hidden flex animate-slide-in">
            <SidebarContent />
          </div>
        </>
      )}
    </>
  );
}
