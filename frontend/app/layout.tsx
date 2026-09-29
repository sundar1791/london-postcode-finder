import type { Metadata } from "next";
import { Hanken_Grotesk, Newsreader } from "next/font/google";
import SiteHeader from "@/components/SiteHeader";
import "./globals.css";

const hanken = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"] });
const newsreader = Newsreader({ variable: "--font-newsreader", subsets: ["latin"], style: ["normal", "italic"] });

export const metadata: Metadata = {
  title: "London Postcode Finder",
  description:
    "Spend 100 tokens on what matters to you. A team of AI agents scores 40 London postcode districts, researches the best five and explains where you'd fit.",
};

const themeScript = `try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-GB" className={`${hanken.variable} ${newsreader.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col">
        <SiteHeader />
        <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 pb-24">{children}</main>
        <footer className="border-t border-rule">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 text-sm text-ink-faint flex flex-wrap gap-x-6 gap-y-2 justify-between">
            <span>Data: data.police.uk, OpenStreetMap contributors, TfL, ONS private rents, postcodes.io.</span>
            <span>A portfolio project by Sundar Subramanian.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
