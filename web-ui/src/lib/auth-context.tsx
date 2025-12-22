'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  isDevMode: boolean;
  token: string | null;
  login: (password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isDevMode, setIsDevMode] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  // Check for existing token on mount or detect dev mode
  useEffect(() => {
    checkAuthStatus();
  }, []);

  async function checkAuthStatus() {
    const storedToken = localStorage.getItem('auth_token');

    if (storedToken) {
      // Verify token is still valid
      await verifyToken(storedToken);
    } else {
      // Check if backend is in dev mode (no UI_PASSWORD set)
      await checkDevMode();
    }
  }

  async function checkDevMode() {
    try {
      // Try to access a protected endpoint without auth
      const response = await axios.get(`${API_URL}/api/info`);

      if (response.status === 200) {
        // Backend is in dev mode! No auth required
        console.log('🔓 Development mode detected - authentication disabled');
        setIsAuthenticated(true);
        setIsDevMode(true);
        setToken('dev-mode');
      }
    } catch (error) {
      // Auth is required (production mode)
      console.log('🔒 Production mode - authentication required');
    } finally {
      setIsLoading(false);
    }
  }

  async function verifyToken(tokenToVerify: string) {
    try {
      const response = await axios.get(`${API_URL}/api/auth/verify`, {
        headers: {
          Authorization: `Bearer ${tokenToVerify}`
        }
      });

      if (response.status === 200) {
        setToken(tokenToVerify);
        setIsAuthenticated(true);
      } else {
        // Token invalid, clear it
        localStorage.removeItem('auth_token');
        setToken(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      // Token verification failed, clear it
      localStorage.removeItem('auth_token');
      setToken(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }

  async function login(password: string) {
    try {
      const response = await axios.post(`${API_URL}/api/auth/login`, {
        password
      });

      const { access_token } = response.data;

      // Store token
      localStorage.setItem('auth_token', access_token);
      setToken(access_token);
      setIsAuthenticated(true);
    } catch (error) {
      // Re-throw error for component to handle
      throw error;
    }
  }

  function logout() {
    localStorage.removeItem('auth_token');
    setToken(null);
    setIsAuthenticated(false);

    // Redirect to login page
    window.location.href = '/login';
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, isDevMode, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
