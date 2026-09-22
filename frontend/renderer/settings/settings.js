'use strict';

const PROVIDER_IDS = ['ollama', 'openai', 'anthropic', 'gemini'];

window.addEventListener('DOMContentLoaded', async () => {
  await loadAll();
  setupEventListeners();
});

async function loadAll() {
  const [config, devices, ollamaModels] = await Promise.all([
    window.electronAPI.getConfig().catch(() => null),
    window.electronAPI.getDevices().catch(() => []),
    window.electronAPI.getOllamaModels().catch(() => []),
  ]);

  if (devices.length) populateDeviceDropdowns(devices);
  if (ollamaModels.length) populateOllamaModels(ollamaModels);
  if (config) fillForm(config);
}

function setupEventListeners() {
  document.getElementById('llm-provider').addEventListener('change', (e) => {
    showProviderFields(e.target.value);
  });

  document.getElementById('refresh-ollama-btn').addEventListener('click', async () => {
    const models = await window.electronAPI.getOllamaModels().catch(() => []);
    populateOllamaModels(models);
  });

  document.getElementById('cancel-btn').addEventListener('click', () => {
    window.electronAPI.closeSettings();
  });

  document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const config = readForm();
    await window.electronAPI.saveConfig(config).catch(console.error);
    flashSaved();
  });
}

// ---------------------------------------------------------------------------
// Form population
// ---------------------------------------------------------------------------

function populateDeviceDropdowns(devices) {
  const micSel = document.getElementById('mic-device');
  const loopSel = document.getElementById('loopback-device');

  // Clear existing options (keep "Default")
  while (micSel.options.length > 1) micSel.remove(1);
  while (loopSel.options.length > 1) loopSel.remove(1);

  for (const dev of devices) {
    const opt = new Option(`${dev.name} (${dev.type})`, dev.index);
    if (dev.type === 'loopback') {
      loopSel.add(opt);
    } else {
      micSel.add(opt.cloneNode(true));
    }
  }
}

function populateOllamaModels(models) {
  const sel = document.getElementById('ollama-model');
  const current = sel.value;
  while (sel.options.length) sel.remove(0);
  if (!models.length) {
    sel.add(new Option('llama3', 'llama3'));
    return;
  }
  for (const m of models) sel.add(new Option(m, m));
  sel.value = current || models[0];
}

function fillForm(config) {
  setVal('audio-source', config.audio_source);
  setVal('mic-device', config.mic_device_index ?? '');
  setVal('loopback-device', config.loopback_device_index ?? '');
  setVal('stt-provider', config.stt_provider);
  setVal('whisper-model', config.whisper_model_size);
  setVal('llm-provider', config.llm_provider);
  setVal('ollama-url', config.ollama_base_url);
  setVal('ollama-model', config.ollama_model);
  setVal('openai-key', config.openai_api_key);
  setVal('openai-model', config.openai_model);
  setVal('anthropic-key', config.anthropic_api_key);
  setVal('anthropic-model', config.anthropic_model);
  setVal('gemini-key', config.gemini_api_key);
  setVal('gemini-model', config.gemini_model);
  setVal('lookback', config.manual_lookback_seconds);
  setVal('auto-interval', config.auto_check_interval_seconds);
  showProviderFields(config.llm_provider);
}

function setVal(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined && value !== null) el.value = value;
}

function showProviderFields(provider) {
  for (const id of PROVIDER_IDS) {
    const el = document.getElementById(`fields-${id}`);
    if (el) el.classList.toggle('visible', id === provider);
  }
}

// ---------------------------------------------------------------------------
// Form reading
// ---------------------------------------------------------------------------

function readForm() {
  const g = (id) => document.getElementById(id)?.value ?? '';
  const gi = (id) => { const v = parseInt(g(id), 10); return isNaN(v) ? null : v; };

  return {
    audio_source: g('audio-source'),
    mic_device_index: gi('mic-device'),
    loopback_device_index: gi('loopback-device'),
    stt_provider: g('stt-provider'),
    whisper_model_size: g('whisper-model'),
    llm_provider: g('llm-provider'),
    ollama_base_url: g('ollama-url') || 'http://localhost:11434',
    ollama_model: g('ollama-model') || 'llama3',
    openai_api_key: g('openai-key'),
    openai_model: g('openai-model'),
    anthropic_api_key: g('anthropic-key'),
    anthropic_model: g('anthropic-model'),
    gemini_api_key: g('gemini-key'),
    gemini_model: g('gemini-model'),
    manual_lookback_seconds: gi('lookback') ?? 45,
    auto_check_interval_seconds: gi('auto-interval') ?? 5,
  };
}

function flashSaved() {
  const el = document.getElementById('saved-msg');
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2500);
}
