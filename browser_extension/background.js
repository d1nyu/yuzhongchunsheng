const PORTS = [8765, 8766, 8767, 8768, 8769, 8770, 8771, 8772];

let bridgePort = null;
let nextProbeAt = 0;
let lastCommandSequence = 0;

async function postPlayback(message, sender) {
  const now = Date.now();
  if (!bridgePort && now < nextProbeAt) {
    return;
  }
  const ports = bridgePort ? [bridgePort] : PORTS;
  const payload = {
    session_id: `${sender.tab?.id ?? -1}:${sender.frameId ?? 0}`,
    title: message.title,
    url: message.url,
    current_time: message.current_time,
    duration: message.duration,
    paused: message.paused,
    can_seek: message.can_seek,
    viewport_area: message.viewport_area,
    last_command_sequence: lastCommandSequence
  };

  for (const port of ports) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/api/playback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload),
        cache: "no-store"
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      bridgePort = port;
      nextProbeAt = 0;
      const result = await response.json();
      const command = result.command;
      const sessionId = payload.session_id;
      if (
        command &&
        command.sequence > lastCommandSequence &&
        command.target_session === sessionId
      ) {
        lastCommandSequence = command.sequence;
        chrome.tabs.sendMessage(
          sender.tab.id,
          {
            type: "yuzhong_seek",
            time: command.time
          },
          { frameId: sender.frameId ?? 0 }
        );
      }
      return;
    } catch (_error) {
      if (bridgePort === port) {
        bridgePort = null;
      }
    }
  }
  nextProbeAt = Date.now() + 5000;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "yuzhong_playback" || !sender.tab?.id) {
    return;
  }
  postPlayback(message, sender)
    .then(() => sendResponse({ ok: true }))
    .catch(() => sendResponse({ ok: false }));
  return true;
});
