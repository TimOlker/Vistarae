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
