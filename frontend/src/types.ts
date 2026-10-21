export type {
  Conversation,
  Decision,
  Deadline,
  Digest,
  DigestWindow,
  GroupDigest,
  Message,
  NeedsYouItem,
  PersonPoints,
  Platform,
} from "./api/digest-schema";
export type { SlothDigest as SlothDigestSchema } from "./api/digest-schema";
export type { paths, operations, components } from "./api/schema";

import type { Platform } from "./api/digest-schema";
import type { components } from "./api/schema";

export type ConversationInfo = components["schemas"]["ConversationInfo"];

export const PLATFORM_LABELS: Record<Platform, string> = {
  whatsapp: "WhatsApp",
  discord: "Discord",
  telegram: "Telegram",
};
