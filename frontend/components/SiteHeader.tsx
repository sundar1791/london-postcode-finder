"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Search" },
  { href: "/learning", label: "What it has learned" },
  { href: "/how-it-works", label: "How it works" },
];

export default function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="border-b border-rule">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center gap-x-8 gap-y-3">
        <Link href="/" className="flex items-center gap-2.5 mr-auto">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
            <line x1="1" y1="13" x2="25" y2="13" stroke="var(--accent)" strokeWidth="4" strokeLinecap="round" />
            <circle cx="13" cy="13" r="6" fill="var(--paper)" stroke="var(--ink)" strokeWidth="2.5" />
          </svg>
          <span className="font-serif text-xl tracking-tight">London Postcode Finder</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm -mx-2 overflow-x-auto">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`px-2 py-1 whitespace-nowrap rounded ${active ? "text-ink font-semibold" : "text-ink-soft hover:text-ink"}`}
              >
                {item.label}
              </Link>
            );
          })}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
