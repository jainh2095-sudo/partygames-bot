from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cogs.additional_games import clean_chain_word
from cogs.connect4 import EMPTY, RED, check_connect4 as detect_connect4
from cogs.tictactoe import best_move, winner
from utils.safety import is_safe_text, sanitize_text


def check_tictactoe() -> None:
    assert winner(["X", "X", "X", " ", "O", " ", "O", " ", " "]) == "X"
    assert winner(["X", "O", "X", "X", "O", "O", "O", "X", "X"]) == "draw"
    assert best_move(["O", "O", " ", "X", " ", " ", "X", " ", " "], "O", "X", "Hard") == 2
    assert best_move(["X", "X", " ", "O", " ", " ", " ", " ", " "], "O", "X", "Medium") == 2


def check_connect4_rules() -> None:
    board = [[EMPTY for _ in range(7)] for _ in range(6)]
    for col in range(4):
        board[5][col] = RED
    assert detect_connect4(board) == RED

    board = [[EMPTY for _ in range(7)] for _ in range(6)]
    for step in range(4):
        board[5 - step][step] = RED
    assert detect_connect4(board) == RED


def check_safety_and_words() -> None:
    assert not is_safe_text("this has porn in it")
    assert "[filtered]" in sanitize_text("no porn please")
    assert clean_chain_word("Namaste") == "namaste"
    assert clean_chain_word("cafe") == "cafe"
    assert clean_chain_word("bonjour!") is None


if __name__ == "__main__":
    check_tictactoe()
    check_connect4_rules()
    check_safety_and_words()
    print("logic checks passed")
