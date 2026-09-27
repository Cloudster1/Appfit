import { notifications } from "@mantine/notifications";

export function notifyError(error: unknown, title = "Something went wrong") {
  notifications.show({
    color: "red",
    title,
    message: error instanceof Error ? error.message : String(error),
  });
}

export function notifySuccess(message: string, title?: string) {
  notifications.show({ color: "teal", title, message });
}
