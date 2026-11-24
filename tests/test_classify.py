import pytest

from radar.classify import classify, is_trusted


@pytest.mark.parametrize("title,item", [
    ("Console Sony PlayStation 5, SSD 825GB, Edição Digital", "ps5"),
    ("PlayStation®5 Slim Disk - Pacote ASTRO BOT e Gran Turismo 7", "ps5"),
    ("Console PlayStation 5 Pro Sony, SSD 2TB", "ps5_pro"),
    ("Playstation 5 Pro 2TB", "ps5_pro"),
    ("Console Xbox Series X 1TB", "xbox_series_x"),
    ("Console Microsoft Xbox Series S 512GB", "xbox_series_s"),
    ("Jogo Grand Theft Auto VI, PS5", "gta6"),
    ("GTA 6 - Xbox Series X|S", "gta6"),
    ("Console PS5 + GTA VI", "ps5"),
    ("Controle Sem Fio Sony DualSense, PlayStation 5", None),
    ("Suporte Vertical para PS5 Pro", None),
    ("Headset Pulse 3D PS5", None),
    ("Capa protetora Xbox Series S", None),
    ("Jogo EA FC 26 PS5", None),
    ("PlayStation 5 DualSense Edge", None),
    ("Console Sony PlayStation 5, SSD 825GB, Controle Sem Fio DualSense + 2 Jogos Digitais", "ps5"),
])
def test_classify(title, item):
    assert classify(title) == item


def test_is_trusted():
    assert is_trusted("KaBuM!", ["KaBuM!"])
    assert is_trusted("Via Magazine Luiza", ["Magazine Luiza"])
    assert not is_trusted("Loja do Zé", ["KaBuM!", "Amazon"])
