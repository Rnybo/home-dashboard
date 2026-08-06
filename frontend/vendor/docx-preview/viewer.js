(function () {
  'use strict';
  var statusEl = document.getElementById('status');
  var docEl = document.getElementById('doc');
  var params = new URLSearchParams(window.location.search);
  var fileUrl = params.get('file');

  if (!fileUrl) {
    statusEl.textContent = 'Ingen fil angivet.';
    return;
  }

  function setStatus(text) { statusEl.textContent = text; statusEl.classList.remove('hidden'); }
  function hideStatus() { statusEl.classList.add('hidden'); }

  async function main() {
    try {
      setStatus('Henter dokument…');
      var resp = await fetch(fileUrl);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      var blob = await resp.blob();

      setStatus('Indlæser dokument…');
      await docx.renderAsync(blob, docEl, undefined, {
        inWrapper: true,
        ignoreWidth: false,
        ignoreHeight: false,
        breakPages: true,
        experimental: true
      });
      hideStatus();
    } catch (err) {
      console.error('docx render failed', err);
      statusEl.innerHTML = 'Kunne ikke vise dokumentet.<br><a style="color:#8cf" href="' +
        fileUrl + '" target="_blank">Åbn/hent filen direkte</a>';
    }
  }

  main();
})();
