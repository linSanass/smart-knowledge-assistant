import { useState } from "react";

function App() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");

  const sendMessage = async () => {
    const response = await fetch(
      "http://127.0.0.1:8000/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: message
        })
      }
    );

    const data = await response.json();

    setAnswer(data.answer);
  };

  return (
    <div style={{ padding: "20px" }}>
      <h1>Smart Knowledge Assistant</h1>

      <input
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="请输入问题"
      />

      <button onClick={sendMessage}>
        发送
      </button>

      <p>{answer}</p>
    </div>
  );
}

export default App;