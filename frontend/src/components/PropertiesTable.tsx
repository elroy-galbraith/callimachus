import { Badge, Blockquote, Code, Group, Stack, Table, Text } from "@mantine/core";

export function PropertiesTable({
  frontmatter,
}: {
  frontmatter: Record<string, unknown>;
}) {
  const entries = Object.entries(frontmatter ?? {});
  if (entries.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        No frontmatter.
      </Text>
    );
  }

  // Pull source_text out for blockquote rendering — it's the reviewer-facing
  // excerpt and reads better as a block than as a one-line table cell.
  const sourceText =
    typeof frontmatter.source_text === "string"
      ? (frontmatter.source_text as string)
      : null;
  const tableEntries = entries.filter(([k]) => k !== "source_text");

  return (
    <Stack gap="sm">
      <Table withTableBorder withColumnBorders striped="even">
        <Table.Tbody>
          {tableEntries.map(([k, v]) => (
            <Table.Tr key={k}>
              <Table.Td style={{ width: 140, verticalAlign: "top" }}>
                <Code>{k}</Code>
              </Table.Td>
              <Table.Td>
                <PropertyValue value={v} />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {sourceText && (
        <Blockquote color="gray" iconSize={16} p="xs" m={0}>
          <Text size="sm">{sourceText}</Text>
        </Blockquote>
      )}
    </Stack>
  );
}

export function PropertyValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return (
      <Text size="sm" c="dimmed">
        —
      </Text>
    );
  }
  if (Array.isArray(value)) {
    if (value.length === 0)
      return (
        <Text size="sm" c="dimmed">
          [ ]
        </Text>
      );
    return (
      <Group gap={4}>
        {value.map((v, i) => (
          <Badge key={i} variant="default" size="sm">
            {String(v)}
          </Badge>
        ))}
      </Group>
    );
  }
  if (typeof value === "object") {
    return (
      <Code block style={{ fontSize: 12 }}>
        {JSON.stringify(value, null, 2)}
      </Code>
    );
  }
  return <Text size="sm">{String(value)}</Text>;
}
