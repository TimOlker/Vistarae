// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";

interface AdminRouteProps {
  children: React.ReactNode;
  onUnauthorizedRedirect: () => void;
}

export const AdminRoute: React.FC<AdminRouteProps> = ({
  children,
  onUnauthorizedRedirect,
}) => {
  const { user, isLoading } = useAuth();
  const { showToast } = useToast();

  useEffect(() => {
    if (!isLoading && (!user || !user.is_admin)) {
      showToast({
        type: "https://vistarae.com/errors/forbidden",
        title: "Forbidden",
        status: 403,
        detail: "Administrator privileges are required to access this console.",
      });
      onUnauthorizedRedirect();
    }
  }, [user, isLoading, showToast, onUnauthorizedRedirect]);

  if (isLoading) {
    return (
      <div
        style={{
          padding: "40px",
          textAlign: "center",
          color: "var(--text-muted)",
        }}
      >
        Verifying administrative authorization...
      </div>
    );
  }

  if (!user || !user.is_admin) {
    return null;
  }

  return <>{children}</>;
};
