"""Regression coverage for large snapshot reconciliation (no network)."""
from aurora_desktop.catalog import LibraryV2
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Event


def test_saved_catalog_can_be_read_during_import(tmp_path, monkeypatch):
    from aurora_desktop.core import Library, playlist_lines
    source = tmp_path / 'input.m3u'
    source.write_text('#EXTM3U\n#EXTINF:-1 group-title="Ao vivo",Saved\nhttps://example.invalid/live/1\n', encoding='utf-8')
    lib = Library(tmp_path / 'catalog.db')
    pid = lib.add_playlist('Synthetic', str(source))
    lib.import_playlist(pid)
    started, release = Event(), Event()
    def slow_lines(location):
        started.set()
        assert release.wait(5), 'test did not release synthetic download'
        yield from playlist_lines(location)
    monkeypatch.setattr('aurora_desktop.core.playlist_lines', slow_lines)
    with ThreadPoolExecutor(max_workers=2) as executor:
        update = executor.submit(lib.import_playlist, pid, merge=True)
        try:
            assert started.wait(5)
            read = executor.submit(lib.items, pid, 'live')
            assert read.result(timeout=2)[0]['title'] == 'Saved'
        finally:
            release.set()
        assert update.result(timeout=5) == 1


def test_delta_preserves_identity_and_only_writes_changed_items(tmp_path, monkeypatch):
    monkeypatch.setattr('aurora_desktop.catalog.get_provider_category_kinds', lambda _: {})
    monkeypatch.setattr('aurora_desktop.catalog.get_provider_series_posters', lambda _: {})
    source = tmp_path / 'input.m3u'
    def write(episodes, extension='ts'):
        source.write_text('#EXTM3U\n' + ''.join(
            f'#EXTINF:-1 xui-id="{i}" group-title="Series",Show S01E{i:02d}\n'
            f'https://example.invalid/series/user/pass/{i}.{extension}\n'
            for i in range(1, episodes + 1)), encoding='utf-8')
    write(15)
    lib = LibraryV2(tmp_path / 'catalog.db')
    pid = lib.add_playlist('Synthetic', str(source))
    lib.import_playlist(pid)
    with lib.connect() as db:
        key = db.execute('SELECT key FROM items WHERE playlist_id=? AND xui_id=?', (pid, '1')).fetchone()[0]
        db.execute('INSERT INTO favorites VALUES (?,?,?,?)', (pid, key, 'series', 'Show'))
        db.execute('INSERT INTO progress(playlist_id,key,seconds) VALUES (?,?,?)', (pid, key, 120))
        db.executescript('''CREATE TABLE writes(action TEXT);
            CREATE TRIGGER log_updates AFTER UPDATE ON items BEGIN INSERT INTO writes VALUES ('update'); END;
            CREATE TRIGGER log_inserts AFTER INSERT ON items BEGIN INSERT INTO writes VALUES ('insert'); END;''')
    lib.import_playlist(pid)
    with lib.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM writes').fetchone()[0] == 0
    write(17)
    lib.import_playlist(pid)
    with lib.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM writes WHERE action='insert'").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM writes WHERE action='update'").fetchone()[0] == 2  # categories of new episodes only
    write(17, 'm3u8')
    lib.import_playlist(pid)
    reopened = LibraryV2(tmp_path / 'catalog.db')
    with reopened.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM items').fetchone()[0] == 17
        assert db.execute('SELECT key FROM items WHERE xui_id=?', ('1',)).fetchone()[0] == key
        assert db.execute('SELECT key FROM favorites').fetchone()[0] == key
        assert db.execute('SELECT seconds FROM progress WHERE key=?', (key,)).fetchone()[0] == 120
        plan = ' '.join(r[3] for r in db.execute('EXPLAIN QUERY PLAN SELECT rowid,key FROM items INDEXED BY idx_items_playlist_rowid WHERE playlist_id=? AND rowid>? ORDER BY rowid LIMIT 1200', (pid, 0)))
        assert 'TEMP B-TREE' not in plan
    def interrupted(_):
        yield '#EXTM3U'
        yield '#EXTINF:-1,Partial new item'
        yield 'https://example.invalid/live/new'
        raise OSError('synthetic interrupted download')
    monkeypatch.setattr('aurora_desktop.core.playlist_lines', interrupted)
    with pytest.raises(OSError, match='interrupted'):
        reopened.import_playlist(pid)
    with reopened.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM items').fetchone()[0] == 17
        assert db.execute('SELECT seconds FROM progress WHERE key=?', (key,)).fetchone()[0] == 120
