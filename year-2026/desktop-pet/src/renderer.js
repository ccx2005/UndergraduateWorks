// ============ 桌面宠物 - 凯尔希 渲染进程 ============
// 结构延续原小橘桌宠（idle/happy/sleep/eating 四态 + 拖拽 + 心心/Zzz 特效），
// 视觉层替换为凯尔希像素小人 PNG，表情变化由整体动效表现。

// --- State machine ---
const States = { IDLE: 'idle', HAPPY: 'happy', SLEEP: 'sleep', EATING: 'eating' };

let currentState = States.IDLE;
let stateTimer = null;
let idleTimer = null;

// --- DOM refs ---
const petBody = document.querySelector('.pet-body');
const sprite = document.getElementById('kaltist-sprite');
const effectsLayer = document.getElementById('effects-layer');
const clickHint = document.getElementById('click-hint');

// --- Dragging ---
let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let hasMoved = false;

document.addEventListener('mousedown', (e) => {
  if (e.button !== 0) return;
  isDragging = true;
  hasMoved = false;
  dragStartX = e.screenX;
  dragStartY = e.screenY;
  document.body.classList.add('dragging');
  if (petBody) petBody.style.transform = 'scale(1.05)';
});

document.addEventListener('mousemove', (e) => {
  if (!isDragging) return;
  const dx = e.screenX - dragStartX;
  const dy = e.screenY - dragStartY;
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasMoved = true;
  dragStartX = e.screenX;
  dragStartY = e.screenY;
  if (window.petAPI) window.petAPI.moveWindow(dx, dy);
});

document.addEventListener('mouseup', () => {
  isDragging = false;
  document.body.classList.remove('dragging');
  if (petBody) petBody.style.transform = '';
  if (!hasMoved) petPetted();
});

document.addEventListener('contextmenu', (e) => e.preventDefault());

// --- IPC: tray menu actions ---
if (window.petAPI) {
  window.petAPI.onPetAction((action) => {
    switch (action) {
      case 'feed': feedPet(); break;
      case 'play': petPetted(); break;
      case 'sleep': toggleSleep(); break;
    }
  });
}

// --- State transitions ---
function setState(state) {
  if (currentState === state) return;
  exitState(currentState);
  currentState = state;
  enterState(state);
}

function exitState() {
  if (stateTimer) { clearTimeout(stateTimer); stateTimer = null; }
  if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
  if (petBody) { petBody.style.animation = ''; petBody.style.transform = ''; }
}

function enterState(state) {
  switch (state) {
    case States.IDLE: startIdle(); break;
    case States.HAPPY: startHappy(); break;
    case States.SLEEP: startSleep(); break;
    case States.EATING: startEating(); break;
  }
}

// --- IDLE ---
function startIdle() {
  if (petBody) petBody.style.animation = 'idleBounce 2s ease-in-out infinite';
  scheduleRandomAction();
}

function scheduleRandomAction() {
  idleTimer = setTimeout(() => {
    if (currentState === States.IDLE) {
      petPetted();
      scheduleRandomAction();
    }
  }, 10000 + Math.random() * 15000);
}

// --- HAPPY ---
function petPetted() {
  if (currentState === States.SLEEP) { setState(States.IDLE); return; }
  setState(States.HAPPY);
}

function startHappy() {
  if (petBody) petBody.style.animation = 'happyWiggle 0.4s ease-in-out 3';
  showHint('嗯，不许乱摸。');
  spawnHearts(4);
  stateTimer = setTimeout(() => setState(States.IDLE), 3000);
}

// --- SLEEP ---
function toggleSleep() {
  setState(currentState === States.SLEEP ? States.IDLE : States.SLEEP);
}

function startSleep() {
  if (petBody) petBody.style.animation = 'sleepBreathe 3s ease-in-out infinite';
  showHint('Zzz...');
  spawnZzz();
  stateTimer = setInterval(() => { if (currentState === States.SLEEP) spawnZzz(); }, 2500);
}

// --- EATING ---
function feedPet() {
  setState(States.EATING);
}

function startEating() {
  if (petBody) petBody.style.animation = 'eatNod 0.4s ease-in-out 5';
  showHint('难得有好东西吃……');
  spawnHearts(2);
  stateTimer = setTimeout(() => setState(States.IDLE), 4000);
}

// --- Helpers ---
function showHint(text) {
  clickHint.textContent = text;
  clickHint.style.opacity = '1';
  setTimeout(() => { clickHint.style.opacity = '0'; }, 1500);
}

function spawnHearts(count) {
  const colors = ['#FF6B6B', '#FF8E8E', '#FF6B9D', '#FECA57', '#FF9FF3'];
  for (let i = 0; i < count; i++) {
    setTimeout(() => {
      const heart = document.createElement('div');
      heart.className = 'effect heart';
      heart.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="' + colors[Math.floor(Math.random() * colors.length)] + '"/></svg>';
      heart.style.left = (25 + Math.random() * 70) + 'px';
      heart.style.top = (15 + Math.random() * 25) + 'px';
      effectsLayer.appendChild(heart);
      setTimeout(() => heart.remove(), 1300);
    }, i * 200);
  }
}

function spawnZzz() {
  const zzz = document.createElement('div');
  zzz.className = 'effect zzz';
  zzz.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24"><text x="0" y="20" font-size="20" fill="#74B9FF" font-weight="bold" font-family="sans-serif">Z</text></svg>';
  zzz.style.left = '72px';
  zzz.style.top = '30px';
  effectsLayer.appendChild(zzz);
  setTimeout(() => zzz.remove(), 2200);
}

// --- Init ---
setState(States.IDLE);