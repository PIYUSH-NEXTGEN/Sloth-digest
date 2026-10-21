import { http, HttpResponse, delay } from "msw";
import type { components } from "../types";
import { sampleDigest } from "./sampleDigest";

type Health = {
  status: "ok";
  version: string;
  model: string;
};

type IngestResult = components["schemas"]["IngestResult"];
type Settings = components["schemas"]["Settings"];

export const handlers = [
  http.get("*/health", () =>
    HttpResponse.json({
      status: "ok",
      version: "0.1.0",
      model: "gemma3:4b",
    } satisfies Health),
  ),

  http.get("*/sources", () =>
    HttpResponse.json({
      conversations: [
        {
          id: "weekend-trip",
          platform: "whatsapp" as const,
          name: "Weekend trip planning 🏔️",
          message_count: 412,
          last_message_at: "2026-10-20T05:41:00Z",
        },
        {
          id: "sunday-cricket-squad",
          platform: "discord" as const,
          name: "sunday-cricket-squad",
          message_count: 187,
          last_message_at: "2026-10-19T23:02:00Z",
        },
      ],
    }),
  ),

  http.post("*/ingest/file", () =>
    HttpResponse.json({
      conversation_id: "weekend-trip",
      imported: 404,
      duplicates: 8,
    } satisfies IngestResult),
  ),

  http.post("*/digest/run", async () => {
    await delay(120);
    return HttpResponse.json({ digest_id: sampleDigest.id }, { status: 202 });
  }),

  http.get("*/digest/latest", () => HttpResponse.json(sampleDigest)),

  http.get("*/digest/:digestId", ({ params }) => {
    if (params["digestId"] !== sampleDigest.id) {
      return HttpResponse.json(
        { detail: "Unknown digest id" },
        { status: 404 },
      );
    }
    return HttpResponse.json(sampleDigest);
  }),

  http.post("*/ask", () =>
    HttpResponse.json(
      { detail: "Ask is not implemented yet (Phase 5)" },
      { status: 501 },
    ),
  ),

  http.get("*/settings", () =>
    HttpResponse.json(DEFAULT_SETTINGS satisfies Settings),
  ),
  http.put("*/settings", async ({ request }) => {
    const body = (await request.json()) as Partial<Settings>;
    return HttpResponse.json({
      ...DEFAULT_SETTINGS,
      ...body,
    } satisfies Settings);
  }),
];

export const DEFAULT_SETTINGS: Settings = {
  user_names: ["Priya", "prids"],
  vip_people: ["Riya"],
  keywords: ["biryani"],
  digest_time: "06:00",
  model: "gemma3:4b",
};
