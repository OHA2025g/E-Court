import React from "react";

/** Catches render failures in a dashboard tab so one chart cannot blank the whole page. */
export default class DashboardTabErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    // eslint-disable-next-line no-console
    console.error(this.props.label || "Dashboard tab", error);
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div
          className="rounded-sm border border-red-200 bg-red-50 px-4 py-6 text-sm text-red-900"
          data-testid="dashboard-tab-error"
          role="alert"
        >
          <div className="font-semibold">
            {this.props.label || "This view"} could not be displayed.
          </div>
          <p className="mt-1 text-red-800/90">
            {String(this.state.error?.message || this.state.error)}
          </p>
          <button
            type="button"
            className="mt-3 rounded-sm border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-red-800"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
