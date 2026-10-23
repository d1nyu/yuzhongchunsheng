(() => {
  if (window.__yuzhongTimeSyncLoaded) {
    return;
  }
  window.__yuzhongTimeSyncLoaded = true;

  function visibleVideo() {
    const videos = Array.from(document.querySelectorAll("video"))
      .filter((video) => {
        const rect = video.getBoundingClientRect();
        if (rect.width < 80 || rect.height < 45) {
          return false;
        }
        const style = window.getComputedStyle(video);
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          Number(video.readyState) >= 1
        );
      })
      .map((video) => {
        const rect = video.getBoundingClientRect();
        return {
          video,
          area: Math.max(0, rect.width) * Math.max(0, rect.height)
        };
      })
      .sort((first, second) => second.area - first.area);
    return videos.length ? videos[0] : null;
  }

  function sendPlayback() {
    const found = visibleVideo();
    if (!found) {
      return;
    }
    const video = found.video;
    const currentTime = Number(video.currentTime);
    const duration = Number(video.duration);
    if (!Number.isFinite(currentTime) || currentTime < 0) {
      return;
    }
    chrome.runtime.sendMessage(
      {
        type: "yuzhong_playback",
        title: document.title || "网页视频",
        url: location.href,
        current_time: currentTime,
        duration: Number.isFinite(duration) ? duration : 0,
        paused: Boolean(video.paused),
        can_seek: Boolean(video.seekable && video.seekable.length),
        viewport_area: found.area
      },
      () => void chrome.runtime.lastError
    );
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (!message || message.type !== "yuzhong_seek") {
      return;
    }
    const found = visibleVideo();
    if (!found || !Number.isFinite(Number(message.time))) {
      return;
    }
    try {
      found.video.currentTime = Math.max(0, Number(message.time));
      found.video.dispatchEvent(new Event("timeupdate"));
    } catch (_error) {
      return;
    }
  });

  setInterval(sendPlayback, 1000);
  document.addEventListener(
    "play",
    (event) => {
      if (event.target instanceof HTMLVideoElement) {
        sendPlayback();
      }
    },
    true
  );
  document.addEventListener(
    "pause",
    (event) => {
      if (event.target instanceof HTMLVideoElement) {
        sendPlayback();
      }
    },
    true
  );
  document.addEventListener(
    "seeked",
    (event) => {
      if (event.target instanceof HTMLVideoElement) {
        sendPlayback();
      }
    },
    true
  );
})();
