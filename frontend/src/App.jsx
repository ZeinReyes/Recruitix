import Dashboard from "./pages/Dashboard";
import Jobs from "./pages/Jobs";

function App() {
  const path = window.location.pathname;

  if (path === "/jobs") {
    return <Jobs />;
  }

  return <Dashboard />;
}

export default App;