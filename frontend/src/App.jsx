import { useEffect, useRef, useState } from "react";

import "./App.css";

import {
  buildRag,
  createConversation,
  createNote,
  deleteConversation,
  deleteDocument,
  getConversation,
  getIndexStatus,
  listConversations,
  listDocuments,
  sendMessage,
  updateNote,
  uploadDocument
} from "./api";

import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import Composer from "./components/Composer";
import KnowledgeDialog from "./components/KnowledgeDialog";
import ConfirmDialog from "./components/ConfirmDialog";


const EMPTY_INDEX_STATUS = {
  built: false,
  building: false,
  finished_at: null,
  last_error: null
};


function App() {

  const [conversations, setConversations] = useState([]);

  const [currentId, setCurrentId] = useState(null);

  const [messages, setMessages] = useState([]);

  const [message, setMessage] = useState("");

  const [role, setRole] = useState("general");

  const [loading, setLoading] = useState(false);

  const [documents, setDocuments] = useState([]);

  const [indexStatus, setIndexStatus] = useState(EMPTY_INDEX_STATUS);

  const [uploading, setUploading] = useState(false);

  // 顶替原来的 alert：错误就地显示在输入框下方
  const [note, setNote] = useState(null);

  // 知识条目对话框：{ mode: "view" | "create" | "edit", item }
  const [dialog, setDialog] = useState(null);

  // 待确认删除的条目
  const [confirmItem, setConfirmItem] = useState(null);

  // 保存 / 删除进行中，用于禁用按钮
  const [busy, setBusy] = useState(false);

  // 触发过构建、但还没观测到它结束
  const [buildWatch, setBuildWatch] = useState(null);

  const scrollRef = useRef(null);

  const conversationsSeq = useRef(0);

  const knowledgeSeq = useRef(0);

  const pollCount = useRef(0);

  // 自己刚建出来的会话：历史由本地维护，
  // 不要让「切换会话」的加载把它覆盖掉
  const skipLoadRef = useRef(null);


  // =========================
  // 数据加载
  // =========================

  const refreshConversations = async () => {

    const seq = ++conversationsSeq.current;

    const data = await listConversations();

    if (seq !== conversationsSeq.current) return data;

    setConversations(data);

    return data;
  };

  const refreshKnowledge = async () => {

    const seq = ++knowledgeSeq.current;

    const [docs, status] = await Promise.all([
      listDocuments(),
      getIndexStatus()
    ]);

    // 文档列表和索引状态必须来自同一次刷新，
    // 否则并发刷新时会出现「状态行已更新、文档行还是旧的」
    if (seq !== knowledgeSeq.current) return { docs, status };

    setDocuments(docs);

    setIndexStatus(status);

    return { docs, status };
  };


  useEffect(() => {

    refreshConversations().catch(
      (error) => setNote({
        text: "加载会话失败：" + error.message,
        error: true
      })
    );

    refreshKnowledge().catch(
      (error) => setNote({
        text: "加载知识库失败：" + error.message,
        error: true
      })
    );

  }, []);


  // 切换会话时加载历史消息
  useEffect(() => {

    // 没有选中会话就没什么可加载的。
    // 这里不顺手 setMessages([])：清空消息由「删除会话」那个操作自己做，
    // 放在 effect 里会在挂载时多触发一次渲染，而且两个地方各清一次容易走岔
    if (currentId === null) {

      return;
    }

    // 刚落库的新会话跳过：它刚发出去的消息还在本地，
    // 重新拉取会把它冲掉
    if (skipLoadRef.current === currentId) {

      skipLoadRef.current = null;

      return;
    }

    let cancelled = false;

    getConversation(currentId)
      .then((data) => {

        if (cancelled) return;

        setMessages(data.messages || []);
      })
      .catch((error) => setNote({
        text: "加载历史失败：" + error.message,
        error: true
      }));

    return () => {

      cancelled = true;
    };

  }, [currentId]);


  // 新消息自动滚到底部
  useEffect(() => {

    const el = scrollRef.current;

    if (el) el.scrollTop = el.scrollHeight;

  }, [messages, loading]);


  // =========================
  // 后台构建期间的轮询
  // =========================

  const hasUnsettledDocs = documents.some(
    (doc) => doc.status === "pending" || doc.status === "processing"
  );

  // 盯梢中：构建已触发，但还没观测到「新一轮真的跑完了」。
  // 不能只看 building 字段——请求返回时后台任务可能还没开始，
  // 服务端会返回 building=false，那会让轮询立刻停掉、界面卡住不动。
  // 所以用触发时的 finished_at 做判据：它变了才说明这一轮结束了
  const watchingBuild =
    buildWatch !== null &&
    (
      indexStatus.building ||
      indexStatus.finished_at === buildWatch.from
    );

  const shouldPoll =
    indexStatus.building || hasUnsettledDocs || watchingBuild;

  useEffect(() => {

    if (!shouldPoll) {

      pollCount.current = 0;

      return;
    }

    const timer = setInterval(() => {

      // 兜底：文档一直卡在 pending 时不要无限轮询
      if (++pollCount.current > 40) {

        clearInterval(timer);

        return;
      }

      refreshKnowledge().catch(() => {});

    }, 1500);

    return () => clearInterval(timer);

  }, [shouldPoll]);

  const watchBuildStart = () => {

    setBuildWatch({ from: indexStatus.finished_at });

    pollCount.current = 0;
  };


  // =========================
  // 会话
  // =========================

  // 新建会话只进入「草稿」状态，不立刻在库里建记录。
  // 真正的创建推迟到发出第一条消息时（见 handleSend），
  // 这样没提问过的会话就不会在列表里留下一堆空的「新会话」
  const handleNewConversation = () => {

    setCurrentId(null);

    setMessages([]);

    setNote(null);
  };

  const handleSelectConversation = (id) => {

    if (id === currentId) return;

    setCurrentId(id);

    setNote(null);
  };

  const handleDeleteConversation = async (id) => {

    try {

      await deleteConversation(id);

      setConversations((prev) =>
        prev.filter((item) => item.id !== id)
      );

      if (id === currentId) {

        setCurrentId(null);

        setMessages([]);
      }

    } catch (error) {

      setNote({ text: "删除会话失败：" + error.message, error: true });
    }
  };


  // =========================
  // 知识库
  // =========================

  const handleUploadFiles = async (files) => {

    setUploading(true);

    setNote(null);

    try {

      for (const file of files) {

        await uploadDocument(file);
      }

      // 上传后后端会自动排队构建，这里进入盯梢状态
      watchBuildStart();

      await refreshKnowledge();

      setNote({
        text: `已上传 ${files.length} 个文件，正在后台建立知识库`
      });

    } catch (error) {

      setNote({ text: "上传失败：" + error.message, error: true });

    } finally {

      setUploading(false);
    }
  };

  // 列表或详情里的删除都先走确认框，不再用浏览器原生 confirm
  const requestDelete = (item) => {

    // 从详情里点删除时先把详情收起，避免两个弹层叠在一起
    setDialog(null);

    setConfirmItem(item);
  };

  const confirmDelete = async () => {

    if (!confirmItem) return;

    setBusy(true);

    try {

      const data = await deleteDocument(confirmItem.id);

      setConfirmItem(null);

      if (data.index_rebuild_scheduled) watchBuildStart();

      // 删除后列表立即刷新
      await refreshKnowledge();

      setNote(null);

    } catch (error) {

      setNote({ text: "删除失败：" + error.message, error: true });

    } finally {

      setBusy(false);
    }
  };

  // 新建 / 编辑手写知识。
  // 后端保存后会排队重建索引，所以和上传一样进入盯梢状态
  const saveNote = async (run, message) => {

    setBusy(true);

    try {

      await run();

      setDialog(null);

      watchBuildStart();

      await refreshKnowledge();

      setNote({ text: message });

    } catch (error) {

      setNote({ text: "保存失败：" + error.message, error: true });

    } finally {

      setBusy(false);
    }
  };

  const handleCreateNote = (title, content) => {

    saveNote(
      () => createNote(title, content),
      "已保存，正在后台更新知识库"
    );
  };

  const handleUpdateNote = (id, title, content) => {

    saveNote(
      () => updateNote(id, title, content),
      "已更新，正在后台更新知识库"
    );
  };

  const handleRebuild = async () => {

    try {

      await buildRag();

      // 先记下当前的 finished_at 作为「新一轮是否跑完」的判据，
      // 必须在改 indexStatus 之前取，否则拿到的是新值
      watchBuildStart();

      // 乐观置为构建中。
      // 后端构建往往比 1.5s 的轮询间隔还快，只靠轮询的话
      // 「知识库构建中…」这个中间态根本来不及渲染，
      // 底栏从「已就绪」到「已就绪」全程没变化，看着像没点动。
      // 下一次轮询会用服务端的真实状态覆盖它
      setIndexStatus((prev) => ({ ...prev, building: true }));

      setNote(null);

    } catch (error) {

      // 409 = 已经有一次构建在跑，跟着它一起轮询即可
      if (error.status === 409) {

        watchBuildStart();

        await refreshKnowledge().catch(() => {});

        return;
      }

      setNote({ text: "构建失败：" + error.message, error: true });
    }
  };


  // =========================
  // 发送
  // =========================

  // 系统自动选模式，用户不再需要选：
  // 知识库已构建就走 RAG（回答会带来源），否则走普通对话
  const autoMode = indexStatus.built ? "rag" : "chat";

  const handleSend = async (override) => {

    const text = (override ?? message).trim();

    if (!text || loading) return;

    let conversationId = currentId;

    setLoading(true);

    setNote(null);

    try {

      if (conversationId === null) {

        const conversation = await createConversation();

        conversationId = conversation.id;

        skipLoadRef.current = conversationId;

        setCurrentId(conversationId);

        setConversations((prev) => [conversation, ...prev]);
      }

      // 乐观渲染用户消息
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text }
      ]);

      setMessage("");

      const data = await sendMessage(
        conversationId,
        text,
        autoMode,
        role
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
          tool_calls: data.tool_calls || []
        }
      ]);

      // 首条消息会改写会话标题，刷新一下列表
      refreshConversations().catch(() => {});

    } catch (error) {

      setNote({ text: "回答失败：" + error.message, error: true });

    } finally {

      setLoading(false);
    }
  };


  // =========================
  // 渲染
  // =========================

  const currentConversation = conversations.find(
    (item) => item.id === currentId
  );

  // 没发过消息的会话不进列表。
  // 正在看的那个例外：刚发出第一条消息时本地还没有最新的 message_count，
  // 不例外的话它会从列表里闪一下
  const visibleConversations = conversations.filter(
    (item) => (item.message_count || 0) > 0 || item.id === currentId
  );

  return (

    <div className="app">

      <Sidebar

        conversations={visibleConversations}
        currentId={currentId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}

        role={role}
        onRoleChange={setRole}

        documents={documents}
        onDeleteDocument={(id) => requestDelete(
          documents.find((item) => item.id === id)
        )}
        onOpenDocument={(item) => setDialog({ mode: "view", item })}
        onNewNote={() => setDialog({ mode: "create", item: null })}

        indexStatus={indexStatus}
        onRebuild={handleRebuild}
        building={indexStatus.building}
      />

      <div className="main">

        <div className="chat-head">

          <div className="chat-title">
            {currentConversation?.title || "新会话"}
          </div>

          <div className="chat-head-right">

            <span
              className={"mode-pill" + (autoMode === "rag" ? " on" : "")}
              title={
                autoMode === "rag"
                  ? "知识库已就绪，回答会附上参考来源"
                  : "尚未建立知识库，当前为普通对话"
              }
            >
              <span className="mode-pill-dot" />
              {autoMode === "rag" ? "知识库问答" : "普通对话"}
            </span>

          </div>

        </div>

        <ChatArea
          messages={messages}
          loading={loading}
          scrollRef={scrollRef}
          hasIndex={indexStatus.built}
          onSuggestion={handleSend}
        />

        <Composer
          value={message}
          onChange={setMessage}
          onSend={() => handleSend()}
          loading={loading}
          onUploadFiles={handleUploadFiles}
          uploading={uploading}
          note={note?.text}
          noteError={note?.error}
        />

      </div>

      <KnowledgeDialog

        // 换条目或换模式时靠 key 重挂载，让表单初值刷新
        key={
          dialog
            ? `${dialog.mode}-${dialog.item?.id ?? "new"}`
            : "closed"
        }

        mode={dialog?.mode}
        item={dialog?.item}
        busy={busy}
        onClose={() => setDialog(null)}
        onCreate={handleCreateNote}
        onUpdate={handleUpdateNote}
        onEdit={(item) => setDialog({ mode: "edit", item })}
        onDelete={requestDelete}
      />

      <ConfirmDialog
        open={confirmItem !== null}
        title="确认删除"
        message={
          `「${confirmItem?.filename || ""}」将被删除，`
          + "并从检索索引中移除，此操作不可撤销。"
        }
        busy={busy}
        onCancel={() => setConfirmItem(null)}
        onConfirm={confirmDelete}
      />

    </div>
  );
}


export default App;
