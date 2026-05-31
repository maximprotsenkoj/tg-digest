const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData || '';

// ── API ──────────────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Init-Data': initData },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    if (tab.dataset.tab === 'channels') loadChannels();
  });
});

// ── Digest ───────────────────────────────────────────────────────────────────

const refreshBtn = document.getElementById('refresh-btn');
const digestList = document.getElementById('digest-list');

function scoreClass(n) {
  if (n >= 8) return 'high';
  if (n >= 5) return 'medium';
  return 'low';
}

function renderCard(post) {
  const sc = post.importance || 0;
  return `
    <div class="card">
      <div class="card-meta">
        <span class="card-channel">@${post.channel}</span>
        <span class="badge badge-${scoreClass(sc)}">${sc}/10</span>
      </div>
      <p class="card-summary">${escHtml(post.summary || '')}</p>
      ${post.text ? `
      <details>
        <summary>Оригинал</summary>
        <p class="original-text">${escHtml(post.text)}</p>
      </details>` : ''}
    </div>
  `;
}

async function loadDigest() {
  refreshBtn.disabled = true;
  refreshBtn.innerHTML = '<span class="spinner"></span> Загружаю...';
  digestList.innerHTML = '<div class="state">Анализирую каналы с помощью AI...</div>';

  try {
    const data = await api('POST', '/api/digest');

    if (data.hint === 'no_channels') {
      digestList.innerHTML = '<div class="state">Сначала добавь каналы во вкладке "Каналы"</div>';
      return;
    }
    if (!data.posts.length) {
      digestList.innerHTML = '<div class="state">Важных новостей не найдено.\nПопробуй позже или добавь больше каналов.</div>';
      return;
    }

    digestList.innerHTML = `<div class="feed">${data.posts.map(renderCard).join('')}</div>`;

    if (data.failed && data.failed.length) {
      digestList.innerHTML += `<div class="state" style="padding:12px 0">⚠️ Не удалось загрузить: ${data.failed.map(c => '@' + c).join(', ')}</div>`;
    }
  } catch (e) {
    digestList.innerHTML = `<div class="state state-error">Ошибка: ${e.message}</div>`;
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.innerHTML = '<span>✨</span> Обновить дайджест';
  }
}

refreshBtn.addEventListener('click', loadDigest);

// ── Channels ─────────────────────────────────────────────────────────────────

const chInput = document.getElementById('ch-input');
const addBtn = document.getElementById('add-btn');
const channelsList = document.getElementById('channels-list');

async function loadChannels() {
  channelsList.innerHTML = '<div class="state">...</div>';
  try {
    const { channels } = await api('GET', '/api/channels');
    if (!channels.length) {
      channelsList.innerHTML = '<div class="state">Нет каналов. Добавь первый!</div>';
      return;
    }
    channelsList.innerHTML = `
      <div class="ch-list">
        ${channels.map(ch => `
          <div class="ch-item">
            <span class="ch-name">@${ch}</span>
            <button class="btn-del" onclick="removeChannel('${ch}')">×</button>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    channelsList.innerHTML = `<div class="state state-error">${e.message}</div>`;
  }
}

async function addChannel() {
  const raw = chInput.value.trim().replace(/^@/, '');
  if (!raw) return;

  addBtn.disabled = true;
  try {
    await api('POST', '/api/channels', { username: raw });
    chInput.value = '';
    await loadChannels();
  } catch (e) {
    tg.showAlert(e.message || 'Не удалось добавить канал');
  } finally {
    addBtn.disabled = false;
  }
}

async function removeChannel(username) {
  try {
    await api('DELETE', `/api/channels/${username}`);
    await loadChannels();
  } catch (e) {
    tg.showAlert('Ошибка удаления');
  }
}

addBtn.addEventListener('click', addChannel);
chInput.addEventListener('keydown', e => { if (e.key === 'Enter') addChannel(); });

// ── Init ─────────────────────────────────────────────────────────────────────

function escHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

loadDigest();
