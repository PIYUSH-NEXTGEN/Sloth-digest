export type Platform = "whatsapp" | "discord" | "telegram" | "other";

export interface Message {
  id: string;
  platform: Platform;
  conversation_id: string;
  sender: string;
  timestamp: string;
  text: string;
  reply_to?: string;
  is_system: boolean;
}

export interface Conversation {
  id: string;
  platform: Platform;
  name: string;
  participants: string[];
}

export interface NeedsYouItem {
  message_id: string;
  from: string;
  summary: string;
  reason: string;
  suggested_reply?: string;
}

export interface Decision {
  text: string;
  message_ids: string[];
}

export interface PersonPoint {
  name: string;
  points: string[];
}

export interface Deadline {
  text: string;
  when?: string;
  message_ids: string[];
}

export interface DigestGroup {
  conversation_id: string;
  platform: Platform;
  name: string;
  message_count: number;
  skipped_count: number;
  tldr: string;
  needs_you: NeedsYouItem[];
  decisions: Decision[];
  by_person: PersonPoint[];
  deadlines: Deadline[];
}

export interface Digest {
  id: string;
  generated_at: string;
  window: { start: string; end: string };
  model: string;
  prompt_version: string;
  groups: DigestGroup[];
}

export const PLATFORM_LABELS: Record<Platform, string> = {
  whatsapp: "WhatsApp",
  discord: "Discord",
  telegram: "Telegram",
  other: "Other",
};
