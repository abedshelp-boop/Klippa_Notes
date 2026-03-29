import React, { useState, useEffect } from 'react';

const API_URL = 'http://localhost:8765';

export default function Settings({ onClose }) {
  const [openaiKey, setOpenaiKey] = useState('');
  const [bufferLength, setBufferLength] = useState(120);
  const [arabizeEnabled, setArabizeEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/settings`)
      .then((r) => r.json())
      .then((data) => {
        if (data.buffer_length) setBufferLength(data.buffer_length);
        if (data.arabize_enabled !== undefined) setArabizeEnabled(data.arabize_enabled);
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${API_URL}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          openai_api_key: openaiKey || undefined,
          buffer_length: bufferLength,
          arabize_enabled: arabizeEnabled,
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
    <div className="settings-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="settings-panel">
        <div className="settings-title">Settings</div>

        <div className="settings-group">
          <label className="settings-label">OpenAI API Key</label>
          <input
            className="settings-input"
            type="password"
            placeholder="sk-..."
            value={openaiKey}
            onChange={(e) => setOpenaiKey(e.target.value)}
          />
        </div>

        <div className="settings-group">
          <label className="settings-label">Audio Buffer Length (seconds)</label>
          <input
            className="settings-input"
            type="number"
            min={30}
            max={300}
            value={bufferLength}
            onChange={(e) => setBufferLength(Number(e.target.value))}
          />
        </div>

        <div className="settings-group">
          <label className="settings-label">Arabic Script Conversion</label>
          <div className="settings-toggle-row">
            <button
              className={`settings-toggle ${arabizeEnabled ? 'active' : ''}`}
              onClick={() => setArabizeEnabled(!arabizeEnabled)}
              type="button"
            >
              <span className="settings-toggle-knob" />
            </button>
            <span className="settings-toggle-description">
              Convert transliterated Arabic words to Arabic script
            </span>
          </div>
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
