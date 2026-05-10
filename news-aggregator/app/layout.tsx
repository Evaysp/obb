import type { Metadata } from 'next';
import { JetBrains_Mono, Newsreader } from 'next/font/google';
import { ThemeProvider } from '@/components/ThemeProvider';
import { ViewProvider } from '@/components/ViewProvider';
import { TranslationProvider } from '@/components/TranslationProvider';
import { StatusBar } from '@/components/StatusBar';
import { TopNav } from '@/components/TopNav';
import { FootBar } from '@/components/FootBar';
import './globals.css';

const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500', '600', '700'],
  display: 'swap',
});

const serif = Newsreader({
  subsets: ['latin'],
  variable: '--font-serif',
  axes: ['opsz'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Observer · Brief',
  description: 'A unified read across English, Japanese and Chinese press.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${mono.variable} ${serif.variable}`}
    >
      <body>
        <ThemeProvider>
          <ViewProvider>
            <TranslationProvider>
              <StatusBar />
              <TopNav />
              <main className="pb-12">{children}</main>
              <FootBar />
            </TranslationProvider>
          </ViewProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
