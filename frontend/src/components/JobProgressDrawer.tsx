import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Drawer,
  Group,
  ScrollArea,
  Stack,
  Text,
} from "@mantine/core";
import {
  IconAlertCircle,
  IconCircleCheck,
  IconInfoCircle,
} from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";

import { subscribeJob } from "../api/sse";
import type { JobEvent } from "../api/types";

interface Props<TResult> {
  jobId: string | null;
  opened: boolean;
  title: string;
  onClose: () => void;
  onDone?: (status: "done" | "error", events: JobEvent[]) => void;
  /**
   * Optional renderer for the final result, fetched separately once the
   * job lands "done". Most callers fetch the result via TanStack Query
   * outside this drawer.
   */
  renderResult?: (result: TResult | null) => React.ReactNode;
}

/**
 * Live SSE log for a JobRegistry job. Subscribes when ``jobId`` becomes
 * non-null and the drawer opens; unsubscribes on close or unmount.
 *
 * The drawer doesn't hold the final result itself — callers pass an
 * ``onDone`` callback and (typically) refetch via TanStack Query.
 */
export function JobProgressDrawer<TResult = unknown>({
  jobId,
  opened,
  title,
  onClose,
  onDone,
  renderResult,
}: Props<TResult>) {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [terminal, setTerminal] = useState<"done" | "error" | null>(null);
  const [resultPayload, setResultPayload] = useState<TResult | null>(null);
  const qc = useQueryClient();

  useEffect(() => {
    if (!jobId || !opened) return;
    setEvents([]);
    setTerminal(null);
    setResultPayload(null);
    const unsub = subscribeJob(jobId, {
      onEvent: (e) => setEvents((prev) => [...prev, e]),
      onEnd: (status) => {
        setTerminal(status);
        // SSE is the authoritative signal that the job is in a terminal
        // state. Invalidate the matching ``useJob`` cache so consumers
        // re-render with the final result without waiting on the polling
        // fallback (which can race past the terminal status).
        qc.invalidateQueries({ queryKey: ["jobs", jobId] });
        onDone?.(status, []); // events are in state, not lifted up here
      },
      onError: () => setTerminal("error"),
    });
    return () => unsub();
    // events / onDone are intentionally NOT in deps — we only want to
    // (re)subscribe on a fresh jobId, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, opened, qc]);

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size="md"
      title={
        <Group gap="sm">
          <Text fw={600}>{title}</Text>
          {terminal === "done" && (
            <Badge color="green" variant="light">
              done
            </Badge>
          )}
          {terminal === "error" && (
            <Badge color="red" variant="light">
              error
            </Badge>
          )}
          {!terminal && jobId && (
            <Badge color="blue" variant="light">
              running
            </Badge>
          )}
        </Group>
      }
    >
      <Stack>
        <ScrollArea h={300} type="auto">
          <Stack gap={4}>
            {events.length === 0 && !terminal && (
              <Text c="dimmed" size="sm">
                Waiting for first event…
              </Text>
            )}
            {events.map((ev, i) => (
              <EventRow key={i} event={ev} />
            ))}
            {terminal === "done" && (
              <Group gap={6} mt="xs">
                <IconCircleCheck size={14} color="var(--mantine-color-green-6)" />
                <Text size="sm" c="green">
                  finished
                </Text>
              </Group>
            )}
            {terminal === "error" && (
              <Alert color="red" icon={<IconAlertCircle size={14} />} mt="xs">
                Job ended with an error — check the last event for details.
              </Alert>
            )}
          </Stack>
        </ScrollArea>
        {renderResult && terminal === "done" && (
          <>{renderResult(resultPayload)}</>
        )}
      </Stack>
    </Drawer>
  );
}

function EventRow({ event }: { event: JobEvent }) {
  const color =
    event.level === "error"
      ? "red"
      : event.level === "warn"
      ? "yellow"
      : "gray";
  return (
    <Group gap={6} align="flex-start" wrap="nowrap">
      <IconInfoCircle
        size={12}
        style={{ marginTop: 4 }}
        color={`var(--mantine-color-${color}-6)`}
      />
      <Text size="xs" c={color === "gray" ? "dimmed" : color}>
        {event.message}
      </Text>
    </Group>
  );
}
