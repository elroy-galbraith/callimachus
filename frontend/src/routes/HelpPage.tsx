import {
  Accordion,
  Anchor,
  Code,
  List,
  Stack,
  Text,
  Title,
} from "@mantine/core";

export function HelpPage() {
  return (
    <Stack>
      <Title order={2}>Help</Title>
      <Text c="dimmed">
        Callimachus is a configurable platform for turning documents into
        typed knowledge graphs — extract entities with an LLM under a
        declarative schema, curate them in a vault, and query the result
        with SPARQL or natural language.
      </Text>

      <Accordion variant="separated">
        <Accordion.Item value="overview">
          <Accordion.Control>Overview</Accordion.Control>
          <Accordion.Panel>
            <Text>
              A <strong>project</strong> binds a <strong>pack</strong>{" "}
              (declarative schema, prompts, IRIs, queries) to a{" "}
              <strong>vault</strong> (extracted entity files) and an{" "}
              <strong>approval workflow</strong> (filesystem or git).
            </Text>
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="workflow">
          <Accordion.Control>Workflow</Accordion.Control>
          <Accordion.Panel>
            <List type="ordered">
              <List.Item>Open or create a project on the Projects page.</List.Item>
              <List.Item>
                On <strong>Dashboard</strong>, drop a PDF in the inbox and run
                extraction.
              </List.Item>
              <List.Item>Review the proposed entities and approve or reject.</List.Item>
              <List.Item>
                Use <strong>Query</strong> to run competency questions or ask
                a natural-language question against the resulting graph.
              </List.Item>
              <List.Item>
                Use <strong>Proposals</strong> to run the consolidator and
                approve refactorings of the vault.
              </List.Item>
            </List>
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="api-key">
          <Accordion.Control>API key</Accordion.Control>
          <Accordion.Panel>
            <Text>
              Set <Code>ANTHROPIC_API_KEY</Code> in <Code>.env</Code> at the
              repo root. The API process reads it on startup; the UI never
              writes the key back over HTTP.
            </Text>
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="source">
          <Accordion.Control>Source</Accordion.Control>
          <Accordion.Panel>
            <Text>
              See the{" "}
              <Anchor href="<YOUR_PROJECT_REPOSITORY_URL>" target="_blank" rel="noreferrer">
                project repository
              </Anchor>{" "}
              for the engine code, packs, and CLI scripts.
            </Text>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}
