import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json' } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Request failed. Please try again.');
  }
  return response.status === 204 ? null : response.json();
}

function App() {
  const [topics, setTopics] = useState([]), [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]), [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(false);
  const [error, setError] = useState(''), [health, setHealth] = useState(null);
  const bottom = useRef(null), selection = useRef(0);
  useEffect(() => {
    api('/topics').then(setTopics).catch(e => setError(e.message));
    const check = () => api('/health').then(setHealth).catch(() => setHealth(null));
    check(); const interval = setInterval(check, 15000); return () => clearInterval(interval);
  }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);
  async function select(id) {
    const version = ++selection.current;
    setActive(id); setMessages([]); setDraft(''); setError(''); setLoading(true);
    try { const data = await api(`/topics/${id}/messages`); if (version === selection.current) setMessages(data); }
    catch (e) { if (version === selection.current) setError(e.message); }
    finally { if (version === selection.current) setLoading(false); }
  }
  function newChat() { ++selection.current; setActive(null); setMessages([]); setDraft(''); setError(''); setLoading(false); }
  async function send(event) {
    event.preventDefault(); if (!draft.trim() || busy || loading) return;
    const content = draft.trim(); setBusy(true); setError('');
    try {
      let id = active;
      if (!id) { const topic = await api('/topics', { method: 'POST', body: '{}' }); id = topic.id; setActive(id); setTopics(t => [topic, ...t]); }
      const data = await api(`/topics/${id}/messages`, { method: 'POST', body: JSON.stringify({ content }) });
      setMessages(data); setDraft('');
      setTopics(t => t.map(topic => topic.id === id && messages.length === 0 ? { ...topic, title: content.slice(0, 70) } : topic));
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function remove() {
    if (!window.confirm('Delete this conversation and all its messages?')) return;
    try { await api(`/topics/${active}`, { method: 'DELETE' }); setTopics(t => t.filter(x => x.id !== active)); newChat(); }
    catch (e) { setError(e.message); }
  }
  const ready = health?.ollama === 'online' && health.model_ready;
  return <div className="app">
    <aside><a className="brand" href="/">◈ <span>Local Chat</span></a><button className="new" disabled={busy} onClick={newChat}>＋ New conversation</button><p className="label">YOUR CONVERSATIONS</p><nav aria-label="Conversations">{topics.map(t => <button key={t.id} disabled={busy} className={active === t.id ? 'topic selected' : 'topic'} onClick={() => select(t.id)}>{t.title}</button>)}{!topics.length && <p className="muted">Your conversations will appear here.</p>}</nav><div className="local">● Stored on this laptop<small>SQLite · No cloud account</small></div></aside>
    <main><header><div><strong>Qwen3 <span>1.7B</span></strong><small><i className={ready ? 'dot online' : 'dot'}/>{ready ? 'Ready on your laptop' : health?.ollama === 'online' ? 'Model needs downloading' : 'Ollama unavailable'}</small></div>{active && <button disabled={busy || loading} className="delete" onClick={remove}>Delete conversation</button>}</header>
      <section className="conversation" aria-label="Messages" aria-live="polite">{!messages.length && !loading && <div className="welcome"><div className="orb">◈</div><p className="eyebrow">YOUR SPACE TO THINK</p><h1>Big ideas. Local intelligence.</h1><p>Ask a question, untangle an idea, or start something new.<br/>Your conversations stay on this laptop.</p><div className="suggestions">{['Explain a complex idea simply', 'Help me plan my next project', 'Write a Python function'].map(s => <button disabled={busy} key={s} onClick={() => setDraft(s)}>{s} ↗</button>)}</div></div>}{loading && <p className="muted">Loading conversation…</p>}{messages.map(m => <article key={m.id} className={`message ${m.role}`}><div className="role">{m.role === 'user' ? 'YOU' : '◈ QWEN3'}</div><div className="content">{m.content}</div></article>)}{busy && <article className="message assistant"><div className="role">◈ QWEN3</div><div className="content thinking">Thinking on your laptop…</div></article>}<div ref={bottom}/></section>
      <footer>{error && <div role="alert" className="error">{error}</div>}<form onSubmit={send}><textarea aria-label="Message" placeholder="Message Qwen3…" value={draft} maxLength={32000} disabled={busy || loading} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(e); } }}/><button className="send" aria-label="Send message" disabled={busy || loading || !draft.trim()} type="submit">↑</button></form><p className="footnote">Powered by Ollama · Enter to send · Shift + Enter for a new line</p></footer>
    </main></div>;
}
createRoot(document.getElementById('root')).render(<App/>);
