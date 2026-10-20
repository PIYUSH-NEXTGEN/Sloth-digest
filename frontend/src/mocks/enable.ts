import { worker } from "./browser";

const mockEnabled =
  import.meta.env.MODE === "development" &&
  import.meta.env["VITE_DISABLE_MSW"] !== "1";

export async function enableMocks(): Promise<void> {
  if (!mockEnabled) {
    return;
  }
  await worker.start({ quiet: true, onUnhandledRequest: "warn" });
}
