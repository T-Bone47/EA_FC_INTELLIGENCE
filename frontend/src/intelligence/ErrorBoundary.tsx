import { Component, type ReactNode } from 'react'

/** A render crash (e.g. a version-skewed backend) must not unmount the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed
      ? <p role="alert" className="ix-scope">Something went wrong while displaying this result. Run the search again.</p>
      : this.props.children
  }
}
