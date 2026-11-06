import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CopyCat",
  description: "CopyCat (MIR MEDIA LABS): swap the people or things in any video, on your own GPU. Based on Openjutsu by D3voz (MIT).",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
