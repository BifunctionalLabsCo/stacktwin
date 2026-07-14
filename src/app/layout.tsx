import type { Metadata } from "next";
import { AppNav } from "../components/AppNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "StackTwin",
  description: "A weekly learning module for developers, generated from live technical signals."
};

const themeScript = `(function(){try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(_){}})()`;

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <AppNav />
        {children}
      </body>
    </html>
  );
}
