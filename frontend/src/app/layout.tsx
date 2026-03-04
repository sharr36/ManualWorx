import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";

const title = "ManualWorx — AI-Powered Manual Intelligence";
const description =
  "Turn equipment manuals into expert knowledge. AI-powered manual intelligence for heavy equipment mechanics.";

export const metadata: Metadata = {
  metadataBase: new URL("https://manualworx.com"),
  title,
  description,
  openGraph: {
    title,
    description,
    type: "website",
    siteName: "ManualWorx",
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
  },
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#059669" />
      </head>
      <body className="antialiased">
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
