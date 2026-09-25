import { useState } from "react";

function App() {

  const [message, setMessage] = useState("");

  const [role, setRole] = useState("unity");

  const [pdfFile, setPdfFile] = useState(null);

  const [messages, setMessages] = useState([]);

  // 上传PDF
  const uploadPdf = async () => {

    if (!pdfFile) {
      alert("请选择PDF文件");
      return;
    }

    const formData = new FormData();

    formData.append(
      "file",
      pdfFile
    );

    const response = await fetch(
      "http://127.0.0.1:8000/upload",
      {
        method: "POST",
        body: formData
      }
    );

    const data = await response.json();

    alert(data.message);
  };

  // 发送消息
  const sendMessage = async () => {

    if (!message.trim()) return;

    const currentMessage = message;

    setMessages(prev => [
      ...prev,
      {
        role: "user",
        content: currentMessage
      }
    ]);

    setMessage("");

    const response = await fetch(
      "http://127.0.0.1:8000/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: currentMessage,
          role: role
        })
      }
    );

    const data = await response.json();

    setMessages(prev => [
      ...prev,
      {
        role: "assistant",
        content: data.answer
      }
    ]);
  };

  return (
    <div
      style={{
        width: "900px",
        margin: "0 auto",
        padding: "20px"
      }}
    >

      <h1>Smart Knowledge Assistant</h1>

      {/* 角色选择 */}
      <select
        value={role}
        onChange={(e) => setRole(e.target.value)}
        style={{
          marginBottom: "10px",
          padding: "8px"
        }}
      >
        <option value="unity">
          Unity导师
        </option>

        <option value="cpp">
          C++导师
        </option>

        <option value="ai">
          AI全栈导师
        </option>

        <option value="digital">
          数字孪生专家
        </option>
      </select>

      <br />

      {/* PDF上传 */}
      <input
        type="file"
        accept=".pdf"
        onChange={(e) => {
          setPdfFile(
            e.target.files[0]
          );
        }}
      />

      <button
        onClick={uploadPdf}
        style={{
          marginLeft: "10px"
        }}
      >
        上传PDF
      </button>

      <hr />

      {/* 聊天记录 */}
      <div
        style={{
          border: "1px solid #ccc",
          height: "500px",
          overflowY: "auto",
          padding: "10px",
          marginBottom: "10px"
        }}
      >
        {
          messages.map((msg, index) => (

            <div
              key={index}
              style={{
                marginBottom: "15px",
                textAlign:
                  msg.role === "user"
                    ? "right"
                    : "left"
              }}
            >
              <strong>
                {
                  msg.role === "user"
                    ? "你"
                    : "AI"
                }
              </strong>

              <div>
                {msg.content}
              </div>

            </div>

          ))
        }
      </div>

      {/* 输入框 */}
      <input
        style={{
          width: "700px",
          padding: "8px",
          marginRight: "10px"
        }}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="请输入问题"
      />

      <button
        onClick={sendMessage}
      >
        发送
      </button>

    </div>
  );
}

export default App;