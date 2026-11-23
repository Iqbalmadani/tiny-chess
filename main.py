# Compact chess engine core (spike v1): negamax + alpha-beta + quiescence,
# MVV-LVA ordering, transposition table, material + PST evaluation.
# Board: list of 64 ints, a1=0 .. h8=63. Pieces: sign = colour (+ white),
# abs: 1=P 2=N 3=B 4=R 5=Q 6=K. Move = (from, to, promo, kind) packed int:
# from | to<<6 | promo<<12 | flag<<15 (1=double,2=ep,4=castleK,8=castleQ)
V = [0, 100, 320, 330, 500, 1000, 0]
PST = {
 1: [0,0,0,0,0,0,0,0, 5,10,10,-20,-20,10,10,5, 5,-5,-10,0,0,-10,-5,5, 0,0,0,20,20,0,0,0, 5,5,10,25,25,10,5,5, 10,10,20,30,30,20,10,10, 50,50,50,50,50,50,50,50, 0,0,0,0,0,0,0,0],
 2: [-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,5,5,0,-20,-40, -30,5,10,15,15,10,5,-30, -30,0,15,20,20,15,0,-30, -30,5,15,20,20,15,5,-30, -30,0,10,15,15,10,0,-30, -40,-20,0,0,0,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50],
 3: [-20,-10,-10,-10,-10,-10,-10,-20, -10,5,0,0,0,0,5,-10, -10,10,10,10,10,10,10,-10, -10,0,10,10,10,10,0,-10, -10,5,5,10,10,5,5,-10, -10,0,5,10,10,5,0,-10, -10,0,0,0,0,0,0,-10, -20,-10,-10,-10,-10,-10,-10,-20],
 4: [0,0,0,5,5,0,0,0, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, 5,10,10,10,10,10,10,5, 0,0,0,0,0,0,0,0],
 5: [-20,-10,-10,-5,-5,-10,-10,-20, -10,0,5,0,0,5,0,-10, -10,5,5,5,5,5,5,-10, 0,0,5,5,5,5,0,-5, -5,0,5,5,5,5,0,-5, -10,0,5,5,5,5,0,-10, -10,0,0,0,0,0,0,-10, -20,-10,-10,-5,-5,-10,-10,-20],
 6: [20,30,10,0,0,10,30,20, 20,20,0,0,0,0,20,20, 10,-20,-20,-20,-20,-20,-20,10, 20,-30,-30,-40,-40,-30,-30,20, 30,-40,-40,-50,-50,-40,-40,30, 30,-40,-40,-50,-50,-40,-40,30, 30,-40,-40,-50,-50,-40,-40,30, 20,-30,-30,-40,-40,-30,-30,20],
}
KE = [0,-10,-20,-30,-30,-20,-10,0, -10,-20,-30,-40,-40,-30,-20,-10, -20,-30,-40,-50,-50,-40,-30,-20, -30,-40,-50,-60,-60,-50,-40,-30, -30,-40,-50,-60,-60,-50,-40,-30, -20,-30,-40,-50,-50,-40,-30,-20, -10,-20,-30,-40,-40,-30,-20,-10, 0,-10,-20,-30,-30,-20,-10,0]
ND = [(-1,-2),(-2,-1),(-2,1),(-1,2),(1,2),(2,1),(2,-1),(1,-2)]
KD = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
BD = [(-1,-1),(-1,1),(1,-1),(1,1)]
RD = [(-1,0),(1,0),(0,-1),(0,1)]

class Pos:
    __slots__ = ('b','turn','castle','ep','half','wk','bk')
    def __init__(self, fen):
        parts = fen.split()
        self.b = [0]*64
        r, f = 7, 0
        for ch in parts[0]:
            if ch == '/': r -= 1; f = 0
            elif ch.isdigit(): f += int(ch)
            else:
                p = 'PNBRQK'.index(ch.upper()) + 1
                self.b[r*8+f] = p if ch.isupper() else -p
                if p == 6:
                    if ch.isupper(): self.wk = r*8+f
                    else: self.bk = r*8+f
                f += 1
        self.turn = 1 if parts[1] == 'w' else -1
        self.castle = parts[2]
        self.ep = -1 if parts[3] == '-' else (int(parts[3][1])-1)*8 + (ord(parts[3][0])-97)
        self.half = int(parts[4]) if len(parts) > 4 else 0

