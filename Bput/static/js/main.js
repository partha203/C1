// CampusOne main.js — vanilla JS, no framework, low-bandwidth friendly

document.addEventListener("DOMContentLoaded", function () {
  var hamburger = document.getElementById("hamburger");
  var sidebar = document.getElementById("sidebar");
  if (hamburger && sidebar) {
    hamburger.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
    document.addEventListener("click", function (e) {
      if (sidebar.classList.contains("open") && !sidebar.contains(e.target) && e.target !== hamburger) {
        sidebar.classList.remove("open");
      }
    });
  }

  // Auto-dismiss flash messages after a while
  document.querySelectorAll(".flash").forEach(function (el) {
    setTimeout(function () { el.style.opacity = "0.6"; }, 6000);
  });

  // Register service worker for offline/PWA support
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/service-worker.js").catch(function () {
      // Offline support is a progressive enhancement; ignore failures silently
    });
  }

  // Offline queue for request/complaint submissions
  var offlineForms = document.querySelectorAll("form[data-offline-queue]");
  offlineForms.forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (navigator.onLine) return; // let it submit normally
      e.preventDefault();
      queueOfflineSubmission(form);
    });
  });

  flushOfflineQueue();
  window.addEventListener("online", flushOfflineQueue);

  // Generic confirmation modal: any form/button with data-confirm="message"
  // shows a modal instead of a native confirm() dialog before submitting.
  initConfirmModals();

  // Loading state: forms that upload a file show a spinner on their submit
  // button while the upload is in flight, so large uploads on slow campus
  // networks don't look frozen.
  document.querySelectorAll('form input[type="file"]').forEach(function (input) {
    var form = input.closest("form");
    if (!form || form.dataset.loadingBound) return;
    form.dataset.loadingBound = "1";
    form.addEventListener("submit", function () {
      var btn = form.querySelector('button[type="submit"]');
      if (btn && !btn.classList.contains("is-loading")) {
        btn.dataset.originalText = btn.innerHTML;
        btn.innerHTML = '<span class="spinner"></span>Uploading…';
        btn.classList.add("is-loading");
      }
    });
  });
});

function initConfirmModals() {
  var overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML =
    '<div class="modal-box">' +
    '  <h3 id="confirmModalTitle">Are you sure?</h3>' +
    '  <p class="muted" id="confirmModalBody"></p>' +
    '  <div class="modal-actions">' +
    '    <button type="button" class="btn btn-ghost" id="confirmModalCancel">Cancel</button>' +
    '    <button type="button" class="btn btn-primary" id="confirmModalOk">Confirm</button>' +
    '  </div>' +
    '</div>';
  document.body.appendChild(overlay);

  var bodyEl = overlay.querySelector("#confirmModalBody");
  var okBtn = overlay.querySelector("#confirmModalOk");
  var cancelBtn = overlay.querySelector("#confirmModalCancel");
  var pendingForm = null;

  function close() {
    overlay.classList.remove("open");
    pendingForm = null;
  }

  overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });
  cancelBtn.addEventListener("click", close);
  okBtn.addEventListener("click", function () {
    if (pendingForm) {
      var real = pendingForm;
      pendingForm = null;
      overlay.classList.remove("open");
      real.submit();
    }
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      bodyEl.textContent = form.getAttribute("data-confirm");
      pendingForm = form;
      overlay.classList.add("open");
    });
  });
}

function queueOfflineSubmission(form) {
  try {
    var data = {};
    new FormData(form).forEach(function (v, k) { data[k] = v; });
    var queue = JSON.parse(localStorage.getItem("campusone_offline_queue") || "[]");
    queue.push({ action: form.action, data: data, ts: Date.now() });
    localStorage.setItem("campusone_offline_queue", JSON.stringify(queue));
    alert("You're offline. This will be submitted automatically once your connection returns.");
  } catch (err) {
    alert("Offline queue is unavailable in this browser. Please retry once you're back online.");
  }
}

function flushOfflineQueue() {
  if (!navigator.onLine) return;
  var queue = [];
  try {
    queue = JSON.parse(localStorage.getItem("campusone_offline_queue") || "[]");
  } catch (err) { return; }
  if (!queue.length) return;

  var remaining = [];
  var sendNext = function (i) {
    if (i >= queue.length) {
      localStorage.setItem("campusone_offline_queue", JSON.stringify(remaining));
      if (remaining.length === 0 && queue.length > 0) {
        console.log("CampusOne: offline queue synced.");
      }
      return;
    }
    var item = queue[i];
    var fd = new FormData();
    Object.keys(item.data).forEach(function (k) { fd.append(k, item.data[k]); });
    fetch(item.action, { method: "POST", body: fd, credentials: "same-origin" })
      .then(function () { sendNext(i + 1); })
      .catch(function () { remaining.push(item); sendNext(i + 1); });
  };
  sendNext(0);
}
