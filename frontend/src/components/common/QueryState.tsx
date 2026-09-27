import { Alert, Center, Loader } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import type { ReactNode } from "react";

type Props = {
  isPending: boolean;
  error: Error | null;
  children: ReactNode;
};

/** Renders a loader or an error alert until the query has data. */
export function QueryState({ isPending, error, children }: Props) {
  if (error) {
    return (
      <Alert color="red" icon={<IconAlertTriangle />} title="Could not load data">
        {error.message}
      </Alert>
    );
  }
  if (isPending) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }
  return <>{children}</>;
}