def attacked(b, sq, by):
    f, r = sq & 7, sq >> 3
    pr = r - by  # pawns of colour 'by' attack from one rank behind
    if 0 <= pr < 8:
        for df in (-1, 1):
            pf = f + df
            if 0 <= pf < 8 and b[pr*8+pf] == by*1: return True
    for df, dr in ND:
        nf, nr = f+df, r+dr
        if 0 <= nf < 8 and 0 <= nr < 8 and b[nr*8+nf] == by*2: return True
    for df, dr in KD:
        nf, nr = f+df, r+dr
        if 0 <= nf < 8 and 0 <= nr < 8 and b[nr*8+nf] == by*6: return True
    for dirs, kinds in ((BD, (3, 5)), (RD, (4, 5))):
        for df, dr in dirs:
            nf, nr = f+df, r+dr
            while 0 <= nf < 8 and 0 <= nr < 8:
                p = b[nr*8+nf]
                if p:
                    if p == by*kinds[0] or p == by*kinds[1]: return True
                    break
                nf += df; nr += dr
    return False

def gen_moves(pos, captures_only=False):
    b, t = pos.b, pos.turn
    moves = []
    for sq in range(64):
        p = b[sq]
        if not p or (p > 0) != (t > 0): continue
        a = abs(p); f, r = sq & 7, sq >> 3
        if a == 1:
            d = 8*t
            start = 1 if t > 0 else 6
            last = 7 if t > 0 else 0
            one = sq + d
            if not captures_only and 0 <= one < 64 and not b[one]:
                if (one >> 3) == last:
                    for pr in (5, 4, 3, 2): moves.append(sq | one<<6 | pr<<12)
                else:
                    moves.append(sq | one<<6)
                    two = sq + 2*d
                    if r == start and not b[two]: moves.append(sq | two<<6 | 1<<15)
            for df in (-1, 1):
                nf = f + df
                if not (0 <= nf < 8): continue
                to = sq + d + df
                if not (0 <= to < 64): continue
                tgt = b[to]
                if tgt and (tgt > 0) != (t > 0):
                    if (to >> 3) == last:
                        for pr in (5, 4, 3, 2): moves.append(sq | to<<6 | pr<<12)
                    else: moves.append(sq | to<<6)
                elif to == pos.ep:
                    moves.append(sq | to<<6 | 2<<15)
        elif a == 2:
            for df, dr in ND:
                nf, nr = f+df, r+dr
                if 0 <= nf < 8 and 0 <= nr < 8:
                    to = nr*8+nf; tgt = b[to]
                    if not tgt: 
                        if not captures_only: moves.append(sq | to<<6)
                    elif (tgt > 0) != (t > 0): moves.append(sq | to<<6)
        elif a == 6:
            for df, dr in KD:
                nf, nr = f+df, r+dr
                if 0 <= nf < 8 and 0 <= nr < 8:
                    to = nr*8+nf; tgt = b[to]
                    if not tgt:
                        if not captures_only: moves.append(sq | to<<6)
                    elif (tgt > 0) != (t > 0): moves.append(sq | to<<6)
            if not captures_only:
                home = 0 if t > 0 else 56
                ks = home + 4
                if sq == ks:
                    c = pos.castle
                    if (('K' if t > 0 else 'k') in c) and not b[home+5] and not b[home+6] and b[home+7] == t*4:
                        if not attacked(b, ks, -t) and not attacked(b, home+5, -t) and not attacked(b, home+6, -t):
                            moves.append(sq | (home+6)<<6 | 4<<15)
                    if (('Q' if t > 0 else 'q') in c) and not b[home+3] and not b[home+2] and not b[home+1] and b[home] == t*4:
                        if not attacked(b, ks, -t) and not attacked(b, home+3, -t) and not attacked(b, home+2, -t):
                            moves.append(sq | (home+2)<<6 | 8<<15)
        else:
            dirs = BD if a == 3 else RD if a == 4 else KD
            for df, dr in dirs:
                nf, nr = f+df, r+dr
                while 0 <= nf < 8 and 0 <= nr < 8:
                    to = nr*8+nf; tgt = b[to]
                    if not tgt:
                        if not captures_only: moves.append(sq | to<<6)
                    else:
                        if (tgt > 0) != (t > 0): moves.append(sq | to<<6)
                        break
                    nf += df; nr += dr
    return moves

