"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Home", icon: "H" },
  { href: "/activities", label: "Activities", icon: "A" },
  { href: "/stats", label: "Stats", icon: "S" },
  { href: "/training", label: "Training", icon: "T" },
  { href: "/coach", label: "Coach", icon: "C" },
  { href: "/settings", label: "Settings", icon: "\u2699" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop top bar */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur hidden md:block">
        <div className="mx-auto flex h-14 max-w-6xl items-center px-4">
          <Link href="/" className="mr-8 text-lg font-bold text-primary">
            TheCoach
          </Link>
          <nav className="flex gap-6">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "text-sm font-medium transition-colors hover:text-primary",
                  pathname === link.href ? "text-primary" : "text-muted-foreground"
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {/* Mobile bottom tab bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur md:hidden safe-bottom">
        <div className="flex justify-around items-center h-14 px-1">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 px-2 py-1 rounded-md text-xs transition-colors",
                pathname === link.href
                  ? "text-primary font-semibold"
                  : "text-muted-foreground"
              )}
            >
              <span className="text-lg leading-none">{link.icon}</span>
              <span className="text-[10px]">{link.label}</span>
            </Link>
          ))}
        </div>
      </nav>
    </>
  );
}
