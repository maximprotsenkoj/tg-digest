const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData || '';

// ── Suggestions ───────────────────────────────────────────────────────────────

const SUGGESTIONS = [
  { username: 'breakingmash',               name: 'Mash' },
  { username: 'rbc_news',                   name: 'РБК' },
  { username: 'meduzaproject',              name: 'Meduza' },
  { username: 'bbbreaking',                 name: 'Раньше всех' },
  { username: 'rian_ru',                    name: 'РИА Новости' },
  { username: 'fontanka_news',              name: 'Фонтанка' },
  { username: 'tinkoff_invest_official',    name: 'Тинькофф' },
  { username: 'bitkogan',                   name: 'Bitkogan' },
  { username: 'durov',                      name: 'Дуров' },
  { username: 'vc_ru',                      name: 'VC.ru' },
  { username: 'habr_com',                   name: 'Хабр' },
  { username: 'ai_machinelearning_big_data',name: 'AI/ML' },
  { username: 'readovkanews',               name: 'Readovka' },
];

// ── API ───────────────────────────────────────────────────────────────────────

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

// ── Channel info cache ────────────────────────────────────────────────────────

async function getChannelInfo(username) {
  const key = `chinfo_${username}`;
  try {
    const cached = localStorage.getItem(key);
    if (cached) {
      const { data, ts } = JSON.parse(cached);
      if (Date.now() - ts < 86_400_000) return data;
    }
  } catch (_) {}
  try {
    const data = await api('GET', `/api/channel-info/${username}`);
    localStorage.setItem(key, JSON.stringify({ data, ts: Date.now() }));
    return data;
  } catch (_) {
    return { title: username, avatar: '' };
  }
}

function letterAvatarHTML(username, size = 36, cls = 'ch-avatar-letter') {
  return `<div class="${cls}" style="width:${size}px;height:${size}px;font-size:${Math.round(size * .38)}px">${(username[0] || '?').toUpperCase()}</div>`;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    if (tab.dataset.tab === 'channels') initChannelsTab();
  });
});

// ── Slider ────────────────────────────────────────────────────────────────────

const HOURS_STEPS  = [3, 6, 12, 24, 72, 168];
const HOURS_LABELS = ['3 часа', '6 часов', '12 часов', '24 часа', '3 дня', '7 дней'];
const slider    = document.getElementById('hours-slider');
const hoursLabel = document.getElementById('hours-label');

function currentHours() { return HOURS_STEPS[+slider.value]; }
slider.addEventListener('input', () => { hoursLabel.textContent = HOURS_LABELS[+slider.value]; });

// ── Importance filter ─────────────────────────────────────────────────────────

let currentMinScore = 7;

document.querySelectorAll('.imp-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.imp-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentMinScore = +btn.dataset.min;
    renderDigest();
  });
});

// ── Tag filter ────────────────────────────────────────────────────────────────

let selectedTags = new Set();
const tagFilterEl = document.getElementById('tag-filter');

function renderTagFilter() {
  const allTags = [...new Set(allPosts.flatMap(p => p.tags || []))].sort();
  if (!allTags.length) { tagFilterEl.classList.add('hidden'); return; }

  const noneSelected = selectedTags.size === 0;
  tagFilterEl.classList.remove('hidden');
  tagFilterEl.innerHTML = `
    <button class="tf-btn tf-btn-all ${noneSelected ? 'active' : ''}" onclick="toggleTag(null)">Все</button>
    ${allTags.map(t => `
      <button class="tf-btn ${selectedTags.has(t) ? 'active' : ''}" onclick="toggleTag('${esc(t)}')">${esc(t)}</button>
    `).join('')}
  `;
}

function toggleTag(tag) {
  if (!tag) {
    selectedTags.clear();
  } else {
    selectedTags.has(tag) ? selectedTags.delete(tag) : selectedTags.add(tag);
  }
  renderTagFilter();
  renderDigest();
}

// ── Digest ────────────────────────────────────────────────────────────────────

let allPosts = [];
const refreshBtn = document.getElementById('refresh-btn');
const digestList  = document.getElementById('digest-list');

function scoreClass(n) {
  if (n >= 8) return 'high';
  if (n >= 5) return 'medium';
  return 'low';
}

function renderMedia(post) {
  const m = post.media;
  if (!m || !m.url) return '';
  const isVideo = m.type === 'video' || m.type === 'video_thumb';
  return `
    <div class="card-media">
      <img src="${esc(m.url)}" loading="lazy" onerror="this.closest('.card-media').remove()" />
      ${isVideo ? `<div class="play-overlay"><div class="play-icon">&#9654;</div></div>` : ''}
    </div>`;
}

function renderCard(post) {
  const sc   = post.importance || 0;
  const tags = (post.tags || []).slice(0, 3).map(t => `<span class="tag">${esc(t)}</span>`).join('');
  const link = post.link || `https://t.me/${post.channel}`;

  return `
    <div class="card">
      <div class="card-top">
        <div class="card-tags">${tags}</div>
        <span class="badge badge-${scoreClass(sc)}">${sc}/10</span>
      </div>
      <p class="card-summary">${esc(post.summary || '')}</p>
      ${renderMedia(post)}
      <details>
        <summary>Оригинал</summary>
        <p class="original-body">${esc(post.text || '')}</p>
        <p class="original-source">Источник: <a href="${esc(link)}" target="_blank">@${esc(post.channel)}</a></p>
      </details>
    </div>`;
}