def make(pos, m):
    b = pos.b; frm = m & 63; to = (m >> 6) & 63; pr = (m >> 12) & 7; fl = m >> 15
    p = b[frm]; cap = b[to]
    undo = (cap, pos.castle, pos.ep, pos.half)
    if fl & 2: cap = b[to - 8*pos.turn]; b[to - 8*pos.turn] = 0
    b[to] = pos.turn*pr if pr else p
    b[frm] = 0
    if fl & 4: b[to-1] = b[to+1]; b[to+1] = 0
    if fl & 8: b[to+1] = b[to-2]; b[to-2] = 0
    if abs(p) == 6:
        if pos.turn > 0: pos.wk = to
        else: pos.bk = to
    pos.ep = to if fl & 1 else -1
    c = pos.castle
    if abs(p) == 6: c = c.replace('K','').replace('Q','') if pos.turn > 0 else c.replace('k','').replace('q','')
    for sq, ch in ((0,'Q'),(7,'K'),(56,'q'),(63,'k')):
        if frm == sq or to == sq: c = c.replace(ch, '')
    pos.castle = c if c else '-'
    pos.half = 0 if abs(p) == 1 or cap else pos.half + 1
    pos.turn = -pos.turn
    return undo

def unmake(pos, m, undo):
    pos.turn = -pos.turn
    b = pos.b; frm = m & 63; to = (m >> 6) & 63; pr = (m >> 12) & 7; fl = m >> 15
    cap, pos.castle, pos.ep, pos.half = undo
    p = b[to]
    b[frm] = pos.turn*1 if pr else p
    b[to] = 0 if fl & 2 else cap
    if fl & 2: b[to - 8*pos.turn] = -pos.turn
    if fl & 4: b[to+1] = b[to-1]; b[to-1] = 0
    if fl & 8: b[to-2] = b[to+1]; b[to+1] = 0
    if abs(b[frm]) == 6:
        if pos.turn > 0: pos.wk = frm
        else: pos.bk = frm

def evaluate(pos):
    b = pos.b; s = 0; phase = 0
    for sq in range(64):
        p = b[sq]
        if not p: continue
        a = abs(p)
        if a < 5: phase += (0, 1, 1, 2, 4, 0)[a]
        tbl = PST[a]
        v = V[a] + (tbl[sq ^ 56] if p > 0 else tbl[sq])
        s += v if p > 0 else -v
    # endgame king table blend
    eg = 1 - min(phase, 24)/24
    if eg > 0:
        s += int(eg * KE[pos.wk ^ 56]) - int(eg * KE[pos.bk])
    return s * pos.turn

nodes = 0
TT = {}
NODE_BUDGET = 60000

def order_key(pos, m):
    to = (m >> 6) & 63; cap = pos.b[to]
    if cap: return 10*V[abs(cap)] - V[abs(pos.b[m & 63])]
    if m >> 15 & 2: return 10*V[1] - V[1]
    pr = (m >> 12) & 7
    return V[pr] if pr else 0

def quiesce(pos, alpha, beta):
    global nodes
    nodes += 1
    stand = evaluate(pos)
    if stand >= beta: return beta
    if stand > alpha: alpha = stand
    ms = gen_moves(pos, captures_only=True)
    ms.sort(key=lambda m: order_key(pos, m), reverse=True)
    for m in ms:
        undo = make(pos, m)
        ksq = pos.wk if pos.turn < 0 else pos.bk
        if attacked(pos.b, ksq, pos.turn):
            unmake(pos, m, undo); continue
        sc = -quiesce(pos, -beta, -alpha)
        unmake(pos, m, undo)
        if sc >= beta: return beta
        if sc > alpha: alpha = sc
    return alpha

