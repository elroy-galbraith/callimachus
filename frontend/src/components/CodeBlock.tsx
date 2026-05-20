import { ActionIcon, Code, Group, Tooltip } from "@mantine/core";
import { useClipboard } from "@mantine/hooks";
import { IconCheck, IconCopy } from "@tabler/icons-react";

/**
 * Pre-formatted code with a copy button. Used for SPARQL, JSON, and the
 * rendered prompts on the Schema page.
 */
export function CodeBlock({
  children,
  maxHeight,
}: {
  children: string;
  maxHeight?: number;
}) {
  const clipboard = useClipboard({ timeout: 1200 });
  return (
    <Group align="flex-start" gap={0} wrap="nowrap" style={{ position: "relative" }}>
      <Code
        block
        style={{
          flexGrow: 1,
          maxHeight,
          overflow: "auto",
          fontSize: 12,
          lineHeight: 1.5,
          paddingRight: 36,
        }}
      >
        {children}
      </Code>
      <Tooltip label={clipboard.copied ? "Copied" : "Copy"} position="left">
        <ActionIcon
          variant="subtle"
          color="gray"
          aria-label="Copy to clipboard"
          onClick={() => clipboard.copy(children)}
          style={{ position: "absolute", right: 6, top: 6 }}
        >
          {clipboard.copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
        </ActionIcon>
      </Tooltip>
    </Group>
  );
}
