from ion import *
from math import ceil
from kandinsky import *
from random import getrandbits
import time
try:
    import gc  # type: ignore
except ImportError:
    gc = None


class Game:
    def __init__(self, s: int) -> None:
        self.screen_size = (320, 222)
        self.size_of_case = s
        self.nx = ceil(self.screen_size[0] / s)
        self.ny = ceil(self.screen_size[1] / s)
        self.c = {
            "grid": color(128, 128, 128),
            "cw": color(200, 200, 200),
            "cb": color(50, 50, 50),
            "w": color(255, 255, 255),
            "b": color(0, 0, 0),
        }
        self.map = [[False] * self.ny for _ in range(self.nx)]
        self.cur = Cursor(self)
        self._ok = False
        self.hist: list[list[bytes]] = []
        self.limit: int | None = 4000
        self.loop()

    def loop(self) -> None:
        self.print_map()
        d = 0.25
        while True:
            self.cur.print_cursor()
            ok = keydown(KEY_OK)
            if ok and not self._ok:
                self.cur.click()
                time.sleep(d)
                self._ok = ok
                continue
            self._ok = ok
            if keydown(KEY_BACKSPACE):
                self.clear_map(); time.sleep(d)
            elif keydown(KEY_EXE):
                self.update_map(); time.sleep(d)
            elif keydown(KEY_MINUS):
                self.undo_map(); time.sleep(d)
            elif keydown(KEY_ANS):
                self.random_map(); time.sleep(d)
            elif keydown(KEY_UP):
                self.cur.move_up(); time.sleep(d)
            elif keydown(KEY_DOWN):
                self.cur.move_down(); time.sleep(d)
            elif keydown(KEY_LEFT):
                self.cur.move_left(); time.sleep(d)
            elif keydown(KEY_RIGHT):
                self.cur.move_right(); time.sleep(d)
            else:
                time.sleep(0.01)

    def update_map(self) -> None:
        self.save_state()
        nm = [[False] * self.ny for _ in range(self.nx)]
        for x in range(self.nx):
            for y in range(self.ny):
                n = self.count_neighbors(x, y)
                nm[x][y] = n == 3 or (self.map[x][y] and n == 2)
        self.map = nm
        self.print_map()

    def count_neighbors(self, x: int, y: int) -> int:
        c = 0
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                if i or j:
                    nx, ny = x + i, y + j
                    if 0 <= nx < self.nx and 0 <= ny < self.ny:
                        c += self.map[nx][ny]
        return c

    def clear_map(self) -> None:
        self.map = [[False] * self.ny for _ in range(self.nx)]
        self.hist = []
        self.print_map()

    def random_map(self) -> None:
        for x in range(self.nx):
            for y in range(self.ny):
                self.map[x][y] = bool(getrandbits(1))
        self.hist = []
        self.print_map()

    def save_state(self) -> None:
        if gc:
            try:
                gc.collect()
            except Exception:
                pass
        comp: list[bytes] = []
        for y in range(self.ny):
            bit = 0
            val = 0
            row: list[int] = []
            for x in range(self.nx):
                val = (val << 1) | (1 if self.map[x][y] else 0)
                bit += 1
                if bit == 8:
                    row.append(val)
                    bit = 0
                    val = 0
            if bit:
                row.append(val << (8 - bit))
            comp.append(bytes(row))
        self.hist.append(comp)
        self.enforce_limit()

    def enforce_limit(self) -> None:
        if self.limit is None:
            return
        total = 0
        for m in self.hist:
            for r in m:
                total += len(r)
        while total > self.limit and self.hist:
            rm = self.hist.pop(0)
            for r in rm:
                total -= len(r)
        if gc:
            try:
                gc.collect()
            except Exception:
                pass

    def undo_map(self) -> None:
        if self.hist:
            prev = self.hist.pop()
            new_map = [[False] * self.ny for _ in range(self.nx)]
            for y in range(self.ny):
                row = prev[y]
                bit_idx = 0
                for b in row:
                    for pos in range(7, -1, -1):
                        if bit_idx < self.nx:
                            new_map[bit_idx][y] = ((b >> pos) & 1) == 1
                            bit_idx += 1
            self.map = new_map
            self.print_map()

    def print_map(self) -> None:
        for i in range(0, self.screen_size[0], self.size_of_case):
            fill_rect(i, 0, 1, self.screen_size[1], self.c["grid"])
        for i in range(0, self.screen_size[1], self.size_of_case):
            fill_rect(0, i, self.screen_size[0], 1, self.c["grid"])
        for x in range(self.nx):
            for y in range(self.ny):
                fill_rect(
                    x * self.size_of_case + 1,
                    y * self.size_of_case + 1,
                    self.size_of_case - 1,
                    self.size_of_case - 1,
                    self.c["b"] if self.map[x][y] else self.c["w"],
                )


class Cursor:
    def __init__(self, g: Game) -> None:
        self.g = g
        self.loc = [0, 0]

    def mv(self, dx: int, dy: int) -> None:
        x, y = self.loc
        nx, ny = x + dx, y + dy
        if 0 <= nx < self.g.nx and 0 <= ny < self.g.ny:
            self.reset_case()
            self.loc = [nx, ny]
        self.print_cursor()

    def move_up(self) -> None:
        self.mv(0, -1)

    def move_down(self) -> None:
        self.mv(0, 1)

    def move_left(self) -> None:
        self.mv(-1, 0)

    def move_right(self) -> None:
        self.mv(1, 0)

    def click(self) -> None:
        x, y = self.loc
        self.g.map[x][y] = not self.g.map[x][y]
        self.print_cursor()

    def reset_case(self) -> None:
        x, y = self.loc
        sz = self.g.size_of_case
        fill_rect(
            x * sz + 1,
            y * sz + 1,
            sz - 1,
            sz - 1,
            self.g.c["b"] if self.g.map[x][y] else self.g.c["w"],
        )

    def print_cursor(self) -> None:
        x, y = self.loc
        sz = self.g.size_of_case
        fill_rect(
            x * sz + 1,
            y * sz + 1,
            sz - 1,
            sz - 1,
            self.g.c["cb"] if self.g.map[x][y] else self.g.c["cw"],
        )


try:
    size = int(input("Taille des cases : "))
except Exception:
    size = 10
Game(size)