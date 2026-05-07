const { test, expect } = require('@playwright/test');

const DASHBOARD_BASE_URL = 'http://localhost:3001';
const MOCK_UPLOAD_NAME = 'e2e-upload.txt';

function jsonResponse(body, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

function parseRequestBody(request) {
  const rawBody = request.postData();
  if (!rawBody) {
    return {};
  }

  try {
    return JSON.parse(rawBody);
  } catch {
    return {};
  }
}

function buildState() {
  const state = {
    subjects: [
      {
        id: 1,
        name: 'Nederlands',
        description: 'Lesmateriaal voor taal en grammatica.',
        retrieval_k: 10,
      },
      {
        id: 2,
        name: 'Wiskunde',
        description: 'Rekensommen en uitleg.',
        retrieval_k: 8,
      },
    ],
    chunks: [
      {
        id: 101,
        subject_id: 1,
        source_file: 'hoofdstuk-1.pdf',
        content: 'Dit is een eerste chunk voor hoofdstuk 1. '.repeat(6),
        created_at: '2026-05-01T08:00:00.000Z',
      },
      {
        id: 102,
        subject_id: 1,
        source_file: 'hoofdstuk-1.pdf',
        content: 'Tweede chunk voor hetzelfde uploadbestand. '.repeat(5),
        created_at: '2026-05-01T08:05:00.000Z',
      },
      {
        id: 103,
        subject_id: 1,
        source_file: 'samenvatting.txt',
        content: 'Korte samenvatting van de lesstof.',
        created_at: '2026-05-01T08:10:00.000Z',
      },
      {
        id: 201,
        subject_id: 2,
        source_file: 'wiskunde-notes.txt',
        content: 'Algebra en rekenregels.',
        created_at: '2026-05-02T08:00:00.000Z',
      },
    ],
    prompts: [
      {
        id: 301,
        title: 'Default Support Prompt',
        content: 'Beantwoord vriendelijk, helder en concreet.',
        is_active: true,
        is_default: true,
        created_at: '2026-05-01T08:00:00.000Z',
        updated_at: '2026-05-01T08:00:00.000Z',
      },
      {
        id: 302,
        title: 'Fallback Prompt',
        content: 'Gebruik dit als fallback prompt.',
        is_active: false,
        is_default: false,
        created_at: '2026-05-01T08:15:00.000Z',
        updated_at: '2026-05-01T08:15:00.000Z',
      },
    ],
    settings: {
      openai_realtime_model: 'gpt-realtime-mini',
      openai_realtime_voice: 'alloy',
    },
    nextIds: {
      subject: 400,
      chunk: 500,
      prompt: 600,
    },
  };

  const getSubjectChunkCount = (subjectId) => state.chunks.filter((chunk) => chunk.subject_id === subjectId).length;

  const buildSubjectListItem = (subject) => ({
    ...subject,
    chunk_count: getSubjectChunkCount(subject.id),
  });

  const buildSubjectDetail = (subjectId) => {
    const subject = state.subjects.find((item) => item.id === subjectId);
    if (!subject) {
      return null;
    }

    return buildSubjectListItem(subject);
  };

  const getSubjectsResponse = () => ({
    subjects: state.subjects.map(buildSubjectListItem),
  });

  const getChunksResponse = (subjectId) => ({
    chunks: state.chunks.filter((chunk) => chunk.subject_id === subjectId),
  });

  const getPromptsResponse = () => ({
    prompts: state.prompts.map((prompt) => ({ ...prompt })),
  });

  const getSettingsResponse = () => ({
    settings: Object.entries(state.settings).map(([key, value]) => ({ key, value })),
  });

  const findPrompt = (promptId) => state.prompts.find((prompt) => prompt.id === promptId);

  const findSubject = (subjectId) => state.subjects.find((subject) => subject.id === subjectId);

  const upsertSetting = (key, value) => {
    state.settings[key] = value;
  };

  const removeSubject = (subjectId) => {
    state.subjects = state.subjects.filter((subject) => subject.id !== subjectId);
    state.chunks = state.chunks.filter((chunk) => chunk.subject_id !== subjectId);
  };

  const addUploadChunks = (subjectId) => {
    const uploadChunks = [
      {
        id: state.nextIds.chunk++,
        subject_id: subjectId,
        source_file: MOCK_UPLOAD_NAME,
        content: 'E2E upload chunk 1. '.repeat(6),
        created_at: '2026-05-07T09:00:00.000Z',
      },
      {
        id: state.nextIds.chunk++,
        subject_id: subjectId,
        source_file: MOCK_UPLOAD_NAME,
        content: 'E2E upload chunk 2. '.repeat(5),
        created_at: '2026-05-07T09:01:00.000Z',
      },
    ];

    state.chunks.push(...uploadChunks);
    return uploadChunks;
  };

  return {
    state,
    buildSubjectDetail,
    getSubjectsResponse,
    getChunksResponse,
    getPromptsResponse,
    getSettingsResponse,
    findPrompt,
    findSubject,
    removeSubject,
    upsertSetting,
    addUploadChunks,
  };
}

async function setupMockApi(page) {
  const mock = buildState();
  const calls = [];

  await page.route(`${DASHBOARD_BASE_URL}/api/query/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const { pathname } = url;

    calls.push({ method, pathname });

    if (pathname === '/api/query/health/gateway' && method === 'GET') {
      return route.fulfill(jsonResponse({
        status: 'healthy',
        gateway: { host: 'localhost', port: 3001 },
      }));
    }

    if (pathname === '/api/query/subjects' && method === 'GET') {
      return route.fulfill(jsonResponse(mock.getSubjectsResponse()));
    }

    if (pathname === '/api/query/subjects' && method === 'POST') {
      const body = parseRequestBody(request);
      const nextSubject = {
        id: mock.state.nextIds.subject++,
        name: body.name,
        description: body.description || '',
        retrieval_k: Number.isInteger(body.retrieval_k) ? body.retrieval_k : 10,
      };

      mock.state.subjects.push(nextSubject);
      return route.fulfill(jsonResponse({ subject: nextSubject }, 201));
    }

    const subjectDetailMatch = pathname.match(/^\/api\/query\/subjects\/(\d+)$/);
    if (subjectDetailMatch) {
      const subjectId = Number(subjectDetailMatch[1]);

      if (method === 'GET') {
        const subject = mock.buildSubjectDetail(subjectId);
        if (!subject) {
          return route.fulfill(jsonResponse({ message: 'Not found' }, 404));
        }

        return route.fulfill(jsonResponse({ subject }));
      }

      if (method === 'PUT') {
        const body = parseRequestBody(request);
        const subject = mock.findSubject(subjectId);

        if (!subject) {
          return route.fulfill(jsonResponse({ message: 'Not found' }, 404));
        }

        subject.name = body.name;
        subject.description = body.description || '';
        subject.retrieval_k = Number.isInteger(body.retrieval_k) ? body.retrieval_k : 10;

        return route.fulfill(jsonResponse({ subject: mock.buildSubjectDetail(subjectId) }));
      }

      if (method === 'DELETE') {
        mock.removeSubject(subjectId);
        return route.fulfill(jsonResponse({ deleted: true }));
      }
    }

    const subjectChunksMatch = pathname.match(/^\/api\/query\/subjects\/(\d+)\/chunks$/);
    if (subjectChunksMatch) {
      const subjectId = Number(subjectChunksMatch[1]);

      if (method === 'GET') {
        return route.fulfill(jsonResponse(mock.getChunksResponse(subjectId)));
      }

      if (method === 'POST') {
        const body = parseRequestBody(request);
        const newChunk = {
          id: mock.state.nextIds.chunk++,
          subject_id: subjectId,
          source_file: body.source_file || 'Untitled',
          content: body.content || '',
          created_at: '2026-05-07T09:15:00.000Z',
        };

        mock.state.chunks.push(newChunk);
        return route.fulfill(jsonResponse(newChunk, 201));
      }
    }

    const chunkDetailMatch = pathname.match(/^\/api\/query\/chunks\/(\d+)$/);
    if (chunkDetailMatch && method === 'DELETE') {
      const chunkId = Number(chunkDetailMatch[1]);
      mock.state.chunks = mock.state.chunks.filter((chunk) => chunk.id !== chunkId);
      return route.fulfill(jsonResponse({ deleted: true }));
    }

    const uploadDeleteMatch = pathname.match(/^\/api\/query\/subjects\/(\d+)\/uploads\/(.+)$/);
    if (uploadDeleteMatch && method === 'DELETE') {
      const subjectId = Number(uploadDeleteMatch[1]);
      const uploadName = decodeURIComponent(uploadDeleteMatch[2]);

      mock.state.chunks = mock.state.chunks.filter(
        (chunk) => !(chunk.subject_id === subjectId && chunk.source_file === uploadName),
      );

      return route.fulfill(jsonResponse({ deleted: true, upload_name: uploadName }));
    }

    const uploadMatch = pathname.match(/^\/api\/query\/subjects\/(\d+)\/upload$/);
    if (uploadMatch && method === 'POST') {
      const subjectId = Number(uploadMatch[1]);
      mock.addUploadChunks(subjectId);
      return route.fulfill(jsonResponse({ message: 'upload complete', upload_name: MOCK_UPLOAD_NAME }, 201));
    }

    if (pathname === '/api/query/prompts' && method === 'GET') {
      return route.fulfill(jsonResponse(mock.getPromptsResponse()));
    }

    if (pathname === '/api/query/prompts' && method === 'POST') {
      const body = parseRequestBody(request);
      const now = '2026-05-07T10:00:00.000Z';
      const prompt = {
        id: mock.state.nextIds.prompt++,
        title: body.title,
        content: body.content,
        is_active: Boolean(body.is_active),
        is_default: Boolean(body.is_default),
        created_at: now,
        updated_at: now,
      };

      mock.state.prompts.push(prompt);
      return route.fulfill(jsonResponse({ prompt }, 201));
    }

    const promptDetailMatch = pathname.match(/^\/api\/query\/prompts\/(\d+)$/);
    if (promptDetailMatch) {
      const promptId = Number(promptDetailMatch[1]);
      const prompt = mock.findPrompt(promptId);

      if (method === 'DELETE') {
        mock.state.prompts = mock.state.prompts.filter((item) => item.id !== promptId);
        return route.fulfill(jsonResponse({ deleted: true }));
      }

      if (!prompt) {
        return route.fulfill(jsonResponse({ message: 'Not found' }, 404));
      }

      if (method === 'PATCH') {
        const body = parseRequestBody(request);
        Object.assign(prompt, {
          title: body.title ?? prompt.title,
          content: body.content ?? prompt.content,
          is_active: body.is_active ?? prompt.is_active,
          is_default: body.is_default ?? prompt.is_default,
          updated_at: '2026-05-07T10:01:00.000Z',
        });

        return route.fulfill(jsonResponse({ ...prompt }));
      }

      if (method === 'GET') {
        return route.fulfill(jsonResponse({ ...prompt }));
      }
    }

    if (pathname === '/api/query/settings' && method === 'GET') {
      return route.fulfill(jsonResponse(mock.getSettingsResponse()));
    }

    if (pathname === '/api/query/settings' && method === 'POST') {
      const body = parseRequestBody(request);
      mock.upsertSetting(body.key, body.value);
      return route.fulfill(jsonResponse({ setting: { key: body.key, value: body.value } }, 201));
    }

    return route.fulfill(jsonResponse({ message: `Unhandled mock route: ${method} ${pathname}` }, 500));
  });

  return { calls, mock };
}

function hasCall(calls, method, pathname) {
  return calls.some((call) => call.method === method && call.pathname === pathname);
}

test.describe('dashboard e2e with mocked API', () => {
  test('covers subjects, chunks, file upload, and subject detail endpoints', async ({ page }) => {
    const { calls } = await setupMockApi(page);

    page.on('dialog', async (dialog) => dialog.accept());

    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Nederlands')).toBeVisible();

    await page.getByRole('button', { name: 'Nieuw Onderwerp', exact: true }).click();
    await page.locator('input[name="name"]').fill('E2E Onderwerp');
    await page.locator('textarea[name="description"]').fill('Volledig gemockte dashboard test');
    await page.locator('input[name="retrieval_k"]').fill('12');
    await page.getByRole('button', { name: 'Opslaan' }).click();
    await expect(page.getByText('E2E Onderwerp')).toBeVisible();

    await page.getByRole('button', { name: 'Nederlands' }).click();
    await expect(page.getByRole('heading', { name: 'Nederlands' })).toBeVisible();

    await page.locator('input[name="name"]').fill('Nederlands bijgewerkt');
    await page.locator('textarea[name="description"]').fill('Bijgewerkte beschrijving voor de e2e test');
    await page.locator('input[name="retrieval_k"]').fill('11');
    await page.getByRole('button', { name: 'Opslaan' }).click();
    await expect(page.getByRole('button', { name: 'Nederlands bijgewerkt' })).toBeVisible();
    await page.getByRole('button', { name: 'Nederlands bijgewerkt' }).click();
    await expect(page.getByRole('button', { name: 'Chunk Toevoegen' })).toBeVisible();

    await page.getByRole('button', { name: 'Chunk Toevoegen' }).click();
    await page.getByPlaceholder('Voer de content in...').fill('Nieuwe handmatige chunk voor de test. '.repeat(5));
    await page.getByPlaceholder('Optional').fill('e2e-manual.txt');
    await page.locator('form').filter({ has: page.getByPlaceholder('Voer de content in...') }).getByRole('button', { name: 'Opslaan', exact: true }).click();
    await expect(page.getByText('e2e-manual.txt')).toBeVisible();

    const manualUploadCard = page.locator('div.border.border-gray-200.rounded-lg.overflow-hidden').filter({
      has: page.getByRole('heading', { name: 'e2e-manual.txt' }),
    });
    await manualUploadCard.first().click();
    await manualUploadCard.first().getByTitle('Verwijder chunk').first().click();
    await expect(page.getByText('hoofdstuk-1.pdf')).toBeVisible();

    await page.getByRole('button', { name: 'Bestand Uploaden' }).click();
    const uploadInput = page.locator('input[type="file"]');
    await uploadInput.setInputFiles({
      name: MOCK_UPLOAD_NAME,
      mimeType: 'text/plain',
      buffer: Buffer.from('Deze tekst wordt als upload naar de mock gestuurd.'),
    });
    await page.getByRole('button', { name: 'Upload', exact: true }).click();
    await expect(page.getByText(MOCK_UPLOAD_NAME)).toBeVisible();



    await page.getByRole('button', { name: 'E2E Onderwerp' }).click();
    await page.getByRole('button', { name: 'Verwijderen' }).click();
    await expect(page.getByText('E2E Onderwerp')).toHaveCount(0);

    expect(hasCall(calls, 'GET', '/api/query/health/gateway')).toBe(true);
    expect(hasCall(calls, 'GET', '/api/query/subjects')).toBe(true);
    expect(hasCall(calls, 'POST', '/api/query/subjects')).toBe(true);
    expect(hasCall(calls, 'PUT', '/api/query/subjects/1')).toBe(true);
    expect(hasCall(calls, 'DELETE', '/api/query/subjects/400')).toBe(true);
    expect(hasCall(calls, 'GET', '/api/query/subjects/1')).toBe(true);
    expect(hasCall(calls, 'GET', '/api/query/subjects/1/chunks')).toBe(true);
    expect(hasCall(calls, 'POST', '/api/query/subjects/1/chunks')).toBe(true);
    expect(hasCall(calls, 'POST', '/api/query/subjects/1/upload')).toBe(true);
  });

  test('covers settings and prompt management endpoints', async ({ page }) => {
    const { calls } = await setupMockApi(page);

    page.on('dialog', async (dialog) => dialog.accept());

    await page.goto('/');
    await expect(page.getByText('Nederlands')).toBeVisible();

    await page.getByRole('button', { name: 'Instellingen' }).click();
    await expect(page.getByRole('heading', { name: 'Service Instellingen' })).toBeVisible();
    await page.getByLabel('Realtime Model').selectOption('gpt-realtime-1.5');
    await page.getByLabel('Stem').selectOption('marin');
    await page.getByRole('button', { name: 'Instellingen Opslaan' }).click();
    await expect(page.getByText('Instellingen succesvol opgeslagen.')).toBeVisible();

    await page.getByRole('button', { name: 'Prompts' }).click();
    await expect(page.getByText('System Prompts (Global)')).toBeVisible();

    await page.getByRole('button', { name: 'Deactiveren' }).first().click();
    await expect(page.getByRole('button', { name: 'Activeren' }).first()).toBeVisible();

    await page.getByRole('button', { name: 'Nieuwe Prompt' }).click();
    await page.getByPlaceholder('Bijv. System Prompt, Instructie, etc.').fill('E2E Prompt');
    await page.getByPlaceholder('Schrijf hier de prompt instructies voor het taalmodel...').fill('Dit is een volledig gemockte prompt voor de dashboard e2e test.');
    await page.getByRole('button', { name: 'Opslaan', exact: true }).click();
    await expect(page.getByText('E2E Prompt')).toBeVisible();

    await page.getByTitle('Verwijderen').first().click();
    await expect(page.getByText('Default Support Prompt')).toHaveCount(0);

    expect(hasCall(calls, 'GET', '/api/query/settings')).toBe(true);
    expect(hasCall(calls, 'POST', '/api/query/settings')).toBe(true);
    expect(calls.filter((call) => call.method === 'POST' && call.pathname === '/api/query/settings')).toHaveLength(2);
    expect(hasCall(calls, 'GET', '/api/query/prompts')).toBe(true);
    expect(hasCall(calls, 'PATCH', '/api/query/prompts/301')).toBe(true);
    expect(hasCall(calls, 'POST', '/api/query/prompts')).toBe(true);
    expect(hasCall(calls, 'DELETE', '/api/query/prompts/301')).toBe(true);
  });
});