import React from "react";
import { useSession } from "./store/session";
import { Lobby } from "./components/Lobby";
import { Table } from "./components/Table";

const App: React.FC = () => {
  const { snapshot } = useSession();
  return (
    <div className="app">
      {snapshot ? <Table snapshot={snapshot} /> : <Lobby />}
    </div>
  );
};

export default App;
