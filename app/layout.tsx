import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { Suspense } from 'react'
import { Providers } from '@/components/providers'
import { AppShell } from '@/components/app-shell'
import { PageSkeleton } from '@/components/page-skeleton'
import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' })

export const metadata: Metadata = {
  title: { default: 'DemandLens — Sales Demand Forecasting', template: '%s | DemandLens' },
  description: 'A transparent sales demand forecasting workspace for retail stores. Explore demand, plan restocks, and compare model performance.',
  generator: 'v0.app',
  icons: { icon: '/icon.svg' },
}

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#fafafa' },
    { media: '(prefers-color-scheme: dark)', color: '#0b0f14' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.variable}>
        <Providers>
          <Suspense fallback={<PageSkeleton />}>
            <AppShell>{children}</AppShell>
          </Suspense>
        </Providers>
      </body>
    </html>
  )
}