function renderDigest() {
  let filtered = allPosts.filter(p => (p.importance || 0) >= currentMinScore);
  if (selectedTags.size > 0) {
    filtered = filtered.filter(p => (p.tags || []).some(t => selectedTags.has(t)));
  }
  if (!filtered.length) {
    digestList.innerHTML = `<div class="state">Ничего не найдено с текущими фильтрами.<br>Попробуй снизить важность или убрать тег.</div>`;
    return;
  }
  digestList.innerHTML = `<div class="feed">${filtered.map(renderCard).join('')}</div>`;
}

async function loadDigest() {
  refreshBtn.disabled = true;
  refreshBtn.innerHTML = '<span class="spinner"></span> Загружаю...';
  digestList.innerHTML = '<div class="state">Анализирую каналы с помощью AI...</div>';
  tagFilterEl.classList.add('hidden');

  try {
    const data = await api('POST', '/api/digest', { hours: currentHours() });

    if (data.hint === 'no_channels') {
      digestList.innerHTML = '<div class="state">Сначала добавь каналы<br>во вкладке "Каналы"</div>';
      return;
    }
    if (!data.posts || !data.posts.length) {
      digestList.innerHTML = `<div class="state">За выбранный период ничего не найдено.<br>Попробуй увеличить диапазон.</div>`;
      return;
    }

    allPosts = data.posts;
    selectedTags.clear();
    renderTagFilter();
    renderDigest();

    if (data.failed && data.failed.length) {
      digestList.innerHTML += `<div class="state" style="padding:6px 0;font-size:12px">⚠️ Не загрузились: ${data.failed.map(c => '@' + c).join(', ')}</div>`;
    }
  } catch (e) {
    digestList.innerHTML = `<div class="state state-error">Ошибка: ${esc(e.message)}</div>`;
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.innerHTML = '<span>✨</span> Обновить дайджест';
  }
}

refreshBtn.addEventListener('click', loadDigest);

// ── Channels ──────────────────────────────────────────────────────────────────

const chInput = document.getElementById('ch-input');
const addBtn  = document.getElementById('add-btn');
const chList  = document.getElementById('channels-list');
const suggsEl = document.getElementById('suggestions');

function renderSuggestions(existing) {
  const set = new Set(existing);
  const available = SUGGESTIONS.filter(s => !set.has(s.username));
  if (!available.length) { suggsEl.innerHTML = ''; return; }
  suggsEl.innerHTML = `
    <p class="suggestions-title">Популярные каналы</p>
    <div class="suggestions-list">
      ${available.map(s => `
        <button class="suggestion-pill" onclick="addFromSuggestion('${s.username}')">
          <span class="pill-letter">${s.name[0].toUpperCase()}</span>${esc(s.name)}
        </button>`).join('')}
    </div>`;
}

async function loadChannels() {
  chList.innerHTML = '<div class="state" style="padding:16px 0">...</div>';
  try {
    const { channels } = await api('GET', '/api/channels');
    renderSuggestions(channels);
    if (!channels.length) {
      chList.innerHTML = '<div class="state" style="padding:16px 0">Нет каналов. Добавь первый!</div>';
      return;
    }
    chList.innerHTML = `<div class="ch-list" id="ch-items">
      ${channels.map(ch => `
        <div class="ch-item" id="chi-${ch}">
          ${letterAvatarHTML(ch)}
          <div class="ch-info">
            <div class="ch-name" id="chname-${ch}">${esc(ch)}</div>
            <div class="ch-username">@${esc(ch)}</div>
          </div>
          <button class="btn-del" onclick="removeChannel('${ch}')">×</button>
        </div>`).join('')}
    </div>`;

    channels.forEach(async ch => {
      const info = await getChannelInfo(ch);
      const nameEl = document.getElementById(`chname-${ch}`);
      const item   = document.getElementById(`chi-${ch}`);
      if (!nameEl || !item) return;
      if (info.title && info.title !== ch) nameEl.textContent = info.title;
      if (info.avatar) {
        const div = item.querySelector('.ch-avatar-letter');
        if (div) {
          const img = document.createElement('img');
          img.className = 'ch-avatar'; img.src = info.avatar;
          img.width = 36; img.height = 36; img.onerror = () => {};
          div.replaceWith(img);
        }
      }
    });
  } catch (e) {
    chList.innerHTML = `<div class="state state-error">${esc(e.message)}</div>`;
  }
}

async function addChannel(username) {
  const raw = (username || chInput.value).trim().replace(/^@/, '');
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

async function addFromSuggestion(username) { await addChannel(username); }

async function removeChannel(username) {
  try {
    await api('DELETE', `/api/channels/${username}`);
    await loadChannels();
  } catch (_) { tg.showAlert('Ошибка удаления'); }
}

function initChannelsTab() { loadChannels(); }

addBtn.addEventListener('click', () => addChannel());
chInput.addEventListener('keydown', e => { if (e.key === 'Enter') addChannel(); });

// ── Utils ─────────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────

loadDigest();
