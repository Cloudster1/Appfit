import { Alert, Center, Loader } from "@mantine/core";
import { IconLock } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import type { Role } from "../api/hooks";
import { useAuth } from "./AuthProvider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    );
  }
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

export function RequireRole({ min, children }: { min: Role; children: ReactNode }) {
  const { hasRole } = useAuth();
  if (!hasRole(min)) {
    return (
      <Alert color="red" icon={<IconLock />} title="Not allowed">
        This page requires the {min} role.
      </Alert>
    );
  }
  return <>{children}</>;
}
