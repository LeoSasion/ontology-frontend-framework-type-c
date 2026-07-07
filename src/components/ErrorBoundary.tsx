import { Component, type ErrorInfo, type ReactNode } from "react";
import { biText } from "./Bilingual";

type ErrorBoundaryProps = {
  children: ReactNode;
};

type ErrorBoundaryState = {
  error: Error | null;
  componentStack: string;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, componentStack: "" };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error, componentStack: "" };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ componentStack: info.componentStack ?? "" });
    console.error("AIBI UI render failed", error, info.componentStack);
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <main className="appFallback" role="alert">
        <section className="mainPanel fallbackPanel">
          <p className="kicker">{biText("界面需要恢复", "Interface needs recovery")}</p>
          <h1>{biText("页面没有丢数据，只是视图渲染中断", "Data is safe; the view stopped rendering")}</h1>
          <p>
            {biText(
              "系统已经拦截了异常，避免整页白屏。刷新后会重新加载当前工作区。",
              "The error was caught to prevent a blank screen. Refresh to reload the current workspace.",
            )}
          </p>
          <button className="primaryButton" onClick={() => window.location.reload()} type="button">
            {biText("刷新页面", "Refresh page")}
          </button>
          <details className="advancedDetails compactAdvanced">
            <summary>{biText("查看错误信息", "View error details")}</summary>
            <pre>{[this.state.error.message, this.state.componentStack].filter(Boolean).join("\n\n")}</pre>
          </details>
        </section>
      </main>
    );
  }
}
