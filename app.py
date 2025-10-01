import time
import threading
from collections import defaultdict, deque
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

# Config
BLOCK_INTERVAL = 8       # seconds per block
CAPACITY = 6             # slots per block
RESERVATION_DELAY = 2    # reserve for block_number + RESERVATION_DELAY

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-a-secure-secret'
socketio = SocketIO(app, cors_allowed_origins="*")  # uses eventlet by default if installed

# Game state (in-memory)
block_number = 0
lock = threading.Lock()

# reservations: dict(block_number -> deque of sid)
reservations = defaultdict(deque)
# pending submissions for the *upcoming* block (non-reserved)
pending = deque()  # elements: (sid, submit_time)

# player stats
players = {}  # sid -> { 'score': int, 'tokens': int }

def block_worker():
    global block_number, pending, reservations
    while True:
        time.sleep(BLOCK_INTERVAL)
        with lock:
            block_number += 1
            # collect reserved for this block
            reserved_queue = reservations.pop(block_number, deque())
            reserved_list = list(reserved_queue)

            # accept reserved first up to capacity
            accepted = []
            while reserved_list and len(accepted) < CAPACITY:
                sid = reserved_list.pop(0)
                accepted.append((sid, 'reserved'))

            # fill remaining slots with earliest pending submissions
            while pending and len(accepted) < CAPACITY:
                sid, ts = pending.popleft()
                accepted.append((sid, 'submitted'))

            # whatever remains in reserved_list are "bumped" (reservation paid but block full)
            bumped = reserved_list + list(pending)  # pending left are waiting for next block
            # we keep pending (they remain queued) — do nothing, they stay in pending deque

        # Send results outside lock
        for sid, kind in accepted:
            # award points
            players.setdefault(sid, {'score':0, 'tokens':10})
            players[sid]['score'] += 1
            socketio.emit('tx_result', {'status':'confirmed', 'block':block_number, 'kind': kind, 'score': players[sid]['score']}, room=sid)

        # Notify bumped reservations: reservation failed (but keep tokens consumed)
        for item in bumped:
            if isinstance(item, tuple):
                # pending tuple (sid, ts)
                sid = item[0]
                # do not emit failure for pending; they still are waiting
            else:
                sid = item
                socketio.emit('tx_result', {'status':'reservation_bumped', 'block':block_number}, room=sid)

        # broadcast new block info
        socketio.emit('block_tick', {'block': block_number, 'capacity': CAPACITY})

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    sid = request.sid
    players.setdefault(sid, {'score': 0, 'tokens': 10})
    join_room(sid)
    emit('connected', {'sid': sid, 'block': block_number, 'tokens': players[sid]['tokens'], 'score': players[sid]['score']})
    print(f"Client connected: {sid}")

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    print("Client disconnected:", sid)
    # Optionally clean up players dict after some timeout

@socketio.on('submit_tx')
def on_submit_tx(data):
    sid = request.sid
    t = time.time()
    with lock:
        # append to pending queue
        pending.append((sid, t))
    emit('tx_submitted', {'time': t})

@socketio.on('reserve_tx')
def on_reserve_tx(data):
    sid = request.sid
    # charge tokens for reservation
    cost = data.get('cost', 2)  # default cost
    with lock:
        player = players.setdefault(sid, {'score':0, 'tokens':10})
        if player['tokens'] < cost:
            emit('reserve_failed', {'reason': 'not_enough_tokens', 'tokens': player['tokens']})
            return
        # consume tokens
        player['tokens'] -= cost
        # target block number
        target_block = block_number + RESERVATION_DELAY
        reservations[target_block].append(sid)
    emit('reserve_success', {'target_block': target_block, 'tokens': players[sid]['tokens']})

# Start the background block worker thread
if __name__ == '__main__':
    thread = threading.Thread(target=block_worker, daemon=True)
    thread.start()
    # Use socketio.run for production; eventlet is preferred if installed.
    socketio.run(app, host='0.0.0.0', port=5000)