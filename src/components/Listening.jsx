import React, { useEffect } from 'react';

const STAGE_COPY = {
  listening: { label: 'Listening' },
  command: { label: 'Transcribing · note what was said' },
  processing: { label: 'Processing · writing it up' },
  saved: { label: 'Saved to your notes' },
};

const WAVE_BARS = Array.from({ length: 22 });

export default function Listening({ stage, transcript, onDismiss }) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onDismiss?.();
      if (e.key === 'Enter') onDismiss?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onDismiss]);

  const copy = STAGE_COPY[stage] || STAGE_COPY.listening;

  return (
    <div className="listening-overlay">
      <div className="listening-rings">
        <div className="listening-ring d1" />
        <div className="listening-ring d2" />
        <div className="listening-ring d3" />
      </div>

      <div className="listening-panel">
        <div className="listening-orb">
          <div className="listening-orb-core" />
          <div className="listening-orb-ring">
            <div className="listening-orb-satellite" />
          </div>
        </div>

        <div className="listening-transcript">
          <div className="listening-stage-label">{copy.label}</div>

          {stage === 'listening' && (
            <>
              <div className="listening-prompt">
                Hey Deen,<em> I'm listening…</em>
              </div>
              <div className="listening-wave">
                {WAVE_BARS.map((_, i) => (
                  <span
                    key={i}
                    className="listening-wave-bar"
                    style={{
                      animationDuration: `${0.6 + (i % 5) * 0.12}s`,
                      animationDelay: `${i * 0.03}s`,
                    }}
                  />
                ))}
              </div>
            </>
          )}

          {(stage === 'command' || stage === 'processing') && (
            <div className="listening-transcribe">
              {transcript ? (
                <>"{transcript}<span className="listening-caret">|</span>"</>
              ) : (
                <em>Give me a moment…</em>
              )}
            </div>
          )}

          {stage === 'saved' && (
            <div className="listening-saved">
              Got it. <em>Added to your notes.</em>
            </div>
          )}
        </div>

        <div className="listening-hints">
          <span>ESC to cancel</span>
          <span className="listening-hint-divider" />
          <span>Say "Stop" when done</span>
          <span className="listening-hint-divider" />
          <button className="listening-dismiss" onClick={onDismiss}>
            DISMISS ↵
          </button>
        </div>
      </div>
    </div>
  );
}
