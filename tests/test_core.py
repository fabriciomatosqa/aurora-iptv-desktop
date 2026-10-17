from pathlib import Path
import pytest
from aurora_desktop.core import Library, episode_info, kind_of, parse_m3u

SAMPLE = '''#EXTM3U
#EXTINF:-1 tvg-name="Canal Aberto" group-title="Ao Vivo",Canal Aberto
https://example.org/channel.m3u8
#EXTINF:-1 group-title="Filmes" tvg-logo="https://example.org/p.jpg",Filme do Dia
https://example.org/movie/id123
#EXTINF:-1 group-title="Séries",Aurora S01E01
https://example.org/series/a/e1
#EXTINF:-1 group-title="Séries",Aurora S01E02
https://example.org/series/a/e2
'''


def test_parser_classifies_and_groups():
    entries = list(parse_m3u(SAMPLE.splitlines()))
    assert [e.kind for e in entries] == ['live', 'movie', 'series', 'series']
    assert entries[2].series_name == entries[3].series_name == 'Aurora'
    assert entries[3].episode == 2
    assert entries[1].logo.endswith('p.jpg')


def test_parser_hls_manifest_rejected():
    with pytest.raises(ValueError, match='HLS'):
        list(parse_m3u(['#EXTM3U', '#EXT-X-TARGETDURATION:6', '#EXTINF:6.0,', 'https://example.org/seg1.ts']))


def test_episode_and_movie_detection():
    assert episode_info('Show 2x13') == ('Show', 2, 13)
    assert kind_of('VOD', 'Show S01E01', 'http://example.com/a') == 'series'
    assert kind_of('Filmes', 'Um filme', 'https://x/y') == 'movie'


def test_database_multi_playlist_and_favorites(tmp_path):
    p = tmp_path / 'my.m3u'
    p.write_text(SAMPLE, encoding='utf8')
    lib = Library(tmp_path / 'app.db')
    one = lib.add_playlist('Casa', str(p))
    two = lib.add_playlist('Outra', str(p))
    assert lib.import_playlist(one) == 4
    assert lib.import_playlist(two) == 4
    assert lib.counts(one) == {'live': 1, 'movie': 1, 'series': 2}
    assert lib.series(one)[0]['title'] == 'Aurora'
    assert len(lib.episodes(one, 'Aurora')) == 2
    lib.set_favorite(one, 'series:aurora', 'series', 'Aurora', True)
    assert lib.is_favorite(one, 'series:aurora')
    assert not lib.is_favorite(two, 'series:aurora')
    movie = lib.items(one, 'movie')[0]
    lib.save_progress(one, movie['key'], 126)
    assert lib.get_progress(one, movie['key']) == 126
    assert lib.recent(one)[0]['title'] == 'Filme do Dia'
    lib.delete_playlist(two)
    assert len(lib.playlists()) == 1
    assert lib.get_progress(one, movie['key']) == 126


def test_failed_import_preserves_old_catalog(tmp_path):
    source = tmp_path / 'sample.m3u'
    source.write_text(SAMPLE, encoding='utf-8')
    lib = Library(tmp_path / 'db.sqlite')
    pid = lib.add_playlist('A', str(source))
    lib.import_playlist(pid)
    source.write_text('#EXTM3U\n#EXTINF:-1,Dead\nhttps://example.org/a\n#EXTINF:-1,Dead\nhttps://example.org/a\n', encoding='utf-8')
    assert lib.import_playlist(pid) == 2
    assert len(lib.items(pid, 'other')) == 1
    source.write_text('not a playlist', encoding='utf-8')
    with pytest.raises(ValueError):
        lib.import_playlist(pid)
    assert len(lib.items(pid, 'other')) == 1


def test_search_pagination(tmp_path):
    path = tmp_path / 'large.m3u'
    with path.open('w') as stream:
        stream.write('#EXTM3U\n')
        for i in range(235):
            stream.write(f'#EXTINF:-1 group-title="Ao vivo",Canal {i:03d}\nhttps://example.org/{i}\n')
    lib = Library(tmp_path / 'app.sqlite')
    pid = lib.add_playlist('Lots', str(path))
    assert lib.import_playlist(pid) == 235
    assert len(lib.items(pid, 'live', limit=100, offset=200)) == 35
    assert len(lib.items(pid, 'live', search='Canal 12')) == 10
