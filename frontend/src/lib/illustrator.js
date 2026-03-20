/**
 * Sdilena logika pro komunikaci s Illustratorem.
 */

/**
 * Nacte aktivni dokument z Illustratoru.
 * @returns {Promise<{name: string}|null>} Objekt s info o dokumentu nebo null.
 */
export async function loadActiveDoc() {
  try {
    const res = await fetch('/api/illustrator/status');
    const data = await res.json();
    if (data.connected && data.documents) {
      let docs = [];
      try {
        const textContent = data.documents?.response?.content?.[0]?.text;
        if (textContent) docs = JSON.parse(textContent);
      } catch { /* fallback */ }
      if (!docs.length) {
        docs = data.documents?.response?.documents || data.documents?.documents || [];
      }
      return docs.length > 0 ? docs[0] : null;
    }
    return null;
  } catch {
    return null;
  }
}
