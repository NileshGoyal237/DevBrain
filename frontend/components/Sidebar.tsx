"use client";

// =============================================================================
// DevBrain AI — Sidebar Navigation
// Fetches /auth/me on mount to show avatar + username or Login button.
// Collapsible on mobile via toggle. Active link highlighted.
// =============================================================================

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Map,
  Code2,
  ScanEye,
  BookOpen,
  MessageSquareCode,
  BarChart3,
  Brain,
  Menu,
  X,
  LogOut,
  Github,
  ChevronRight,
} from "lucide-react";
import { getCurrentUser, getLoginUrl, clearToken, isAuthenticated } from "@/lib/api";
import type { User } from "@/lib/types";

// ---------------------------------------------------------------------------
// Nav items
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { href: "/dashboard",  label: "Dashboard",   icon: LayoutDashboard },
  { href: "/roadmap",    label: "Roadmap",      icon: Map             },
  { href: "/challenges", label: "Challenges",   icon: Code2           },
  { href: "/review",     label: "Code Review",  icon: ScanEye         },
  { href: "/resources",  label: "Resources",    icon: BookOpen        },
  { href: "/interview",  label: "Interview",    icon: MessageSquareCode },
  { href: "/progress",   label: "Progress",     icon: BarChart3       },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Sidebar() {
  const pathname = usePathname();
  const router   = useRouter();

  const [user, setUser]           = useState<User | null>(null);
  const [loading, setLoading]     = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Fetch current user once
  useEffect(() => {
    if (!isAuthenticated()) {
      setLoading(false);
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const handleLogin = useCallback(async () => {
    try {
      const { auth_url } = await getLoginUrl();
      window.location.href = auth_url;
    } catch {
      // fallback: navigate to GitHub OAuth directly if needed
    }
  }, []);

  const handleLogout = useCallback(() => {
    clearToken();
    setUser(null);
    router.push("/");
  }, [router]);

  // Hide sidebar on landing / auth pages
  const hideSidebar = pathname === "/" || pathname.startsWith("/auth");
  if (hideSidebar) return null;

  return (
    <>
      {/* ── Mobile toggle ── */}
      <button
        className="fixed top-4 left-4 z-50 p-2 rounded-lg bg-[#1a1d2e] border border-[#2d3148]
                   text-gray-400 hover:text-white transition-colors lg:hidden"
        onClick={() => setMobileOpen((o) => !o)}
        aria-label="Toggle menu"
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* ── Backdrop (mobile) ── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Sidebar panel ── */}
      <aside
        className={`
          fixed top-0 left-0 z-40 h-full w-64 flex flex-col
          bg-[#0f1117] border-r border-[#2d3148]
          transform transition-transform duration-300 ease-in-out
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
          lg:static lg:translate-x-0 lg:flex
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-5 border-b border-[#2d3148]">
          <div className="w-8 h-8 rounded-lg bg-[#6366f1] flex items-center justify-center glow-pulse">
            <Brain size={18} className="text-white" />
          </div>
          <div>
            <span className="font-bold text-white tracking-tight">DevBrain</span>
            <span className="text-[#6366f1] font-bold"> AI</span>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                  transition-all duration-150 group
                  ${
                    isActive
                      ? "bg-[#6366f1]/15 text-white border border-[#6366f1]/30"
                      : "text-gray-400 hover:text-white hover:bg-[#1a1d2e]"
                  }
                `}
              >
                <Icon
                  size={18}
                  className={isActive ? "text-[#6366f1]" : "text-gray-500 group-hover:text-gray-300"}
                />
                <span className="flex-1">{label}</span>
                {isActive && (
                  <ChevronRight size={14} className="text-[#6366f1]/60" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* User section */}
        <div className="border-t border-[#2d3148] px-3 py-3">
          {loading ? (
            <div className="h-10 rounded-lg bg-[#1a1d2e] animate-pulse" />
          ) : user ? (
            <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
              {user.avatar_url ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={user.avatar_url}
                  alt={user.username}
                  className="w-8 h-8 rounded-full ring-2 ring-[#6366f1]/40 shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-[#6366f1]/30 flex items-center justify-center shrink-0">
                  <span className="text-xs font-bold text-[#818cf8]">
                    {user.username[0]?.toUpperCase()}
                  </span>
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {user.name ?? user.username}
                </p>
                <p className="text-xs text-gray-500 truncate">@{user.username}</p>
              </div>
              <button
                onClick={handleLogout}
                title="Sign out"
                className="p-1.5 rounded-md text-gray-500 hover:text-red-400 hover:bg-red-400/10 transition-colors"
              >
                <LogOut size={15} />
              </button>
            </div>
          ) : (
            <button
              onClick={handleLogin}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg
                         bg-[#1a1d2e] border border-[#2d3148] hover:border-[#6366f1]/50
                         text-sm font-medium text-gray-300 hover:text-white transition-all duration-200"
            >
              <Github size={16} />
              Login with GitHub
            </button>
          )}
        </div>
      </aside>
    </>
  );
}