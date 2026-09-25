import { useState } from "react";

function App() {

  const [message, setMessage] = useState("");

  const [role, setRole] = useState("unity");

  const [pdfFile, setPdfFile] = useState(null);

  const [messages, setMessages] = useState([]);

  const [sources, setSources] = useState([]);

  const [knowledgeBuilt, setKnowledgeBuilt] =
    useState(false);

  // 上传PDF
  const uploadPdf = async () => {

    if (!pdfFile) {
      alert("请选择PDF");
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

  // 构建知识库
  const buildRag = async () => {

    const response = await fetch(
      "http://127.0.0.1:8000/build-rag"
    );

    const data = await response.json();

    alert(
      `知识库构建完成，共${data.chunk_count}个Chunk`
    );

    setKnowledgeBuilt(true);
  };

  // 普通聊天
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
          "Content-Type":
            "application/json"
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

  // RAG问答
  const askKnowledge = async () => {

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
      "http://127.0.0.1:8000/rag-chat",
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json"
        },
        body: JSON.stringify({
          question: currentMessage
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

    setSources(
      data.sources || []
    );
  };

  return (

    <div
      style={{
        width: "1100px",
        margin: "0 auto",
        padding: "20px",
        color: "white"
      }}
    >

      <h1>
        Smart Knowledge Assistant
      </h1>

      <select
        value={role}
        onChange={(e) =>
          setRole(e.target.value)
        }
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

      <hr />

      <input
        type="file"
        accept=".pdf"
        onChange={(e) =>
          setPdfFile(
            e.target.files[0]
          )
        }
      />

      <button
        onClick={uploadPdf}
      >
        上传PDF
      </button>

      <button
        onClick={buildRag}
        style={{
          marginLeft: "10px"
        }}
      >
        构建知识库
      </button>

      <p>
        当前文件：
        {
          pdfFile
            ? pdfFile.name
            : "未选择"
        }
      </p>

      <p>
        状态：
        {
          knowledgeBuilt
            ? "知识库已构建"
            : "未构建"
        }
      </p>

      <hr />

      <div
        style={{
          border: "1px solid #666",
          height: "500px",
          overflowY: "auto",
          padding: "10px"
        }}
      >

        {
          messages.map(
            (
              msg,
              index
            ) => (

              <div
                key={index}
                style={{
                  marginBottom:
                    "15px",
                  textAlign:
                    msg.role ===
                    "user"
                      ? "right"
                      : "left"
                }}
              >
                <b>
                  {
                    msg.role ===
                    "user"
                      ? "你"
                      : "AI"
                  }
                </b>

                <div>
                  {
                    msg.content
                  }
                </div>

              </div>
            )
          )
        }

      </div>

      <br />

      <input
        value={message}
        onChange={(e) =>
          setMessage(
            e.target.value
          )
        }
        style={{
          width: "700px",
          padding: "10px"
        }}
      />

      <button
        onClick={sendMessage}
      >
        AI聊天
      </button>

      <button
        onClick={askKnowledge}
        style={{
          marginLeft: "10px"
        }}
      >
        知识库问答
      </button>

      <hr />

      <h3>
        检索到的知识来源
      </h3>

      {
        sources.map(
          (
            source,
            index
          ) => (

            <div
              key={index}
              style={{
                border:
                  "1px solid #666",
                padding: "10px",
                marginBottom:
                  "10px"
              }}
            >
              <b>
                Chunk
                {index + 1}
              </b>

              <p>
                {source}
              </p>

            </div>
          )
        )
      }

    </div>
  );
}

export default App;