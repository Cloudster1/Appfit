import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router";

import { RequireAuth, RequireRole } from "./auth/guards";
import { AppShellLayout } from "./layout/AppShellLayout";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { AppsPage } from "./pages/AppsPage";

// Secondary pages are code-split; the apps page (the landing page) stays in the main bundle.
const AppDetailPage = lazy(() => import("./pages/AppDetailPage").then((m) => ({ default: m.AppDetailPage })));
const AppEditPage = lazy(() => import("./pages/AppEditPage").then((m) => ({ default: m.AppEditPage })));
const LandscapePage = lazy(() => import("./pages/LandscapePage").then((m) => ({ default: m.LandscapePage })));
const ImportPage = lazy(() => import("./pages/ImportPage").then((m) => ({ default: m.ImportPage })));
const UsersPage = lazy(() => import("./pages/UsersPage").then((m) => ({ default: m.UsersPage })));
const SystemPage = lazy(() => import("./pages/SystemPage").then((m) => ({ default: m.SystemPage })));

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShellLayout />
          </RequireAuth>
        }
      >
        <Route index element={<AppsPage />} />
        {/* The catalog and search share the landing page. */}
        <Route path="apps" element={<Navigate to="/" replace />} />
        <Route
          path="apps/new"
          element={
            <RequireRole min="editor">
              <AppEditPage />
            </RequireRole>
          }
        />
        <Route path="apps/:slug" element={<AppDetailPage />} />
        <Route path="landscape" element={<LandscapePage />} />
        <Route
          path="apps/:slug/edit"
          element={
            <RequireRole min="editor">
              <AppEditPage />
            </RequireRole>
          }
        />
        <Route
          path="import"
          element={
            <RequireRole min="editor">
              <ImportPage />
            </RequireRole>
          }
        />
        <Route
          path="admin/users"
          element={
            <RequireRole min="admin">
              <UsersPage />
            </RequireRole>
          }
        />
        <Route
          path="admin/system"
          element={
            <RequireRole min="admin">
              <SystemPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
