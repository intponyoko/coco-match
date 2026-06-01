import { useEffect, useMemo, useState } from "react";

export type ActorRole = "executive" | "department" | "individual" | "admin";

export type ApprovalStatus =
  | "draft"
  | "edited"
  | "submitted"
  | "pending"
  | "approved";

export type ApprovalRecord = {
  tableName: string;
  status: ApprovalStatus;
  actorRole: ActorRole;
  comment: string;
  updatedAt: string;
};

const STORAGE_KEY = "coco-match-approval-state-v1";

function readRecords(): ApprovalRecord[] {
  if (typeof window === "undefined") {
    return [];
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return [];
  }
  try {
    return JSON.parse(raw) as ApprovalRecord[];
  } catch {
    return [];
  }
}

function writeRecords(records: ApprovalRecord[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
}

export function useApprovalState() {
  const [records, setRecords] = useState<ApprovalRecord[]>([]);

  useEffect(() => {
    setRecords(readRecords());
  }, []);

  const latest = useMemo(() => {
    const map = new Map<string, ApprovalRecord>();
    for (const record of records) {
      map.set(record.tableName, record);
    }
    return map;
  }, [records]);

  const latestRecords = useMemo(() => Array.from(latest.values()), [latest]);

  function setTableApproval(
    tableName: string,
    status: ApprovalStatus,
    actorRole: ActorRole,
    comment = "",
  ) {
    const nextRecord = {
      tableName,
      status,
      actorRole,
      comment,
      updatedAt: new Date().toISOString(),
    };
    const next = [...readRecords(), nextRecord];
    writeRecords(next);
    setRecords(next);
  }

  function statusOf(tableName: string, fallback = "draft") {
    return latest.get(tableName)?.status ?? fallback;
  }

  function clearApprovals() {
    setRecords([]);
    writeRecords([]);
  }

  function approvalsPayload(): Record<string, Record<string, unknown>> {
    return Object.fromEntries(
      latestRecords
        .filter((record) => record.status === "approved")
        .map((record) => [
          record.tableName,
          {
            status: "approved",
            actor: record.actorRole,
            comment: record.comment,
            approved_at: record.updatedAt,
          },
        ]),
    );
  }

  return { records, latestRecords, statusOf, setTableApproval, approvalsPayload, clearApprovals };
}
