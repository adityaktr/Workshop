import { useEffect, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

function App() {
  const [appliances, setAppliances] = useState([]);
  const [total, setTotal] = useState(0);
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const [name, setName] = useState("");
  const [wattage, setWattage] = useState("");
  const [priority, setPriority] = useState("");

  async function loadData() {
    let listResponse = await fetch(API + "/appliances");
    let list = await listResponse.json();
    let wattResponse = await fetch(API + "/appliances/wattage");
    let watt = await wattResponse.json();
    setAppliances(list);
    setTotal(watt.total_wattage);
  }

  useEffect(() => {
    loadData().catch(() => {
      setIsError(true);
      setMessage("Could not reach the server. Start the backend first.");
    });
  }, []);

  async function handleResponse(response) {
    let data = await response.json();
    if (!response.ok) {
      let text = "Request failed";
      if (data.detail && data.detail.message) {
        text = data.detail.message;
      }
      setIsError(true);
      setMessage(text);
    } else {
      setIsError(false);
      setMessage(data.message || "Done");
    }
    await loadData();
  }

  async function addAppliance(event) {
    event.preventDefault();
    let response = await fetch(API + "/appliances", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        wattage: Number(wattage),
        priority: Number(priority),
      }),
    });
    await handleResponse(response);
    if (response.ok) {
      setName("");
      setWattage("");
      setPriority("");
    }
  }

  async function turnOn(id) {
    let response = await fetch(API + "/appliances/" + id + "/on", { method: "POST" });
    await handleResponse(response);
  }

  async function turnOff(id) {
    let response = await fetch(API + "/appliances/" + id + "/off", { method: "POST" });
    await handleResponse(response);
  }

  async function removeAppliance(id) {
    let response = await fetch(API + "/appliances/" + id, { method: "DELETE" });
    await handleResponse(response);
  }

  let free = 800 - total;
  let barWidth = (total / 800) * 100;

  return (
    <div className="page">
      <h1>Inverter Load Manager</h1>
      <p>Limit is 800W. Priority 1 is the most important.</p>

      <div className="bar-box">
        <div className="bar-fill" style={{ width: barWidth + "%" }}></div>
      </div>
      <p>
        {total}W used, {free}W free
      </p>

      {message !== "" && <p className={isError ? "msg error" : "msg"}>{message}</p>}

      <h2>Add appliance</h2>
      <form onSubmit={addAppliance}>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          placeholder="Wattage"
          type="number"
          min="1"
          value={wattage}
          onChange={(e) => setWattage(e.target.value)}
          required
        />
        <input
          placeholder="Priority"
          type="number"
          min="1"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          required
        />
        <button type="submit">Add</button>
      </form>

      <h2>Appliances</h2>
      {appliances.length === 0 && <p>No appliances yet.</p>}

      {appliances.map((item) => (
        <div className={"row " + item.status} key={item.id}>
          <div>
            <b>{item.name}</b>
            <div>
              {item.wattage}W, priority {item.priority}
            </div>
            <div>
              {item.status === "running" && "Running"}
              {item.status === "off" && "Off"}
              {item.status === "shed" && "Shed — paused, waiting for capacity"}
            </div>
          </div>
          <div>
            <button onClick={() => turnOn(item.id)}>On</button>
            <button onClick={() => turnOff(item.id)}>Off</button>
            <button onClick={() => removeAppliance(item.id)}>Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default App;
