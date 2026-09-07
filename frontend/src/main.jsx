import React from 'react';
import { createRoot } from 'react-dom/client';
import SimulationApp from './SimulationApp.jsx';
import './simulation.css';

class ErrorBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <main className="sim-main"><div className="sim-error"><h1>Unable to display the simulation</h1><p>Reload the page and try again.</p><button onClick={() => window.location.reload()}>Reload</button></div></main> : this.props.children;
  }
}

createRoot(document.getElementById('root')).render(<React.StrictMode><ErrorBoundary><SimulationApp /></ErrorBoundary></React.StrictMode>);
