import { Alert, Badge, Stack, Table, Text } from "@mantine/core";

import type { SparqlResultOut } from "../api/types";
import { CodeBlock } from "./CodeBlock";

/**
 * Render any of the three SPARQL result kinds the engine returns:
 * SELECT (table), ASK (boolean badge), CONSTRUCT/DESCRIBE (triple list).
 */
export function SparqlResultsTable({ result }: { result: SparqlResultOut }) {
  if (result.kind === "ask") {
    return (
      <Alert
        color={result.value ? "green" : "yellow"}
        title={`ASK → ${result.value ? "true" : "false"}`}
      />
    );
  }
  if (result.kind === "graph") {
    if (result.triples.length === 0) {
      return <Text c="dimmed">(no triples)</Text>;
    }
    return (
      <Stack gap="xs">
        <Text size="sm" c="dimmed">
          {result.triples.length} triple(s)
        </Text>
        <CodeBlock maxHeight={400}>{result.triples.join("\n")}</CodeBlock>
      </Stack>
    );
  }
  // SELECT
  if (result.rows.length === 0) {
    return (
      <Alert color="gray" title="No rows" variant="light">
        The query parsed and ran, but returned no rows.
      </Alert>
    );
  }
  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">
        <Badge variant="light" mr={6}>
          {result.rows.length}
        </Badge>
        row{result.rows.length === 1 ? "" : "s"}
      </Text>
      <Table.ScrollContainer minWidth={400}>
        <Table
          withTableBorder
          withColumnBorders
          striped
          highlightOnHover
          stickyHeader
        >
          <Table.Thead>
            <Table.Tr>
              {result.variables.map((v) => (
                <Table.Th key={v}>{v}</Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {result.rows.map((row, i) => (
              <Table.Tr key={i}>
                {result.variables.map((v) => (
                  <Table.Td key={v}>
                    <Text
                      size="sm"
                      ff="ui-monospace, monospace"
                      style={{ wordBreak: "break-all" }}
                    >
                      {row[v] ?? <Text component="span" c="dimmed">—</Text>}
                    </Text>
                  </Table.Td>
                ))}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  );
}
