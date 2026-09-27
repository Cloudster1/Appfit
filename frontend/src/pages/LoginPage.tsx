import { Alert, Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconAlertTriangle } from "@tabler/icons-react";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { useAuth } from "../auth/AuthProvider";
import { APP_TITLE, LOGO_SIZE } from "../config";

const LOGIN_CARD_WIDTH = 380;

function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const form = useForm({
    initialValues: { email: "", password: "" },
    validate: {
      email: (v) => (v.trim() ? null : "Email is required"),
      password: (v) => (v ? null : "Password is required"),
    },
  });

  if (user) return <Navigate to={safeNext(params.get("next"))} replace />;

  const submit = form.onSubmit(async ({ email, password }) => {
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate(safeNext(params.get("next")), { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  });

  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="md" p="xl" w={LOGIN_CARD_WIDTH}>
        <form onSubmit={submit}>
          <Stack>
            <Stack gap={0} align="center">
              <img src="/favicon.svg" alt="" width={LOGO_SIZE * 2} height={LOGO_SIZE * 2} />
              <Title order={2}>{APP_TITLE}</Title>
              <Text c="dimmed" size="sm">
                Find the right application for your requirements
              </Text>
            </Stack>
            {error && (
              <Alert color="red" icon={<IconAlertTriangle />}>
                {error}
              </Alert>
            )}
            <TextInput label="Email" autoComplete="username" autoFocus {...form.getInputProps("email")} />
            <PasswordInput
              label="Password"
              autoComplete="current-password"
              {...form.getInputProps("password")}
            />
            <Button type="submit" loading={submitting} fullWidth>
              Sign in
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  );
}
