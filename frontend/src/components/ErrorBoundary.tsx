import { Component, type ErrorInfo, type ReactNode } from "react";
import { Alert, Button, Stack, Text } from "@mantine/core";

interface Props {
  children: ReactNode;
  /** Custom fallback UI. Receives the error so callers can tailor the message. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
  /** Short label shown in the default fallback (e.g. "graph", "proposal card"). */
  label?: string;
}

interface State {
  error: Error | null;
}

/**
 * Class-based error boundary — catches synchronous render errors in the
 * subtree and shows a contained error message instead of crashing the
 * whole app. Use around any subtree that does WASM, heavy third-party
 * rendering, or DOM manipulation outside of React.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) {
      return this.props.fallback(error, this.reset);
    }

    const label = this.props.label ?? "component";
    return (
      <Alert color="red" variant="light" title={`${label} failed to render`}>
        <Stack gap={6}>
          <Text size="xs" ff="monospace">
            {error.message || String(error)}
          </Text>
          <Button size="compact-xs" variant="subtle" color="red" onClick={this.reset}>
            Retry
          </Button>
        </Stack>
      </Alert>
    );
  }
}
