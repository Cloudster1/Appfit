import { fireEvent, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { Route, Routes } from "react-router";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { LoginPage } from "../pages/LoginPage";
import { renderWithProviders } from "../test/utils";
import { useAuth } from "./AuthProvider";
import { RequireAuth } from "./guards";

const user = {
  id: "u1",
  email: "editor@example.com",
  display_name: "Eddie Editor",
  role: "editor",
  auth_provider: "local",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

const server = setupServer(
  http.get("*/api/auth/me", () => HttpResponse.json({ detail: "Not authenticated" }, { status: 401 })),
  http.post("*/api/auth/login", async ({ request }) => {
    const body = (await request.json()) as { password: string };
    return body.password === "right-password"
      ? HttpResponse.json({ user, access_token: "t", token_type: "bearer" })
      : HttpResponse.json({ detail: "Invalid email or password" }, { status: 401 });
  }),
  http.post("*/api/auth/logout", () => new HttpResponse(null, { status: 204 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

function Home() {
  const { user: me, logout } = useAuth();
  return (
    <div>
      <p>Welcome {me?.display_name}</p>
      <button onClick={() => void logout()}>Log out</button>
    </div>
  );
}

function Tree() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Home />
          </RequireAuth>
        }
      />
    </Routes>
  );
}

async function signIn(password: string) {
  fireEvent.change(await screen.findByLabelText("Email"), { target: { value: user.email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("login flow", () => {
  it("redirects to login, signs in, lands on the protected page and signs out again", async () => {
    renderWithProviders(<Tree />, { withAuth: true });
    await signIn("right-password");
    expect(await screen.findByText("Welcome Eddie Editor")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows the server error for wrong credentials", async () => {
    renderWithProviders(<Tree />, { withAuth: true });
    await signIn("wrong-password");
    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });
});
