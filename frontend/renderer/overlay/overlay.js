'use strict';

let isCapturing = false;
let isAutoMode = false;
let isThinking = false;

const statusDot   = document.getElementById('status-dot');
const captureBtn  = document.getElementById('capture-btn');
const triggerBtn  = document.getElementById('trigger-btn');
const clearBtn    = document.getElementById('clear-btn');
const modeToggle  = document.getElementById('mode-toggle');
const settingsBtn = document.getElementById('settings-btn');
const answerPanel = document.getElementById('answer-panel');
const emptyState  = document.getElementById('empty-state');

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

window.addEventListener('DOMContentLoaded', async () => {
  const config = await window.electronAPI.getConfig().catch(() => null);
  if (config) {
    isAutoMode = config.app_mode === 'auto';
    modeToggle.checked = isAutoMode;
    updateModeUI();
  }

  // Pull live status from backend
  const status = await window.electronAPI.getStatus().catch(() => null);
  if (status) {
    setCapturing(status.capturing);
    isAutoMode = status.mode === 'auto';
    modeToggle.checked = isAutoMode;
    updateModeUI();
  }

  // Subscribe to WebSocket-pushed events
  window.electronAPI.onAnswer(handleAnswer);
  window.electronAPI.onStatus(handleStatus);
  window.electronAPI.onError(handleError);
});

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------

captureBtn.addEventListener('click', async () => {
  captureBtn.disabled = true;
  try {
    if (isCapturing) {
      await window.electronAPI.stopCapture();
    } else {
      await window.electronAPI.startCapture();
    }
  } finally {
    captureBtn.disabled = false;
  }
});

triggerBtn.addEventListener('click', async () => {
  if (isThinking) return;
  setThinking(true);
  try {
    await window.electronAPI.triggerManual();
    // Answer arrives via WebSocket onAnswer
  } catch (e) {
    appendError('Failed to contact backend.');
  } finally {
    setThinking(false);
  }
});

modeToggle.addEventListener('change', async () => {
  const newMode = modeToggle.checked ? 'auto' : 'manual';
  const config = await window.electronAPI.getConfig().catch(() => null);
  if (config) {
    await window.electronAPI.saveConfig({ ...config, app_mode: newMode }).catch(() => {});
  }
  isAutoMode = modeToggle.checked;
  updateModeUI();
});

settingsBtn.addEventListener('click', () => {
  window.electronAPI.openSettings();
});

clearBtn.addEventListener('click', () => {
  // Remove all answer cards, keep empty state hidden until needed
  const cards = answerPanel.querySelectorAll('.answer-card, .error-card, .thinking');
  cards.forEach(c => c.remove());
  updateEmptyState();
});

// ---------------------------------------------------------------------------
// WebSocket event handlers
// ---------------------------------------------------------------------------

function handleAnswer({ question, answer }) {
  setThinking(false);
  appendAnswer(question, answer);
}

function handleStatus({ capturing, mode }) {
  setCapturing(capturing);
  isAutoMode = mode === 'auto';
  modeToggle.checked = isAutoMode;
  updateModeUI();
}

function handleError({ message }) {
  appendError(message);
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

function setCapturing(active) {
  isCapturing = active;
  statusDot.classList.toggle('active', active);
  captureBtn.textContent = active ? 'Stop' : 'Start';
  captureBtn.classList.toggle('active', active);
}

function updateModeUI() {
  const isManual = !isAutoMode;
  triggerBtn.classList.toggle('hidden', !isManual);
}

function setThinking(active) {
  isThinking = active;
  triggerBtn.disabled = active;

  const existing = answerPanel.querySelector('.thinking');
  if (active && !existing) {
    const el = document.createElement('div');
    el.className = 'thinking';
    el.innerHTML = `<span>Analyzing...</span>
      <div class="thinking-dots">
        <span></span><span></span><span></span>
      </div>`;
    answerPanel.prepend(el);
    updateEmptyState();
  } else if (!active && existing) {
    existing.remove();
    updateEmptyState();
  }
}

function appendAnswer(question, answer) {
  const card = document.createElement('div');
  card.className = 'answer-card';
  card.innerHTML = `
    <div class="question">Question</div>
    <div class="question-text">${escapeHtml(question)}</div>
    <div class="answer">${escapeHtml(answer)}</div>
  `;
  answerPanel.prepend(card);

  // Cap DOM at 10 cards
  const cards = answerPanel.querySelectorAll('.answer-card');
  if (cards.length > 10) cards[cards.length - 1].remove();

  updateEmptyState();
}

function appendError(message) {
  const el = document.createElement('div');
  el.className = 'error-card answer-card';
  el.style.borderColor = 'rgba(239,68,68,0.3)';
  el.innerHTML = `<div class="question" style="color:#f87171">Error</div>
                  <div class="answer" style="color:#f87171">${escapeHtml(message)}</div>`;
  answerPanel.prepend(el);
  updateEmptyState();
}

function updateEmptyState() {
  const hasContent = answerPanel.querySelectorAll('.answer-card, .thinking, .error-card').length > 0;
  emptyState.style.display = hasContent ? 'none' : 'flex';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}
