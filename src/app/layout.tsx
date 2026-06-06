import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StackTwin",
  description: "A weekly learning module for developers, generated from live technical signals."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
