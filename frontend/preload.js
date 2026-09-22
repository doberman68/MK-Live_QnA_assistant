'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Config
  getConfig:        ()       => ipcRenderer.invoke('get-config'),
  saveConfig:       (config) => ipcRenderer.invoke('save-config', config),

  // Devices / models
  getDevices:       ()       => ipcRenderer.invoke('get-devices'),
  getOllamaModels:  ()       => ipcRenderer.invoke('get-ollama-models'),

  // Capture control
  startCapture:     ()       => ipcRenderer.invoke('start-capture'),
  stopCapture:      ()       => ipcRenderer.invoke('stop-capture'),

  // Manual trigger
  triggerManual:    ()       => ipcRenderer.invoke('trigger-manual'),

  // Status
  getStatus:        ()       => ipcRenderer.invoke('get-status'),

  // Events pushed from main → renderer
  onAnswer:         (cb) => ipcRenderer.on('answer',     (_, data) => cb(data)),
  onTranscript:     (cb) => ipcRenderer.on('transcript', (_, data) => cb(data)),
  onStatus:         (cb) => ipcRenderer.on('status',     (_, data) => cb(data)),
  onError:          (cb) => ipcRenderer.on('error',      (_, data) => cb(data)),

  // Cleanup
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),

  // Window management
  openSettings:     ()       => ipcRenderer.send('open-settings'),
  closeSettings:    ()       => ipcRenderer.send('close-settings'),
});
