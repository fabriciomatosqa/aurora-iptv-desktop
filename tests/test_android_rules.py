"""Behavior parity tests derived from Android source and its edge-case contracts."""
from aurora_desktop.android_rules import (
    normalized,classify_content,series_identity,movie_category,football_details,
    is_adult_group,provider_api_endpoint
)


def test_android_classification_hint_and_provider_path_override():
    assert classify_content("Globo","Canais | Filmes","https://e.test/live/x/1.ts")=="live"
    assert classify_content("Ação HD","Drama","https://e.test/movie/x/2.mp4")=="movie"
    assert classify_content("Show S02E08","Diversos","https://e.test/series/x/3.mp4")=="series"
    assert classify_content("Fora de Ordem","Tudo", "https://e.test/live/x/4.ts","movie")=="movie"
    assert classify_content("Cine","Canais de filmes","https://e.test/live/x/4.ts")=="live"


def test_android_series_episode_notation_and_identity():
    a=series_identity("A Teia - Temporada 02 Ep 11 [FHD]")
    assert (a.title,a.season,a.episode)==("A Teia",2,11)
    b=series_identity("A Teia 2x12 - Final [HD]")
    assert (b.title,b.season,b.episode)==("A Teia",2,12)
    c=series_identity("Outro Episódio 9",series_id="9",series_title="Comédia",season_number=1,episode_number=9)
    assert (c.identifier,c.title,c.episode)==("id:9","Comédia",9)
    assert series_identity("A Teia S02E08").identifier==a.identifier


def test_android_movie_category_aliases():
    assert movie_category("FILMES: Ação")=="Ação"
    assert movie_category("Movies 4K")=="__aurora_4k__"
    assert movie_category("Filmes - Documentários")=="Documentários"
    assert movie_category("Filmes: Ficção Científica")=="Ficção científica"


def test_android_adult_detection_normalized():
    assert is_adult_group("🔞 +18")
    assert is_adult_group("Filmes | Adultos")
    assert not is_adult_group("Canais infantis")


def test_android_football_validation_does_not_guess_non_matches():
    x=football_details("Brasileirão: Flamengo x Vasco","Futebol")
    assert x is not None and x.home=="Flamengo" and x.away=="Vasco"
    assert football_details("Resenha: Flamengo x Vasco","Brasileirão") is None
    assert football_details("NBA: Lakers x Celtics","Futebol") is None
    assert football_details("Flamengo x Vasco","") is None
    assert football_details("Flamengo x Flamengo","Brasileirão") is None


def test_android_provider_url_credentials_stay_on_own_host():
    url=provider_api_endpoint("https://iptv.example.org/sub/get.php?username=user&password=pa%26ss&type=m3u_plus","get_series_categories")
    assert url=="https://iptv.example.org/sub/player_api.php?username=user&password=pa%26ss&action=get_series_categories"
    assert provider_api_endpoint("https://other.com/live.m3u","get_series") is None
    assert provider_api_endpoint("file:///tmp/list.m3u","get_series") is None
