const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData || '';

// ── Popular channel suggestions ───────────────────────────────────────────────

const SUGGESTIONS = [
  { username: 'breakingmash',        name: 'Mash' },
  { username: 'rbc_news',            name: 'РБК' },
  { username: 'meduzaproject',       name: 'Meduza' },
  { username: 'bbbreaking',          name: 'Раньше всех' },
  { username: 'fontanka_news',       name: 'Фонтанка' },
  { username: 'rian_ru',             name: 'РИА Новости' },
  { username: 'tinkoff_invest_official', name: 'Тинькофф' },
  { username: 'bitkogan',            name: 'Bitkogan' },
  { username: 'durov',               name: 'Дуров' },
  { username: 'vc_ru',               name: 'VC.ru' },
  { username: 'habr_com',            name: 'Хабр' },
  { username: 'ai_machinelearning_big_data', name: 'AI/ML' },
  { username: 'techsparks',          name: 'TechSparks' },
  { username: 'readovkanews',        name: 'Readovka' },
  { username: 'bankrollo',           name: 'Банкролло' },
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

function avatarEl(info, username, size = 36) {
  if (info && info.avatar) {
    return `<img class="ch-avatar" src="${esc(info.avatar)}" width="${size}" height="${size}" loading="lazy" onerror="this.replaceWith(letterAvatar('${esc(username)}', ${size}))" />`;
  }
  return letterAvatarHTML(username, size);
}

function letterAvatarHTML(username, size = 36, cls = 'ch-avatar-letter') {
  return `<div class="${cls}" style="width:${size}px;height:${size}px;font-size:${Math.round(size * 0.38)}px">${(username[0] || '?').toUpperCase()}</div>`;
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

const HOURS_STEPS = [3, 6, 12, 24, 72, 168];
const HOURS_LABELS = ['3 часа', '6 часов', '12 часов', '24 часа', '3 дня', '7 дней'];

const slider = document.getElementById('hours-slider');
const hoursLabel = document.getElementById('hours-label');

function currentHours() { return HOURS_STEPS[+slider.value]; }

slider.addEventListener('input', () => {
  hoursLabel.textContent = HOURS_LABELS[+slider.value];
});

// ── Importance filter ─────────────────────────────────────────────────────────

let currentMinScore = 7;
let allPosts = [];

document.querySelectorAll('.imp-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.imp-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentMinScore = +btn.dataset.min;
    renderDigest();
  });
});

// ── Digest ────────────────────────────────────────────────────────────────────

const refreshBtn = document.getElementById('refresh-btn');
const digestList = document.getElementById('digest-list');

function scoreClass(n) {
  if (n >= 8) return 'high';
  if (n >= 5) return 'medium';
  return 'low';
}

function renderCard(post) {
  const sc = post.importance || 0;
  const tags = (post.tags || []).slice(0, 2).map(t => `<span class="tag">${esc(t)}</span>`).join('');
  const link = post.link || `https://t.me/${post.channel}`;

  return `
    <div class="card">
      <div class="card-top">
        <div class="card-tags">${tags}</div>
        <span class="badge badge-${scoreClass(sc)}">${sc}/10</span>
      </div>
      <p class="card-summary">${esc(post.summary || '')}</p>
      <details>
        <summary>Оригинал</summary>
        <p class="original-body">${esc(post.text || '')}</p>
        <p class="original-source">
          Источник: <a href="${esc(link)}" target="_blank">@${esc(post.channel)}</a>
        </p>
      </details>
    </div>`;
}

function renderDigest() {
  const filtered = allPosts.filter(p => (p.importance || 0) >= currentMinScore);
  if (!filtered.length) {
    digestList.innerHTML = `<div class="state">Нет постов с выбранным уровнем важности.<br>Попробуй снизить фильтр или расширить период.</div>`;
    return;
  }
  digestList.innerHTML = `<div class="feed">${filtered.map(renderCard).join('')}</div>`;
}

async function loadDigest() {
  refreshBtn.disabled = true;
  refreshBtn.innerHTML = '<span class="spinner"></span> Загружаю...';
  digestList.innerHTML = '<div class="state">Анализирую каналы с помощью AI...</div>';

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
    renderDigest();

    if (data.failed && data.failed.length) {
      digestList.innerHTML += `<div class="state" style="padding:8px 0;font-size:12px">⚠️ Не удалось загрузить: ${data.failed.map(c => '@' + c).join(', ')}</div>`;
    }
  } catch (e) {
    digestList.innerHTML = `<div class="state state-error">Ошибка: ${esc(e.message)}</div>`;
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.innerHTML = '<span>✨</span> Обновить дайджест';
  }
}

refreshBtn.addEventListener('click', loadDigest);

// ── Channels tab ──────────────────────────────────────────────────────────────

const chInput  = document.getElementById('ch-input');
const addBtn   = document.getElementById('add-btn');
const chList   = document.getElementById('channels-list');
const suggsEl  = document.getElementById('suggestions');

function renderSuggestions(existing) {
  const set = new Set(existing);
  const available = SUGGESTIONS.filter(s => !set.has(s.username));
  if (!available.length) { suggsEl.innerHTML = ''; return; }

  suggsEl.innerHTML = `
    <p class="suggestions-title">Популярные каналы</p>
    <div class="suggestions-list">
      ${available.map(s => `
        <button class="suggestion-pill" onclick="addFromSuggestion('${s.username}')">
          <span class="pill-letter">${s.name[0].toUpperCase()}</span>
          ${esc(s.name)}
        </button>
      `).join('')}
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

    // Render list, then load avatars async
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

    // Load avatars and names in background
    channels.forEach(async ch => {
      const info = await getChannelInfo(ch);
      const nameEl = document.getElementById(`chname-${ch}`);
      const item = document.getElementById(`chi-${ch}`);
      if (!nameEl || !item) return;
      if (info.title && info.title !== ch) nameEl.textContent = info.title;
      if (info.avatar) {
        const avatarDiv = item.querySelector('.ch-avatar-letter');
        if (avatarDiv) {
          const img = document.createElement('img');
          img.className = 'ch-avatar';
          img.src = info.avatar;
          img.width = 36; img.height = 36;
          img.onerror = () => {};
          avatarDiv.replaceWith(img);
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

async function addFromSuggestion(username) {
  await addChannel(username);
}

async function removeChannel(username) {
  try {
    await api('DELETE', `/api/channels/${username}`);
    await loadChannels();
  } catch (_) {
    tg.showAlert('Ошибка удаления');
  }
}

function initChannelsTab() { loadChannels(); }

addBtn.addEventListener('click', () => addChannel());
chInput.addEventListener('keydown', e => { if (e.key === 'Enter') addChannel(); });

// ── Utils ─────────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────

loadDigest();
