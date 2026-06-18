import type { Metadata } from "next";
import { ThemeToggle } from "../components/ThemeToggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "StackTwin",
  description: "A weekly learning module for developers, generated from live technical signals."
};

const themeScript = `(function(){var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)})()`;

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <div style={{ position: "fixed", top: 16, right: 16, zIndex: 100 }}>
          <ThemeToggle />
        </div>
        {children}
      </body>
    </html>
  );
}
