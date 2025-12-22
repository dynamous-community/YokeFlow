'use client';

import { ThemeProvider } from '@/contexts/ThemeContext';
import { AuthProvider, useAuth } from '@/lib/auth-context';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Toaster } from 'sonner';
import { usePathname } from 'next/navigation';

function Header() {
  const { isAuthenticated, isDevMode, logout } = useAuth();
  const pathname = usePathname();

  // Don't show header on login page
  if (pathname === '/login') {
    return null;
  }

  return (
    <header className="border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/50 backdrop-blur sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-8 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">
            Autonomous Coding Agent
          </h1>
          <div className="flex items-center gap-6">
            <nav className="flex items-center gap-6 text-sm font-medium">
              <a href="/" className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
                Projects
              </a>
              <a href="/create" className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
                Create
              </a>
              <a href="/prompt-improvements" className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
                Prompt Improvements
              </a>
            </nav>
            <ThemeToggle />
            {isAuthenticated && !isDevMode && (
              <button
                onClick={logout}
                className="text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
              >
                Logout
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

export function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProtectedRoute>
          <Toaster position="top-right" richColors theme="dark" />
          <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1 max-w-7xl w-full mx-auto px-8 py-8">
              {children}
            </main>
            <footer className="border-t border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/50 backdrop-blur">
              <div className="max-w-7xl mx-auto px-8 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                Autonomous Coding Agent Platform
              </div>
            </footer>
          </div>
        </ProtectedRoute>
      </AuthProvider>
    </ThemeProvider>
  );
}
