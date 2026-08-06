(function () {
  'use strict';
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'pdf.worker.min.js';

  var statusEl = document.getElementById('status');
  var pagesEl = document.getElementById('pages');
  var params = new URLSearchParams(window.location.search);
  var fileUrl = params.get('file');

  if (!fileUrl) {
    statusEl.textContent = 'Ingen fil angivet.';
    return;
  }

  function setStatus(text) { statusEl.textContent = text; statusEl.classList.remove('hidden'); }
  function hideStatus() { statusEl.classList.add('hidden'); }

  async function renderPage(pdf, pageNum, targetWidth) {
    var page = await pdf.getPage(pageNum);
    var viewport = page.getViewport({ scale: 1 });
    var scale = targetWidth / viewport.width;
    var scaledViewport = page.getViewport({ scale: scale });

    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    var dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(scaledViewport.width * dpr);
    canvas.height = Math.floor(scaledViewport.height * dpr);
    canvas.style.width = Math.floor(scaledViewport.width) + 'px';
    canvas.style.height = Math.floor(scaledViewport.height) + 'px';
    ctx.scale(dpr, dpr);

    pagesEl.appendChild(canvas);
    await page.render({ canvasContext: ctx, viewport: scaledViewport }).promise;
  }

  async function main() {
    try {
      setStatus('Indlæser PDF…');
      var loadingTask = pdfjsLib.getDocument({ url: fileUrl, withCredentials: false });
      var pdf = await loadingTask.promise;
      var targetWidth = Math.min(document.documentElement.clientWidth || 800, 1000);

      for (var i = 1; i <= pdf.numPages; i++) {
        setStatus('Indlæser side ' + i + ' af ' + pdf.numPages + '…');
        await renderPage(pdf, i, targetWidth);
      }
      hideStatus();
    } catch (err) {
      console.error('PDF render failed', err);
      statusEl.innerHTML = 'Kunne ikke vise PDF\'en.<br><a style="color:#8cf" href="' +
        fileUrl + '" target="_blank">Åbn/hent filen direkte</a>';
    }
  }

  main();
})();