def search(pos, depth, alpha, beta, ply):
    global nodes
    if nodes >= NODE_BUDGET: return quiesce(pos, alpha, beta)
    if pos.half >= 100: return 0
    key = (tuple(pos.b), pos.turn, pos.castle, pos.ep)
    ent = TT.get(key)
    tt_move = -1
    if ent and ent[0] >= depth:
        if ent[1] == 0: return ent[2]
        if ent[1] == 1 and ent[2] > alpha: alpha = ent[2]
        elif ent[1] == 2 and ent[2] < beta: beta = ent[2]
        if alpha >= beta: return ent[2]
    if ent: tt_move = ent[3]
    if depth <= 0: return quiesce(pos, alpha, beta)
    nodes += 1
    ms = gen_moves(pos)
    ms.sort(key=lambda m: (100000 if m == tt_move else order_key(pos, m)), reverse=True)
    best = -10**9; best_m = -1; legal = 0; a0 = alpha
    for m in ms:
        undo = make(pos, m)
        ksq = pos.wk if pos.turn < 0 else pos.bk
        if attacked(pos.b, ksq, pos.turn):
            unmake(pos, m, undo); continue
        legal += 1
        sc = -search(pos, depth-1, -beta, -alpha, ply+1)
        unmake(pos, m, undo)
        if sc > best: best, best_m = sc, m
        if sc > alpha: alpha = sc
        if alpha >= beta: break
    if legal == 0:
        ksq = pos.wk if pos.turn < 0 else pos.bk
        # side to move is -pos.turn after make/unmake cycle; pos.turn is mover
        ksq = pos.wk if pos.turn > 0 else pos.bk
        return -99999 + ply if attacked(pos.b, ksq, -pos.turn) else 0
    flag = 0 if a0 < best < beta else (2 if best <= a0 else 1)
    TT[key] = (depth, flag, best, best_m)
    return best

def best_move(fen, legal_uci):
    global nodes
    pos = Pos(fen)
    nodes = 0
    TT.clear()
    root = []
    for u in legal_uci:
        frm = (int(u[1])-1)*8 + (ord(u[0])-97)
        to = (int(u[3])-1)*8 + (ord(u[2])-97)
        pr = 'NBRQ'.index(u[4].upper()) + 2 if len(u) == 5 else 0
        root.append((u, frm | to<<6 | pr<<12))
    best_u, best_s = root[0][0], -10**9
    for depth in (1, 2, 3, 4, 5, 6):
        cur_u, cur_s = best_u, -10**9
        scored = []
        for u, m in root:
            undo = make(pos, m)
            sc = -search(pos, depth-1, -10**9, 10**9, 1)
            unmake(pos, m, undo)
            scored.append((sc, u))
            if sc > cur_s: cur_s, cur_u = sc, u
        best_u, best_s = cur_u, cur_s
        if nodes >= NODE_BUDGET: break
    return best_u


# --- env protocol loop (MAKEFUN_ENV_URL) ---
import json, os, sys, urllib.request, urllib.error
U = os.environ.get("MAKEFUN_ENV_URL") or sys.exit("MAKEFUN_ENV_URL is not set")
def post(path, body):
    req = urllib.request.Request(U + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res: return json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f"{path}: HTTP {e.code} {e.read().decode(errors='replace')}")
while True:
    g = post("/game", {})
    if g["status"] == "done": break
    while g["status"] == "your_move":
        g = post("/move", {"game": g["game"], "move": best_move(g["fen"], g["legal_moves"])})
    print(f"game {g['game']}: {g['outcome']} by {g['reason']}", file=sys.stderr)
print(f"done: {g.get('wins')} won, {g.get('draws')} drawn, {g.get('losses')} lost", file=sys.stderr)
