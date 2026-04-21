import React, { useEffect, useState } from 'react';

const API_URL = 'http://localhost:8765';

export default function Settings({ onClose }) {
  const [openaiKey, setOpenaiKey] = useState('');
  const [assemblyaiKey, setAssemblyaiKey] = useState('');
  const [hasOpenaiKey, setHasOpenaiKey] = useState(false);
  const [hasAssemblyaiKey, setHasAssemblyaiKey] = useState(false);
  const [bufferLength, setBufferLength] = useState(600);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/settings`)
      .then((r) => r.json())
      .then((data) => {
        if (data.buffer_length) setBufferLength(data.buffer_length);
        setHasOpenaiKey(!!data.has_openai_key);
        setHasAssemblyaiKey(!!data.has_assemblyai_key);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${API_URL}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          openai_api_key: openaiKey || undefined,
          assemblyai_api_key: assemblyaiKey || undefined,
          buffer_length: bufferLength,
        }),
      });
      onClose();
    } catch (err) {
      console.error('[Settings] Save failed:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="settings-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="settings-panel">
        <div className="settings-eyebrow">DEEN · SETTINGS</div>
        <div className="settings-title">Preferences</div>

        <div className="settings-group">
          <label className="settings-label">
            AssemblyAI API Key {hasAssemblyaiKey && <span style={{ opacity: 0.5 }}>· set</span>}
          </label>
          <input
            className="settings-input"
            type="password"
            placeholder={hasAssemblyaiKey ? 'leave blank to keep existing key' : 'your AssemblyAI key'}
            value={assemblyaiKey}
            onChange={(e) => setAssemblyaiKey(e.target.value)}
          />
          <div className="settings-hint" style={{ fontSize: 12, opacity: 0.6, marginTop: 4 }}>
            Primary transcription engine (Universal-3 Pro with Islamic keyterms).
          </div>
        </div>

        <div className="settings-group">
          <label className="settings-label">
            OpenAI API Key {hasOpenaiKey && <span style={{ opacity: 0.5 }}>· set</span>}
          </label>
          <input
            className="settings-input"
            type="password"
            placeholder={hasOpenaiKey ? 'leave blank to keep existing key' : 'sk-...'}
            value={openaiKey}
            onChange={(e) => setOpenaiKey(e.target.value)}
          />
          <div className="settings-hint" style={{ fontSize: 12, opacity: 0.6, marginTop: 4 }}>
            Used for note generation (GPT-4o-mini) and transcription fallback.
          </div>
        </div>

        <div className="settings-group">
          <label className="settings-label">Audio Buffer Length (seconds)</label>
          <input
            className="settings-input"
            type="number"
            min={60}
            max={1800}
            value={bufferLength}
            onChange={(e) => setBufferLength(Number(e.target.value))}
          />
        </div>

        <div className="settings-actions">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
