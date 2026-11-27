/* ==========================================================================
   PCResourceMonitor — iPad Mini 1 Dashboard Client Logic
   Target: iOS 9.3.5 Mobile Safari (WebKit iOS 9)
   Strict ES5 JavaScript • XMLHttpRequest Polling • Zero Modern ES6+ Features
   ========================================================================== */

(function () {
  'use strict';

  // State Management
  var POLL_INTERVAL_MS = 1000;
  var XHR_TIMEOUT_MS = 2500;
  var STALE_THRESHOLD_MS = 3500;

  var lastSequence = 0;
  var lastSuccessTime = 0;
  var consecutiveFailures = 0;
  var isPollingActive = false;
  var pollTimer = null;

  // Cached DOM Element References
  var dom = {};

  // ==========================================================================
  // Helper Utilities (Strict ES5)
  // ==========================================================================

  function setText(el, text) {
    if (!el) return;
    if (typeof el.textContent !== 'undefined') {
      el.textContent = text;
    } else {
      el.innerText = text;
    }
  }

  function formatBytes(bytes) {
    if (bytes === null || typeof bytes === 'undefined' || isNaN(bytes)) {
      return { value: '--', unit: 'GB' };
    }
    var b = Number(bytes);
    if (b <= 0) return { value: '0.0', unit: 'B' };
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = Math.floor(Math.log(b) / Math.log(1024));
    if (i < 0) i = 0;
    if (i >= units.length) i = units.length - 1;
    var precision = i >= 3 ? 1 : 0;
    var v = (b / Math.pow(1024, i)).toFixed(precision);
    return { value: v, unit: units[i] };
  }

  function formatRate(bytesPerSec) {
    if (bytesPerSec === null || typeof bytesPerSec === 'undefined' || isNaN(bytesPerSec)) {
      return '--';
    }
    var r = Number(bytesPerSec);
    if (r < 0) return '0 B/s';
    if (r < 1024) return r.toFixed(0) + ' B/s';
    if (r < 1048576) return (r / 1024).toFixed(1) + ' KB/s';
    if (r < 1073741824) return (r / 1048576).toFixed(1) + ' MB/s';
    return (r / 1073741824).toFixed(2) + ' GB/s';
  }

  function formatUptime(seconds) {
    if (seconds === null || typeof seconds === 'undefined' || isNaN(seconds)) {
      return '--:--:--';
    }
    var s = Math.floor(Number(seconds));
    var days = Math.floor(s / 86400);
    s %= 86400;
    var hours = Math.floor(s / 3600);
    s %= 3600;
    var minutes = Math.floor(s / 60);
    var secs = s % 60;

    var pad = function (n) {
      return (n < 10 ? '0' : '') + n;
    };

    if (days > 0) {
      return days + 'd ' + pad(hours) + 'h ' + pad(minutes) + 'm ' + pad(secs) + 's';
    }
    return pad(hours) + ':' + pad(minutes) + ':' + pad(secs);
  }

  function formatBootTime(timestamp) {
    if (!timestamp || isNaN(timestamp)) return '--';
    var d = new Date(Number(timestamp) * 1000);
    if (isNaN(d.getTime())) return '--';
    var pad = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' +
           pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  // ==========================================================================
  // DOM Cache Initialization
  // ==========================================================================

  function initDomCache() {
    // HUD Header elements
    dom.hudHostname = document.getElementById('hud-hostname');
    dom.hudOs = document.getElementById('hud-os');
    dom.hudBadge = document.getElementById('hud-status-badge');
    dom.hudSequence = document.getElementById('hud-sequence');
    dom.hudAge = document.getElementById('hud-age');
    dom.hudUptimeVal = document.getElementById('hud-uptime-val');

    // CPU Card elements
    dom.cpuName = document.getElementById('cpu-name');
    dom.cpuTopology = document.getElementById('cpu-topology');
    dom.cpuUsageVal = document.getElementById('cpu-usage-val');
    dom.cpuUsageBar = document.getElementById('cpu-usage-bar');
    dom.cpuFreqVal = document.getElementById('cpu-freq-val');
    dom.cpuTempVal = document.getElementById('cpu-temp-val');
    dom.cpuTempBadge = document.getElementById('cpu-temp-badge');
    dom.cpuPowerVal = document.getElementById('cpu-power-val');
    dom.cpuPowerBadge = document.getElementById('cpu-power-badge');
    dom.cpuCoresMatrix = document.getElementById('cpu-cores-matrix');

    // NVIDIA GPU elements
    dom.gpuNvidiaName = document.getElementById('gpu-nvidia-name');
    dom.gpuNvidiaUsageVal = document.getElementById('gpu-nvidia-usage-val');
    dom.gpuNvidiaUsageBar = document.getElementById('gpu-nvidia-usage-bar');
    dom.gpuNvidiaTempVal = document.getElementById('gpu-nvidia-temp-val');
    dom.gpuNvidiaTempBadge = document.getElementById('gpu-nvidia-temp-badge');
    dom.gpuNvidiaPowerVal = document.getElementById('gpu-nvidia-power-val');
    dom.gpuNvidiaPowerBadge = document.getElementById('gpu-nvidia-power-badge');
    dom.gpuNvidiaClockVal = document.getElementById('gpu-nvidia-clock-val');
    dom.gpuNvidiaVramText = document.getElementById('gpu-nvidia-vram-text');
    dom.gpuNvidiaVramBar = document.getElementById('gpu-nvidia-vram-bar');

    // System RAM elements
    dom.ramMetaBadge = document.getElementById('ram-meta-badge');
    dom.ramUsageVal = document.getElementById('ram-usage-val');
    dom.ramUsageBar = document.getElementById('ram-usage-bar');
    dom.ramUsageSubtext = document.getElementById('ram-usage-subtext');
    dom.ramUsedVal = document.getElementById('ram-used-val');
    dom.ramAvailVal = document.getElementById('ram-avail-val');
    dom.ramTotalVal = document.getElementById('ram-total-val');

    // AMD APU elements
    dom.gpuAmdName = document.getElementById('gpu-amd-name');
    dom.gpuAmdVramDedicated = document.getElementById('gpu-amd-vram-dedicated');
    dom.gpuAmdVramShared = document.getElementById('gpu-amd-vram-shared');
    dom.gpuAmdType = document.getElementById('gpu-amd-type');

    // Storage elements
    dom.storageVolumeCount = document.getElementById('storage-volume-count');
    dom.storageVolumesList = document.getElementById('storage-volumes-list');
    dom.storageIoStatus = document.getElementById('storage-io-status');
    dom.storageReadRate = document.getElementById('storage-read-rate');
    dom.storageWriteRate = document.getElementById('storage-write-rate');

    // Network elements
    dom.netInterfaceBadge = document.getElementById('net-interface-badge');
    dom.netDownRate = document.getElementById('net-down-rate');
    dom.netUpRate = document.getElementById('net-up-rate');
    dom.netPrimaryAdapter = document.getElementById('net-primary-adapter');
    dom.netSummaryStatus = document.getElementById('net-summary-status');

    // Diagnostics elements
    dom.diagHostname = document.getElementById('diag-hostname');
    dom.diagOs = document.getElementById('diag-os');
    dom.diagCpuName = document.getElementById('diag-cpu-name');
    dom.diagBootTime = document.getElementById('diag-boot-time');

    // Toast element
    dom.toast = document.getElementById('connection-toast');
    dom.toastMessage = document.getElementById('toast-message');

    // Pre-populate 12 Core Bar Elements in Matrix
    if (dom.cpuCoresMatrix) {
      dom.cpuCoresMatrix.innerHTML = '';
      dom.coreFills = [];
      for (var c = 0; c < 12; c++) {
        var wrap = document.createElement('div');
        wrap.className = 'core-bar-wrap';
        wrap.title = 'Core ' + c;
        var fill = document.createElement('div');
        fill.className = 'core-bar-fill';
        fill.id = 'cpu-core-fill-' + c;
        wrap.appendChild(fill);
        dom.cpuCoresMatrix.appendChild(wrap);
        dom.coreFills.push(fill);
      }
    }
  }

  // ==========================================================================
  // Connection State Machine & HUD Presentation
  // ==========================================================================

  function updateStatusBadge(state, label) {
    if (!dom.hudBadge) return;
    dom.hudBadge.className = 'hud-badge status-' + state;
    setText(dom.hudBadge, label);

    if (state === 'offline') {
      if (dom.toast) {
        dom.toast.className = 'connection-toast';
        setText(dom.toastMessage, 'Host connection lost. Retrying over USB tunnel...');
      }
    } else {
      if (dom.toast) {
        dom.toast.className = 'connection-toast toast-hidden';
      }
    }
  }

  function checkFreshness() {
    if (lastSuccessTime === 0) return;
    var now = new Date().getTime();
    var ageSec = Math.floor((now - lastSuccessTime) / 1000);

    if (dom.hudAge) {
      setText(dom.hudAge, ageSec + 's ago');
    }

    if (ageSec >= Math.floor(STALE_THRESHOLD_MS / 1000) && consecutiveFailures === 0) {
      updateStatusBadge('stale', 'STALE (' + ageSec + 's)');
    }
  }

  // ==========================================================================
  // Section Renderers
  // ==========================================================================

  function renderCpu(cpu, system) {
    if (!cpu || cpu.status === 'error') {
      setText(dom.cpuUsageVal, '--');
      if (dom.cpuUsageBar) dom.cpuUsageBar.style.width = '0%';
      return;
    }

    // CPU Model & Topology
    if (system && system.cpu_name) {
      setText(dom.cpuName, system.cpu_name);
    }
    var phys = (typeof cpu.cores_physical === 'number') ? cpu.cores_physical : '--';
    var log = (typeof cpu.cores_logical === 'number') ? cpu.cores_logical : '--';
    setText(dom.cpuTopology, phys + ' Cores / ' + log + ' Threads');

    // Total CPU Utilization
    if (typeof cpu.usage_percent === 'number') {
      var usage = cpu.usage_percent;
      setText(dom.cpuUsageVal, Math.round(usage) + '');
      if (dom.cpuUsageBar) {
        dom.cpuUsageBar.style.width = clamp(usage, 0, 100) + '%';
        if (usage >= 85) {
          dom.cpuUsageBar.className = 'progress-fill fill-cyan fill-alert';
        } else {
          dom.cpuUsageBar.className = 'progress-fill fill-cyan';
        }
      }
    } else {
      setText(dom.cpuUsageVal, '--');
      if (dom.cpuUsageBar) dom.cpuUsageBar.style.width = '0%';
    }

    // Frequency
    if (cpu.frequency_mhz && !isNaN(cpu.frequency_mhz)) {
      var ghz = (Number(cpu.frequency_mhz) / 1000).toFixed(2);
      setText(dom.cpuFreqVal, ghz + ' GHz');
    } else {
      setText(dom.cpuFreqVal, '-- GHz');
    }

    // Package Temperature (Honest unavailable handling)
    var tempObj = cpu.temperature_c;
    if (tempObj && tempObj.status === 'ok' && typeof tempObj.value === 'number') {
      setText(dom.cpuTempVal, tempObj.value.toFixed(1) + ' \u00B0C');
      if (dom.cpuTempBadge) dom.cpuTempBadge.style.display = 'none';
    } else {
      setText(dom.cpuTempVal, '-- \u00B0C');
      if (dom.cpuTempBadge) {
        dom.cpuTempBadge.className = 'sub-badge badge-na';
        dom.cpuTempBadge.style.display = 'inline-block';
        setText(dom.cpuTempBadge, 'BRIDGE OFFLINE');
      }
    }

    // Package Power (Honest unavailable handling)
    var powerObj = cpu.power_watts;
    if (powerObj && powerObj.status === 'ok' && typeof powerObj.value === 'number') {
      setText(dom.cpuPowerVal, powerObj.value.toFixed(1) + ' W');
      if (dom.cpuPowerBadge) dom.cpuPowerBadge.style.display = 'none';
    } else {
      setText(dom.cpuPowerVal, '-- W');
      if (dom.cpuPowerBadge) {
        dom.cpuPowerBadge.className = 'sub-badge badge-na';
        dom.cpuPowerBadge.style.display = 'inline-block';
        setText(dom.cpuPowerBadge, 'N/A');
      }
    }

    // Per-core Matrix
    var cores = cpu.per_core_percent;
    if (cores && cores.length) {
      if (!dom.coreFills || dom.coreFills.length !== cores.length) {
        if (dom.cpuCoresMatrix) {
          dom.cpuCoresMatrix.innerHTML = '';
          dom.coreFills = [];
          for (var c = 0; c < cores.length; c++) {
            var wrap = document.createElement('div');
            wrap.className = 'core-bar-wrap';
            wrap.title = 'Core ' + c;
            var fill = document.createElement('div');
            fill.className = 'core-bar-fill';
            fill.id = 'cpu-core-fill-' + c;
            wrap.appendChild(fill);
            dom.cpuCoresMatrix.appendChild(wrap);
            dom.coreFills.push(fill);
          }
        }
      }
      if (dom.coreFills) {
        for (var i = 0; i < dom.coreFills.length; i++) {
          var fillEl = dom.coreFills[i];
          var val = clamp(Number(cores[i]) || 0, 0, 100);
          fillEl.style.height = val + '%';
          if (val >= 85) {
            fillEl.style.backgroundColor = '#ef4444';
          } else {
            fillEl.style.backgroundColor = '#00d2ff';
          }
        }
      }
    }
  }

  // Multi-GPU Classifier (Identifies NVIDIA dGPU vs AMD iGPU strictly via vendor ID and name)
  function classifyGpus(devices) {
    var nvidia = null;
    var amd = null;

    if (!devices || !devices.length) {
      return { nvidia: null, amd: null };
    }

    for (var i = 0; i < devices.length; i++) {
      var d = devices[i];
      var name = (d.name || '').toLowerCase();
      var vid = (d.vendor_id || '').toLowerCase();

      var isNvidia = (vid === '0x10de') || (name.indexOf('nvidia') !== -1) || (name.indexOf('geforce') !== -1);
      var isAmd = (vid === '0x1002') || (name.indexOf('amd') !== -1) || (name.indexOf('radeon') !== -1);

      if (isNvidia && !nvidia) {
        nvidia = d;
      } else if (isAmd && !amd) {
        amd = d;
      }
    }

    return { nvidia: nvidia, amd: amd };
  }

  function renderGpus(gpus) {
    if (!gpus || gpus.status === 'error') {
      setText(dom.gpuNvidiaUsageVal, '--');
      if (dom.gpuNvidiaUsageBar) dom.gpuNvidiaUsageBar.style.width = '0%';
      return;
    }

    var classified = classifyGpus(gpus.devices);
    var nvidia = classified.nvidia;
    var amd = classified.amd;

    // --- 1. Dedicated NVIDIA GPU ---
    if (nvidia) {
      if (nvidia.name) setText(dom.gpuNvidiaName, nvidia.name);

      // Core Utilization
      var util = nvidia.utilization_percent;
      if (util && util.status === 'ok' && typeof util.value === 'number') {
        setText(dom.gpuNvidiaUsageVal, Math.round(util.value) + '');
        if (dom.gpuNvidiaUsageBar) {
          dom.gpuNvidiaUsageBar.style.width = clamp(util.value, 0, 100) + '%';
          if (util.value >= 85) {
            dom.gpuNvidiaUsageBar.className = 'progress-fill fill-purple fill-alert';
          } else {
            dom.gpuNvidiaUsageBar.className = 'progress-fill fill-purple';
          }
        }
      } else {
        setText(dom.gpuNvidiaUsageVal, '--');
        if (dom.gpuNvidiaUsageBar) dom.gpuNvidiaUsageBar.style.width = '0%';
      }

      // Temperature
      var temp = nvidia.temperature_c;
      if (temp && temp.status === 'ok' && typeof temp.value === 'number') {
        setText(dom.gpuNvidiaTempVal, temp.value.toFixed(1) + ' \u00B0C');
        if (dom.gpuNvidiaTempBadge) dom.gpuNvidiaTempBadge.style.display = 'none';
      } else {
        setText(dom.gpuNvidiaTempVal, '-- \u00B0C');
        if (dom.gpuNvidiaTempBadge) {
          dom.gpuNvidiaTempBadge.className = 'sub-badge badge-na';
          dom.gpuNvidiaTempBadge.style.display = 'inline-block';
          setText(dom.gpuNvidiaTempBadge, 'N/A');
        }
      }

      // Power
      if (typeof nvidia.power_watts === 'number') {
        setText(dom.gpuNvidiaPowerVal, nvidia.power_watts.toFixed(1) + ' W');
        if (dom.gpuNvidiaPowerBadge) dom.gpuNvidiaPowerBadge.style.display = 'none';
      } else {
        setText(dom.gpuNvidiaPowerVal, '-- W');
        if (dom.gpuNvidiaPowerBadge) {
          dom.gpuNvidiaPowerBadge.className = 'sub-badge badge-na';
          dom.gpuNvidiaPowerBadge.style.display = 'inline-block';
          setText(dom.gpuNvidiaPowerBadge, 'N/A');
        }
      }

      // Graphics Clock
      var clocks = nvidia.clocks_mhz;
      if (clocks && typeof clocks.graphics === 'number') {
        setText(dom.gpuNvidiaClockVal, clocks.graphics + ' MHz');
      } else {
        setText(dom.gpuNvidiaClockVal, '-- MHz');
      }

      // Dedicated VRAM
      var mem = (nvidia.memory && nvidia.memory.dedicated) ? nvidia.memory.dedicated : null;
      if (mem && mem.status === 'ok' && mem.total_bytes) {
        var usedB = formatBytes(mem.used_bytes || 0);
        var totB = formatBytes(mem.total_bytes);
        var pct = mem.used_bytes ? Math.round((mem.used_bytes / mem.total_bytes) * 100) : 0;
        setText(dom.gpuNvidiaVramText, usedB.value + ' / ' + totB.value + ' ' + totB.unit + ' (' + pct + '%)');
        if (dom.gpuNvidiaVramBar) {
          dom.gpuNvidiaVramBar.style.width = clamp(pct, 0, 100) + '%';
        }
      } else {
        setText(dom.gpuNvidiaVramText, '-- / -- GB');
        if (dom.gpuNvidiaVramBar) dom.gpuNvidiaVramBar.style.width = '0%';
      }
    } else {
      setText(dom.gpuNvidiaName, 'NVIDIA GPU (Not Detected)');
      setText(dom.gpuNvidiaUsageVal, '--');
      if (dom.gpuNvidiaUsageBar) dom.gpuNvidiaUsageBar.style.width = '0%';
      setText(dom.gpuNvidiaTempVal, '-- \u00B0C');
      if (dom.gpuNvidiaTempBadge) {
        dom.gpuNvidiaTempBadge.className = 'sub-badge badge-na';
        dom.gpuNvidiaTempBadge.style.display = 'inline-block';
        setText(dom.gpuNvidiaTempBadge, 'N/A');
      }
      setText(dom.gpuNvidiaPowerVal, '-- W');
      if (dom.gpuNvidiaPowerBadge) {
        dom.gpuNvidiaPowerBadge.className = 'sub-badge badge-na';
        dom.gpuNvidiaPowerBadge.style.display = 'inline-block';
        setText(dom.gpuNvidiaPowerBadge, 'N/A');
      }
      setText(dom.gpuNvidiaClockVal, '-- MHz');
      setText(dom.gpuNvidiaVramText, '-- / -- GB');
      if (dom.gpuNvidiaVramBar) dom.gpuNvidiaVramBar.style.width = '0%';
    }

    // --- 2. Integrated AMD APU ---
    if (amd) {
      if (amd.name) setText(dom.gpuAmdName, amd.name);

      var amdMem = amd.memory || {};
      var dedMem = amdMem.dedicated || {};
      var sharedMem = amdMem.shared_system || {};

      if (dedMem.total_bytes) {
        var dedFmt = formatBytes(dedMem.total_bytes);
        setText(dom.gpuAmdVramDedicated, dedFmt.value + ' ' + dedFmt.unit);
      } else {
        setText(dom.gpuAmdVramDedicated, '-- MB');
      }

      if (sharedMem.budget_bytes) {
        var sharedFmt = formatBytes(sharedMem.budget_bytes);
        setText(dom.gpuAmdVramShared, sharedFmt.value + ' ' + sharedFmt.unit);
      } else {
        setText(dom.gpuAmdVramShared, '-- GB');
      }

      setText(dom.gpuAmdType, amd.adapter_type ? ('Integrated (' + amd.adapter_type + ')') : 'Integrated APU');
    } else {
      setText(dom.gpuAmdName, 'AMD Graphics (Not Detected)');
      setText(dom.gpuAmdVramDedicated, '-- MB');
      setText(dom.gpuAmdVramShared, '-- GB');
      setText(dom.gpuAmdType, 'Absent');
    }
  }

  function renderMemory(memory) {
    if (!memory || memory.status === 'error') {
      setText(dom.ramUsageVal, '--');
      if (dom.ramUsageBar) dom.ramUsageBar.style.width = '0%';
      return;
    }

    var pct = (typeof memory.usage_percent === 'number') ? Math.round(memory.usage_percent) : 0;
    setText(dom.ramUsageVal, pct + '');
    if (dom.ramUsageBar) {
      dom.ramUsageBar.style.width = clamp(pct, 0, 100) + '%';
      if (pct >= 90) {
        dom.ramUsageBar.className = 'progress-fill fill-green fill-alert';
      } else {
        dom.ramUsageBar.className = 'progress-fill fill-green';
      }
    }

    var used = formatBytes(memory.used_bytes);
    var avail = formatBytes(memory.available_bytes);
    var total = formatBytes(memory.total_bytes);

    setText(dom.ramUsedVal, used.value + ' ' + used.unit);
    setText(dom.ramAvailVal, avail.value + ' ' + avail.unit);
    setText(dom.ramTotalVal, total.value + ' ' + total.unit);
    setText(dom.ramUsageSubtext, used.value + ' ' + used.unit + ' used of ' + total.value + ' ' + total.unit);
    setText(dom.ramMetaBadge, total.value + ' ' + total.unit + ' DDR5');
  }

  function renderStorage(storage) {
    if (!storage || storage.status === 'error') return;

    var volumes = storage.volumes || [];
    setText(dom.storageVolumeCount, volumes.length + ' Fixed Drives');

    if (dom.storageVolumesList) {
      // Re-use or populate volume rows cleanly
      dom.storageVolumesList.innerHTML = '';
      for (var v = 0; v < volumes.length; v++) {
        var vol = volumes[v];
        var usedFmt = formatBytes(vol.used_bytes);
        var totalFmt = formatBytes(vol.total_bytes);
        var freeFmt = formatBytes(vol.free_bytes);
        var pct = (typeof vol.usage_percent === 'number') ? Math.round(vol.usage_percent) : 0;

        var row = document.createElement('div');
        row.className = 'volume-row';

        var header = document.createElement('div');
        header.className = 'volume-header';
        header.innerHTML = '<span class="volume-name">Drive ' + (vol.mount || vol.device) + ' (' + (vol.fstype || 'NTFS') + ')</span>' +
                           '<span class="volume-meta">' + pct + '% (' + usedFmt.value + ' / ' + totalFmt.value + ' ' + totalFmt.unit + ')</span>';

        var track = document.createElement('div');
        track.className = 'progress-track';
        var fill = document.createElement('div');
        fill.className = 'progress-fill fill-orange' + (pct >= 90 ? ' fill-alert' : '');
        fill.style.width = clamp(pct, 0, 100) + '%';
        track.appendChild(fill);

        var subtext = document.createElement('div');
        subtext.className = 'volume-subtext';
        subtext.innerHTML = freeFmt.value + ' ' + freeFmt.unit + ' free space remaining';

        row.appendChild(header);
        row.appendChild(track);
        row.appendChild(subtext);
        dom.storageVolumesList.appendChild(row);
      }
    }

    // Disk I/O Rates
    var io = storage.io_throughput;
    if (io && io.status === 'ok') {
      var readRate = io.read_bytes_per_second;
      var writeRate = io.write_bytes_per_second;
      setText(dom.storageReadRate, formatRate(readRate));
      setText(dom.storageWriteRate, formatRate(writeRate));
      var isZero = (readRate === 0 && writeRate === 0);
      setText(dom.storageIoStatus, isZero ? 'IDLE' : 'ACTIVE');
      if (dom.storageIoStatus) {
        dom.storageIoStatus.className = isZero ? 'sub-badge badge-na' : 'sub-badge status-live';
      }
    } else {
      setText(dom.storageReadRate, '--');
      setText(dom.storageWriteRate, '--');
      setText(dom.storageIoStatus, 'N/A');
      if (dom.storageIoStatus) dom.storageIoStatus.className = 'sub-badge badge-na';
    }
  }

  function renderNetwork(network) {
    if (!network || network.status === 'error') return;

    var summary = network.summary || {};
    var down = summary.download_bytes_per_second;
    var up = summary.upload_bytes_per_second;

    setText(dom.netDownRate, formatRate(down));
    setText(dom.netUpRate, formatRate(up));

    var adapterName = summary.primary_interface || 'Ethernet';
    setText(dom.netPrimaryAdapter, adapterName);
    setText(dom.netInterfaceBadge, adapterName.toUpperCase());

    var status = summary.status || 'unknown';
    setText(dom.netSummaryStatus, status.toUpperCase());
  }

  function renderSystem(system, sequence) {
    if (!system) return;

    setText(dom.hudHostname, system.hostname || 'PC-HOST');
    setText(dom.hudOs, system.os || 'Windows 11');
    setText(dom.diagHostname, system.hostname || '--');
    setText(dom.diagOs, system.os || '--');
    setText(dom.diagCpuName, system.cpu_name || '--');

    if (system.boot_time_timestamp) {
      setText(dom.diagBootTime, formatBootTime(system.boot_time_timestamp));
    }

    if (typeof system.uptime_seconds === 'number') {
      setText(dom.hudUptimeVal, formatUptime(system.uptime_seconds));
    }

    setText(dom.hudSequence, 'SEQ #' + sequence);
  }

  // ==========================================================================
  // XHR Poller & Sequence Rejection Engine
  // ==========================================================================

  function pollStatus() {
    if (isPollingActive) return;
    isPollingActive = true;

    var xhr = new XMLHttpRequest();
    // Cache-busting timestamp parameter for iOS Safari
    var url = '/api/v1/status?_t=' + (new Date().getTime());
    xhr.open('GET', url, true);
    xhr.timeout = XHR_TIMEOUT_MS;

    xhr.onload = function () {
      isPollingActive = false;
      if (xhr.status === 200) {
        try {
          var payload = JSON.parse(xhr.responseText);

          // Sequence Check: Reject duplicate and out-of-order responses,
          // while detecting a genuine sequence reset on server restart.
          if (typeof payload.sequence === 'number') {
            var seq = payload.sequence;
            var isServerRestart = (lastSequence > 0) && (
              seq === 1 ||
              (seq < lastSequence && consecutiveFailures > 0)
            );

            if (isServerRestart) {
              // Server restarted: establish new sequence baseline
              lastSequence = seq;
            } else if (lastSequence !== 0 && seq <= lastSequence) {
              // Duplicate or out-of-order response: discard
              scheduleNextPoll(POLL_INTERVAL_MS);
              return;
            } else {
              lastSequence = seq;
            }
          }

          lastSuccessTime = new Date().getTime();
          consecutiveFailures = 0;
          updateStatusBadge('live', 'LIVE');

          if (dom.hudAge) setText(dom.hudAge, '0s ago');

          // Render Sections
          var secs = payload.sections || {};
          renderCpu(secs.cpu, secs.system);
          renderGpus(secs.gpus);
          renderMemory(secs.memory);
          renderStorage(secs.storage);
          renderNetwork(secs.network);
          renderSystem(secs.system, payload.sequence);

        } catch (e) {
          // JSON parsing exception
          handlePollError();
        }
      } else {
        handlePollError();
      }
      scheduleNextPoll(POLL_INTERVAL_MS);
    };

    xhr.onerror = function () {
      isPollingActive = false;
      handlePollError();
      scheduleNextPoll(2000); // Backoff to 2s on error
    };

    xhr.ontimeout = function () {
      isPollingActive = false;
      handlePollError();
      scheduleNextPoll(2000); // Backoff to 2s on timeout
    };

    xhr.send();
  }

  function handlePollError() {
    consecutiveFailures++;
    if (consecutiveFailures >= 2) {
      updateStatusBadge('offline', 'OFFLINE');
    }
  }

  function scheduleNextPoll(delayMs) {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = setTimeout(function () {
      pollStatus();
    }, delayMs);
  }

  // ==========================================================================
  // Initialization
  // ==========================================================================

  function init() {
    initDomCache();
    updateStatusBadge('connecting', 'CONNECTING');

    // Start polling immediately
    pollStatus();

    // Start freshness checker interval (every 1 second)
    setInterval(checkFreshness, 1000);
  }

  // Safe DOMReady execution for legacy Safari
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    init();
  } else if (document.addEventListener) {
    document.addEventListener('DOMContentLoaded', init, false);
  } else if (window.attachEvent) {
    window.attachEvent('onload', init);
  }

})();
