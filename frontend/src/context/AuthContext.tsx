// Copyright (c) 2026 Tim Olker
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// SPDX-License-Identifier: Apache-2.0

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { authService, type UserSession } from "../services/auth";

interface AuthContextValue {
  user: UserSession | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<UserSession>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<UserSession | null>(() =>
    authService.getStoredUser(),
  );
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    const token = authService.getStoredToken();
    const mockUserId = localStorage.getItem("vistarae_mock_user_id");

    if (token || mockUserId) {
      try {
        const u = await authService.fetchCurrentUser();
        setUser(u);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("vistarae_auth_sync"));
        }
      } catch {
        // If token expired, clear session
        authService.clearSession();
        setUser(null);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("vistarae_auth_sync"));
        }
      }
    } else {
      setUser(null);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email: string, pass: string): Promise<UserSession> => {
    const { user: loggedInUser } = await authService.login(email, pass);
    setUser(loggedInUser);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("vistarae_auth_sync"));
    }
    return loggedInUser;
  };

  const logout = async () => {
    await authService.logout();
    setUser(null);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("vistarae_auth_sync"));
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
