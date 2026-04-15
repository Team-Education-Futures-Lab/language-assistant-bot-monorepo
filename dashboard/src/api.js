const configuredApiBaseUrl =
  process.env.REACT_APP_API_BASE_URL ||
  process.env.VITE_AI_API_BASE_URL;

export const API_BASE_URL = configuredApiBaseUrl
  ? configuredApiBaseUrl.replace(/\/$/, '')
  : undefined;

const resolveApiBaseUrl = (baseUrl = API_BASE_URL) => {
  if (!baseUrl) {
    throw new Error('Dashboard API base URL is not configured. Set REACT_APP_API_BASE_URL.');
  }

  return baseUrl.replace(/\/$/, '');
};

const buildApiUrl = (path, baseUrl) => `${resolveApiBaseUrl(baseUrl)}${path}`;

const fetchJson = async (path, options = {}, baseUrl) => {
  const response = await fetch(buildApiUrl(path, baseUrl), options);

  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(data.message || `API-fout: ${response.status}`);
  }

  return data;
};

export const fetchApiHealth = async (baseUrl) => {
  // The detailed health endpoint can return 503 when a downstream service is slow.
  // For dashboard boot, we only need to know if the gateway itself is reachable.
  const response = await fetch(buildApiUrl('/api/query/health/gateway', baseUrl));
  return response.ok;
};

export const fetchSubjects = async (baseUrl) => {
  const data = await fetchJson('/api/query/subjects', {}, baseUrl);
  return data.subjects || [];
};

export const fetchSubjectById = async (subjectId, baseUrl) => {
  const data = await fetchJson(`/api/query/subjects/${subjectId}`, {}, baseUrl);
  return data.subject || null;
};

export const createSubject = async (subjectData, baseUrl) => {
  const data = await fetchJson('/api/query/subjects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subjectData),
  }, baseUrl);

  return data.subject;
};

export const updateSubject = async (subjectId, subjectData, baseUrl) => {
  const data = await fetchJson(`/api/query/subjects/${subjectId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subjectData),
  }, baseUrl);

  return data.subject;
};

export const deleteSubject = async (subjectId, baseUrl) => {
  await fetchJson(`/api/query/subjects/${subjectId}`, {
    method: 'DELETE',
  }, baseUrl);
};

export const fetchChunks = async (subjectId, baseUrl) => {
  const data = await fetchJson(`/api/query/subjects/${subjectId}/chunks`, {}, baseUrl);
  return data.chunks || [];
};

export const createChunk = async (subjectId, chunkData, baseUrl) => {
  const data = await fetchJson(`/api/query/subjects/${subjectId}/chunks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(chunkData),
  }, baseUrl);

  return data;
};

export const deleteChunk = async (chunkId, baseUrl) => {
  await fetchJson(`/api/query/chunks/${chunkId}`, {
    method: 'DELETE',
  }, baseUrl);
};

export const deleteUpload = async (subjectId, uploadName, baseUrl) => {
  await fetchJson(`/api/query/subjects/${subjectId}/uploads/${encodeURIComponent(uploadName)}`, {
    method: 'DELETE',
  }, baseUrl);
};

export const uploadSubjectFile = async (subjectId, file, chunkSize, baseUrl, onProgress) =>
  new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_size', chunkSize);

    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      const isSuccess = xhr.status >= 200 && xhr.status < 300;
      let response = {};

      try {
        response = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch {
        response = {};
      }

      if (isSuccess) {
        resolve(response);
        return;
      }

      reject(new Error(response.message || response.error || 'Fout bij uploaden van bestand'));
    };

    xhr.onerror = () => {
      reject(new Error('Fout bij uploaden van bestand. Controleer of de backend service actief is.'));
    };

    xhr.open('POST', buildApiUrl(`/api/query/subjects/${subjectId}/upload`, baseUrl));
    xhr.send(formData);
  });

export const fetchPrompts = async (baseUrl) => {
  const data = await fetchJson('/api/query/prompts', {}, baseUrl);
  return data.prompts || [];
};

export const createPrompt = async (promptData, baseUrl) => {
  const data = await fetchJson('/api/query/prompts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(promptData),
  }, baseUrl);

  return data;
};

export const updatePrompt = async (promptId, updates, baseUrl) => {
  const data = await fetchJson(`/api/query/prompts/${promptId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  }, baseUrl);

  return data;
};

export const deletePrompt = async (promptId, baseUrl) => {
  await fetchJson(`/api/query/prompts/${promptId}`, {
    method: 'DELETE',
  }, baseUrl);
};

export const fetchSettings = async (baseUrl) => {
  const data = await fetchJson('/api/query/settings', {}, baseUrl);
  return data.settings || [];
};

export const saveSettings = async (settings, settingDescriptions, baseUrl) => {
  for (const [key, value] of Object.entries(settings)) {
    await fetchJson('/api/query/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        key,
        value,
        description: settingDescriptions[key] || '',
      }),
    }, baseUrl);
  }
};