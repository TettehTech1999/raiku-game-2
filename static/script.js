document.addEventListener('DOMContentLoaded', () => {
  const socket = io();
  const blockNumEl = document.getElementById('block-num');
  const capacityEl = document.getElementById('capacity');
  const submitBtn = document.getElementById('submit-btn');
  const reserveBtn = document.getElementById('reserve-btn');
  const statusEl = document.getElementById('status');
  const resultsEl = document.getElementById('results');
  const tokensEl = document.getElementById('tokens');
  const scoreEl = document.getElementById('score');

  socket.on('connect', () => {
    status('Connected to server');
  });

  socket.on('connected', (data) => {
    tokensEl.textContent = data.tokens;
    scoreEl.textContent = data.score;
    blockNumEl.textContent = data.block;
  });

  socket.on('block_tick', (data) => {
    blockNumEl.textContent = data.block;
    capacityEl.textContent = data.capacity;
    status(`Block ${data.block} started`);
  });

  socket.on('tx_submitted', (data) => {
    const t = new Date(data.time * 1000).toLocaleTimeString();
    status(`Tx submitted at ${t}`);
  });

  socket.on('reserve_success', (data) => {
    tokensEl.textContent = data.tokens;
    status(`Reserved for block ${data.target_block}. Tokens left: ${data.tokens}`);
  });

  socket.on('reserve_failed', (data) => {
    status(`Reserve failed: ${data.reason}`);
  });

  socket.on('tx_result', (data) => {
    const p = document.createElement('p');
    p.textContent = `Result: ${data.status} (${data.kind || ''}) in block ${data.block} — Score: ${data.score || '-'}`;
    resultsEl.prepend(p);
    if (data.score !== undefined) scoreEl.textContent = data.score;
  });

  submitBtn.addEventListener('click', () => {
    socket.emit('submit_tx', {});
  });

  reserveBtn.addEventListener('click', () => {
    socket.emit('reserve_tx', {cost: 2});
  });

  function status(txt) {
    statusEl.textContent = txt;
  }
});