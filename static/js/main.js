(function () {
  const linkInput = document.getElementById("link-input");
  const pasteBtn = document.getElementById("paste-btn");
  const downloadBtn = document.getElementById("download-btn");
  const errorMessage = document.getElementById("error-message");
  const loading = document.getElementById("loading");
  const inputView = document.getElementById("input-view");
  const successView = document.getElementById("success-view");
  const resetBtn = document.getElementById("reset-btn");

  function showError(text) {
    errorMessage.textContent = text;
    errorMessage.hidden = false;
  }

  function hideError() {
    errorMessage.hidden = true;
  }

  function setLoading(isLoading) {
    loading.hidden = !isLoading;
    downloadBtn.disabled = isLoading;
    pasteBtn.disabled = isLoading;
  }

  function looksLikeFacebookLink(url) {
    return url.includes("facebook.com") || url.includes("fb.watch");
  }

  // Extrae el nombre de archivo del header Content-Disposition,
  // con un valor por defecto por si acaso.
  function getFilenameFromResponse(response) {
    const header = response.headers.get("Content-Disposition") || "";
    const match = header.match(/filename="?([^"]+)"?/);
    return match ? match[1] : `reel_${Date.now()}.mp4`;
  }

  pasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        linkInput.value = text.trim();
        hideError();
      } else {
        showError("No hay nada copiado en el portapapeles.");
      }
    } catch (err) {
      showError(
        "No se pudo leer el portapapeles automáticamente. Pega el link manualmente (mantén presionado y elige 'Pegar')."
      );
    }
  });

  downloadBtn.addEventListener("click", async () => {
    const url = linkInput.value.trim();
    hideError();

    if (!url) {
      showError("Pega el link del Reel primero.");
      return;
    }
    if (!looksLikeFacebookLink(url)) {
      showError("Ese no parece un link de Facebook.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      const contentType = response.headers.get("Content-Type") || "";

      if (!response.ok || contentType.includes("application/json")) {
        const data = await response.json().catch(() => null);
        showError(
          (data && data.error) || "Ocurrió un error al descargar el video."
        );
        setLoading(false);
        return;
      }

      const filename = getFilenameFromResponse(response);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(objectUrl);

      setLoading(false);
      inputView.hidden = true;
      successView.hidden = false;
    } catch (err) {
      setLoading(false);
      showError("No se pudo completar la descarga. Revisa tu conexión e intenta de nuevo.");
    }
  });

  resetBtn.addEventListener("click", () => {
    linkInput.value = "";
    hideError();
    successView.hidden = true;
    inputView.hidden = false;
  });
})();
